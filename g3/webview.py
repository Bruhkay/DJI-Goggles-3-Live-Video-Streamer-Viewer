"""Built-in viewer for phones, tablets and other computers on the same network.

Serves a small web page and an MJPEG stream (works in every browser, needs
no app, and OBS can use it as a Media Source too).
"""
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>%(title)s</title>
<style>
 :root{color-scheme:dark}
 html,body{margin:0;height:100%%;background:#07080a;color:#e6e9ef;font:15px -apple-system,system-ui,Segoe UI,Roboto,sans-serif}
 #v{position:fixed;inset:0;width:100%%;height:100%%;object-fit:contain;background:#000}
 #bar{position:fixed;left:12px;top:12px;display:flex;gap:8px;align-items:center;padding:6px 12px;border-radius:999px;
      background:rgba(15,17,22,.72);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);transition:opacity .4s}
 #dot{width:9px;height:9px;border-radius:50%%;background:#8a93a3}
 .live #dot{background:#ff3b30;box-shadow:0 0 10px #ff3b30}
 #fs{position:fixed;right:12px;top:12px;border:0;color:#e6e9ef;background:rgba(15,17,22,.72);border-radius:999px;padding:7px 14px;font:inherit}
 .idle #bar,.idle #fs{opacity:0}
</style></head>
<body><img id="v" alt="">
<div id="bar"><div id="dot"></div><b>%(title)s</b><span id="st"></span></div>
<button id="fs">⛶</button>
<script>
const v=document.getElementById('v'),st=document.getElementById('st');
function start(){v.src='stream.mjpg?'+Date.now()}
v.onerror=()=>{document.body.classList.remove('live');st.textContent=' · %(reconnecting)s';setTimeout(start,1500)};
v.onload=()=>{document.body.classList.add('live');st.textContent=''};
start();
document.getElementById('fs').onclick=()=>{const e=document.documentElement;(e.requestFullscreen||e.webkitRequestFullscreen||(()=>{})).call(e)};
let t;function wake(){document.body.classList.remove('idle');clearTimeout(t);t=setTimeout(()=>document.body.classList.add('idle'),3000)}
['mousemove','touchstart'].forEach(e=>addEventListener(e,wake));wake();
setInterval(async()=>{try{const s=await (await fetch('status.json',{cache:'no-store'})).json();
 if(s.live)document.body.classList.add('live')}catch(e){}},3000);
</script></body></html>"""


def lan_addresses():
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))          # no packet is sent; picks the outgoing interface
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    return ips or ["127.0.0.1"]


class WebViewer(object):
    def __init__(self, port=8090, title="SkyFeed Studio", reconnecting="reconnecting…"):
        self.port = port
        self.title = title
        self.reconnecting = reconnecting
        self.jpeg = None
        self.seq = 0
        self.cond = threading.Condition()
        self.clients = 0
        self.httpd = None
        self.status = {}
        self.fps_limit = 30
        self.error = ""

    # -- producer side
    def wants_frame(self):
        return self.clients > 0

    def publish(self, jpeg):
        with self.cond:
            self.jpeg = jpeg
            self.seq += 1
            self.cond.notify_all()

    # -- server
    def start(self):
        viewer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _send(self, code, ctype, body):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = self.path.split("?")[0]
                if path in ("/", "/index.html"):
                    body = (PAGE % {"title": viewer.title, "reconnecting": viewer.reconnecting}).encode("utf-8")
                    return self._send(200, "text/html; charset=utf-8", body)
                if path == "/status.json":
                    return self._send(200, "application/json", json.dumps(viewer.status).encode())
                if path == "/snapshot.jpg":
                    with viewer.cond:
                        if viewer.jpeg is None:
                            viewer.cond.wait(2.0)
                        j = viewer.jpeg
                    return self._send(200, "image/jpeg", j) if j else self._send(503, "text/plain", b"no video")
                if path == "/stream.mjpg":
                    return self._stream()
                return self._send(404, "text/plain", b"not found")

            def _stream(self):
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                viewer.clients += 1
                last = -1
                try:
                    while True:
                        with viewer.cond:
                            if viewer.seq == last:
                                viewer.cond.wait(5.0)
                            j, last = viewer.jpeg, viewer.seq
                        if j is None:
                            continue
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                         + str(len(j)).encode() + b"\r\n\r\n" + j + b"\r\n")
                except (OSError, ValueError):
                    pass
                finally:
                    viewer.clients -= 1

        try:
            self.httpd = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        except OSError as e:
            self.error = str(e)
            return False
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="webviewer").start()
        self.error = ""
        return True

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        with self.cond:
            self.cond.notify_all()

    def urls(self):
        return ["http://%s:%d/" % (ip, self.port) for ip in lan_addresses()]
