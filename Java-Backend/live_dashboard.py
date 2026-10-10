from flask import Flask, render_template_string
import mysql.connector

app = Flask(__name__)

# The HTML and CSS for the front-end
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Zero-Trust Security Log</title>
    <!-- Auto-refreshes the page every 3 seconds so the logs update live! -->
    <meta http-equiv="refresh" content="3"> 
    <style>
        body { background-color: #050505; color: #00ff00; font-family: 'Courier New', Courier, monospace; padding: 30px; margin: 0; }
        h1 { text-align: center; text-shadow: 0 0 15px #00ff00; letter-spacing: 2px; }
        .container { max-width: 1200px; margin: 0 auto; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; background-color: #111; box-shadow: 0 0 20px rgba(0, 255, 0, 0.1); }
        th, td { border: 1px solid #333; padding: 15px; text-align: left; }
        th { background-color: #1a1a1a; text-transform: uppercase; letter-spacing: 1px; }
        tr:nth-child(even) { background-color: #0a0a0a; }
        
        /* Dynamic Color Coding */
        .alert { color: #ff3333; font-weight: bold; text-shadow: 0 0 8px #ff0000; }
        .granted { color: #33ff33; font-weight: bold; }
        .neutral { color: #aaaaaa; }
        
        /* The Blinking Live Recording Dot */
        .status-indicator { text-align: center; margin-bottom: 20px; font-size: 1.2em; color: #aaaaaa; }
        .live-dot { height: 12px; width: 12px; background-color: #ff0000; border-radius: 50%; display: inline-block; margin-right: 8px; animation: blink 1s infinite; box-shadow: 0 0 10px #ff0000; }
        @keyframes blink { 50% { opacity: 0; } }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ LIVE THREAT & ACCESS DASHBOARD 🛡️</h1>
        <div class="status-indicator"><span class="live-dot"></span> LIVE EDGE-NODE FEED</div>
        
        <table>
            <tr>
                <th>Log ID</th>
                <th>Timestamp</th>
                <th>Subject Identity</th>
                <th>Clearance Level</th>
                <th>Edge Decision</th>
                <th>Lock Status</th>
            </tr>
            {% for row in logs %}
            <tr>
                <td class="neutral">{{ row[0] }}</td>
                <td class="neutral">{{ row[1] }}</td>
                <td class="{% if 'INTRUDER' in row[2] or 'Hardware' in row[2] %}alert{% else %}granted{% endif %}">{{ row[2] }}</td>
                <td>{{ row[3] }}</td>
                <td>{{ row[4] }}</td>
                <td class="{% if 'BUZZER' in row[5] %}alert{% else %}granted{% endif %}">{{ row[5] }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    try:
        # Yash needs to ensure this matches his local Mac MySQL password
        conn = mysql.connector.connect(
            host="localhost", 
            user="root", 
            password="password", 
            database="smart_door_demo"
        )
        cursor = conn.cursor()
        
        # Pulls from the God-Mode View
        cursor.execute("SELECT * FROM vw_live_threat_dashboard LIMIT 15")
        logs = cursor.fetchall()
        conn.close()
    except Exception as e:
        # If the database goes offline, show an error instead of crashing the page
        logs = [[0, "ERROR", "DATABASE OFFLINE", "NONE", "FAIL", "UNKNOWN"]]
        
    return render_template_string(HTML_TEMPLATE, logs=logs)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)