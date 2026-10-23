package gateway;
import java.time.*;
import java.util.*;
import org.json.*;

public final class Decisions {
    public interface Messenger { boolean request(String id); }
    static final class Request {
        final String id,device; final Integer finger; final int confidence; final Instant deadline;
        String action="PENDING",reason="WAITING_FOR_OWNER"; boolean notified=false;
        Request(String id,String device,Integer finger,int confidence,Instant deadline){this.id=id;this.device=device;this.finger=finger;this.confidence=confidence;this.deadline=deadline;}
    }
    private final Map<String,Request> requests=new HashMap<>();
    private final Store store;private final Clock clock;private final int seconds,minConfidence;
    public Decisions(Store store,Clock clock,int seconds,int minConfidence){this.store=store;this.clock=clock;this.seconds=seconds;this.minConfidence=minConfidence;}
    public synchronized JSONObject start(String id,String device,Integer finger,int confidence,boolean forceReview) throws Exception {
        Request old=requests.get(id);
        if(old!=null){if(!old.device.equals(device))throw new IllegalArgumentException("Request belongs to another device");return result(old);}
        // Never replay an old OPEN after a server restart.
        if(store.exists(id)) return new JSONObject().put("request_id",id).put("action","DENY").put("reason","ALREADY_PROCESSED");
        expire();
        for(Request r:requests.values()) if(r.device.equals(device)&&r.action.equals("PENDING"))
            throw new IllegalArgumentException("An approval is already pending for this device");
        if(requests.size()>=1000) requests.entrySet().removeIf(e->!e.getValue().action.equals("PENDING"));
        if(requests.size()>=1000)throw new IllegalArgumentException("Too many requests");
        var r=new Request(id,device,finger,confidence,clock.instant().plusSeconds(seconds));
        requests.put(id,r); // Registered BEFORE any Telegram message is sent.
        if(!forceReview && finger!=null && confidence>=minConfidence && store.authorized(finger)) finish(r,"OPEN","REGISTERED_FINGER");
        return result(r);
    }
    public synchronized JSONObject get(String id,String device) throws Exception {
        var r=requests.get(id);if(r==null||!r.device.equals(device))throw new NoSuchElementException("Unknown request");expire();return result(r);
    }
    public synchronized boolean answer(String id,boolean approve) throws Exception {
        expire();var r=requests.get(id);if(r==null||!r.action.equals("PENDING"))return false;
        finish(r,approve?"OPEN":"DENY",approve?"OWNER_APPROVED":"OWNER_DENIED");return true;
    }
    public synchronized boolean claimNotification(String id) throws Exception {
        expire();var r=requests.get(id);
        if(r==null||!r.action.equals("PENDING")||r.notified)return false;
        r.notified=true;return true;
    }
    public synchronized boolean pending(String id) throws Exception {
        expire();var r=requests.get(id);return r!=null&&r.action.equals("PENDING");
    }
    public synchronized void unavailable(String id) throws Exception {
        var r=requests.get(id);if(r!=null&&r.action.equals("PENDING"))finish(r,"DENY","TELEGRAM_UNAVAILABLE");
    }
    public synchronized void cancel(String device) throws Exception {
        for(var r:requests.values())if(r.device.equals(device)&&r.action.equals("PENDING"))finish(r,"DENY","TAMPER_DURING_REVIEW");
    }
    public synchronized void expire() throws Exception {
        for(var r:requests.values())if(r.action.equals("PENDING")&&!clock.instant().isBefore(r.deadline))finish(r,"DENY","TIMEOUT");
    }
    private void finish(Request r,String action,String reason) throws Exception {
        // Mark denied before writing; a DB failure must never leave an OPEN decision.
        r.action="DENY";r.reason="DATABASE_ERROR";
        if(!store.record(r.id,r.device,r.finger,r.confidence,"ACCESS",action,reason)) {r.reason="ALREADY_PROCESSED";return;}
        r.action=action;r.reason=reason;
    }
    private JSONObject result(Request r){return new JSONObject().put("request_id",r.id).put("action",r.action).put("reason",r.reason).put("remaining_seconds",Math.max(0,Duration.between(clock.instant(),r.deadline).toSeconds()));}
}
