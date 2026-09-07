import java.net.*;
import java.io.*;

public class GatewayServer {
    public static void main(String[] args) {
        int port = 8080;
        try (ServerSocket serverSocket = new ServerSocket(port)) {
            System.out.println("Central Hub listening on port " + port + "...");
            
            while (true) {
                Socket clientSocket = serverSocket.accept();
                System.out.println("ESP32 Connected: " + clientSocket.getInetAddress().getHostAddress());
                
                BufferedReader in = new BufferedReader(new InputStreamReader(clientSocket.getInputStream()));
                String inputLine;
                while ((inputLine = in.readLine()) != null) {
                    System.out.println("Received Payload: " + inputLine);
                }
            }
        } catch (Exception e) {
            System.out.println("Server Exception: " + e.getMessage());
        }
    }
}