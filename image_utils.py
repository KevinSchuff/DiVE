import io, os, requests
import numpy as np
import cv2
from urllib.parse import urlparse, parse_qs, unquote
from flask import Response, request
from functools import lru_cache
from proxy import proxify
import re

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 10

# check if string looks like url
def is_url(s: str) -> bool:
    return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9+.\-]*://', s)) or s.startswith("data:")

# normalizes file path string
def norm_path(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")

def bg_url_from_csv_value(raw_val: str):
    if not raw_val:
        return None
    s = str(raw_val).strip()
    if not s:
        return None
    if is_url(s):
        return proxify(s)               # external URL through Proxy
    return "/assets/" + norm_path(s)    # relative paths in assets


def _load_bytes_from_source(src: str) -> bytes:
    """Load raw bytes from assets, /img_proxy?url=..., or http(s)."""
    if not src:
        raise ValueError("empty source")

    if src.startswith("/assets/"):
        rel = src[len("/assets/"):]
        path = os.path.join(ASSETS_DIR, rel)
        with open(path, "rb") as f:
            return f.read()

    # /img_proxy?url=... for merged images served through proxy
    if src.startswith("/img_proxy"):
        parsed = urlparse(src)
        qs = parse_qs(parsed.query)
        real = unquote(qs.get("url", [""])[0])
        if not real:
            raise ValueError("img_proxy missing url param")
        r = requests.get(real, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        r.raise_for_status()
        return r.content

    # http(s)://...
    if src.startswith("http://") or src.startswith("https://"):
        r = requests.get(src, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        r.raise_for_status()
        return r.content

    # Fallback: treat as assets-relative path
    return _load_bytes_from_source("/assets/" + src.lstrip("./").replace("\\", "/"))


# identical merge urls only get calculated once
@lru_cache(maxsize=1024)
def merge_side_by_side(front: str, back: str, w: int = 200, h: int = 200) -> bytes:
    """Return merged image: left half from front + right half from back (stretched to w×h)."""

    # Load raw bytes
    fb = _load_bytes_from_source(front)
    bb = _load_bytes_from_source(back)

    # Decode into OpenCV images
    fimg = cv2.imdecode(np.frombuffer(fb, np.uint8), cv2.IMREAD_COLOR)
    bimg = cv2.imdecode(np.frombuffer(bb, np.uint8), cv2.IMREAD_COLOR)
    if fimg is None or bimg is None:
        raise ValueError("One of the images could not be decoded")

    # Direct resize to target size (may distort aspect ratio)
    f_resized = cv2.resize(fimg, (w, h), interpolation=cv2.INTER_AREA)
    b_resized = cv2.resize(bimg, (w, h), interpolation=cv2.INTER_AREA)

    # Left half from front, right half from back
    mid = w // 2
    left_half  = f_resized[:, :mid]
    right_half = b_resized[:, mid:w]
    merged = np.hstack((left_half, right_half))

    # Encode back to PNG
    ok, buf = cv2.imencode(".png", merged)
    if not ok:
        raise ValueError("Encoding merged image failed")

    return buf.tobytes()




def register_merge_route(flask_app):
    """Register /merge_split route in Flask app."""
    @flask_app.get("/merge_split")
    def merge_split_route():
        front = request.args.get("front") or ""
        back  = request.args.get("back") or ""
        w     = request.args.get("w", type=int) or 200
        h     = request.args.get("h", type=int) or 200
        if not front or not back:
            return Response("missing front/back", status=400)
        try:
            data = merge_side_by_side(front, back, w, h)
            resp = Response(data, mimetype="image/png")
            resp.headers["Cache-Control"] = "public, max-age=86400"
            return resp
        except Exception as e:
            return Response(f"merge error: {e}", status=500)
