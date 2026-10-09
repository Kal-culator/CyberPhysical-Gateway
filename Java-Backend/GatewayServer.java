import java.io.*;
import java.net.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import org.json.JSONArray;
import org.json.JSONObject;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;

public class GatewayServer {
    private static final ExecutorService pool = Executors.newFixedThreadPool(10);
    private static final AtomicReference<CompletableFuture<String>> pendingDecision = new AtomicReference<>();
    private static long lastUpdateId = 0;
    
    // Telegram API
    private static final String BOT_TOKEN = "8715105333:AAFqA454czMeq0aNJfztXuLUXOsfu0vflwU";
    private static final String CHAT_ID = "6301149879";

    // ANSI Color Codes
    private static final String RESET = "\u001B[0m";
    private static final String BOLD = "\u001B[1m";
    private static final String CYAN = "\u001B[36m";
    private static final String GREEN = "\u001B[32m";
    private static final String YELLOW = "\u001B[33m";
    private static final String RED = "\u001B[31m";

    public static void main(String[] args) {
        int port = 8080;
        
        // Start the non-blocking background polling thread for Telegram buttons
        new Thread(GatewayServer::pollTelegramUpdates).start();

        try (ServerSocket serverSocket = new ServerSocket(port)) {
            System.out.println(CYAN + BOLD + "╔════════════════════════════════════════════════════╗" + RESET);
            System.out.println(CYAN + BOLD + "║ 🛡️ ZERO-TRUST HUB: INTERACTIVE POLLING ACTIVE 🛡️  ║" + RESET);
            System.out.println(CYAN + BOLD + "╚════════════════════════════════════════════════════╝" + RESET);
            System.out.println(GREEN + "▶ Listening for Raspberry Pi on port " + port + "..." + RESET);
            
            // J.A.R.V.I.S. Startup Announcement
            speak("Zero-Trust Hub initialized. All systems online.");
            
            while (true) {
                Socket clientSocket = serverSocket.accept();
                System.out.println(CYAN + "\n▶ Incoming connection from Edge Node" + RESET);
                pool.execute(new ClientHandler(clientSocket));
            }
        } catch (IOException e) {
            System.out.println(RED + "Server Exception: " + e.getMessage() + RESET);
        }
    }

    private static class ClientHandler implements Runnable {
        private Socket socket;

        public ClientHandler(Socket socket) {
            this.socket = socket;
        }

        @Override
        public void run() {
            try (BufferedReader in = new BufferedReader(new InputStreamReader(socket.getInputStream()));
                 PrintWriter out = new PrintWriter(socket.getOutputStream(), true)) {
                
                String inputLine;
                while ((inputLine = in.readLine()) != null) {
                    System.out.println(YELLOW + "  [Raw Payload] " + RESET + inputLine);
                    
                    if (inputLine.contains("\"TAMPER\"")) {
                        System.out.println(RED + BOLD + "🚨 TAMPERING! Fetching camera and firing Zero-Trust alert..." + RESET);
                        speak("Critical security alert. Physical tampering detected."); // Voice Alert
                        boolean imageSaved = fetchCameraImage();
                        sendTelegramAlert(imageSaved, false, false); // Standard automatic alert
                        continue; 
                    }
                    
                    if (inputLine.contains("\"REVIEW\"")) {
                        System.out.println(YELLOW + BOLD + "⚠️ UNKNOWN FINGERPRINT! Requesting manual Telegram review..." + RESET);
                        speak("Unrecognized fingerprint. Awaiting owner authorization."); // Voice Alert
                        boolean imageSaved = fetchCameraImage();
                        
                        // Send interactive prompt with buttons
                        sendTelegramAlert(imageSaved, false, true); 
                        
                        CompletableFuture<String> decisionFuture = new CompletableFuture<>();
                        pendingDecision.set(decisionFuture);
                        
                        String finalAction = "BUZZER"; // Default fallback is to deny
                        try {
                            System.out.println(CYAN + "  ⏳ Waiting up to 45 seconds for owner to tap a button..." + RESET);
                            finalAction = decisionFuture.get(45, TimeUnit.SECONDS);
                            System.out.println(GREEN + BOLD + "  ✅ Owner Decision Received: " + finalAction + RESET);
                            
                            // Voice Alert based on Telegram button press
                            if (finalAction.equals("OPEN")) {
                                speak("Access granted. Unlocking door.");
                            } else {
                                speak("Access denied. Intruder logged.");
                            }
                            
                        } catch (TimeoutException te) {
                            System.out.println(RED + "  ❌ Timeout! Owner did not respond. Defaulting to lock/buzzer." + RESET);
                            speak("Timeout. Authorization denied."); // Voice Alert
                            pendingDecision.set(null);
                        } catch (Exception e) {
                            System.out.println(RED + "  ❌ Interrupted: " + e.getMessage() + RESET);
                        }
                        
                        // Write back to Pi
                        out.println("{\"action\":\"" + finalAction + "\"}");
                        continue;
                    }
                    
                    try {
                        JSONObject payload = new JSONObject(inputLine);
                        System.out.println(GREEN + "  [Parsed] Action: " + payload.optString("pi_decision") + RESET);
                    } catch (Exception ignored) {}
                }
            } catch (IOException e) {
                System.out.println(YELLOW + "▶ Edge Node Disconnected." + RESET);
            } finally {
                try { socket.close(); } catch (IOException e) {}
            }
        }
    }

