"""Reference resolvers, site links and the filter vocabularies for /pexels/*.

ONE param per input (tripadvisor QueryOrIdField convention, never a sibling
`url`/`id` pair). Resolvers raise ValueError with a user-facing message
(schema_fields.RefField turns it into a 400):

    photo / video   a numeric media id (691668) OR any pexels.com photo /
                    video link — canonical (/photo/<slug>-<id>/), id-only
                    (/photo/<id>/), localized (/de-de/foto/<slug>-<id>/),
                    a download link (/download/video/<id>/) or an
                    images.pexels.com / videos.pexels.com file link
    user            a numeric user id (121938), a handle (@eberhardgross),
                    a profile slug (eberhardgross, ffc-aarman-22995634) OR
                    a pexels.com profile link (/@eberhardgross/...)
    collection      a 7-character collection id (cwgidat), its slug
                    (mighty-mountains-cwgidat) OR a /collections/<slug>/ link

Photos and videos share one id space on pexels.com (api/v3/media/<id>
answers either), so the two resolvers are the same function; the endpoint
checks the record's type and 404s a video id sent to /photos/* and vice
versa (pexels/api.py).

The filter vocabularies are the site's own search filter options, read from
its Next.js bundle (_app-*.js, 2026-11-03) and confirmed against the
api/v3/search 422 messages, which list the accepted values.
"""
import re
from urllib.parse import urlparse

SITE = "https://www.pexels.com"
API_LOCALE_DEFAULT = "en-us"

# The 28 UI locales pexels.com serves (the site's `locales` list, read from
# __NEXT_DATA__ 2026-11-03). The API takes them lower-cased as a path prefix
# (/de-de/api/v3/...) and localizes titles, tags and slugs.
LOCALES = (
    "en-US", "pt-BR", "es-ES", "ca-ES", "de-DE", "it-IT", "fr-FR", "sv-SE", "id-ID",
    "pl-PL", "ja-JP", "zh-TW", "zh-CN", "ko-KR", "th-TH", "nl-NL", "hu-HU", "vi-VN",
    "cs-CZ", "da-DK", "fi-FI", "uk-UA", "el-GR", "ro-RO", "nb-NO", "sk-SK", "tr-TR", "ru-RU",
)
_LOCALE_BY_LOWER = {loc.lower(): loc for loc in LOCALES}
_LOCALE_BY_LANG = {}
for _loc in LOCALES:
    _LOCALE_BY_LANG.setdefault(_loc.split("-")[0].lower(), _loc)


def resolve_locale(value):
    """"de-DE" / "de-de" / "de" / "zh_TW" -> the API path prefix ("de-de").
    Unknown -> ValueError listing the accepted locales."""
    value = (value or "").strip().replace("_", "-")
    if not value:
        return API_LOCALE_DEFAULT
    full = _LOCALE_BY_LOWER.get(value.lower())
    if full is None:
        full = _LOCALE_BY_LANG.get(value.lower())
    if full is None:
        raise ValueError("Must be one of the pexels.com locales: " + ", ".join(LOCALES) + ".")
    return full.lower()


# ---- media / users / collections ------------------------------------------------

_HOSTS = ("pexels.com", "www.pexels.com", "images.pexels.com", "videos.pexels.com")

_ID_RE = re.compile(r"^[0-9]{1,12}$")
# /photo/<slug>-<id>/, /video/<slug>-<id>/, /de-de/foto/<slug>-<id>/,
# /photo/<id>/, /download/video/<id>/, /photos/<id>/pexels-photo-<id>.jpeg,
# /video-files/<id>/<file>.mp4 — the id is the last all-digit run that ends
# a path segment or follows the slug's final hyphen.
_LINK_ID_RE = re.compile(r"(?:^|[/-])([0-9]{1,12})(?=/|$|\.)")
# pexels.com sections that are never a photo / video page: a profile link
# (/@ffc-aarman-22995634/) or a collection slug (/collections/summer-2024/)
# would otherwise hand its trailing digits over as a media id
_NON_MEDIA_PATH_RE = re.compile(r"(?:^|/)(?:@[^/]*|collections|challenges|search)(?:/|$)")
_COLLECTION_ID_RE = re.compile(r"^[a-z0-9]{5,10}$", re.I)
_COLLECTION_LINK_RE = re.compile(r"/collections/([^/?#]+)")
_USER_LINK_RE = re.compile(r"/@([^/?#]+)")
_USER_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")


def _as_url(value):
    """http(s) / protocol-relative link -> parsed URL, or None for bare input."""
    if value.startswith(("http://", "https://", "//")):
        return urlparse(value if not value.startswith("//") else "https:" + value)
    return None


def _check_host(url):
    host = (url.hostname or "").lower()
    if host not in _HOSTS and not host.endswith(".pexels.com"):
        raise ValueError("Must be a pexels.com link.")


