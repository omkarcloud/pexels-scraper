"""Pexels transport: plain curl_cffi with browser-impersonated TLS against
the JSON the site's own Next.js client calls. No browser, no cookies, no
mint. Egress: the pod's own IP (config.pexels_proxy(), knob PEXELS_EXIT) —
every JSON surface answered 200 from the pod and from 2/2 datacenter and
2/2 US residential ports (pod probe 2026-11-03, table in config.py). A
retryable failure drops the thread's session, so the retry rides a fresh
exit when the knob points at a proxy.

The HTML pages are NOT used: the id-only /photo/<id>/ page is a Cloudflare
403 from the pod's own IP and from one exit in two, and /video/<id>/ is a
Cloudflare JS challenge on every tier — while www.pexels.com/<locale>/api/
v3/... is open everywhere with one static header,
`pexels-client-id` (the public web client id baked into the site's bundle;
without it the API answers 401 "Bad API credentials").

Surfaces (all GET, JSON:API-ish bodies; pexels/parsers.py reads them):

  * SEARCH   /api/v3/search/photos|videos?query&page&per_page=24&seo_tags=true
             + filters; /api/v3/search/users?query&page&per_page=24
             per_page is clamped to 24 and the site serves 20 pages at most
             per query (pagination.total_pages lies, saying 334)
  * MEDIUM   /api/v3/media/<id>?seo_tags=true, /media/<id>/details (EXIF /
             file / content safety), /media/<id>/stats (views / downloads /
             likes), /media/<id>/similar?page&per_page
  * USER     /api/v3/users/<id|slug>?preview_photos=4, /users/<id>/stats,
             /users/<id>/media/recent|popular?type&page&per_page,
             /api/v2/users/<id>/followers|followings?page&per_page,
             /api/v3/users?leaderboard=views|approved_uploads&span&hero
  * LISTS    /api/v2/collections, /api/v3/collections/<id> (+ /tags,
             /media), /api/v3/search/suggestions/<prefix>,
             /api/v3/search/trending?type&media_type&geo_code,
             /api/v3/challenges?page&per_page

Failure taxonomy (scraper_errors, mapped to HTTP by route_glue):
  PexelsUpstreamError  transport failure / 5xx / 401 (client id rotated) — retryable
  PexelsBlocked        403 / 429 / Cloudflare challenge where JSON was expected — retryable
  PexelsBadRequest     upstream 422 (its error_messages verbatim)          — never retried
  PexelsNotFound       404 "Medium / User / Collection Not Found"          — never retried
"""
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

# Allow direct execution (python pexels/fetch.py): flat imports resolve
# like under the server. Idempotent when imported normally.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import egress
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError
from pexels.refs import API_LOCALE_DEFAULT, SITE

IMPERSONATE = "chrome"
TIMEOUT = 30

_CHALLENGE_MARKERS = ("just a moment", "cf-chl", "challenge-platform", "attention required", "cf_chl_opt")


class PexelsUpstreamError(UpstreamError):
    """Transport failure, 5xx or a rotated client id (401) — retryable."""


class PexelsBlocked(PexelsUpstreamError, Blocked):
    """403 / 429 or a Cloudflare challenge page where JSON was expected — retryable."""


class PexelsBadRequest(BadRequest):
    """Upstream 422 — the site rejected a parameter; never retried."""


class PexelsNotFound(NotFound):
    """Medium / user / collection does not exist — never retried."""


# One session per thread (cheroot workers and our own small pool): a curl
# handle must not be shared across threads; the GETs are stateless so a
# thread-lifetime session with keep-alive is enough.
_local = threading.local()


def _session():
    sess = getattr(_local, "session", None)
    if sess is None:
        from curl_cffi import requests as curl_requests
        proxy = config.pexels_proxy()
        sess = curl_requests.Session(impersonate=IMPERSONATE)
        if proxy:
            sess.proxies = {"http": proxy, "https": proxy}
        sess.headers.update({
            "accept": "application/json, text/plain, */*",
            "accept-language": egress.accept_language(proxy),
            "content-type": "application/json",
            "pexels-client-id": config.PEXELS_CLIENT_ID,
            "x-client-type": "react",
            "referer": SITE + "/",
        })
        _local.session = sess
    return sess


