"""
This module provides image proxy endpoint. The /img_proxy route fetches remote images for the client to work around CORS restrictions.
"""

import requests
from flask import request, Response, abort
from urllib.parse import urlsplit, quote


# Whitelist hosts
ALLOWED_IMG_HOSTS = None
# max image size 8 MB
MAX_IMAGE_BYTES = 8 * 1024 * 1024
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 10

def register_image_proxy(flask_app):
    """
    Registers a secure proxy route at /img_proxy in Flask app.
    Endpoint accepts GET requests with query parameters url.
    Fetches the remote image, downloads it and serves it to the client making the request.

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
        This function itself does not raise expections, but created route may return HTTP 4xx or 5xx responses.
    """

    @flask_app.get("/img_proxy")
    def img_proxy():
        url = request.args.get("url", "")
        if not url:
            abort(400, "missing url")
        # allow only http(s) urls
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https"):
            abort(400, "invalid scheme")
        # extract hostname
        host = parsed.netloc.split("@")[-1].split(":")[0].lower()
        if ALLOWED_IMG_HOSTS is not None and host not in ALLOWED_IMG_HOSTS:
            abort(403, "host not allowed")

        try:
            # get img request
            r = requests.get(
                url, stream=True, allow_redirects=True,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
            )
        except requests.RequestException as e:
            abort(502, f"fetch error: {e}")

        # only continue if request worked
        if r.status_code != 200:
            abort(r.status_code)

        # make sure it is an image
        ct = (r.headers.get("Content-Type") or "").lower()
        if not ct.startswith("image/"):
            abort(415, "unsupported media type")

        # read image date in chucks (avoids large memory use) 
        data = b""
        total = 0
        for chunk in r.iter_content(64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_IMAGE_BYTES:     # max 8 MP pictures
                abort(413, "image too large")
            data += chunk

        resp = Response(data, mimetype=ct or "image/jpeg")
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp


def proxify(url):
    """
    Generates a local proxy URL for an image.

    Parameters
    ----------
    url : str
        Original remote image URL.

    Returns
    -------
    str
        URL pointing to the local proxy endpoint.
    """

    return f"/img_proxy?url={quote(url, safe=':/%?&=')}"
