import java.io.*;
import java.net.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import org.json.JSONArray;
import org.json.JSONObject;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;

public class GatewayServer {
    // --- SERVER THREADING & STATE ---
    private static final ExecutorService pool = Executors.newFixedThreadPool(10);
    private static final AtomicReference<CompletableFuture<String>> pendingDecision = new AtomicReference<>();
    private static final AtomicLong currentRequestId = new AtomicLong(-1);
    private static long lastUpdateId = 0;
    
    // --- CREDENTIALS (Hardcoded for Demo Simplicity) ---
    private static final String BOT_TOKEN = "YOUR_NEW_BOT_TOKEN_HERE"; 
    private static final String DB_PASS   = "password"; // Yash's Mac MySQL password
    private static final String CHAT_ID   = "6301149879";

    static class CameraStatus {
        boolean saved = false;
        boolean blinded = false;
    }

    public static void main(String[] args) {
        // Boot Background Services
        new Thread(GatewayServer::pollTelegramUpdates).start();
        speak("Zero-Trust Hub initialized. All systems online.");

        // Start Main TCP Server
        try (ServerSocket serverSocket = new ServerSocket(8080)) {
            System.out.println("▶ Listening for Edge Node on port 8080...");
            while (true) {
                pool.execute(new ClientHandler(serverSocket.accept()));
            }
        } catch (IOException e) { 
            e.printStackTrace(); 
        }
    }

    // ==========================================
    // EDGE NODE HANDLER
    // ==========================================
    private static class ClientHandler implements Runnable {
        private Socket socket;
        public ClientHandler(Socket socket) { this.socket = socket; }

        @Override
        public void run() {
            try (BufferedReader in = new BufferedReader(new InputStreamReader(socket.getInputStream()));
                 PrintWriter out = new PrintWriter(socket.getOutputStream(), true)) {
                
                String inputLine;
                while ((inputLine = in.readLine()) != null) {
                    System.out.println("  [Raw Payload] " + inputLine);
                    
                    // --- SCENARIO A: PHYSICAL TAMPER ---
                    if (inputLine.contains("\"TAMPER\"")) {
                        speak("Critical security alert. Physical tampering detected.");
                        CameraStatus cam = fetchCameraImage();
                        sendTelegramAlert(cam, false);
                        logAccess("NONE", "TAMPER", "BUZZER");
                        continue; 
                    }
                    
                    // --- SCENARIO B: UNKNOWN FINGERPRINT ---
                    if (inputLine.contains("\"REVIEW\"")) {
                        speak("Unrecognized fingerprint. Awaiting owner authorization.");
                        CameraStatus cam = fetchCameraImage();
                        
                        long reqId = System.currentTimeMillis();
                        currentRequestId.set(reqId);
                        
                        sendTelegramAlert(cam, true); 
                        
                        CompletableFuture<String> decisionFuture = new CompletableFuture<>();
                        pendingDecision.set(decisionFuture);
                        
                        String finalAction = "BUZZER"; 
                        try {
                            finalAction = decisionFuture.get(30, TimeUnit.SECONDS);
                            if (finalAction.equals("OPEN")) {
                                speak("Access granted. Unlocking door.");
                            } else {
                                speak("Access denied. Intruder logged.");
                            }
                        } catch (Exception e) {
                            speak("Timeout. Authorization denied.");
                            pendingDecision.set(null);
                        }
                        
                        out.println("{\"action\":\"" + finalAction + "\"}");
                        logAccess("UNKNOWN", "REVIEW", finalAction);
                        continue;
                    }
                    
                    // --- SCENARIO C: AUTHORIZED ACCESS ---
                    try {
                        JSONObject payload = new JSONObject(inputLine);
                        String decision = payload.optString("pi_decision");
                        String fingerId = payload.optString("fingerprint_id", "UNKNOWN");
                        String action   = decision.equals("GRANTED") ? "OPEN" : "BUZZER";
                        logAccess(fingerId, decision, action);
                    } catch (Exception ignored) {}
                }
            } catch (IOException e) {} 
            finally { 
                try { socket.close(); } catch (IOException e) {} 
            }
        }
    }

    // ==========================================
    // HARDWARE & API INTEGRATIONS
    // ==========================================
    private static CameraStatus fetchCameraImage() {
        CameraStatus status = new CameraStatus();
        try (ServerSocket camServer = new ServerSocket(8081)) {
            camServer.setSoTimeout(10000); 
            Socket espSocket = camServer.accept();
            BufferedImage espFrame = ImageIO.read(espSocket.getInputStream());
            if (espFrame != null) {
                ImageIO.write(espFrame, "jpg", new File("intruder.jpg"));
                status.saved = true;
                // status.blinded = SecurityAnalytics.isCameraBlinded(SecurityAnalytics.calculateAverageLuminance(espFrame), true);
            }
            espSocket.close();
        } catch (Exception e) {}
        return status;
    }

