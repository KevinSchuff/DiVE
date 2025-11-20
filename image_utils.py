"""
This module handels interaction with image urls and merging images.
"""

import os, requests
import numpy as np
import cv2
from urllib.parse import urlparse, parse_qs, unquote
from flask import Response, request
from functools import lru_cache


ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 10

def _load_bytes_from_source(src: str) -> bytes:
    """
    Load raw bytes from source string

    Parameters
    ----------
    scr : str
        Source string corresponding to image url or relative path

    Returns
    -------
    bytes
        Raw file contents loaded from the source.

    Raises
    ------
    ValueError
        for img_proxy case if url does not contain url query parameter.
    """

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
def merge_side_by_side(front, back, w = 200, h = 200):
    """
    Merges two images side by side into a new png image.
    Loads images, resizes them to be the same width height and than merges them.
    Left side should come front image of a coin and right side from a back image of a coin.
    Also it caches function results.

    Parameters
    ----------
    front : str
        Source string for left side of merged image.
    back : str
        Source string for right side of merged image.
    w : int
        Target width for merged image. Default is set to 200(pixels).
    h : int
        Target height for merged image. Default is set to 200(pixels).

    Returns
    -------
    bytes
        PNG encoded merged image.

    Raises
    ------
    ValueError
        If input image couldnt be decoded or enoding of merged image failed.
    """

    # Load raw bytes
    front_bytes = _load_bytes_from_source(front)
    back_bytes = _load_bytes_from_source(back)

    # Decode into OpenCV images
    front_img_decoded = cv2.imdecode(np.frombuffer(front_bytes, np.uint8), cv2.IMREAD_COLOR)
    back_img_decoded = cv2.imdecode(np.frombuffer(back_bytes, np.uint8), cv2.IMREAD_COLOR)
    if front_img_decoded is None or back_img_decoded is None:
        raise ValueError("One of the images could not be decoded")

    # Direct resize to target size (may distort aspect ratio)
    front_img_resized = cv2.resize(front_img_decoded, (w, h), interpolation=cv2.INTER_AREA)
    back_img_resized = cv2.resize(back_img_decoded, (w, h), interpolation=cv2.INTER_AREA)

    # Left half from front, right half from back
    mid = w // 2
    left_half  = front_img_resized[:, :mid]
    right_half = back_img_resized[:, mid:w]
    merged = np.hstack((left_half, right_half))

    # Encode back to PNG
    ok, buf = cv2.imencode(".png", merged)
    if not ok:
        raise ValueError("Encoding merged image failed")

    return buf.tobytes()


def register_merge_route(flask_app):
    """
    Register /merge_split route in Flask app.
    Endpoint accepts GET requests with query parameters front, back, w, h.

    Parameters
    ----------
    flask_app : Flask
        Flask application instance, where the route will be registered.

    Returns
    -------
    None

    Raises
    ------
    None   
        This function itself does not raise expections, but created route may return HTTP 400 or 500 responses.
    """

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
