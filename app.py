"""Local video downloader: a small Flask UI on top of yt-dlp."""
import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

import yt_dlp
from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)
DOWNLOADS = Path(__file__).parent / "downloads"
DOWNLOADS.mkdir(exist_ok=True)
JOBS = {}


def find_ffmpeg():
    """Use system ffmpeg if present, otherwise the binary bundled by imageio-ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


FFMPEG = find_ffmpeg()
BASE = {"quiet": True, "no_warnings": True, "noplaylist": True, "playlist_items": "1"}
if FFMPEG:
    BASE["ffmpeg_location"] = FFMPEG

# Instagram and Facebook often need a logged-in session (optional, see README).
COOKIES = Path(__file__).parent / "cookies.txt"
if COOKIES.exists():
    BASE["cookiefile"] = str(COOKIES)
elif os.environ.get("COOKIES_FROM_BROWSER"):
    BASE["cookiesfrombrowser"] = (os.environ["COOKIES_FROM_BROWSER"],)


def clean(err):
    msg = re.sub(r"\x1b\[[0-9;]*m", "", str(err)).replace("ERROR: ", "")
    print(msg)  # full yt-dlp message, visible in the terminal
    if re.search(r"cookies|log ?in|sign in", msg, re.I):
        return ("This link needs a logged-in session. Add a cookies.txt file or set "
                "COOKIES_FROM_BROWSER (see the README), then try again.")
    return msg


def hook(job, p):
    j = JOBS[job]
    if p["status"] == "downloading":
        total = p.get("total_bytes") or p.get("total_bytes_estimate") or 0
        done = p.get("downloaded_bytes", 0)
        j.update(
            status="downloading",
            percent=round(done * 100 / total, 1) if total else 0,
            speed=(p.get("_speed_str") or "").strip(),
            eta=(p.get("_eta_str") or "").strip(),
        )
    elif p["status"] == "finished":
        j.update(status="processing", percent=100)


def build_opts(job, d):
    o = dict(
        BASE,
        outtmpl=str(DOWNLOADS / job / "%(title).120B.%(ext)s"),
        progress_hooks=[lambda p: hook(job, p)],
    )
    if d.get("kind") == "audio":
        o["format"] = "bestaudio/best"
        if FFMPEG:
            o["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": d.get("afmt", "mp3"),
                "preferredquality": str(d.get("abr", "192")),
            }]
    else:
        h = int(d.get("height") or 0)  # 0 means best available
        cap = f"[height<=?{h}]" if h else ""  # "?" keeps formats that report no height
        if FFMPEG:
            o["format"] = f"bv*{cap}+ba/b{cap}/b"
            o["merge_output_format"] = d.get("vfmt", "mp4")
            if d.get("vfmt", "mp4") == "mp4":
                o["format_sort"] = ["res", "ext:mp4:m4a"]  # prefer widely playable H.264/AAC
        else:
            o["format"] = f"b{cap}/b"  # no ffmpeg: single pre-merged file only
    return o


def run(job, url, opts):
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        files = [p for p in (DOWNLOADS / job).iterdir() if p.suffix not in (".part", ".ytdl")]
        best = max(files, key=lambda p: p.stat().st_size)
        JOBS[job].update(status="done", percent=100, file=best.name)
    except Exception as e:
        JOBS[job].update(status="error", error=clean(e))


def cleanup_loop():
    """Delete finished downloads after an hour."""
    while True:
        time.sleep(600)
        for d in DOWNLOADS.iterdir():
            if d.is_dir() and time.time() - d.stat().st_mtime > 3600:
                shutil.rmtree(d, ignore_errors=True)
                JOBS.pop(d.name, None)


@app.get("/")
def index():
    return render_template("index.html", has_ffmpeg=bool(FFMPEG))


@app.post("/api/info")
def info():
    url = ((request.get_json(silent=True) or {}).get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return jsonify(error="Paste a full link that starts with https://"), 400
    try:
        with yt_dlp.YoutubeDL(BASE) as ydl:
            d = ydl.extract_info(url, download=False)
    except Exception as e:
        return jsonify(error=clean(e)), 400
    if d.get("entries"):  # playlist or multi-video post: use the first video
        d = next(iter(d["entries"]), None)
        if not d:
            return jsonify(error="No video found at that link."), 400
    heights = sorted(
        {f["height"] for f in d.get("formats", []) if f.get("height") and f.get("vcodec") != "none"},
        reverse=True,
    )
    return jsonify(
        title=d.get("title"),
        channel=d.get("uploader"),
        duration=d.get("duration") or 0,
        thumbnail=d.get("thumbnail"),
        heights=heights,
    )


@app.post("/api/download")
def download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return jsonify(error="Paste a full link that starts with https://"), 400
    job = uuid.uuid4().hex
    JOBS[job] = {"status": "starting", "percent": 0, "speed": "", "eta": ""}
    threading.Thread(target=run, args=(job, url, build_opts(job, data)), daemon=True).start()
    return jsonify(job=job)


@app.get("/api/status/<job>")
def status(job):
    if job not in JOBS:
        return jsonify(error="Unknown download."), 404
    return jsonify(JOBS[job])


@app.get("/api/file/<job>")
def file(job):
    j = JOBS.get(job)
    if not j or j.get("status") != "done":
        return jsonify(error="File not ready."), 404
    return send_file(DOWNLOADS / job / j["file"], as_attachment=True)


threading.Thread(target=cleanup_loop, daemon=True).start()

if __name__ == "__main__":
    # Bound to localhost on purpose. Do not expose this app to the public internet.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
