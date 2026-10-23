package gateway;
import java.nio.file.*;
import java.io.*;
import java.util.*;

public final class Settings {
    final Properties p = new Properties();
    public Settings(Path path) throws IOException {
        try (var in = Files.newInputStream(path)) { p.load(in); }
        if (text("api.token", "").length() < 32 || text("api.token", "").contains("CHANGE"))
            throw new IllegalArgumentException("Run tools/configure.py: api.token must be a generated secret of at least 32 characters.");
        integer("server.port",8080,1024,65535);
        integer("approval.seconds",30,5,60);
    }
    String raw(String k,String d) { return p.getProperty(k,d); }
    String text(String k,String d) { return p.getProperty(k,d).trim(); }
    boolean flag(String k,boolean d) { return Boolean.parseBoolean(text(k,""+d)); }
    int integer(String k,int d,int min,int max) {
        int n=Integer.parseInt(text(k,""+d));
        if(n<min || n>max) throw new IllegalArgumentException("Invalid "+k);
        return n;
    }
    boolean simulation() {return flag("simulation",false);}
}
