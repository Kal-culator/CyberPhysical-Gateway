package gateway;
import com.sun.net.httpserver.*;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.json.*;

public final class Main {
    final Settings settings;final Store store;final Decisions decisions;final Camera camera;final Telegram telegram;
    final AtomicLong alertSequence=new AtomicLong();volatile String lastAlert="";volatile long lastAlertAt=0;
    final Instant boot=Instant.now();final Map<String,Long> cooldown=new HashMap<>();
    Main(Settings settings) throws Exception {
        this.settings=settings;
        store=new Store(settings.simulation()?"jdbc:h2:mem:gateway;MODE=MySQL;DB_CLOSE_DELAY=-1":settings.text("db.url","jdbc:mysql://localhost:3306/cyberphysical_v2?connectTimeout=3000&socketTimeout=5000"),settings.simulation()?"sa":settings.text("db.user","gateway"),settings.simulation()?"":settings.raw("db.password",""));
        store.initialize();decisions=new Decisions(store,Clock.systemUTC(),settings.integer("approval.seconds",30,5,60),settings.integer("minimum.confidence",50,1,1000));
        camera=new Camera(Clock.systemUTC(),settings.integer("camera.dark_threshold",18,0,255),settings.integer("camera.dark_frames",4,1,100));telegram=new Telegram(settings,decisions);
    }
    synchronized void tamper(String reason) throws Exception {
        long now=System.currentTimeMillis();if(now-cooldown.getOrDefault(reason,0L)<30000)return;
        cooldown.put(reason,now);lastAlert=reason;lastAlertAt=now;alertSequence.incrementAndGet();
        decisions.cancel("door-1");
        try{store.record(UUID.randomUUID().toString(),"door-1",null,null,"TAMPER","DENY",reason);}
        finally{telegram.alert("Door tamper warning: "+reason+". Check the demonstration hardware.");}
    }
    boolean blocked(){return System.currentTimeMillis()-lastAlertAt<5000;}
    static byte[] read(HttpExchange x,int limit)throws IOException{byte[] b=x.getRequestBody().readNBytes(limit+1);if(b.length>limit)throw new IllegalArgumentException("Request too large");return b;}
    static void send(HttpExchange x,int status,String type,byte[] data)throws IOException{x.getResponseHeaders().set("Content-Type",type);x.getResponseHeaders().set("Cache-Control","no-store");x.sendResponseHeaders(status,data.length);try(var out=x.getResponseBody()){out.write(data);}}
    static void json(HttpExchange x,int status,JSONObject o)throws IOException{send(x,status,"application/json",o.toString().getBytes(StandardCharsets.UTF_8));}
    static String safeId(String s){if(!s.matches("[A-Za-z0-9_-]{8,64}"))throw new IllegalArgumentException("Invalid request ID");return s;}
    void handle(HttpExchange x)throws IOException {
        try{
            String path=x.getRequestURI().getPath(),method=x.getRequestMethod();
            if(path.equals("/")&&method.equals("GET")){send(x,200,"text/html; charset=utf-8",DASHBOARD.getBytes(StandardCharsets.UTF_8));return;}
            if(path.equals("/health")&&method.equals("GET")){json(x,200,new JSONObject().put("service","gateway-v2").put("simulation",settings.simulation()));return;}
            String token=x.getRequestHeaders().getFirst("X-API-Key");
            if(token==null||!MessageDigest.isEqual(token.getBytes(StandardCharsets.UTF_8),settings.text("api.token","").getBytes(StandardCharsets.UTF_8))){json(x,401,new JSONObject().put("error","API key missing or wrong"));return;}
            if(path.equals("/api/events")&&method.equals("GET")){json(x,200,new JSONObject().put("events",store.recent()).put("camera",camera.status()).put("simulation",settings.simulation()));return;}
            if(path.equals("/api/security")&&method.equals("GET")){json(x,200,new JSONObject().put("sequence",alertSequence.get()).put("reason",lastAlert).put("blocked",blocked()).put("simulation",settings.simulation()));return;}
            if(path.equals("/api/camera")&&method.equals("POST")){
                boolean dark=camera.accept(read(x,300000));if(dark&&settings.flag("camera.monitor",false))tamper("CAMERA_DARK_OR_COVERED");
                json(x,200,camera.status());return;
            }
            if(path.equals("/api/access")&&method.equals("POST")){
                var body=new JSONObject(new String(read(x,4096),StandardCharsets.UTF_8));
                String device=body.getString("device_id");if(!device.equals("door-1"))throw new IllegalArgumentException("Unknown device_id");
                String id=safeId(body.getString("request_id"));
                if(blocked()){json(x,200,new JSONObject().put("request_id",id).put("action","DENY").put("reason","RECENT_TAMPER").put("simulation",settings.simulation()));return;}
                Integer finger=body.isNull("fingerprint_id")?null:body.getInt("fingerprint_id");int confidence=body.optInt("confidence",0);
                if(finger!=null&&(finger<1||finger>1000)||confidence<0||confidence>1000)throw new IllegalArgumentException("Invalid fingerprint fields");
                var result=decisions.start(id,device,finger,confidence,body.optBoolean("force_review",false));
                if(result.getString("action").equals("PENDING")&&decisions.claimNotification(id)){
                    if(settings.simulation())System.out.println("SIMULATION pending request "+id);
                    else telegram.approval(id,camera.fresh());
                }
                result.put("simulation",settings.simulation());json(x,200,result);return;
            }
            if(path.startsWith("/api/requests/")&&method.equals("GET")){
                var result=decisions.get(safeId(path.substring("/api/requests/".length())),"door-1");json(x,200,result.put("simulation",settings.simulation()));return;
            }
            if(path.equals("/api/tamper")&&method.equals("POST")){
                var body=new JSONObject(new String(read(x,4096),StandardCharsets.UTF_8));String reason=body.getString("reason");
                if(!Set.of("MPU_MOTION","MPU_OFFLINE","FINGERPRINT_OFFLINE","LCD_OFFLINE").contains(reason))throw new IllegalArgumentException("Unknown tamper reason");
                tamper(reason);json(x,200,new JSONObject().put("ok",true));return;
            }
            if(settings.simulation()&&path.equals("/api/simulate/decision")&&method.equals("POST")){
                var body=new JSONObject(new String(read(x,4096),StandardCharsets.UTF_8));boolean ok=decisions.answer(body.getString("request_id"),body.getBoolean("approve"));json(x,200,new JSONObject().put("accepted",ok));return;
            }
            json(x,404,new JSONObject().put("error","Unknown route or method"));
        }catch(IllegalArgumentException|JSONException e){json(x,400,new JSONObject().put("error",e.getMessage()));}
        catch(NoSuchElementException e){json(x,404,new JSONObject().put("error","Unknown request"));}
        catch(Exception e){System.err.println("Request failed: "+e.getClass().getSimpleName());json(x,503,new JSONObject().put("error","Service unavailable; access denied"));}
        finally{x.close();}
    }
    void start()throws Exception{
        var server=HttpServer.create(new InetSocketAddress(settings.text("server.bind","0.0.0.0"),settings.integer("server.port",8080,1024,65535)),32);
        server.createContext("/",this::handle);server.setExecutor(new ThreadPoolExecutor(4,12,60,TimeUnit.SECONDS,new ArrayBlockingQueue<>(64),new ThreadPoolExecutor.CallerRunsPolicy()));server.start();
        if(!settings.simulation())telegram.start();
        var scheduler=Executors.newSingleThreadScheduledExecutor(r->{var t=new Thread(r,"expiry");t.setDaemon(true);return t;});
        scheduler.scheduleAtFixedRate(()->{try{decisions.expire();if(settings.flag("camera.monitor",false)&&Duration.between(boot,Instant.now()).toSeconds()>30&&camera.stale(15))tamper("CAMERA_OFFLINE");}catch(Exception e){System.err.println("Background check unavailable: "+e.getClass().getSimpleName());}},1,1,TimeUnit.SECONDS);
        System.out.println("Gateway V2 listening on port "+settings.text("server.port","8080")+(settings.simulation()?" — SIMULATION ONLY":" — MySQL connected"));
    }
    public static void main(String[] args)throws Exception{new Main(new Settings(Path.of(args.length>0?args[0]:"config.properties"))).start();}
    static final String DASHBOARD="""
<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Door demonstration</title>
<style>body{font:17px system-ui;background:#101722;color:#edf2fa;max-width:1000px;margin:40px auto;padding:20px}input,button{padding:12px;font:inherit}table{border-collapse:collapse;width:100%;margin-top:25px}td,th{text-align:left;border-bottom:1px solid #344154;padding:12px}#state{color:#85d9c4}small{color:#bcc8da}</style>
<h1>Door access log</h1><p id="state">Enter your API key to view events.</p><input id="key" type="password" placeholder="API key" autocomplete="off"><button id="connect">Connect</button><p><small>The log records decisions, not proof that the physical bolt moved. No door-position sensor is installed.</small></p><p id="camera"></p><table><thead><tr><th>Time</th><th>Person</th><th>Event</th><th>Decision</th><th>Reason</th></tr></thead><tbody id="rows"></tbody></table>
<script>
let key='',active=false;document.getElementById('connect').onclick=()=>{key=document.getElementById('key').value;if(!active){active=true;tick()}};
async function tick(){try{let r=await fetch('/api/events',{headers:{'X-API-Key':key}});if(!r.ok)throw Error('Cannot load events: HTTP '+r.status);let data=await r.json();document.getElementById('state').textContent=data.simulation?'SIMULATION — no hardware':'Connected';document.getElementById('camera').textContent='Camera last received: '+(data.camera.seen||'not yet')+'; brightness '+data.camera.mean_brightness.toFixed(1);let rows=document.getElementById('rows');rows.replaceChildren();for(let e of data.events){let tr=document.createElement('tr');for(let k of ['time','person','type','decision','reason']){let td=document.createElement('td');td.textContent=e[k];tr.append(td)}rows.append(tr)}}catch(e){document.getElementById('state').textContent=e.message}setTimeout(tick,2500)}
</script></html>
""";
}
