# Video Downloader

A small local web app. Paste a YouTube, Instagram or Facebook link, pick a quality (up to the highest the video offers) or an audio format (MP3, M4A, Opus, WAV, FLAC), and save the file. It is a simple interface on top of [yt-dlp](https://github.com/yt-dlp/yt-dlp).

## Run it

Requires Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in your browser.

## Notes

- **ffmpeg** merges video and audio streams and converts audio. If it is not installed on your system, the app uses the copy bundled by `imageio-ffmpeg`.
- **YouTube** may require a JavaScript runtime for yt-dlp. If fetching fails, install [Node.js](https://nodejs.org) 20+ or [Deno](https://deno.com), and run `pip install -U yt-dlp`. Keep yt-dlp updated, since sites change often.
- Downloads are written to `downloads/` and deleted after an hour.
- Single videos only. A playlist link, or a post with several videos, downloads the first video.
- **Instagram and Facebook:** public videos and reels often work as they are, but many posts need a logged-in session. Either save your browser cookies as `cookies.txt` in the project folder, or set the `COOKIES_FROM_BROWSER` environment variable to your browser (for example `firefox`). Never upload `cookies.txt` to GitHub (it is already in `.gitignore`), and be aware that heavy automated use with your own login can get an account flagged.
- The server listens on `127.0.0.1` only. Do not expose it to the public internet.

## Responsible use

Only download content you own, content under a license that allows it, or content you have permission to save. Downloading from YouTube, Instagram or Facebook can violate their Terms of Service, and you are responsible for how you use this tool.

