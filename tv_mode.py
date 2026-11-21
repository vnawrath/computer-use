"""
TV mode: a remote-control page for very old browsers (smart TVs etc.).

No WebSockets, no canvas, no modern JS. The screen is a periodically
refreshed JPEG inside <input type="image">, so a click submits the
x/y position as a plain form post (works in pre-JavaScript browsers).

Routes (all under /tv):
  GET  /tv              control page (login form if not authenticated)
  POST /tv/login        exchange API_KEY for a session cookie
  GET  /tv/logout       clear the cookie
  GET  /tv/frame.jpg    current screenshot as JPEG (?w=<width>)
  POST /tv/act          click / key / type, then redirect back to /tv
  GET  /tv/tv.js        tiny ES3 refresh script (kept external for the CSP)
  GET  /tv/tv.css       stylesheet
"""

import hashlib
import hmac
import io
import os
import shutil
import subprocess
import threading
import time
from urllib.parse import urlencode

from flask import Response, make_response, redirect, request
from markupsafe import escape
from PIL import Image

COOKIE_NAME = "tv_session"
WIDTHS = [640, 800, 960, 1024, 1280]
DEFAULT_WIDTH = 960
REFRESH_MS = int(os.environ.get("TV_REFRESH_MS", "1500"))
JPEG_QUALITY = int(os.environ.get("TV_JPEG_QUALITY", "60"))
FRAME_CACHE_SECONDS = 0.4
MJPEG_FPS = int(os.environ.get("TV_MJPEG_FPS", "10"))
MJPEG_QUALITY = int(os.environ.get("TV_MJPEG_QUALITY", "6"))
LIVE_FPS = int(os.environ.get("TV_LIVE_FPS", "15"))
LIVE_BITRATE = os.environ.get("TV_LIVE_BITRATE", "2500k")
AUDIO_SOURCE = os.environ.get("TV_AUDIO_SOURCE", "tv.monitor")

MODES = [
    ("click", "Click"),
    ("double", "Double"),
    ("right", "Right"),
    ("move", "Move"),
    ("scrollup", "Scroll up"),
    ("scrolldown", "Scroll down"),
]
MODE_IDS = {m for m, _ in MODES}

# Submit-button label -> key / hotkey sent to the desktop
KEYS = [
    ("Esc", ["esc"]),
    ("Tab", ["tab"]),
    ("Enter", ["enter"]),
    ("Bksp", ["backspace"]),
    ("Left", ["left"]),
    ("Up", ["up"]),
    ("Down", ["down"]),
    ("Right", ["right"]),
    ("PgUp", ["pageup"]),
    ("PgDn", ["pagedown"]),
    ("Alt+Tab", ["alt", "tab"]),
    ("Ctrl+L", ["ctrl", "l"]),
]
KEY_MAP = dict(KEYS)

JS = """(function () {
  var img = document.getElementById('screen');
  if (!img) { return; }
  var base = img.getAttribute('data-src');
  var delay = parseInt(img.getAttribute('data-ms'), 10) || 1500;
  function next() {
    setTimeout(function () {
      img.src = base + '&t=' + (new Date()).getTime();
    }, delay);
  }
  img.onload = next;
  img.onerror = function () { setTimeout(next, 3000); };
  if (img.complete) { next(); }
})();
"""

LIVE_JS = """(function () {
  var img = document.getElementById('live');
  var snd = document.getElementById('snd');
  function later(fn, ms) { setTimeout(fn, ms); }
  if (img) {
    img.onerror = function () {
      later(function () { img.src = '/tv/mjpeg?t=' + (new Date()).getTime(); }, 2000);
    };
  }
  if (snd && snd.addEventListener) {
    var restart = function () {
      later(function () {
        snd.src = '/tv/audio.mp3?t=' + (new Date()).getTime();
        try { snd.play(); } catch (e) {}
      }, 2000);
    };
    snd.addEventListener('error', restart, false);
    snd.addEventListener('ended', restart, false);
  }
})();
"""