def _drop_session():
    """Close the thread's session so a poisoned connection (or a refused
    exit) dies and the next call opens a fresh one."""
    sess = getattr(_local, "session", None)
    _local.session = None
    if sess is not None:
        try:
            sess.close()
        except Exception:
            pass


def _retrying(fn):
    """Run fn() under the shared retry policy (PexelsUpstreamError only;
    NotFound / BadRequest surface immediately)."""
    last = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            return fn()
        except PexelsUpstreamError as e:
            last = e
            _drop_session()
            if attempt < config.MAX_RETRIES:
                time.sleep(config.RETRY_BACKOFF * attempt)
    raise last


def _error_messages(resp):
    try:
        body = resp.json()
    except Exception:
        return None
    if isinstance(body, dict):
        messages = body.get("error_messages")
        if isinstance(messages, list) and messages:
            return "; ".join(str(m) for m in messages)
    return None


def _classify(resp, label):
    """Map an HTTP response to the error taxonomy; return the parsed JSON."""
    status = resp.status_code
    if status == 404:
        raise PexelsNotFound(_error_messages(resp) or f"{label} not found")
    if status == 422 or status == 400:
        raise PexelsBadRequest(_error_messages(resp) or f"HTTP {status} for {label}")
    if status in (401,):
        # the public client id was rotated: a fresh exit will not help, but
        # the retry costs nothing and the message names the cause
        raise PexelsUpstreamError(f"HTTP 401 for {label}: {_error_messages(resp) or 'bad API credentials'} "
                                  "(config.PEXELS_CLIENT_ID needs the site's current pexels-client-id)")
    if status in (403, 429):
        raise PexelsBlocked(f"HTTP {status} for {label}")
    if status != 200:
        raise PexelsUpstreamError(f"HTTP {status} for {label}")
    text = resp.text or ""
    try:
        return resp.json()
    except Exception:
        lowered = text[:4000].lower()
        if any(marker in lowered for marker in _CHALLENGE_MARKERS):
            raise PexelsBlocked(f"Cloudflare challenge for {label}")
        raise PexelsUpstreamError(f"non-JSON response for {label}: {text[:120]!r}")


def api_get(path, params=None, label=None, locale=API_LOCALE_DEFAULT):
    """GET www.pexels.com/<locale>/api/<path> -> parsed JSON (a dict)."""
    label = label or path
    url = f"{SITE}/{locale or API_LOCALE_DEFAULT}/api/{path.lstrip('/')}"
    clean = {k: v for k, v in (params or {}).items() if v is not None}

    def once():
        try:
            resp = _session().get(url, params=clean, timeout=TIMEOUT)
        except Exception as e:
            raise PexelsUpstreamError(f"request failed: {type(e).__name__}: {e}")
        payload = _classify(resp, label)
        if not isinstance(payload, (dict, list)):
            raise PexelsUpstreamError(f"unexpected payload shape for {label}")
        return payload
    return _retrying(once)


def fetch_many(calls):
    """Run several zero-arg fetches in parallel (each worker thread has its
    own session) and return their results in order; the first exception
    propagates. `calls` is a list of callables."""
    if len(calls) <= 1:
        return [call() for call in calls]
    with ThreadPoolExecutor(max_workers=min(len(calls), config.PEXELS_WORKERS)) as pool:
        futures = [pool.submit(call) for call in calls]
        return [f.result() for f in futures]


# ---- search -----------------------------------------------------------------------------


def fetch_search(mode, query, page=1, locale=API_LOCALE_DEFAULT, **filters):
    """api/v3/search/<photos|videos>: `filters` are the site's own API
    params (orientation, size, people_count, people_age, date_from,
    min_width / max_width / min_height / max_height, min_duration /
    max_duration, frame_rate, resolution_name, user_id). The UI's `color`
    swatch is not among them: the server ignores it, even on the site's own
    search page (2026-11-03)."""
    params = {"query": query, "page": page, "per_page": 24, "seo_tags": "true", **filters}
    return api_get(f"v3/search/{mode}", params, f"{mode} search", locale)


