import requests
from flask import request, Response, abort
from urllib.parse import urlsplit, quote

# Image server does not allow you to embed its images directly
# Only these hosts allowed
ALLOWED_IMG_HOSTS = {
    "data.corpus-nummorum.eu",
    "picsum.photos",
    # CHANGE : other hosts should be automatically added
}

MAX_IMAGE_BYTES = 8 * 1024 * 1024
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 10

def register_image_proxy(flask_app):
    """"Registers a secure proxy route at /img_proxy."""
    @flask_app.get("/img_proxy")
    def img_proxy():
        url = request.args.get("url", "")
        if not url:
            abort(400, "missing url")

        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https"):
            abort(400, "invalid scheme")

        host = parsed.netloc.split("@")[-1].split(":")[0].lower()
        if host not in ALLOWED_IMG_HOSTS:
            abort(403, "host not allowed")

        try:
            r = requests.get(
                url, stream=True, allow_redirects=True,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
            )
        except requests.RequestException as e:
            abort(502, f"fetch error: {e}")

        if r.status_code != 200:
            abort(r.status_code)

        ct = (r.headers.get("Content-Type") or "").lower()
        if not ct.startswith("image/"):
            abort(415, "unsupported media type")

        data = b""
        total = 0
        for chunk in r.iter_content(64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_IMAGE_BYTES:
                abort(413, "image too large")
            data += chunk

        resp = Response(data, mimetype=ct or "image/jpeg")
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp

def proxify(url: str) -> str:
    """Generates a local proxy URL for an image"""
    return f"/img_proxy?url={quote(url, safe=':/%?&=')}"