    public static void sendTelegramAlert(CameraStatus cam, boolean isInteractive) {
        long reqId = currentRequestId.get();
        String caption = isInteractive ? "⚠️ UNKNOWN FINGERPRINT DETECTED! Approve access?" : 
                         (cam.blinded ? "🚨 ALERT: Unauthorized Fingerprint AND Camera Blinded!" : "🚨 ALERT: Tamper Detected!");
        
        String markupJson = isInteractive ? "{\"inline_keyboard\":[[{\"text\":\"✅ Approve\",\"callback_data\":\"APPROVE_" + reqId + "\"},{\"text\":\"❌ Deny\",\"callback_data\":\"DENY_" + reqId + "\"}]]}" : "";
        
        try {
            String command;
            if (cam.saved) {
                String markupFlag = isInteractive ? "-F reply_markup='" + markupJson + "'" : "";
                command = "curl -s --max-time 10 -X POST https://api.telegram.org/bot" + BOT_TOKEN + "/sendPhoto -F chat_id=" + CHAT_ID + " -F photo=@intruder.jpg -F caption=\"" + caption + "\" " + markupFlag;
            } else {
                JSONObject payload = new JSONObject();
                payload.put("chat_id", CHAT_ID);
                payload.put("text", caption + " (Camera offline)");
                if (isInteractive) payload.put("reply_markup", new JSONObject(markupJson));
                
                command = "curl -s --max-time 10 -X POST https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage -H \"Content-Type: application/json\" -d '" + payload.toString() + "'";
            }
            new ProcessBuilder("bash", "-c", command).start().waitFor();
        } catch (Exception e) {}
    }

    private static void pollTelegramUpdates() {
        while (true) {
            try {
                URL url = new URL("https://api.telegram.org/bot" + BOT_TOKEN + "/getUpdates?timeout=10&offset=" + (lastUpdateId + 1));
                HttpURLConnection con = (HttpURLConnection) url.openConnection();
                con.setConnectTimeout(10000);
                con.setReadTimeout(20000); 
                
                BufferedReader in = new BufferedReader(new InputStreamReader(con.getInputStream()));
                StringBuilder response = new StringBuilder();
                String inputLine;
                while ((inputLine = in.readLine()) != null) response.append(inputLine);
                in.close();
                
                JSONObject json = new JSONObject(response.toString());
                if (json.getBoolean("ok")) {
                    JSONArray result = json.getJSONArray("result");
                    for (int i = 0; i < result.length(); i++) {
                        JSONObject update = result.getJSONObject(i);
                        lastUpdateId = update.getLong("update_id");
                        if (update.has("callback_query")) {
                            JSONObject callback = update.getJSONObject("callback_query");
                            String data = callback.getString("data");
                            long reqId = currentRequestId.get();
                            
                            new ProcessBuilder("bash", "-c", "curl -s --max-time 10 -X POST https://api.telegram.org/bot" + BOT_TOKEN + "/answerCallbackQuery -d callback_query_id=" + callback.getString("id")).start();
                            
                            if (data.endsWith("_" + reqId)) {
                                CompletableFuture<String> future = pendingDecision.getAndSet(null);
                                if (future != null && !future.isDone()) {
                                    future.complete(data.startsWith("APPROVE") ? "OPEN" : "BUZZER");
                                }
                            }
                        }
                    }
                }
            } catch (Exception e) { try { Thread.sleep(3000); } catch (Exception ie) {} }
        }
    }

    private static void speak(String message) {
        try { new ProcessBuilder("say", message).start(); } catch (Exception e) {}
    }

    // ==========================================
    // DATABASE LOGGING
    // ==========================================
    private static void logAccess(String fingerprintId, String piDecision, String finalAction) {
        String dbUrl = "jdbc:mysql://localhost:3306/smart_door_demo"; 
        String sql = "INSERT INTO access_events (fingerprint_id, pi_decision, final_action) VALUES (?, ?, ?)";
        try (java.sql.Connection conn = java.sql.DriverManager.getConnection(dbUrl, "root", DB_PASS);
             java.sql.PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setString(1, fingerprintId);
            pstmt.setString(2, piDecision);
            pstmt.setString(3, finalAction);
            pstmt.executeUpdate();
            System.out.println("  💾 Saved to DB!");
        } catch (Exception e) { 
            System.out.println("  ❌ DB Error: " + e.getMessage()); 
        }
    }
}