"""Configuration for the Pexels Scraper. Everything can be set with an
environment variable; the defaults work out of the box.

    PORT              port the API listens on (default 8000)
    PEXELS_PROXY      proxy URL for every request, e.g. http://user:pass@host:port
                      (default: none — direct). Pexels' JSON answers home,
                      office and cloud server IPs alike, so you very likely
                      don't need this.
    PEXELS_CLIENT_ID  the public web client id the pexels.com site sends with
                      its own JSON calls (default: the current one). Only
                      change it if every call starts answering 401.
    PEXELS_WORKERS    parallel upstream calls inside one request (default 4;
                      a details call fetches the medium, its EXIF row and its
                      stats at once)

Everything else below is a plain constant with a working default — edit it
here if you need to.
"""
import os

PORT = int(os.environ.get("PORT", "8000"))

# Retry policy for transport errors and blocks (every request).
MAX_RETRIES = 3
RETRY_BACKOFF = 2          # seconds, multiplied by the attempt number

PEXELS_PROXY = os.environ.get("PEXELS_PROXY") or None
PEXELS_CLIENT_ID = os.environ.get("PEXELS_CLIENT_ID", "4faffa81915014bbd90c420f22898950")
PEXELS_WORKERS = int(os.environ.get("PEXELS_WORKERS", "4"))


def pexels_proxy():
    """The proxy for one curl session (None = direct)."""
    return os.environ.get("PEXELS_PROXY") or None
