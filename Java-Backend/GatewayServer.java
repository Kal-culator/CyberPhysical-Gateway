import java.io.*;
import java.net.*;
import java.util.concurrent.*;
import org.json.JSONObject; 

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