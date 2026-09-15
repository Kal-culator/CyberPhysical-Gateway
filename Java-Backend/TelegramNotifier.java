import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;

public class TelegramNotifier {
    
    private static final String BOT_TOKEN = "8715105333:AAFqA454czMeq0aNJfztXuLUXOsfu0vflwU";
    private static final String CHAT_ID = "6301149879";


    public static void sendAlert(String message) {
        try {
            String encodedMessage = URLEncoder.encode(message, "UTF-8");
            
            String urlString = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage?chat_id=" + CHAT_ID + "&text=" + encodedMessage;
            
            URL url = new URL(urlString);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            
            int responseCode = conn.getResponseCode();
            if (responseCode == 200) {
                System.out.println("[SUCCESS] Telegram Alert Sent: " + message);
            } else {
                System.out.println("[ERROR] Failed to send Telegram alert. HTTP Code: " + responseCode);
            }
            
        } catch (Exception e) {
            System.out.println("Telegram API Error: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        System.out.println("Pinging Telegram API...");
        sendAlert("🚨 TEST ALERT: CyberPhysical Gateway backend is officially online!");
    }
}