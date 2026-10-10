"""
Door access dashboard - visual upgrade.

Drop-in replacement for the old live_dashboard.py:
  * same database, same view (vw_live_threat_dashboard), same query
  * same route "/" and same port 5000
  * read-only: it never writes to MySQL and never talks to the Pi or the Java server
  * works fully offline: no CDN, no web fonts, no external requests

Extras (all optional, all read-only):
  * "/" no longer reloads the whole page every 3 s. It updates in place.
  * "/api/logs" returns the same data as JSON for the page's own use.
  * DB settings can be overridden with env vars DB_HOST, DB_USER, DB_PASSWORD.
    With nothing set, it uses the same values as before (localhost / root / password).

Needs on the Mac:  pip install flask mysql-connector-python
"""
import os

from flask import Flask, jsonify, render_template_string
import mysql.connector

app = Flask(__name__)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "password"),
    "database": "smart_door_demo",
    "connection_timeout": 3,  # a dead database should not hang the page
}

DECISION_LABELS = {"GRANTED": ("Granted", "ok"),
                   "REVIEW": ("Owner review", "warn"),
                   "TAMPER": ("Tamper", "bad")}
LOCK_LABELS = {"OPEN": ("Unlocked", "ok"),
               "BUZZER": ("Buzzer on", "bad")}


def _text(value):
    """MySQL connectors sometimes hand back bytes for computed columns."""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", "replace")
    return "" if value is None else str(value)


def shape_row(r):
    """Turn one row of vw_live_threat_dashboard into a plain dict for the page.

    Column order of the view: 0 Log_ID, 1 Timestamp, 2 Subject_Identity,
    3 Clearance, 4 Edge_Node_Decision, 5 Physical_Lock_Status.
    """
    who, clearance = _text(r[2]), _text(r[3])
    decision, lock = _text(r[4]), _text(r[5])
    dec_u, lock_u = decision.upper(), lock.upper()

    unknown = "INTRUDER" in who.upper()
    denied = "BUZZER" in lock_u
    opened = "OPEN" in lock_u and not denied
    tamper = dec_u == "TAMPER"

    if tamper:
        headline, note = "Tamper alert", "Physical tampering detected"
    elif denied:
        headline = "Access denied"
        note = "Unregistered fingerprint" if unknown else "Owner did not approve"
    elif opened and dec_u == "REVIEW":
        headline, note = "Door opened", "Approved by the owner on Telegram"
    elif opened:
        headline, note = "Door opened", "Fingerprint matched"
    else:
        headline, note = (lock or "Unknown result"), decision

    try:
        log_id = int(r[0])
    except (TypeError, ValueError):
        log_id = 0

    d_label, d_cls = DECISION_LABELS.get(dec_u, (decision, "dim"))
    l_label, l_cls = LOCK_LABELS.get(lock_u, (lock, "dim"))

    return {
        "id": log_id,
        "time": _text(r[1]),
        "who": who,
        "clearance": clearance,
        "decision": d_label, "decision_cls": d_cls,
        "lock": l_label, "lock_cls": l_cls,
        "level": "alert" if (unknown or denied or tamper) else "ok",
        "headline": headline,
        "note": note,
        "unknown": unknown, "denied": denied, "opened": opened,
    }


