#!/usr/bin/env python3
"""
WebTester-Kali — simple authorized website load tester for Kali Linux.
Stdlib only. No pip install needed.

Usage:
    python3 webtester.py
Then open in browser:
    http://127.0.0.1:8080

Safety rules baked in (cannot be bypassed from the GUI):
  - Ownership confirmation checkbox is REQUIRED before every test.
  - Every request carries an identifiable User-Agent with contact info.
  - Hard caps: max 500 concurrent users, max 2000 req/sec, max 600 sec.
  - No "unlimited" mode. No proxies, no header spoofing, no evasion.
  - 429 / 503 responses are reported as results, never evaded.
"""

import csv
import io
import json
import threading
import time
import urllib.request
import urllib.error
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HOST, PORT = "127.0.0.1", 8080
MAX_USERS = 500
MAX_RPS = 2000
MAX_DURATION = 600   # 10 minutes
MIN_DURATION = 5
UA = "WebTester-Kali/1.0 (authorized load test; contact yaseenahmad13579@gmail.com)"

state = {
    "running": False,
    "stop_event": None,
    "url": "",
    "users": 0,
    "rps": 0,
    "duration": 0,
    "started_at": 0.0,
    "sent": 0,
    "ok": 0,
    "errors": 0,
    "codes": {},
    "lat_sum": 0.0,
    "lat_n": 0,
    "lat_min": None,
    "lat_max": 0.0,
    "lat_samples": deque(maxlen=2000),
    "lock": threading.Lock(),
}


def do_request(url):
    t0 = time.time()
    code = 0
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read(65536)
            code = resp.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception:
        code = 0
    ms = (time.time() - t0) * 1000.0
    with state["lock"]:
        state["sent"] += 1
        if 200 <= code < 400:
            state["ok"] += 1
        else:
            state["errors"] += 1
        k = str(code)
        state["codes"][k] = state["codes"].get(k, 0) + 1
        state["lat_sum"] += ms
        state["lat_n"] += 1
        state["lat_max"] = max(state["lat_max"], ms)
        state["lat_min"] = ms if state["lat_min"] is None else min(state["lat_min"], ms)
        state["lat_samples"].append(ms)


def worker(url, per_worker_rps, end_time, stop_event):
    gap = 1.0 / per_worker_rps if per_worker_rps > 0 else 0
    while not stop_event.is_set() and time.time() < end_time:
        t0 = time.time()
        do_request(url)
        wait = gap - (time.time() - t0)
        if wait > 0 and stop_event.wait(wait):
            break