    private static boolean fetchCameraImage() {
        boolean imageSaved = false;
        try (ServerSocket camServer = new ServerSocket(8081)) {
            camServer.setSoTimeout(10000); 
            Socket espSocket = camServer.accept();
            BufferedImage espFrame = ImageIO.read(espSocket.getInputStream());
            
            if (espFrame != null) {
                File outputFile = new File("intruder.jpg");
                ImageIO.write(espFrame, "jpg", outputFile);
                System.out.println(GREEN + "  ✅ ESP32 image successfully saved." + RESET);
                imageSaved = true;

                double luminance = SecurityAnalytics.calculateAverageLuminance(espFrame);
                if (SecurityAnalytics.isCameraBlinded(luminance, true)) {
                    System.out.println(RED + BOLD + "  ⚠️ WARNING: Camera appears blinded! (Luminance: " + String.format("%.2f", luminance) + ")" + RESET);
                    speak("Warning. Camera sensor obstructed."); // Voice Alert
                }
            }
            espSocket.close();
        } catch (SocketTimeoutException ste) {
            System.out.println(RED + "  ❌ ESP32 connection timed out!" + RESET);
        } catch (Exception e) {
            System.out.println(RED + "  ❌ Error fetching camera: " + e.getMessage() + RESET);
        }
        return imageSaved;
    }

    public static void sendTelegramAlert(boolean hasImage, boolean cameraBlinded, boolean isInteractive) {
        String caption = isInteractive ? 
            "⚠️ UNKNOWN FINGERPRINT DETECTED! Approve access?" : 
            (cameraBlinded ? "🚨 ALERT: Unauthorized Fingerprint AND Camera Blinded!" : "🚨 ALERT: Tamper Detected!");
            
        String markup = isInteractive ? 
            "-F reply_markup=\"{\\\"inline_keyboard\\\":[[{\\\"text\\\":\\\"✅ Approve\\\",\\\"callback_data\\\":\\\"APPROVE\\\"},{\\\"text\\\":\\\"❌ Deny\\\",\\\"callback_data\\\":\\\"DENY\\\"}]]}\"" : "";

        try {
            String command = hasImage ? 
                "curl -s -X POST https://api.telegram.org/bot" + BOT_TOKEN + "/sendPhoto -F chat_id=" + CHAT_ID + " -F photo=@intruder.jpg -F caption=\"" + caption + "\" " + markup :
                "curl -s -X POST https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage -d chat_id=" + CHAT_ID + " -d text=\"" + caption + "\"";

            ProcessBuilder pb = new ProcessBuilder("bash", "-c", command);
            pb.start().waitFor();
        } catch (Exception e) {
            System.out.println(RED + "  ❌ Telegram post failed." + RESET);
        }
    }

    private static void pollTelegramUpdates() {
        while (true) {
            try {
                URL url = new URL("https://api.telegram.org/bot" + BOT_TOKEN + "/getUpdates?timeout=10&offset=" + (lastUpdateId + 1));
                HttpURLConnection con = (HttpURLConnection) url.openConnection();
                con.setRequestMethod("GET");
                
                BufferedReader in = new BufferedReader(new InputStreamReader(con.getInputStream()));
                StringBuilder response = new StringBuilder();
                String inputLine;
                while ((inputLine = in.readLine()) != null) { response.append(inputLine); }
                in.close();
                
                JSONObject json = new JSONObject(response.toString());
                if (json.getBoolean("ok")) {
                    JSONArray result = json.getJSONArray("result");
                    for (int i = 0; i < result.length(); i++) {
                        JSONObject update = result.getJSONObject(i);
                        lastUpdateId = update.getLong("update_id");
                        
                        if (update.has("callback_query")) {
                            JSONObject callback = update.getJSONObject("callback_query");
                            String callbackId = callback.getString("id");
                            String data = callback.getString("data"); // "APPROVE" or "DENY"
                            
                            // Acknowledge the button press so the loading icon stops spinning
                            new ProcessBuilder("bash", "-c", "curl -s -X POST https://api.telegram.org/bot" + BOT_TOKEN + "/answerCallbackQuery -d callback_query_id=" + callbackId).start();
                            
                            CompletableFuture<String> future = pendingDecision.getAndSet(null);
                            if (future != null && !future.isDone()) {
                                future.complete(data.equals("APPROVE") ? "OPEN" : "BUZZER");
                            }
                        }
                    }
                }
            } catch (Exception e) {
                // Fails silently in the background and retries if Wi-Fi drops
                try { Thread.sleep(3000); } catch (InterruptedException ie) {}
            }
        }
    }

    // --- J.A.R.V.I.S. VOICE ENGINE ---
    private static void speak(String message) {
        try {
            // Uses the native macOS text-to-speech engine
            new ProcessBuilder("say", message).start();
        } catch (Exception e) {
            // Fails silently so it never crashes the server if audio is unavailable
        }
    }
}