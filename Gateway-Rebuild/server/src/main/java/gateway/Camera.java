package gateway;
import java.io.*;
import java.time.*;
import javax.imageio.*;
import javax.imageio.stream.*;
import org.json.*;

public final class Camera {
    private byte[] latest;private Instant seen;private double mean;private int darkCount;
    private final Clock clock;private final int threshold,frames;
    public Camera(Clock clock,int threshold,int frames){this.clock=clock;this.threshold=threshold;this.frames=frames;}
    public synchronized boolean accept(byte[] bytes) throws IOException {
        if(bytes.length<4||bytes[0]!=(byte)0xff||bytes[1]!=(byte)0xd8)throw new IOException("Expected JPEG");
        try(var stream=ImageIO.createImageInputStream(new ByteArrayInputStream(bytes))){
            var readers=ImageIO.getImageReaders(stream);if(!readers.hasNext())throw new IOException("Invalid JPEG");var reader=readers.next();
            try{reader.setInput(stream);int w=reader.getWidth(0),h=reader.getHeight(0);if(w>1600||h>1200||w<1||h<1)throw new IOException("Image dimensions exceed limit");
                var im=reader.read(0);double sum=0;int n=0;
                for(int y=0;y<h;y+=4)for(int x=0;x<w;x+=4){int rgb=im.getRGB(x,y);sum+=0.2126*((rgb>>16)&255)+0.7152*((rgb>>8)&255)+0.0722*(rgb&255);n++;}
                mean=sum/n;latest=bytes.clone();seen=clock.instant();darkCount=mean<threshold?darkCount+1:0;
                return darkCount>=frames;
            }finally{reader.dispose();}
        }
    }
    public synchronized byte[] fresh(){return seen!=null&&Duration.between(seen,clock.instant()).toSeconds()<15?latest.clone():null;}
    public synchronized boolean stale(int seconds){return seen==null||Duration.between(seen,clock.instant()).toSeconds()>seconds;}
    public synchronized JSONObject status(){return new JSONObject().put("seen",seen==null?JSONObject.NULL:seen.toString()).put("mean_brightness",mean).put("dark_frames",darkCount);}
}