def resolve_medium(value):
    """Bare media id or any pexels.com photo / video link -> the numeric id (int)."""
    value = (value or "").strip()
    if _ID_RE.match(value):
        return int(value)
    url = _as_url(value)
    if url is not None:
        _check_host(url)
        path = url.path.rstrip("/")
        ids = _LINK_ID_RE.findall(path) if not _NON_MEDIA_PATH_RE.search(path) else []
        if ids:
            return int(ids[-1])
        raise ValueError("Must be a pexels.com photo or video link "
                         f"({SITE}/photo/<slug>-<id>/ or {SITE}/video/<slug>-<id>/).")
    raise ValueError(f"Must be a numeric Pexels media id (691668) or a pexels.com photo / video link.")


resolve_photo = resolve_medium
resolve_video = resolve_medium


def resolve_user(value):
    """Bare user id, @handle, profile slug or a pexels.com profile link -> the
    API reference (id as given, or the slug without '@')."""
    value = (value or "").strip()
    url = _as_url(value)
    if url is not None:
        _check_host(url)
        match = _USER_LINK_RE.search(url.path)
        if match and _USER_SLUG_RE.match(match.group(1)):
            return match.group(1)
        raise ValueError(f"Must be a pexels.com profile link ({SITE}/@<username>/).")
    value = value.lstrip("@").strip()
    if _ID_RE.match(value) or _USER_SLUG_RE.match(value):
        return value
    raise ValueError("Must be a Pexels user id (121938), a handle (@eberhardgross) "
                     "or a pexels.com profile link.")


def resolve_collection(value):
    """Collection id, slug ("mighty-mountains-cwgidat") or /collections/ link
    -> the collection id (lower-case; the API also takes the full slug, so
    the id suffix is what every form reduces to)."""
    value = (value or "").strip()
    url = _as_url(value)
    if url is not None:
        _check_host(url)
        match = _COLLECTION_LINK_RE.search(url.path)
        if not match:
            raise ValueError(f"Must be a pexels.com collection link ({SITE}/collections/<slug>/).")
        value = match.group(1)
    value = value.strip("/")
    candidate = value.rsplit("-", 1)[-1] if "-" in value else value
    if _COLLECTION_ID_RE.match(candidate):
        return candidate.lower()
    raise ValueError("Must be a Pexels collection id (cwgidat), its slug "
                     "(mighty-mountains-cwgidat) or a pexels.com collection link.")


# ---- links ----------------------------------------------------------------------

def medium_link(kind, slug, medium_id, locale=None):
    """The page link: /photo/<slug>-<id>/ or /video/<slug>-<id>/, under the
    locale prefix for a localized slug (/de-de/photo/<german-slug>-<id>/
    answers 200, 2026-11-03). Without a slug the id-only /photo/<id>/ form
    301s to the canonical page for both kinds."""
    kind = "video" if kind == "video" else "photo"
    prefix = f"/{locale.lower()}" if locale and locale.lower() != API_LOCALE_DEFAULT else ""
    if slug:
        return f"{SITE}{prefix}/{kind}/{slug}-{medium_id}/"
    return f"{SITE}{prefix}/photo/{medium_id}/"


def user_link(slug):
    return f"{SITE}/@{slug}/" if slug else None


def collection_link(slug):
    return f"{SITE}/collections/{slug}/" if slug else None


def challenge_link(slug):
    return f"{SITE}/challenges/{slug}/" if slug else None


def search_link(term, kind="photos"):
    from urllib.parse import quote
    if not term:
        return None
    path = "search/videos" if kind == "videos" else "search"
    return f"{SITE}/{path}/{quote(term)}/"


# ---- search filter vocabularies ---------------------------------------------------

ORIENTATIONS = ("landscape", "portrait", "square")
SIZES = ("small", "medium", "large")            # min original size: 4 / 12 / 24 MP photos, SD / HD / 4K videos
PEOPLE_COUNTS = {"0": "0", "1": "1", "2": "2", "3+": "3_plus"}
PEOPLE_AGES = ("baby", "child", "teenager", "adult", "senior_adult")
DATE_FROM = ("last_24_hours", "last_week", "last_month", "last_year")
FRAME_RATES = {"24": "24", "25": "25", "30": "30", "50": "50", "60+": "60_plus"}
RESOLUTIONS = ("1080p", "4K", "8K")

# user media
USER_MEDIA_TYPES = ("photos", "videos", "all")
USER_MEDIA_SORTS = {"recent": "recent", "popular": "popular"}
FOLLOW_DIRECTIONS = {"followers": "followers", "following": "followings"}

# leaderboard
LEADERBOARD_METRICS = {"views": "views", "uploads": "approved_uploads"}
LEADERBOARD_SPANS = ("all_time", "last_30_days")

# trending searches
TRENDING_TYPES = ("popular", "trending")
TRENDING_MEDIA_TYPES = {"photos": "photo", "videos": "video"}

# search page size: the site clamps per_page to 24 and serves 20 pages at most
SEARCH_PAGE_SIZE = 24
SEARCH_MAX_PAGES = 20
SEARCH_MAX_RESULTS = SEARCH_PAGE_SIZE * SEARCH_MAX_PAGES
# every other list honours per_page up to at least 80 (measured 2026-11-03)
LIST_MAX_PAGE_SIZE = 80
# the site reports at most 10,000 results for a search (pagination.total_results)
SEARCH_TOTAL_CAP = 10000
