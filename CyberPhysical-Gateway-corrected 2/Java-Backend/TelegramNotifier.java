import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

public class TelegramNotifier {
    private static final String BOT_TOKEN = System.getenv("TELEGRAM_BOT_TOKEN");
    private static final String CHAT_ID = System.getenv("TELEGRAM_CHAT_ID");

    public static void sendAlert(String message) {
        if (BOT_TOKEN == null || CHAT_ID == null) {
            System.out.println("Telegram skipped: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.");
            return;
        }
        try {
            String encoded = URLEncoder.encode(message, StandardCharsets.UTF_8);
            URL url = new URL("https://api.telegram.org/bot" + BOT_TOKEN
                    + "/sendMessage?chat_id=" + CHAT_ID + "&text=" + encoded);
            HttpURLConnection connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(5000);
            connection.setReadTimeout(5000);
            System.out.println("Telegram response: HTTP " + connection.getResponseCode());
            connection.disconnect();
        } catch (Exception error) {
            System.out.println("Telegram API error: " + error.getMessage());
        }
    }
}
