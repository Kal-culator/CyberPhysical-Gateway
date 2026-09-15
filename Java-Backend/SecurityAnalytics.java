import java.awt.Color;
import java.awt.image.BufferedImage;

public class SecurityAnalytics {


    public static double calculateAverageLuminance(BufferedImage image) {
        if (image == null) {
            return 100.0; 
        }

        int width = image.getWidth();
        int height = image.getHeight();
        double totalLuminance = 0;
        int totalPixels = width * height;

        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                // Extract the Red, Green, and Blue integer values for the current pixel
                Color color = new Color(image.getRGB(x, y));
                int r = color.getRed();
                int g = color.getGreen();
                int b = color.getBlue();

                double pixelLuminance = (0.299 * r) + (0.587 * g) + (0.114 * b);
                totalLuminance += pixelLuminance;
            }
        }


        return totalLuminance / totalPixels;
    }


    public static boolean isCameraBlinded(double averageLuminance, boolean motionDetected) {
        return (averageLuminance < 5.0 && motionDetected);
    }
}