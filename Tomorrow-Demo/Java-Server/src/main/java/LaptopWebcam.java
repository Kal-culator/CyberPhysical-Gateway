import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.TimeUnit;

/** One fresh laptop image per review; never reads an image left by another request. */
final class LaptopWebcam {
    static byte[] capture() throws IOException, InterruptedException {
        Path image = Files.createTempFile("door-visitor-", ".jpg");
        Process process = null;
        try {
            process = new ProcessBuilder(env("WEBCAM_PYTHON", "python3"),
                    env("WEBCAM_SCRIPT", "capture_webcam.py"), "--output", image.toString(),
                    "--index", env("WEBCAM_INDEX", "0"))
                    .redirectOutput(ProcessBuilder.Redirect.INHERIT)
                    .redirectError(ProcessBuilder.Redirect.INHERIT).start();
            if (!process.waitFor(8, TimeUnit.SECONDS)) {
                throw new IOException("Capture timed out; check camera permissions or close other camera apps.");
            }
            if (process.exitValue() != 0) throw new IOException("Capture helper failed.");
            long size = Files.size(image);
            if (size < 4 || size > 10_000_000) throw new IOException("Missing or oversized JPEG.");
            byte[] bytes = Files.readAllBytes(image);
            if ((bytes[0] & 255) != 255 || (bytes[1] & 255) != 216
                    || (bytes[bytes.length - 2] & 255) != 255 || (bytes[bytes.length - 1] & 255) != 217) {
                throw new IOException("Capture is not a JPEG.");
            }
            return bytes;
        } finally {
            if (process != null && process.isAlive()) {
                process.destroyForcibly();
                process.waitFor(1, TimeUnit.SECONDS);
            }
            Files.deleteIfExists(image);
        }
    }

    private static String env(String key, String fallback) {
        String value = System.getenv(key);
        return value == null || value.isBlank() ? fallback : value;
    }
}
