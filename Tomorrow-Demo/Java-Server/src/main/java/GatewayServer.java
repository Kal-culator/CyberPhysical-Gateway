import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class GatewayServer {
    private static final int PORT = integerEnvironment("SERVER_PORT", 8080);
    private static final int APPROVAL_SECONDS = integerEnvironment("APPROVAL_TIMEOUT_SECONDS", 30);
    private static final String DB_URL = environment(
            "DB_URL", "jdbc:mysql://localhost:3306/smart_door_demo?serverTimezone=UTC");
    private static final String DB_USER = environment("DB_USER", "root");
    private static final String DB_PASSWORD = environment("DB_PASSWORD", "");
    private static final String BOT_TOKEN = environment("TELEGRAM_BOT_TOKEN", "");
    private static final String CHAT_ID = environment("TELEGRAM_CHAT_ID", "");
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5)).build();
    private static long nextUpdateId = 0;

    private GatewayServer() {}

    public static void main(String[] args) throws Exception {
        if (args.length == 1 && "--self-test".equals(args[0])) {
            Event sample = Event.fromJson(
                    "{\"device_id\":\"door-1\",\"fingerprint_id\":null,"
                    + "\"confidence\":0,\"pi_decision\":\"REVIEW\",\"relay_channel\":0}");
            if (sample.fingerprintId != null || sample.confidence != 0
                    || sample.relayChannel != 0 || !"REVIEW".equals(sample.piDecision)) {
                throw new IllegalStateException("Event parser self-test failed");
            }
            long update = highestUpdateId("{\"ok\":true,\"result\":[{\"update_id\":41}]}");
            if (update != 41) throw new IllegalStateException("Telegram parser self-test failed");
            CallbackAnswer callback = findCallback(
                    "{\"callback_query\":{\"id\":\"query-7\",\"from\":{},"
                    + "\"message\":{},\"data\":\"YES:abc123\"}}", "abc123");
            if (callback == null || !callback.yes || !"query-7".equals(callback.callbackId)) {
                throw new IllegalStateException("Telegram callback self-test failed");
            }
            System.out.println("Java event and Telegram parser self-tests passed.");
            return;
        }

        checkDatabase();
        checkTelegram();
        try (ServerSocket server = new ServerSocket(PORT)) {
            System.out.printf("Gateway server listening on port %d.%n", PORT);
            System.out.println("Keep this terminal open during the demonstration.");
            while (true) {
                try (Socket socket = server.accept()) {
                    handle(socket);
                } catch (Exception error) {
                    System.err.println("Event failed: " + error.getMessage());
                }
            }
        }
    }

    private static void checkDatabase() {
        try (Connection ignored = databaseConnection()) {
            System.out.println("MySQL connection OK.");
        } catch (SQLException error) {
            System.err.println("MySQL is unavailable: " + error.getMessage());
            System.err.println("Approval can still work, but events will not be stored.");
        }
    }

    private static void checkTelegram() {
        if (BOT_TOKEN.isBlank() || CHAT_ID.isBlank()) {
            System.err.println("Telegram is not configured. Unknown fingerprints will be denied.");
            return;
        }
        try {
            telegram("getMe", Map.of(), 5);
            String pending = getUpdates(0);
            long highest = highestUpdateId(pending);
            if (highest >= 0) nextUpdateId = highest + 1;
            System.out.println("Telegram bot connection OK.");
        } catch (Exception error) {
            System.err.println("Telegram is unavailable: " + error.getMessage());
            System.err.println("Unknown fingerprints will be denied unless this is fixed.");
        }
    }

    private static void handle(Socket socket) throws IOException {
        socket.setSoTimeout(2000);
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                    socket.getInputStream(), StandardCharsets.UTF_8));
             PrintWriter writer = new PrintWriter(socket.getOutputStream(), true, StandardCharsets.UTF_8)) {
            String line = reader.readLine();
            if (line == null || line.length() > 2048) {
                throw new IllegalArgumentException("Missing or oversized event");
            }
            Event event = Event.fromJson(line);
            Decision decision = "REVIEW".equals(event.piDecision)
                    ? requestTelegramApproval(event)
                    : new Decision("NOT_REQUIRED", "OPEN", 2);

            writer.printf(
                    "{\"action\":\"%s\",\"telegram_decision\":\"%s\"}%n",
                    decision.action, decision.telegramDecision);

            StoredResult result = null;
            try {
                result = store(event, decision);
            } catch (SQLException error) {
                System.err.println("Could not store event: " + error.getMessage());
            }

            String name = result == null || result.userName == null ? "unknown" : result.userName;
            String eventNumber = result == null ? "not stored" : Long.toString(result.eventId);
            System.out.printf(
                    "%s | Pi=%s | fingerprint=%s | Telegram=%s | action=%s | event=%s%n",
                    name, event.piDecision, event.fingerprintId, decision.telegramDecision,
                    decision.action, eventNumber);
        }
    }

    private static Decision requestTelegramApproval(Event event) {
        if (BOT_TOKEN.isBlank() || CHAT_ID.isBlank()) {
            return new Decision("ERROR", "BUZZER", 1);
        }
        String requestId = UUID.randomUUID().toString().replace("-", "").substring(0, 12);
        String description = event.fingerprintId == null
                ? "Fingerprint was not recognized."
                : "Fingerprint ID " + event.fingerprintId + " is not locally authorized.";
        String keyboard = "{\"inline_keyboard\":[[{\"text\":\"YES - OPEN\","
                + "\"callback_data\":\"YES:" + requestId + "\"},{\"text\":\"NO - DENY\","
                + "\"callback_data\":\"NO:" + requestId + "\"}]]}";
        try {
            Map<String, String> send = new LinkedHashMap<>();
            send.put("chat_id", CHAT_ID);
            send.put("text", "Unknown fingerprint at " + event.deviceId + ".\n" + description
                    + "\nOpen the lock? Reply within " + APPROVAL_SECONDS + " seconds.");
            send.put("reply_markup", keyboard);
            String sent = telegram("sendMessage", send, 8);
            int messageId = firstInteger(sent, "message_id");
            long deadline = System.nanoTime() + Duration.ofSeconds(APPROVAL_SECONDS).toNanos();
            while (System.nanoTime() < deadline) {
                long remaining = Duration.ofNanos(deadline - System.nanoTime()).toSeconds();
                int pollSeconds = (int) Math.max(1, Math.min(3, remaining));
                String updates = getUpdates(pollSeconds);
                long highest = highestUpdateId(updates);
                if (highest >= nextUpdateId) nextUpdateId = highest + 1;
                CallbackAnswer answer = findCallback(updates, requestId);
                if (answer != null) {
                    boolean yes = answer.yes;
                    answerCallback(answer.callbackId, yes ? "Door opening" : "Access denied");
                    finishTelegramMessage(messageId, yes ? "YES - door opened." : "NO - access denied.");
                    return new Decision(yes ? "YES" : "NO", yes ? "OPEN" : "BUZZER", yes ? 2 : 1);
                }
            }
            finishTelegramMessage(messageId, "Timed out after " + APPROVAL_SECONDS + " seconds - access denied.");
            return new Decision("TIMEOUT", "BUZZER", 1);
        } catch (Exception error) {
            System.err.println("Telegram approval failed: " + error.getMessage());
            return new Decision("ERROR", "BUZZER", 1);
        }
    }

    private static String getUpdates(int timeoutSeconds) throws IOException, InterruptedException {
        Map<String, String> fields = new LinkedHashMap<>();
        fields.put("offset", Long.toString(nextUpdateId));
        fields.put("timeout", Integer.toString(timeoutSeconds));
        fields.put("allowed_updates", "[\"callback_query\"]");
        return telegram("getUpdates", fields, timeoutSeconds + 5);
    }

    private static void answerCallback(String callbackId, String text)
            throws IOException, InterruptedException {
        telegram("answerCallbackQuery", Map.of(
                "callback_query_id", callbackId, "text", text), 5);
    }

    private static void finishTelegramMessage(int messageId, String text)
            throws IOException, InterruptedException {
        Map<String, String> fields = new LinkedHashMap<>();
        fields.put("chat_id", CHAT_ID);
        fields.put("message_id", Integer.toString(messageId));
        fields.put("text", text);
        fields.put("reply_markup", "{\"inline_keyboard\":[]}");
        telegram("editMessageText", fields, 5);
    }

    private static String telegram(String method, Map<String, String> fields, int timeoutSeconds)
            throws IOException, InterruptedException {
        StringBuilder form = new StringBuilder();
        for (Map.Entry<String, String> field : fields.entrySet()) {
            if (form.length() > 0) form.append('&');
            form.append(URLEncoder.encode(field.getKey(), StandardCharsets.UTF_8));
            form.append('=');
            form.append(URLEncoder.encode(field.getValue(), StandardCharsets.UTF_8));
        }
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create("https://api.telegram.org/bot" + BOT_TOKEN + "/" + method))
                .timeout(Duration.ofSeconds(Math.max(5, timeoutSeconds)))
                .header("Content-Type", "application/x-www-form-urlencoded")
                .POST(HttpRequest.BodyPublishers.ofString(form.toString()))
                .build();
        HttpResponse<String> response = HTTP.send(
                request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        if (response.statusCode() != 200
                || !Pattern.compile("\\\"ok\\\"\\s*:\\s*true").matcher(response.body()).find()) {
            throw new IOException("Telegram " + method + " returned HTTP " + response.statusCode());
        }
        return response.body();
    }

    private static long highestUpdateId(String json) {
        Matcher matcher = Pattern.compile("\\\"update_id\\\"\\s*:\\s*(\\d+)").matcher(json);
        long highest = -1;
        while (matcher.find()) highest = Math.max(highest, Long.parseLong(matcher.group(1)));
        return highest;
    }

    private static CallbackAnswer findCallback(String json, String requestId) {
        Pattern pattern = Pattern.compile(
                "\\\"callback_query\\\"\\s*:\\s*\\{\\s*\\\"id\\\"\\s*:\\s*\\\"([^\\\"]+)\\\""
                + "(?:(?!\\\"callback_query\\\"\\s*:).)*?"
                + "\\\"data\\\"\\s*:\\s*\\\"(YES|NO):" + Pattern.quote(requestId) + "\\\"",
                Pattern.DOTALL);
        Matcher matcher = pattern.matcher(json);
        if (!matcher.find()) return null;
        return new CallbackAnswer(matcher.group(1), "YES".equals(matcher.group(2)));
    }

    private static int firstInteger(String json, String field) {
        Matcher matcher = Pattern.compile("\\\"" + Pattern.quote(field)
                + "\\\"\\s*:\\s*(\\d+)").matcher(json);
        if (!matcher.find()) throw new IllegalArgumentException("Telegram response missing " + field);
        return Integer.parseInt(matcher.group(1));
    }

    private static StoredResult store(Event event, Decision decision) throws SQLException {
        try (Connection connection = databaseConnection()) {
            connection.setAutoCommit(false);
            try {
                Long userId = null;
                String userName = null;
                boolean authorized = false;
                if (event.fingerprintId != null) {
                    String lookup = "SELECT user_id, user_name, authorized FROM users WHERE fingerprint_id = ?";
                    try (PreparedStatement statement = connection.prepareStatement(lookup)) {
                        statement.setInt(1, event.fingerprintId);
                        try (ResultSet rows = statement.executeQuery()) {
                            if (rows.next()) {
                                userId = rows.getLong("user_id");
                                userName = rows.getString("user_name");
                                authorized = rows.getBoolean("authorized");
                            }
                        }
                    }
                }

                String insert = "INSERT INTO access_events "
                        + "(device_id, fingerprint_id, confidence, pi_decision, database_authorized, "
                        + "telegram_decision, final_action, user_id, relay_channel) "
                        + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)";
                long eventId;
                try (PreparedStatement statement = connection.prepareStatement(
                        insert, PreparedStatement.RETURN_GENERATED_KEYS)) {
                    statement.setString(1, event.deviceId);
                    if (event.fingerprintId == null) statement.setNull(2, java.sql.Types.INTEGER);
                    else statement.setInt(2, event.fingerprintId);
                    statement.setInt(3, event.confidence);
                    statement.setString(4, event.piDecision);
                    statement.setBoolean(5, authorized);
                    statement.setString(6, decision.telegramDecision);
                    statement.setString(7, decision.action);
                    if (userId == null) statement.setNull(8, java.sql.Types.BIGINT);
                    else statement.setLong(8, userId);
                    statement.setInt(9, decision.relayChannel);
                    statement.executeUpdate();
                    try (ResultSet keys = statement.getGeneratedKeys()) {
                        if (!keys.next()) throw new SQLException("No event ID returned");
                        eventId = keys.getLong(1);
                    }
                }
                connection.commit();
                return new StoredResult(eventId, userName, authorized);
            } catch (SQLException error) {
                connection.rollback();
                throw error;
            }
        }
    }

    private static Connection databaseConnection() throws SQLException {
        return DriverManager.getConnection(DB_URL, DB_USER, DB_PASSWORD);
    }

    private static String environment(String name, String fallback) {
        String value = System.getenv(name);
        return value == null || value.isBlank() ? fallback : value;
    }

    private static int integerEnvironment(String name, int fallback) {
        String value = System.getenv(name);
        return value == null || value.isBlank() ? fallback : Integer.parseInt(value);
    }

    private static final class Event {
        final String deviceId;
        final Integer fingerprintId;
        final int confidence;
        final String piDecision;
        final int relayChannel;

        Event(String deviceId, Integer fingerprintId, int confidence,
              String piDecision, int relayChannel) {
            this.deviceId = deviceId;
            this.fingerprintId = fingerprintId;
            this.confidence = confidence;
            this.piDecision = piDecision;
            this.relayChannel = relayChannel;
        }

        static Event fromJson(String json) {
            String deviceId = requiredString(json, "device_id");
            Integer fingerprintId = nullableInteger(json, "fingerprint_id");
            int confidence = requiredInteger(json, "confidence");
            String decision = requiredString(json, "pi_decision");
            int relay = requiredInteger(json, "relay_channel");
            if (!decision.equals("GRANTED") && !decision.equals("REVIEW")) {
                throw new IllegalArgumentException("pi_decision must be GRANTED or REVIEW");
            }
            if (deviceId.isBlank() || deviceId.length() > 80 || confidence < 0 || relay < 0 || relay > 2) {
                throw new IllegalArgumentException("Event value is outside the allowed range");
            }
            return new Event(deviceId, fingerprintId, confidence, decision, relay);
        }

        private static String requiredString(String json, String field) {
            Matcher matcher = Pattern.compile("\\\"" + Pattern.quote(field)
                    + "\\\"\\s*:\\s*\\\"([^\\\"]*)\\\"").matcher(json);
            if (!matcher.find()) throw new IllegalArgumentException("Missing " + field);
            return matcher.group(1);
        }

        private static int requiredInteger(String json, String field) {
            Matcher matcher = Pattern.compile("\\\"" + Pattern.quote(field)
                    + "\\\"\\s*:\\s*(-?\\d+)").matcher(json);
            if (!matcher.find()) throw new IllegalArgumentException("Missing " + field);
            return Integer.parseInt(matcher.group(1));
        }

        private static Integer nullableInteger(String json, String field) {
            Matcher matcher = Pattern.compile("\\\"" + Pattern.quote(field)
                    + "\\\"\\s*:\\s*(null|-?\\d+)").matcher(json);
            if (!matcher.find()) throw new IllegalArgumentException("Missing " + field);
            return "null".equals(matcher.group(1)) ? null : Integer.valueOf(matcher.group(1));
        }
    }

    private static final class Decision {
        final String telegramDecision;
        final String action;
        final int relayChannel;

        Decision(String telegramDecision, String action, int relayChannel) {
            this.telegramDecision = telegramDecision;
            this.action = action;
            this.relayChannel = relayChannel;
        }
    }

    private static final class CallbackAnswer {
        final String callbackId;
        final boolean yes;

        CallbackAnswer(String callbackId, boolean yes) {
            this.callbackId = callbackId;
            this.yes = yes;
        }
    }

    private static final class StoredResult {
        final long eventId;
        final String userName;
        final boolean authorized;

        StoredResult(long eventId, String userName, boolean authorized) {
            this.eventId = eventId;
            this.userName = userName;
            this.authorized = authorized;
        }
    }
}
