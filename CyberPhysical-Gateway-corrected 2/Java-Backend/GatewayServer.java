import java.awt.image.BufferedImage;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.imageio.ImageIO;

public class GatewayServer {
    private static final int PI_PORT = 8080;
    private static final int CAMERA_PORT = 8081;
    private static final ExecutorService POOL = Executors.newFixedThreadPool(10);
    private static final Object CAMERA_LOCK = new Object();
    private static final Pattern ACTION = Pattern.compile("\\\"action\\\"\\s*:\\s*\\\"([^\\\"]+)\\\"");
    private static final Pattern SENSOR = Pattern.compile("\\\"sensor\\\"\\s*:\\s*\\\"([^\\\"]+)\\\"");
    private static final Pattern UID = Pattern.compile("\\\"uid\\\"\\s*:\\s*(-?\\d+)");

    public static void main(String[] args) {
        try (ServerSocket server = new ServerSocket(PI_PORT)) {
            System.out.println("Gateway listening for the Raspberry Pi on port " + PI_PORT);
            System.out.println("ESP32-CAM will connect on port " + CAMERA_PORT + " after a denial.");
            while (true) {
                Socket client = server.accept();
                POOL.execute(() -> handlePi(client));
            }
        } catch (IOException error) {
            System.err.println("Gateway stopped: " + error.getMessage());
        } finally {
            POOL.shutdown();
        }
    }

    private static void handlePi(Socket socket) {
        try (socket; BufferedReader input = new BufferedReader(
                new InputStreamReader(socket.getInputStream()))) {
            String line;
            while ((line = input.readLine()) != null) {
                String action = field(ACTION, line);
                String sensor = field(SENSOR, line);
                String uid = field(UID, line);
                if (action == null || sensor == null || uid == null) {
                    System.out.println("Ignored malformed Pi message: " + line);
                    continue;
                }
                System.out.println("Pi event: sensor=" + sensor + ", uid=" + uid
                        + ", action=" + action);
                if (action.equals("denied") || action.equals("tamper")) {
                    POOL.execute(GatewayServer::receiveCameraImage);
                }
            }
        } catch (IOException error) {
            System.out.println("Pi client disconnected: " + error.getMessage());
        }
    }

    private static String field(Pattern pattern, String json) {
        Matcher matcher = pattern.matcher(json);
        return matcher.find() ? matcher.group(1) : null;
    }

    private static void receiveCameraImage() {
        // Only one thread may own port 8081 at a time if denials happen close together.
        synchronized (CAMERA_LOCK) {
            System.out.println("Denied fingerprint: waiting up to 15 seconds for ESP32-CAM...");
            try (ServerSocket cameraServer = new ServerSocket(CAMERA_PORT)) {
                cameraServer.setSoTimeout(15000);
                try (Socket camera = cameraServer.accept()) {
                    camera.setSoTimeout(10000);
                    BufferedImage frame = ImageIO.read(camera.getInputStream());
                    if (frame == null) {
                        throw new IOException("camera data was not a readable JPEG");
                    }
                    double luminance = SecurityAnalytics.calculateAverageLuminance(frame);
                    System.out.printf("Camera luminance: %.2f%n", luminance);
                    if (SecurityAnalytics.isCameraBlinded(luminance, true)) {
                        TelegramNotifier.sendAlert(
                                "CRITICAL: Camera may be blinded. Luminance: " + luminance);
                    } else {
                        TelegramNotifier.sendAlert("ALERT: Invalid fingerprint detected.");
                    }
                }
            } catch (SocketTimeoutException error) {
                System.out.println("No ESP32-CAM image arrived within 15 seconds.");
            } catch (IOException error) {
                System.out.println("Camera receive error: " + error.getMessage());
            }
        }
    }
}
