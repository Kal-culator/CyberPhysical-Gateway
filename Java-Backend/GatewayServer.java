import java.io.*;
import java.net.*;
import java.util.concurrent.*;

public class GatewayServer {
    // Thread pool to handle multiple connections simultaneously
    private static final ExecutorService pool = Executors.newFixedThreadPool(10);

    public static void main(String[] args) {
        int port = 8080;
        try (ServerSocket serverSocket = new ServerSocket(port)) {
            System.out.println("Zero-Trust Hub listening on port " + port + "...");
            
            while (true) {
                Socket clientSocket = serverSocket.accept();
                System.out.println("Incoming connection from: " + clientSocket.getInetAddress().getHostAddress());
                
                // Hand the connection off to a new thread and instantly go back to listening
                pool.execute(new ClientHandler(clientSocket));
            }
        } catch (IOException e) {
            System.out.println("Server Exception: " + e.getMessage());
        }
    }

    // Inner class defining the thread logic
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
                    System.out.println("Processing Payload: " + inputLine);
                    // Sadiq's database logic and JSON parsing will go here later
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