def fetch_users_search(query, page=1, per_page=24):
    return api_get("v3/search/users", {"query": query, "page": page, "per_page": per_page}, "users search")


def fetch_suggestions(prefix):
    # the prefix is a path segment: "mountain lake" / "a/b" / "c#d" must
    # travel percent-encoded (the site answers the encoded form, 2026-11-03)
    return api_get(f"v3/search/suggestions/{quote(prefix, safe='')}", None, "search suggestions")


def fetch_trending(kind="popular", media_type=None, geo_code=None, limit=50):
    params = {"type": kind, "limit": limit, "media_type": media_type, "geo_code": geo_code}
    return api_get("v3/search/trending", params, "trending searches")


# ---- media ------------------------------------------------------------------------------


def fetch_medium(medium_id, locale=API_LOCALE_DEFAULT):
    return api_get(f"v3/media/{medium_id}", {"seo_tags": "true"}, f"medium {medium_id}", locale)


def fetch_medium_details(medium_id):
    return api_get(f"v3/media/{medium_id}/details", None, f"medium {medium_id} details")


def fetch_medium_stats(medium_id):
    return api_get(f"v3/media/{medium_id}/stats", None, f"medium {medium_id} stats")


def fetch_similar(medium_id, page=1, per_page=24, locale=API_LOCALE_DEFAULT):
    return api_get(f"v3/media/{medium_id}/similar", {"page": page, "per_page": per_page, "seo_tags": "true"},
                   f"medium {medium_id} similar", locale)


# ---- users ------------------------------------------------------------------------------


def fetch_user(user_ref, preview_photos=4):
    """api/v3/users/<id|slug> — the site takes a numeric id, a slug
    (eberhardgross) or a slug-id (ffc-aarman-22995634)."""
    return api_get(f"v3/users/{user_ref}", {"preview_photos": preview_photos}, f"user {user_ref}")


def fetch_user_stats(user_id):
    return api_get(f"v3/users/{user_id}/stats", {"span": "all_time"}, f"user {user_id} stats")


def fetch_user_media(user_id, sort="recent", media_type=None, page=1, per_page=24, locale=API_LOCALE_DEFAULT):
    params = {"page": page, "per_page": per_page, "seo_tags": "true",
              "type": media_type if media_type in ("photos", "videos") else None}
    return api_get(f"v3/users/{user_id}/media/{sort}", params, f"user {user_id} media", locale)


def fetch_user_follows(user_id, direction="followers", page=1, per_page=24):
    """api/v2/users/<id>/followers | followings."""
    return api_get(f"v2/users/{user_id}/{direction}", {"page": page, "per_page": per_page},
                   f"user {user_id} {direction}")


def fetch_leaderboard(metric="views", span="all_time", heroes_only=None, page=1, per_page=24):
    params = {"leaderboard": metric, "span": span, "preview_photos": 4, "per_page": per_page, "page": page,
              "hero": "true" if heroes_only else None}
    return api_get("v3/users", params, "leaderboard")


# ---- collections / challenges -------------------------------------------------------


def fetch_collections(page=1, per_page=24):
    return api_get("v2/collections", {"page": page, "per_page": per_page}, "collections")


def fetch_collection(collection_id):
    return api_get(f"v3/collections/{collection_id}", None, f"collection {collection_id}")


def fetch_collection_tags(collection_id):
    return api_get(f"v3/collections/{collection_id}/tags", None, f"collection {collection_id} tags")


def fetch_collection_media(collection_id, page=1, per_page=24, locale=API_LOCALE_DEFAULT):
    return api_get(f"v3/collections/{collection_id}/media", {"page": page, "per_page": per_page, "seo_tags": "true"},
                   f"collection {collection_id} media", locale)


def fetch_challenges(page=1, per_page=24):
    return api_get("v3/challenges", {"page": page, "per_page": per_page}, "challenges")