def run_engine(url, users, rps, duration):
    stop_event = threading.Event()
    end_time = time.time() + duration
    with state["lock"]:
        state["sent"] = 0
        state["ok"] = 0
        state["errors"] = 0
        state["codes"] = {}
        state["lat_sum"] = 0.0
        state["lat_n"] = 0
        state["lat_min"] = None
        state["lat_max"] = 0.0
        state["lat_samples"].clear()
        state["running"] = True
        state["stop_event"] = stop_event
        state["url"] = url
        state["users"] = users
        state["rps"] = rps
        state["duration"] = duration
        state["started_at"] = time.time()
    per = rps / users
    threads = [
        threading.Thread(target=worker, args=(url, per, end_time, stop_event), daemon=True)
        for _ in range(users)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with state["lock"]:
        state["running"] = False
        state["stop_event"] = None


def snapshot():
    with state["lock"]:
        samples = sorted(state["lat_samples"])
        avg = state["lat_sum"] / state["lat_n"] if state["lat_n"] else 0.0
        p95 = samples[int(len(samples) * 0.95)] if samples else 0.0
        elapsed = time.time() - state["started_at"] if state["started_at"] else 0.0
        return {
            "running": state["running"],
            "url": state["url"],
            "users": state["users"],
            "target_rps": state["rps"],
            "duration": state["duration"],
            "elapsed": round(elapsed, 1),
            "sent": state["sent"],
            "ok": state["ok"],
            "errors": state["errors"],
            "codes": dict(state["codes"]),
            "avg_ms": round(avg, 1),
            "p95_ms": round(p95, 1),
            "min_ms": round(state["lat_min"] or 0.0, 1),
            "max_ms": round(state["lat_max"], 1),
            "actual_rps": round(state["sent"] / elapsed, 1) if elapsed > 0 else 0.0,
        }

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WebTester-Kali</title>
<style>
  * { box-sizing: border-box; font-family: system-ui, sans-serif; }
  body { background: #0d1117; color: #e6edf3; margin: 0; padding: 24px; }
  .wrap { max-width: 760px; margin: 0 auto; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .sub { color: #8b949e; font-size: 13px; margin-bottom: 20px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 18px; margin-bottom: 16px; }
  label { display: block; font-size: 13px; color: #8b949e; margin: 12px 0 4px; }
  input[type=text], input[type=number] { width: 100%; padding: 10px; border-radius: 8px;
    border: 1px solid #30363d; background: #0d1117; color: #e6edf3; font-size: 15px; }
  .row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
  .check { display: flex; gap: 10px; align-items: flex-start; margin-top: 16px;
    background: #1c2b1c; border: 1px solid #2f6b2f; border-radius: 8px; padding: 12px; font-size: 14px; }
  .check input { margin-top: 3px; transform: scale(1.3); }
  .btns { display: flex; gap: 10px; margin-top: 16px; }
  button { flex: 1; padding: 12px; font-size: 16px; border: none; border-radius: 8px; cursor: pointer; }
  #startBtn { background: #238636; color: #fff; }
  #startBtn:disabled { background: #30363d; color: #8b949e; cursor: not-allowed; }
  #stopBtn { background: #da3633; color: #fff; }
  #stopBtn:disabled { background: #30363d; color: #8b949e; cursor: not-allowed; }
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
  .stat { background: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 10px; text-align: center; }
  .stat .v { font-size: 20px; font-weight: 700; }
  .stat .k { font-size: 11px; color: #8b949e; margin-top: 2px; }
  .ok { color: #3fb950; } .bad { color: #f85149; } .warn { color: #d29922; }
  #msg { min-height: 20px; font-size: 14px; margin-top: 10px; }
  #dl { display: inline-block; margin-top: 10px; color: #58a6ff; font-size: 14px; }
  .note { font-size: 12px; color: #8b949e; margin-top: 14px; line-height: 1.5; }
  code { background: #0d1117; padding: 2px 6px; border-radius: 4px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>WebTester-Kali</h1>
  <div class="sub">Authorized website load tester &mdash; runs on localhost only</div>

  <div class="card">
    <label>Website URL (http:// or https://)</label>
    <input type="text" id="url" placeholder="https://example.com">
    <div class="row">
      <div><label>Concurrent users (1&ndash;500)</label><input type="number" id="users" value="10" min="1" max="500"></div>
      <div><label>Target req/sec (1&ndash;2000)</label><input type="number" id="rps" value="20" min="1" max="2000"></div>
      <div><label>Duration sec (5&ndash;600)</label><input type="number" id="dur" value="60" min="5" max="600"></div>
    </div>
    <div class="check">
      <input type="checkbox" id="own">
      <span><b>Ownership confirm:</b> ye website meri hai ya mujhe is par load test karne ki ijazat hai. Bina ijazat kisi aur ki site par test <b>na</b> karein.</span>
    </div>
    <div class="btns">
      <button id="startBtn" onclick="startTest()">START TEST</button>
      <button id="stopBtn" onclick="stopTest()" disabled>STOP</button>
    </div>
    <div id="msg"></div>
  </div>

  <div class="card">
    <h3 style="margin:0 0 12px;font-size:15px">Live stats</h3>
    <div class="stats">
      <div class="stat"><div class="v" id="s_sent">0</div><div class="k">requests sent</div></div>
      <div class="stat"><div class="v ok" id="s_ok">0</div><div class="k">success (2xx/3xx)</div></div>
      <div class="stat"><div class="v bad" id="s_err">0</div><div class="k">failed</div></div>
      <div class="stat"><div class="v" id="s_rps">0</div><div class="k">actual req/sec</div></div>
      <div class="stat"><div class="v" id="s_avg">0</div><div class="k">avg ms</div></div>
      <div class="stat"><div class="v" id="s_p95">0</div><div class="k">p95 ms</div></div>
      <div class="stat"><div class="v" id="s_min">0</div><div class="k">min ms</div></div>
      <div class="stat"><div class="v" id="s_max">0</div><div class="k">max ms</div></div>
    </div>
    <div class="note" id="s_codes">status codes: &mdash;</div>
    <div class="note" id="s_time">idle</div>
    <a id="dl" href="/api/report">Download CSV report</a>
  </div>

  <div class="note">
    Safety: har request mein identifiable User-Agent jata hai. Max 500 users / 2000 req-sec / 10 min.
    Koi proxy, koi spoofing, koi "unlimited" mode nahi. 429/503 block hone par wahi result mein dikhega.
  </div>
</div>
<script>
let timer = null;
function msg(t, cls){ const m = document.getElementById('msg'); m.textContent = t; m.className = cls || ''; }
async function startTest(){
  const body = {
    url: document.getElementById('url').value.trim(),
    users: parseInt(document.getElementById('users').value),
    rps: parseInt(document.getElementById('rps').value),
    duration: parseInt(document.getElementById('dur').value),
    own: document.getElementById('own').checked
  };
  msg('Starting...', 'warn');
  const r = await fetch('/api/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  const j = await r.json();
  if(!r.ok){ msg('Error: ' + (j.error || r.status), 'bad'); return; }
  msg('Test running...', 'ok');
  document.getElementById('startBtn').disabled = true;
  document.getElementById('stopBtn').disabled = false;
  if(timer) clearInterval(timer);
  timer = setInterval(poll, 1000);
  poll();
}
async function stopTest(){
  await fetch('/api/stop', {method:'POST'});
  msg('Stopped.', 'warn');
}
async function poll(){
  const r = await fetch('/api/stats');
  const s = await r.json();
  document.getElementById('s_sent').textContent = s.sent;
  document.getElementById('s_ok').textContent = s.ok;
  document.getElementById('s_err').textContent = s.errors;
  document.getElementById('s_rps').textContent = s.actual_rps;
  document.getElementById('s_avg').textContent = s.avg_ms;
  document.getElementById('s_p95').textContent = s.p95_ms;
  document.getElementById('s_min').textContent = s.min_ms;
  document.getElementById('s_max').textContent = s.max_ms;
  document.getElementById('s_codes').textContent = 'status codes: ' +
    (Object.entries(s.codes).map(([k,v]) => k + ' x' + v).join(', ') || '—');
  document.getElementById('s_time').textContent = s.running
    ? ('running: ' + s.url + ' — ' + s.elapsed + 's / ' + s.duration + 's')
    : ('finished: ' + s.sent + ' requests in ' + s.elapsed + 's');
  if(!s.running){
    clearInterval(timer); timer = null;
    document.getElementById('startBtn').disabled = false;
    document.getElementById('stopBtn').disabled = true;
    msg('Test finished. CSV report ready below.', 'ok');
  }
}
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, ctype, body):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, "application/json", json.dumps(obj))

    def do_GET(self):
        if self.path == "/":
            self._send(200, "text/html; charset=utf-8", PAGE)
        elif self.path == "/api/stats":
            self._json(snapshot())
        elif self.path == "/api/report":
            s = snapshot()
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["metric", "value"])
            for k in ("url", "users", "target_rps", "duration", "elapsed", "sent",
                      "ok", "errors", "avg_ms", "p95_ms", "min_ms", "max_ms", "actual_rps"):
                w.writerow([k, s[k]])
            w.writerow([])
            w.writerow(["status_code", "count"])
            for code, n in sorted(s["codes"].items()):
                w.writerow([code, n])
            body = buf.getvalue().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition", 'attachment; filename="webtester-report.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/api/stop":
            with state["lock"]:
                ev = state["stop_event"]
            if ev:
                ev.set()
            self._json({"ok": True})
            return
        if self.path != "/api/start":
            self._json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._json({"error": "invalid JSON"}, 400)
            return

        if not data.get("own"):
            self._json({"error": "Pehle ownership confirm karo (checkbox tick karo)."}, 400)
            return
        url = str(data.get("url", "")).strip()
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.netloc:
            self._json({"error": "URL ghalat hai. http:// ya https:// se shuru hona chahiye."}, 400)
            return
        try:
            users = int(data.get("users", 0))
            rps = int(data.get("rps", 0))
            duration = int(data.get("duration", 0))
        except (TypeError, ValueError):
            self._json({"error": "users / req-sec / duration number mein do."}, 400)
            return
        if not (1 <= users <= MAX_USERS):
            self._json({"error": f"users 1 se {MAX_USERS} tak ho sakte hain."}, 400)
            return
        if not (1 <= rps <= MAX_RPS):
            self._json({"error": f"req/sec 1 se {MAX_RPS} tak ho sakta hai."}, 400)
            return
        if not (MIN_DURATION <= duration <= MAX_DURATION):
            self._json({"error": f"duration {MIN_DURATION} se {MAX_DURATION} sec tak."}, 400)
            return
        with state["lock"]:
            if state["running"]:
                self._json({"error": "Ek test pehle se chal raha hai. Pehle STOP dabao."}, 409)
                return
        threading.Thread(target=run_engine, args=(url, users, rps, duration), daemon=True).start()
        self._json({"ok": True})


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"WebTester-Kali running: http://{HOST}:{PORT}")
    print("Browser mein kholo, URL dalo, ownership tick karo, START dabao.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
