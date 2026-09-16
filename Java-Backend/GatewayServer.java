import java.io.*;
import java.net.*;
import java.util.concurrent.*;
import org.json.JSONObject;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;

public class GatewayServer {
    private static final ExecutorService pool = Executors.newFixedThreadPool(10);

    public static void main(String[] args) {
        int port = 8080;
        try (ServerSocket serverSocket = new ServerSocket(port)) {
            System.out.println("Zero-Trust Hub listening on port " + port + "...");
            
            while (true) {
                Socket clientSocket = serverSocket.accept();
                System.out.println("Incoming connection from: " + clientSocket.getInetAddress().getHostAddress());
                pool.execute(new ClientHandler(clientSocket));
            }
        } catch (IOException e) {
            System.out.println("Server Exception: " + e.getMessage());
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
                    System.out.println("Raw Payload Received: " + inputLine);
                    
                    
                    if (inputLine.trim().equals("TAMPER") || inputLine.contains("\"TAMPER\"")) {
                        System.out.println("🚨 Pi reported tampering! Engaging camera...");
                        
                        try {
                            System.out.println("Waiting for ESP32 image stream on port 8081...");
                            try (ServerSocket camServer = new ServerSocket(8081)) {
                                Socket espSocket = camServer.accept();
                                BufferedImage espFrame = ImageIO.read(espSocket.getInputStream());
                                
                                double luminance = SecurityAnalytics.calculateAverageLuminance(espFrame);
                                
                                if (SecurityAnalytics.isCameraBlinded(luminance, true)) {
                                    TelegramNotifier.sendAlert("🚨 CRITICAL: Camera blinded! Luminance: " + luminance);
                                } else {
                                    TelegramNotifier.sendAlert("⚠️ ALERT: Invalid fingerprint/motion! (Cam not blinded)");
                                }
                                espSocket.close();
                            }
                        } catch (Exception e) {
                            System.out.println("Error fetching camera image: " + e.getMessage());
                        }
                        continue; 
                    }
                    
                    try {
                        JSONObject payload = new JSONObject(inputLine);
                        String sensor = payload.getString("sensor");
                        int uid = payload.getInt("uid");
                        String action = payload.getString("action");
                        
                        System.out.println("Parsed -> Sensor: " + sensor + " | UID: " + uid);
                        
                    } catch (Exception e) {
                        System.out.println("JSON Parsing Error: " + e.getMessage());
                    }
                }
            } catch (IOException e) {
                System.out.println("Client Disconnected.");
            } finally {
                try {
                    socket.close();
                } catch (IOException e) {
                    e.printStackTrace();
                }
            }
        }
    }
}