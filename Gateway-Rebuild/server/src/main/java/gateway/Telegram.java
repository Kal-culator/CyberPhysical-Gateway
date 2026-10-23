package gateway;
import java.net.*;
import java.net.http.*;
import java.time.*;
import java.nio.charset.StandardCharsets;
import java.io.*;
import java.util.concurrent.*;
import org.json.*;

public final class Telegram {
    private final String token,chat,owner;
    private final Decisions decisions;
    private final HttpClient http=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(4)).build();
    private final ExecutorService outbound=Executors.newSingleThreadExecutor(r->{var t=new Thread(r,"telegram-send");t.setDaemon(true);return t;});
    public Telegram(Settings s,Decisions decisions){token=s.text("telegram.token","");chat=s.text("telegram.chat_id","");owner=s.text("telegram.owner_id","");this.decisions=decisions;}
    boolean configured(){return !token.isBlank()&&!chat.isBlank()&&!owner.isBlank();}
    private JSONObject api(String method,JSONObject data) throws Exception {
        var req=HttpRequest.newBuilder(URI.create("https://api.telegram.org/bot"+token+"/"+method)).timeout(Duration.ofSeconds(method.equals("getUpdates")?20:8)).header("Content-Type","application/json").POST(HttpRequest.BodyPublishers.ofString(data.toString())).build();
        var response=http.send(req,HttpResponse.BodyHandlers.ofString());var json=new JSONObject(response.body());
        if(response.statusCode()!=200||!json.optBoolean("ok"))throw new IOException("Telegram rejected "+method+" (HTTP "+response.statusCode()+")");
        return json;
    }
    public void approval(String id,byte[] photo) {
        outbound.submit(()->{
            try {
                if(!configured()){decisions.unavailable(id);return;}
                // Skip queued requests that have already expired.
                if(!decisions.pending(id))return;
                var markup=new JSONObject().put("inline_keyboard",new JSONArray().put(new JSONArray()
                    .put(new JSONObject().put("text","Approve").put("callback_data","A:"+id))
                    .put(new JSONObject().put("text","Deny").put("callback_data","D:"+id))));
                api("sendMessage",new JSONObject().put("chat_id",chat).put("text","Unknown fingerprint at door-1. Approve only if you recognize the visitor. Request expires 30 seconds after the scan.").put("reply_markup",markup));
                if(photo!=null) {
                    try{sendPhoto(photo,"Camera at request time. Request "+id.substring(0,8));}
                    catch(Exception photoError){System.err.println("Camera photo upload failed; approval buttons remain usable.");}
                }
            } catch(Exception e){System.err.println("Telegram request failed (check token, chat, internet).");try{decisions.unavailable(id);}catch(Exception ignored){}}
        });
    }
    public void alert(String text){if(configured())outbound.submit(()->{try{api("sendMessage",new JSONObject().put("chat_id",chat).put("text",text));}catch(Exception e){System.err.println("Telegram alert could not be delivered.");}});}
    private void sendPhoto(byte[] photo,String caption) throws Exception {
        String b="GatewayBoundary"+System.nanoTime();var out=new ByteArrayOutputStream();
        for(var pair:new String[][]{{"chat_id",chat},{"caption",caption}})
            out.write(("--"+b+"\r\nContent-Disposition: form-data; name=\""+pair[0]+"\"\r\n\r\n"+pair[1]+"\r\n").getBytes(StandardCharsets.UTF_8));
        out.write(("--"+b+"\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"door.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n").getBytes(StandardCharsets.UTF_8));out.write(photo);out.write(("\r\n--"+b+"--\r\n").getBytes(StandardCharsets.UTF_8));
        var req=HttpRequest.newBuilder(URI.create("https://api.telegram.org/bot"+token+"/sendPhoto")).timeout(Duration.ofSeconds(8)).header("Content-Type","multipart/form-data; boundary="+b).POST(HttpRequest.BodyPublishers.ofByteArray(out.toByteArray())).build();
        var res=http.send(req,HttpResponse.BodyHandlers.ofString());if(res.statusCode()!=200||!new JSONObject(res.body()).optBoolean("ok"))throw new IOException("Photo upload failed");
    }
    static boolean ownerMatches(JSONObject callback,String chat,String owner){
        var message=callback.optJSONObject("message");var from=callback.optJSONObject("from");
        return message!=null&&message.optJSONObject("chat")!=null&&from!=null
            &&chat.equals(String.valueOf(message.getJSONObject("chat").opt("id")))&&owner.equals(String.valueOf(from.opt("id")));
    }
    public void start(){if(!configured()){System.out.println("Telegram disabled: unknown fingerprints will be denied.");return;}
        Thread t=new Thread(()->{long offset=0;while(!Thread.currentThread().isInterrupted()) {
            try{
                var response=api("getUpdates",new JSONObject().put("offset",offset).put("timeout",10).put("allowed_updates",new JSONArray().put("callback_query")));
                for(Object o:response.getJSONArray("result")) {
                    var update=(JSONObject)o;offset=update.getLong("update_id")+1;var cb=update.optJSONObject("callback_query");if(cb==null)continue;
                    String message="Not authorized or request expired.";String data=cb.optString("data","");
                    if(ownerMatches(cb,chat,owner)&&(data.startsWith("A:")||data.startsWith("D:")))
                        if(decisions.answer(data.substring(2),data.startsWith("A:")))message="Decision received.";
                    api("answerCallbackQuery",new JSONObject().put("callback_query_id",cb.getString("id")).put("text",message));
                }
            }catch(Exception e){System.err.println("Telegram polling unavailable; retrying. Only one server may poll this bot.");try{Thread.sleep(3000);}catch(InterruptedException stop){return;}}
        }},"telegram-poll");t.setDaemon(true);t.start();
    }
}
