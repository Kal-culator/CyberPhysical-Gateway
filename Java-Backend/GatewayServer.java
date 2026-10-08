import java.io.*;
import java.net.*;
import java.util.concurrent.*;
import org.json.JSONObject;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;

public class GatewayServer {
    private static final ExecutorService pool = Executors.newFixedThreadPool(10);
    
    // Telegram API
    private static final String BOT_TOKEN = "8715105333:AAFqA454czMeq0aNJfztXuLUXOsfu0vflwU";
    private static final String CHAT_ID = "6301149879";

    // ANSI Color Codes for Pretty Console
    private static final String RESET = "\u001B[0m";
    private static final String BOLD = "\u001B[1m";
    private static final String CYAN = "\u001B[36m";
    private static final String GREEN = "\u001B[32m";
    private static final String YELLOW = "\u001B[33m";
    private static final String RED = "\u001B[31m";

    public static void main(String[] args) {
        int port = 8080;
        try (ServerSocket serverSocket = new ServerSocket(port)) {
            System.out.println(CYAN + BOLD + "╔════════════════════════════════════════════════════╗" + RESET);
            System.out.println(CYAN + BOLD + "║      🛡️  ZERO-TRUST HUB (MAC SERVER) 🛡️            ║" + RESET);
            System.out.println(CYAN + BOLD + "╚════════════════════════════════════════════════════╝" + RESET);
            System.out.println(GREEN + "▶ Listening on port " + port + "..." + RESET);
            
            while (true) {
                Socket clientSocket = serverSocket.accept();
                System.out.println(CYAN + "\n▶ Incoming connection from: " + clientSocket.getInetAddress().getHostAddress() + RESET);
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
            try (BufferedReader in = new BufferedReader(new InputStreamReader(socket.getInputStream()))) {
                String inputLine;
                while ((inputLine = in.readLine()) != null) {
                    System.out.println(YELLOW + "  [Raw Payload] " + RESET + inputLine);
                    
                    if (inputLine.trim().equals("TAMPER") || inputLine.contains("\"TAMPER\"")) {
                        System.out.println(RED + BOLD + "🚨 PI REPORTED TAMPERING! Waiting for ESP32 camera on port 8081..." + RESET);
                        
                        boolean imageSaved = false;
                        
                        // Step 1: Secure the Image FIRST
                        try (ServerSocket camServer = new ServerSocket(8081)) {
                            camServer.setSoTimeout(10000); 
                            Socket espSocket = camServer.accept();
                            BufferedImage espFrame = ImageIO.read(espSocket.getInputStream());
                            
                            if (espFrame != null) {
                                File outputFile = new File("intruder.jpg");
                                ImageIO.write(espFrame, "jpg", outputFile);
                                System.out.println(GREEN + "  ✅ Image successfully saved as intruder.jpg" + RESET);
                                imageSaved = true;
                            }
                            espSocket.close();
                        } catch (SocketTimeoutException ste) {
                            System.out.println(RED + "  ❌ ESP32 Camera connection timed out!" + RESET);
                        } catch (Exception e) {
                            System.out.println(RED + "  ❌ Error fetching camera image: " + e.getMessage() + RESET);
                        }
                        
                        // Step 2: Send Alert AFTER image is ready (with Auto-Reconnect)
                        sendTelegramAlert(imageSaved);
                        continue; 
                    }
                    
                    try {
                        JSONObject payload = new JSONObject(inputLine);
                        System.out.println(GREEN + "  [Parsed] Sensor: " + payload.optString("sensor") + " | UID: " + payload.optInt("uid") + RESET);
                    } catch (Exception e) {
                        // Ignore JSON parsing errors for basic string commands
                    }
                }
            } catch (IOException e) {
                System.out.println(YELLOW + "▶ Client Disconnected." + RESET);
            } finally {
                try {
                    socket.close();
                } catch (IOException e) {
                    e.printStackTrace();
                }
            }
        }
    }

    // --- BULLETPROOF TELEGRAM RETRY LOGIC ---
    public static void sendTelegramAlert(boolean hasImage) {
        int maxRetries = 3;
        int attempt = 0;
        boolean sent = false;

        while (attempt < maxRetries && !sent) {
            try {
                attempt++;
                System.out.println(CYAN + "📡 Sending Telegram Alert (Attempt " + attempt + "/" + maxRetries + ")..." + RESET);
                
                String command;
                if (hasImage) {
                    command = "curl -s -X POST https://api.telegram.org/bot" + BOT_TOKEN + "/sendPhoto " +
                              "-F chat_id=" + CHAT_ID + " " +
                              "-F photo=@intruder.jpg " +
                              "-F caption=\"🚨 ALERT: Unauthorized Fingerprint Detected!\"";
                } else {
                    // Fallback just in case the ESP-CAM dies, so you still get a text warning
                    command = "curl -s -X POST https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage " +
                              "-d chat_id=" + CHAT_ID + " " +
                              "-d text=\"🚨 ALERT: Tamper detected, but ESP32 camera failed to capture image!\"";
                }

                ProcessBuilder processBuilder = new ProcessBuilder("bash", "-c", command);
                Process process = processBuilder.start();
                int exitCode = process.waitFor(); 
                
                if (exitCode == 0) {
                    System.out.println(GREEN + BOLD + "  ✅ Telegram alert successfully delivered!" + RESET);
                    sent = true;
                } else {
                    System.out.println(RED + "  ⚠️ API rejected request. Exit code: " + exitCode + RESET);
                }
            } catch (Exception e) {
                System.out.println(RED + "  ❌ Network error: " + e.getMessage() + RESET);
            }

            // If it failed, wait 3 seconds and loop again
            if (!sent && attempt < maxRetries) {
                System.out.println(YELLOW + "  🔄 Spotty connection. Retrying in 3 seconds..." + RESET);
                try {
                    Thread.sleep(3000);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                }
            }
        }

        if (!sent) {
            System.out.println(RED + BOLD + "💀 FATAL: Could not send Telegram alert after " + maxRetries + " attempts." + RESET);
        }
    }
}