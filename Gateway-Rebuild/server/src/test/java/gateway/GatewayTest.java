package gateway;
import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.*;
import org.json.*;
import java.time.*;
import java.util.*;
import java.io.*;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;

class GatewayTest {
    static class Time extends Clock {
        Instant now=Instant.parse("2026-01-01T00:00:00Z");
        public Instant instant(){return now;}public ZoneId getZone(){return ZoneOffset.UTC;}public Clock withZone(ZoneId z){return this;}
        void advance(int seconds){now=now.plusSeconds(seconds);}
    }
    Store store;Time time;Decisions decisions;
    @BeforeEach void init()throws Exception{
        store=new Store("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1","sa","");store.initialize();time=new Time();decisions=new Decisions(store,time,30,50);
    }
    @Test void knownFingerOpensAndLogsOnce()throws Exception {
        var a=decisions.start("request-1","door-1",1,80,false);assertEquals("OPEN",a.getString("action"));
        decisions.start("request-1","door-1",1,80,false);assertEquals(1,store.recent().length());
    }
    @Test void unregisteredAndLowConfidenceRequireOwner()throws Exception {
        assertEquals("PENDING",decisions.start("request-1","door-1",1,20,false).getString("action"));
        assertTrue(decisions.answer("request-1",false));
        assertEquals("PENDING",decisions.start("request-2","door-1",5,100,false).getString("action"));
    }
    @Test void immediateApprovalCannotRaceRequestCreation()throws Exception {
        decisions.start("request-1","door-1",null,0,false);
        assertTrue(decisions.answer("request-1",true));
        assertEquals("OPEN",decisions.get("request-1","door-1").getString("action"));
        assertFalse(decisions.answer("request-1",false));
    }
    @Test void deadlineRejectsLateApproval()throws Exception {
        decisions.start("request-1","door-1",null,0,false);time.advance(30);
        assertFalse(decisions.answer("request-1",true));
        assertEquals("TIMEOUT",decisions.get("request-1","door-1").getString("reason"));
        assertEquals("DENY",store.recent().getJSONObject(0).getString("decision"));
    }
    @Test void ownerDenialAndTelegramFailureFailClosed()throws Exception {
        decisions.start("request-1","door-1",null,0,false);decisions.answer("request-1",false);
        assertEquals("DENY",decisions.get("request-1","door-1").getString("action"));
        decisions.start("request-2","door-1",null,0,false);decisions.unavailable("request-2");
        assertEquals("TELEGRAM_UNAVAILABLE",decisions.get("request-2","door-1").getString("reason"));
    }
    @Test void tamperCancelsPendingDecision()throws Exception {
        decisions.start("request-1","door-1",null,0,false);decisions.cancel("door-1");
        assertFalse(decisions.answer("request-1",true));assertEquals("DENY",decisions.get("request-1","door-1").getString("action"));
    }
    @Test void restartDoesNotReplayAnOpening()throws Exception {
        decisions.start("request-1","door-1",1,100,false);
        var restarted=new Decisions(store,time,30,50);
        assertEquals("DENY",restarted.start("request-1","door-1",1,100,false).getString("action"));
    }
    @Test void databaseRevocationIsRespected()throws Exception {
        try(var c=store.open();var s=c.createStatement()){s.executeUpdate("UPDATE gateway_users SET authorized=FALSE WHERE fingerprint_id=1");}
        assertEquals("PENDING",decisions.start("request-1","door-1",1,100,false).getString("action"));
    }
    @Test void databaseFailureNeverReturnsOpen()throws Exception {
        decisions.start("request-1","door-1",null,0,false);
        try(var c=store.open();var s=c.createStatement()){s.executeUpdate("DROP TABLE gateway_events");}
        assertThrows(Exception.class,()->decisions.answer("request-1",true));
        assertEquals("DENY",decisions.get("request-1","door-1").getString("action"));
    }
    @Test void twoPendingRequestsForSameDoorAreRejected()throws Exception {
        decisions.start("request-1","door-1",null,0,false);
        assertThrows(IllegalArgumentException.class,()->decisions.start("request-2","door-1",null,0,false));
    }
    @Test void deletedSampleUserIsNotRecreatedOnRestart()throws Exception {
        try(var c=store.open();var q=c.createStatement()){q.executeUpdate("DELETE FROM gateway_users WHERE fingerprint_id=1");}
        store.initialize();assertFalse(store.authorized(1));
    }
    @Test void notificationCanBeClaimedOnlyOnce()throws Exception {
        decisions.start("request-1","door-1",null,0,false);
        assertTrue(decisions.claimNotification("request-1"));assertFalse(decisions.claimNotification("request-1"));
        time.advance(30);assertFalse(decisions.pending("request-1"));
    }
    @Test void callbackMustMatchBothOwnerAndChat(){
        var cb=new JSONObject().put("from",new JSONObject().put("id",123)).put("message",new JSONObject().put("chat",new JSONObject().put("id",456)));
        assertTrue(Telegram.ownerMatches(cb,"456","123"));assertFalse(Telegram.ownerMatches(cb,"456","999"));assertFalse(Telegram.ownerMatches(cb,"999","123"));assertFalse(Telegram.ownerMatches(new JSONObject(),"456","123"));
    }
    @Test void darkFramesNeedPersistenceAndBrightFrameResetsCounter()throws Exception {
        var camera=new Camera(time,18,3);byte[] dark=jpeg(0),bright=jpeg(255);
        assertFalse(camera.accept(dark));assertFalse(camera.accept(dark));assertTrue(camera.accept(dark));assertFalse(camera.accept(bright));assertFalse(camera.accept(dark));
        assertNotNull(camera.fresh());time.advance(16);assertNull(camera.fresh());assertTrue(camera.stale(15));
        assertThrows(IOException.class,()->camera.accept(new byte[]{1,2,3}));
    }
    static byte[] jpeg(int level)throws Exception{var im=new BufferedImage(16,16,BufferedImage.TYPE_INT_RGB);int rgb=(level<<16)|(level<<8)|level;for(int y=0;y<16;y++)for(int x=0;x<16;x++)im.setRGB(x,y,rgb);var out=new ByteArrayOutputStream();ImageIO.write(im,"jpg",out);return out.toByteArray();}
}