def fetch_logs():
    """Same query as before. Returns (database_ok, rows)."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vw_live_threat_dashboard LIMIT 15")
            raw = cursor.fetchall()
        finally:
            conn.close()
        return True, [shape_row(r) for r in raw]
    except Exception:
        return False, []


def payload():
    ok, rows = fetch_logs()
    return {
        "db_ok": ok,
        "rows": rows,
        "counts": {
            "opened": sum(1 for r in rows if r["opened"]),
            "denied": sum(1 for r in rows if r["denied"]),
            "unknown": sum(1 for r in rows if r["unknown"]),
        },
    }


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Door access log</title>
<style>
  :root {
    --bg: #0a0f17;
    --panel: #111924;
    --line: #1f2c3d;
    --text: #e8eef6;
    --dim: #8696ab;
    --ok: #3ddc97;
    --warn: #f6b93b;
    --bad: #ff5a6e;
    --idle: #6f8199;
    --sans: "Avenir Next", "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
    --mono: ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
  }
  * { box-sizing: border-box; }
  html { background: var(--bg); }
  body {
    margin: 0; padding: clamp(16px, 3vw, 40px);
    background: var(--bg); color: var(--text);
    font-family: var(--sans); font-size: 16px; line-height: 1.45;
  }
  .wrap { max-width: 1240px; margin: 0 auto; }

  /* ---------- top bar ---------- */
  .top { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 22px; }
  h1 { margin: 0; font-size: clamp(1.25rem, 2.2vw, 1.6rem); font-weight: 650; letter-spacing: -0.01em; }
  .sub { margin: 2px 0 0; color: var(--dim); font-size: 0.92rem; }
  .status { display: inline-flex; align-items: center; gap: 10px; padding: 8px 14px; border: 1px solid var(--line); border-radius: 999px; background: var(--panel); font-size: 0.9rem; }
  .status .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--ok); }
  .status.online .dot { animation: pulse 2s ease-in-out infinite; }
  .status.dboff .dot, .status.lost .dot { background: var(--bad); }
  .status .sync { color: var(--dim); font-family: var(--mono); font-size: 0.82rem; }

  /* ---------- latest event ---------- */
  .hero {
    --accent: var(--idle);
    display: grid; grid-template-columns: auto 1fr auto; gap: clamp(16px, 3vw, 36px); align-items: center;
    padding: clamp(18px, 3vw, 32px);
    background: var(--panel); border: 1px solid var(--line); border-left: 6px solid var(--accent);
    border-radius: 10px;
  }
  .hero.ok { --accent: var(--ok); }
  .hero.alert { --accent: var(--bad); }
  .hero.warn { --accent: var(--warn); }
  .hero.flash { animation: flash 2.4s ease-out; }
  .mark {
    width: clamp(64px, 8vw, 96px); height: clamp(64px, 8vw, 96px);
    display: grid; place-items: center; border-radius: 50%;
    border: 2px solid var(--accent); color: var(--accent);
  }
  .mark svg { width: 52%; height: 52%; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; display: none; }
  .hero.idle .i-closed, .hero.ok .i-open, .hero.alert .i-alert, .hero.warn .i-alert { display: block; }
  .headline { margin: 0; font-size: clamp(2rem, 5vw, 3.5rem); line-height: 1.05; font-weight: 750; letter-spacing: -0.02em; color: var(--accent); }
  .who { margin: 8px 0 0; font-size: clamp(1.1rem, 2vw, 1.5rem); font-weight: 550; }
  .meta { margin: 4px 0 0; color: var(--dim); }
  .meta b { font-family: var(--mono); font-weight: 500; color: var(--text); }
  .counts { display: flex; gap: clamp(16px, 2.5vw, 32px); }
  .count { text-align: left; min-width: 64px; }
  .count .n { display: block; font-size: clamp(1.8rem, 3.4vw, 2.6rem); font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; }
  .count .l { display: block; margin-top: 6px; color: var(--dim); font-size: 0.85rem; max-width: 9ch; }
  .count.ok .n { color: var(--ok); }
  .count.bad .n { color: var(--bad); }
  .count.warn .n { color: var(--warn); }
  .counts-note { margin: 10px 0 0; color: var(--dim); font-size: 0.8rem; text-align: right; }

  /* ---------- log ---------- */
  .log { margin-top: 22px; background: var(--panel); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
  .log h2 { margin: 0; padding: 16px 20px; font-size: 1rem; font-weight: 650; border-bottom: 1px solid var(--line); }
  .scroll { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; min-width: 760px; }
  th { text-align: left; padding: 10px 20px; color: var(--dim); font-weight: 500; font-size: 0.85rem; border-bottom: 1px solid var(--line); white-space: nowrap; }
  td { padding: 14px 20px; border-bottom: 1px solid var(--line); vertical-align: middle; }
  tbody tr:last-child td { border-bottom: 0; }
  tr.alert td:first-child { box-shadow: inset 4px 0 0 var(--bad); }
  tr.ok td:first-child { box-shadow: inset 4px 0 0 var(--ok); }
  tr.alert { background: rgba(255, 90, 110, 0.06); }
  tr.fresh { animation: fresh 2.4s ease-out; }
  .t { font-family: var(--mono); font-size: 0.95rem; white-space: nowrap; }
  .t small { display: block; margin-top: 2px; color: var(--dim); font-family: var(--sans); font-size: 0.78rem; }
  .person { display: flex; align-items: center; gap: 12px; font-weight: 550; }
  .avatar { flex: none; width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; background: #1a2636; color: var(--text); font-size: 0.85rem; font-weight: 650; }
  tr.alert .avatar { background: rgba(255, 90, 110, 0.18); color: var(--bad); }
  .clear { color: var(--dim); }
  .pill { display: inline-block; padding: 3px 11px; border-radius: 999px; font-size: 0.85rem; font-weight: 550; border: 1px solid currentColor; white-space: nowrap; }
  .pill.ok { color: var(--ok); }
  .pill.warn { color: var(--warn); }
  .pill.bad { color: var(--bad); }
  .pill.dim { color: var(--idle); }
  .id { font-family: var(--mono); color: var(--dim); font-size: 0.85rem; }
  .empty { padding: 40px 20px; text-align: center; color: var(--dim); }

  /* ---------- motion ---------- */
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.25; } }
  @keyframes flash { 0% { box-shadow: 0 0 0 0 transparent, inset 0 0 0 999px color-mix(in srgb, var(--accent) 22%, transparent); }
                     100% { box-shadow: 0 0 0 0 transparent, inset 0 0 0 999px transparent; } }
  @keyframes fresh { from { background: rgba(246, 185, 59, 0.2); } to { background: transparent; } }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; } }

  @media (max-width: 860px) {
    .hero { grid-template-columns: auto 1fr; }
    .hero .side { grid-column: 1 / -1; }
    .counts-note { text-align: left; }
  }
</style>
</head>
<body>
<div class="wrap">

  <header class="top">
    <div>
      <h1>Door access log</h1>
      <p class="sub">Live feed from the door. Updates every 3 seconds.</p>
    </div>
    <div id="status" class="status online" role="status">
      <span class="dot"></span><span id="status-text">Live</span><span class="sync" id="sync"></span>
    </div>
  </header>

  <section id="hero" class="hero idle" aria-live="polite">
    <div class="mark" aria-hidden="true">
      <svg class="i-closed" viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>
      <svg class="i-open" viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 7.5-1.9"/></svg>
      <svg class="i-alert" viewBox="0 0 24 24"><path d="M12 4 21 19H3z"/><path d="M12 10v4M12 16.5v.5"/></svg>
    </div>
    <div>
      <p class="headline" id="h-head">Waiting for the first scan</p>
      <p class="who" id="h-who"></p>
      <p class="meta" id="h-meta">Events appear here the moment someone uses the door.</p>
    </div>
    <div class="side">
      <div class="counts">
        <div class="count ok"><span class="n" id="c-opened">0</span><span class="l">Door opened</span></div>
        <div class="count bad"><span class="n" id="c-denied">0</span><span class="l">Access denied</span></div>
        <div class="count warn"><span class="n" id="c-unknown">0</span><span class="l">Unknown people</span></div>
      </div>
      <p class="counts-note">Across the last 15 events</p>
    </div>
  </section>

  <section class="log">
    <h2>Recent events</h2>
    <div class="scroll">
      <table>
        <thead>
          <tr>
            <th>When</th><th>Person</th><th>Clearance</th>
            <th>Door decision</th><th>Lock</th><th>Log #</th>
          </tr>
        </thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
  </section>

</div>

<script id="boot" type="application/json">{{ boot|tojson }}</script>
<script>
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var lastId = null;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function setStatus(kind) {
    var s = $('status');
    s.className = 'status ' + kind;
    $('status-text').textContent =
      kind === 'online' ? 'Live' :
      kind === 'dboff' ? 'Database offline' : 'Lost connection to dashboard';
    var n = new Date();
    $('sync').textContent = n.toLocaleTimeString([], { hour12: false });
  }

  function splitTime(t) {
    var p = t.split(' - ');
    return p.length === 2 ? { clock: p[1], date: p[0] } : { clock: t, date: '' };
  }

  function renderHero(d) {
    var hero = $('hero'), r = d.rows[0];
    if (!d.db_ok) {
      hero.className = 'hero warn';
      $('h-head').textContent = 'Database offline';
      $('h-who').textContent = '';
      $('h-meta').textContent = 'Start MySQL. This page reconnects by itself.';
    } else if (!r) {
      hero.className = 'hero idle';
      $('h-head').textContent = 'Waiting for the first scan';
      $('h-who').textContent = '';
      $('h-meta').textContent = 'Events appear here the moment someone uses the door.';
    } else {
      hero.className = 'hero ' + r.level;
      var t = splitTime(r.time);
      $('h-head').textContent = r.headline;
      $('h-who').textContent = r.who + (r.clearance && r.clearance !== 'NONE' ? ' \u00b7 ' + r.clearance : '');
      var meta = $('h-meta');
      meta.textContent = '';
      meta.appendChild(el('b', '', t.clock));
      meta.appendChild(document.createTextNode((t.date ? ', ' + t.date : '') + '. ' + r.note + '.'));
    }
    $('c-opened').textContent = d.counts.opened;
    $('c-denied').textContent = d.counts.denied;
    $('c-unknown').textContent = d.counts.unknown;
  }

  function renderRows(d, fresh) {
    var tb = $('rows');
    tb.textContent = '';
    if (!d.rows.length) {
      var tr0 = el('tr'), td0 = el('td', 'empty',
        d.db_ok ? 'No events yet. Scan a finger on the door to see it here.'
                : 'Cannot read the database.');
      td0.colSpan = 6;
      tr0.appendChild(td0);
      tb.appendChild(tr0);
      return;
    }
    d.rows.forEach(function (r) {
      var tr = el('tr', r.level + (fresh[r.id] ? ' fresh' : ''));

      var tdT = el('td', 't'), t = splitTime(r.time);
      tdT.textContent = t.clock;
      if (t.date) tdT.appendChild(el('small', '', t.date));
      tr.appendChild(tdT);

      var tdP = el('td'), box = el('div', 'person');
      var initial = r.unknown ? '!' : (r.who.charAt(0) || '?').toUpperCase();
      box.appendChild(el('span', 'avatar', initial));
      box.appendChild(el('span', '', r.who));
      tdP.appendChild(box);
      tr.appendChild(tdP);

      tr.appendChild(el('td', 'clear', r.clearance === 'NONE' ? 'No clearance' : r.clearance));

      var tdD = el('td'); tdD.appendChild(el('span', 'pill ' + r.decision_cls, r.decision));
      tr.appendChild(tdD);
      var tdL = el('td'); tdL.appendChild(el('span', 'pill ' + r.lock_cls, r.lock));
      tr.appendChild(tdL);

      tr.appendChild(el('td', 'id', '#' + r.id));
      tb.appendChild(tr);
    });
  }

  function apply(d, announce) {
    var maxId = 0, fresh = {}, newest = null;
    d.rows.forEach(function (r) {
      if (r.id > maxId) maxId = r.id;
      if (announce && lastId !== null && r.id > lastId) {
        fresh[r.id] = true;
        if (!newest) newest = r;   // rows come newest first
      }
    });
    renderHero(d);
    renderRows(d, fresh);
    if (newest) {
      var h = $('hero');
      h.classList.remove('flash');
      void h.offsetWidth;          // restart the animation
      h.classList.add('flash');
    }
    if (lastId === null || maxId > lastId) lastId = maxId;
    setStatus(d.db_ok ? 'online' : 'dboff');
  }

  function tick() {
    fetch('/api/logs', { cache: 'no-store' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) { apply(d, true); })
      .catch(function () { setStatus('lost'); })
      .then(function () { setTimeout(tick, 3000); });
  }

  apply(JSON.parse($('boot').textContent), false);
  setTimeout(tick, 3000);
})();
</script>
</body>
</html>
"""


@app.route("/")
def dashboard():
    return render_template_string(PAGE, boot=payload())


@app.route("/api/logs")
def api_logs():
    response = jsonify(payload())
    response.headers["Cache-Control"] = "no-store"
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)