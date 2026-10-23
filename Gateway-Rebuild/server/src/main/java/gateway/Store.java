package gateway;
import java.sql.*;
import org.json.*;

public final class Store {
    private final String url,user,password;
    public Store(String url,String user,String password) {this.url=url;this.user=user;this.password=password;}
    Connection open() throws SQLException {return DriverManager.getConnection(url,user,password);}
    public void initialize() throws SQLException {
        try(var c=open();var s=c.createStatement()) {
            s.executeUpdate("CREATE TABLE IF NOT EXISTS gateway_schema (id INT PRIMARY KEY, version INT NOT NULL)");
            boolean fresh;
            try(var r=s.executeQuery("SELECT version FROM gateway_schema WHERE id=1")) {
                fresh=!r.next();
                if(!fresh && r.getInt(1)!=1) throw new SQLException("Unsupported schema version; do not use the old smart_door_demo database.");
            }
            s.executeUpdate("CREATE TABLE IF NOT EXISTS gateway_users (fingerprint_id INT PRIMARY KEY, full_name VARCHAR(100) NOT NULL, authorized BOOLEAN NOT NULL DEFAULT TRUE)");
            s.executeUpdate("CREATE TABLE IF NOT EXISTS gateway_events (event_id BIGINT AUTO_INCREMENT PRIMARY KEY, request_id VARCHAR(64) NOT NULL UNIQUE, device_id VARCHAR(80) NOT NULL, fingerprint_id INT NULL, confidence INT NULL, event_type VARCHAR(40) NOT NULL, decision VARCHAR(30) NOT NULL, reason VARCHAR(100) NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)");
            s.executeUpdate("INSERT INTO gateway_schema (id,version) SELECT 1,1 WHERE NOT EXISTS (SELECT 1 FROM gateway_schema WHERE id=1)");
            if(fresh) s.executeUpdate("INSERT INTO gateway_users (fingerprint_id,full_name,authorized) SELECT 1,'Demo User',TRUE WHERE NOT EXISTS (SELECT 1 FROM gateway_users WHERE fingerprint_id=1)");
            // Deliberately reference every required column: fail at startup on incompatible schemas.
            s.executeQuery("SELECT request_id,device_id,fingerprint_id,confidence,event_type,decision,reason,created_at FROM gateway_events WHERE 1=0").close();
            s.executeQuery("SELECT fingerprint_id,full_name,authorized FROM gateway_users WHERE 1=0").close();
        }
    }
    public boolean authorized(int id) throws SQLException {
        try(var c=open();var q=c.prepareStatement("SELECT authorized FROM gateway_users WHERE fingerprint_id=?")) {
            q.setInt(1,id);try(var r=q.executeQuery()){return r.next() && r.getBoolean(1);}
        }
    }
    public synchronized boolean record(String id,String device,Integer finger,Integer confidence,String type,String decision,String reason) throws SQLException {
        try(var c=open();var q=c.prepareStatement("INSERT INTO gateway_events (request_id,device_id,fingerprint_id,confidence,event_type,decision,reason) VALUES (?,?,?,?,?,?,?)")) {
            q.setString(1,id);q.setString(2,device);q.setObject(3,finger);q.setObject(4,confidence);q.setString(5,type);q.setString(6,decision);q.setString(7,reason);
            q.executeUpdate();return true;
        } catch(SQLException e) { if(e.getSQLState()!=null && e.getSQLState().startsWith("23")) return false;throw e; }
    }
    public boolean exists(String id) throws SQLException {
        try(var c=open();var q=c.prepareStatement("SELECT 1 FROM gateway_events WHERE request_id=?")){q.setString(1,id);try(var r=q.executeQuery()){return r.next();}}
    }
    public JSONArray recent() throws SQLException {
        var a=new JSONArray();
        try(var c=open();var q=c.createStatement();var r=q.executeQuery("SELECT e.*,u.full_name FROM gateway_events e LEFT JOIN gateway_users u ON e.fingerprint_id=u.fingerprint_id ORDER BY event_id DESC LIMIT 50")) {
            while(r.next()) a.put(new JSONObject().put("time",r.getString("created_at")).put("person",r.getString("full_name")==null?"Unknown / system":r.getString("full_name")).put("type",r.getString("event_type")).put("decision",r.getString("decision")).put("reason",r.getString("reason")));
        }return a;
    }
}