CSS = """body { background: #111; color: #eee; font-family: sans-serif; margin: 4px; }
form { margin: 0; }
.screen { display: block; border: 0; margin: 0 0 4px 0; }
.bar { margin: 3px 0; }
.bar a, .bar input { font-size: 16px; padding: 4px 8px; margin: 1px; }
.bar a { color: #eee; background: #333; text-decoration: none; border: 1px solid #555; }
.bar a.on { background: #36c; border-color: #69f; }
.text { width: 320px; }
.msg { color: #9c9; font-size: 14px; }
.err { color: #f88; }
body.livebody { margin: 0; background: #000; overflow: hidden; }
.live { display: block; width: 100%; height: 100%; height: 100vh; background: #000; object-fit: contain; }
.snd { position: absolute; left: 8px; bottom: 8px; opacity: 0.6; }
.audiobar { height: 40px; font-size: 14px; }
.audiobar a { color: #9cf; }
.ctl { width: 100%; height: 650px; height: calc(100vh - 52px); border: 0; }
"""


def register_tv(app, limiter, api_key):
    frame_lock = threading.Lock()
    frame_cache = {"t": 0.0, "img": None}
    session_token = (
        hmac.new(api_key.encode(), b"tv-session", hashlib.sha256).hexdigest()
        if api_key
        else None
    )
    has_xdotool = shutil.which("xdotool") is not None

    # ---------- helpers ----------

    def authed():
        if not api_key:
            return True
        value = request.cookies.get(COOKIE_NAME, "")
        return hmac.compare_digest(value, session_token)

    def get_width():
        try:
            w = int(request.values.get("w", DEFAULT_WIDTH))
        except ValueError:
            w = DEFAULT_WIDTH
        return w if w in WIDTHS else DEFAULT_WIDTH

    def get_mode():
        m = request.values.get("mode", "click")
        return m if m in MODE_IDS else "click"

    def page_url(w, mode, msg=None):
        params = {"w": w, "mode": mode}
        if msg:
            params["msg"] = msg
        return "/tv/control?" + urlencode(params)

    def grab_screen():
        """Return a PIL image of the screen, cached briefly so viewers share captures."""
        with frame_lock:
            now = time.time()
            if frame_cache["img"] is not None and now - frame_cache["t"] < FRAME_CACHE_SECONDS:
                return frame_cache["img"]
            path = "/tmp/tv_frame.png"
            subprocess.run(["scrot", "-o", path], capture_output=True, timeout=10, check=True)
            with Image.open(path) as im:
                img = im.convert("RGB")
            frame_cache["img"] = img
            frame_cache["t"] = now
            return img

    def screen_size():
        import pyautogui

        return pyautogui.size()

    def html_page(body, refresh_fallback=False, body_class=""):
        head_extra = ""
        if refresh_fallback:
            # Browsers without JS reload the whole page instead.
            head_extra = '<noscript><meta http-equiv="refresh" content="5"></noscript>'
        html = (
            "<!DOCTYPE html>\n<html><head>"
            '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
            "<title>TV desktop</title>"
            '<link rel="stylesheet" href="/tv/tv.css">'
            f'{head_extra}</head><body class="{body_class}">{body}</body></html>'
        )
        resp = make_response(html)
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # ---------- routes ----------

    @limiter.exempt
    def tv_page():
        if not authed():
            err = request.args.get("err")
            body = (
                "<h2>Desktop login</h2>"
                + ('<p class="err">Wrong key.</p>' if err else "")
                + '<form method="post" action="/tv/login" accept-charset="utf-8">'
                '<input type="password" name="key" size="30"> '
                '<input type="submit" value="Log in"></form>'
            )
            return html_page(body)

        # Live view: one H.264 + AAC stream in a plain <video>. Control happens via the API.
        body = (
            '<img id="live" class="live" src="/tv/mjpeg" alt="">'
            '<div class="snd"><audio id="snd" src="/tv/audio.mp3" autoplay controls preload="none"></audio></div>'
            '<script type="text/javascript" src="/tv/live.js"></script>'
        )
        return html_page(body, body_class="livebody")

    @limiter.exempt
    def tv_control():
        if not authed():
            return html_page('<a href="/tv" target="_top">Log in</a>')

        w = get_width()
        mode = get_mode()
        msg = request.args.get("msg", "")
        try:
            sw, sh = screen_size()
            h = int(round(w * sh / float(sw)))
        except Exception:
            h = int(round(w * 10 / 16.0))
        src = f"/tv/frame.jpg?w={w}"

        modes = " ".join(
            f'<a href="{escape(page_url(w, m))}" class="{"on" if m == mode else ""}">{label}</a>'
            for m, label in MODES
        )
        sizes = " ".join(
            f'<a href="{escape(page_url(x, mode))}" class="{"on" if x == w else ""}">{x}</a>'
            for x in WIDTHS
        )
        keys = " ".join(
            f'<input type="submit" name="key" value="{escape(label)}">' for label, _ in KEYS
        )
        hidden = (
            f'<input type="hidden" name="w" value="{w}">'
            f'<input type="hidden" name="mode" value="{mode}">'
        )
        body = (
            '<form method="post" action="/tv/act" accept-charset="utf-8">'
            + hidden
            + f'<input type="image" name="c" id="screen" class="screen" src="{src}&t={int(time.time() * 1000)}" '
            f'data-src="{src}" data-ms="{REFRESH_MS}" width="{w}" height="{h}" alt="screen">'
            "</form>"
            f'<div class="bar">Tap mode: {modes}</div>'
            '<form method="post" action="/tv/act" accept-charset="utf-8"><div class="bar">'
            + hidden
            + keys
            + "</div><div class=\"bar\">"
            '<input type="text" name="text" class="text"> '
            '<input type="submit" name="send" value="Type"> '
            '<input type="submit" name="send" value="Type+Enter">'
            "</div></form>"
            f'<div class="bar">Size: {sizes} &nbsp; <a href="/tv/logout" target="_top">Log out</a></div>'
            + (f'<div class="msg">{escape(msg)}</div>' if msg else "")
            + '<script type="text/javascript" src="/tv/tv.js"></script>'
        )
        return html_page(body, refresh_fallback=True)

    @limiter.limit("10 per minute", override_defaults=True)
    def tv_login():
        key = request.form.get("key", "")
        if api_key and not hmac.compare_digest(key, api_key):
            return redirect("/tv?err=1", code=302)
        resp = redirect("/tv", code=302)
        if session_token:
            resp.set_cookie(
                COOKIE_NAME,
                session_token,
                max_age=60 * 60 * 24 * 365,
                httponly=True,
                samesite="Lax",
                path="/tv",
            )
        return resp

    @limiter.exempt
    def tv_logout():
        resp = redirect("/tv", code=302)
        resp.set_cookie(COOKIE_NAME, "", expires=0, path="/tv")
        return resp

    @limiter.exempt
    def tv_frame():
        if not authed():
            return Response("Unauthorized", status=403)
        w = get_width()
        try:
            img = grab_screen()
        except Exception as e:
            return Response(f"Screenshot failed: {e}", status=500)
        if img.width != w:
            h = int(round(w * img.height / float(img.width)))
            img = img.resize((w, h), Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        resp = Response(buf.getvalue(), mimetype="image/jpeg")
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    @limiter.exempt
    def tv_act():
        if not authed():
            return redirect("/tv", code=302)
        import pyautogui

        w = get_width()
        mode = get_mode()
        msg = ""
        try:
            if "c.x" in request.form:
                sw, sh = screen_size()
                scale = sw / float(w)
                x = min(sw - 1, max(0, int(int(request.form["c.x"]) * scale)))
                y = min(sh - 1, max(0, int(int(request.form["c.y"]) * scale)))
                if mode == "click":
                    pyautogui.click(x, y)
                elif mode == "double":
                    pyautogui.doubleClick(x, y)
                elif mode == "right":
                    pyautogui.rightClick(x, y)
                elif mode == "move":
                    pyautogui.moveTo(x, y)
                elif mode == "scrollup":
                    pyautogui.moveTo(x, y)
                    pyautogui.scroll(5)
                elif mode == "scrolldown":
                    pyautogui.moveTo(x, y)
                    pyautogui.scroll(-5)
                msg = f"{mode} at {x},{y}"
            elif request.form.get("key") in KEY_MAP:
                keys = KEY_MAP[request.form["key"]]
                if len(keys) == 1:
                    pyautogui.press(keys[0])
                else:
                    pyautogui.hotkey(*keys)
                msg = "key " + request.form["key"]
            elif "send" in request.form:
                text = request.form.get("text", "")
                if text:
                    if has_xdotool:
                        # xdotool handles non-ASCII (e.g. Czech) characters
                        subprocess.run(
                            ["xdotool", "type", "--delay", "15", "--", text],
                            timeout=60,
                            check=True,
                        )
                    else:
                        pyautogui.write(text)
                if "Enter" in request.form["send"]:
                    pyautogui.press("enter")
                msg = "typed"
        except Exception as e:
            msg = f"error: {e}"
        # Give the desktop a moment to react so the next frame shows the result
        time.sleep(0.3)
        return redirect(page_url(w, mode, msg), code=302)

    @limiter.exempt
    def tv_audio():
        if not authed():
            return Response("Unauthorized", status=403)
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-fflags", "nobuffer", "-f", "pulse", "-fragment_size", "2048",
            "-i", AUDIO_SOURCE, "-ac", "2", "-ar", "44100",
            "-c:a", "libmp3lame", "-b:a", "128k", "-flush_packets", "1", "-f", "mp3", "-",
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

        def generate():
            try:
                while True:
                    chunk = proc.stdout.read(4096)
                    if not chunk:
                        break
                    yield chunk
            finally:
                proc.kill()
                proc.wait()

        resp = Response(generate(), mimetype="audio/mpeg", direct_passthrough=True)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @limiter.exempt
    def tv_live():
        if not authed():
            return Response("Unauthorized", status=403)
        try:
            sw, sh = screen_size()
        except Exception:
            sw, sh = 1280, 800
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-thread_queue_size", "512", "-f", "x11grab", "-framerate", str(LIVE_FPS),
            "-video_size", f"{sw}x{sh}", "-draw_mouse", "1", "-i", os.environ.get("DISPLAY", ":0"),
            "-thread_queue_size", "512", "-f", "pulse", "-i", AUDIO_SOURCE,
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-profile:v", "baseline", "-pix_fmt", "yuv420p",
            "-g", str(LIVE_FPS * 2), "-b:v", LIVE_BITRATE, "-maxrate", LIVE_BITRATE, "-bufsize", LIVE_BITRATE,
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-f", "mp4", "-movflags", "frag_keyframe+empty_moov+default_base_moof",
            "-frag_duration", "500000", "-",
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

        def generate():
            try:
                while True:
                    chunk = proc.stdout.read(16384)
                    if not chunk:
                        break
                    yield chunk
            finally:
                proc.kill()
                proc.wait()

        resp = Response(generate(), mimetype="video/mp4", direct_passthrough=True)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @limiter.exempt
    def tv_mjpeg():
        if not authed():
            return Response("Unauthorized", status=403)
        try:
            sw, sh = screen_size()
        except Exception:
            sw, sh = 1280, 800
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "x11grab", "-framerate", str(MJPEG_FPS), "-video_size", f"{sw}x{sh}",
            "-draw_mouse", "1", "-i", os.environ.get("DISPLAY", ":0"),
            "-c:v", "mjpeg", "-q:v", str(MJPEG_QUALITY), "-pix_fmt", "yuvj420p",
            "-f", "mpjpeg", "-boundary_tag", "frame", "-",
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

        def generate():
            try:
                while True:
                    chunk = proc.stdout.read(16384)
                    if not chunk:
                        break
                    yield chunk
            finally:
                proc.kill()
                proc.wait()

        resp = Response(
            generate(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
            direct_passthrough=True,
        )
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @limiter.exempt
    def tv_live_js():
        resp = Response(LIVE_JS, mimetype="text/javascript")
        resp.headers["Cache-Control"] = "max-age=60"
        return resp

    @limiter.exempt
    def tv_js():
        resp = Response(JS, mimetype="text/javascript")
        resp.headers["Cache-Control"] = "max-age=3600"
        return resp

    @limiter.exempt
    def tv_css():
        resp = Response(CSS, mimetype="text/css")
        resp.headers["Cache-Control"] = "max-age=3600"
        return resp

    app.add_url_rule("/tv", "tv_page", tv_page, methods=["GET"])
    app.add_url_rule("/tv/control", "tv_control", tv_control, methods=["GET"])
    app.add_url_rule("/tv/live.mp4", "tv_live", tv_live, methods=["GET"])
    app.add_url_rule("/tv/mjpeg", "tv_mjpeg", tv_mjpeg, methods=["GET"])
    app.add_url_rule("/tv/live.js", "tv_live_js", tv_live_js, methods=["GET"])
    app.add_url_rule("/tv/audio.mp3", "tv_audio", tv_audio, methods=["GET"])
    app.add_url_rule("/tv/login", "tv_login", tv_login, methods=["POST"])
    app.add_url_rule("/tv/logout", "tv_logout", tv_logout, methods=["GET"])
    app.add_url_rule("/tv/frame.jpg", "tv_frame", tv_frame, methods=["GET"])
    app.add_url_rule("/tv/act", "tv_act", tv_act, methods=["POST"])
    app.add_url_rule("/tv/tv.js", "tv_js", tv_js, methods=["GET"])
    app.add_url_rule("/tv/tv.css", "tv_css", tv_css, methods=["GET"])
