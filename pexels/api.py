"""The /pexels/* endpoint functions (route_glue's route_table calls them
with the schema's loaded kwargs).

Caching (cache.cached_call, keyed on the validated params):
  * photos/details and videos/details share ONE cached record per media id
    (pexels.medium: the medium + its details + stats rows fetched in
    parallel, plus the cached photographer profile), so a client that reads
    a photo and then its photographer pays one upstream round for the user.
  * users/details, the `user` search filter and the details' photographer
    block share pexels.user (profile + stats, keyed on the reference the
    caller gave: a slug and the numeric id are two rows of the same user).
  * every list endpoint caches its own page.
"""
from cache import cached_call
from pexels import cache_config as ttl
from pexels import parsers, refs
from pexels.fetch import (PexelsNotFound, fetch_challenges, fetch_collection, fetch_collection_media,
                          fetch_collection_tags, fetch_collections, fetch_leaderboard, fetch_many, fetch_medium,
                          fetch_medium_details, fetch_medium_stats, fetch_search, fetch_similar, fetch_suggestions,
                          fetch_trending, fetch_user, fetch_user_follows, fetch_user_media, fetch_user_stats,
                          fetch_users_search)

# ---- shared records --------------------------------------------------------------------


def _user_record(user):
    """Profile + all-time stats for a user id / slug (cached)."""
    def load(user):
        payload = fetch_user(user)
        user_id = parsers.g(payload, "data", "id")
        stats = fetch_user_stats(user_id) if user_id else None
        record = parsers.parse_user(payload.get("data"), stats)
        if record is None:
            raise PexelsNotFound(f"user {user} not found")
        return record
    return cached_call("pexels.user", {"user": str(user)}, load, ttl.USER_CACHE)


def _user_id(user):
    """A numeric reference as is; a slug through the cached profile."""
    if user is None:
        return None
    if str(user).isdigit():
        return int(user)
    return _user_record(user)["id"]


def _medium_record(medium, locale):
    """The medium, its EXIF / file / safety row and its stats (three
    parallel calls), with the full photographer profile (cached)."""
    def load(medium, locale):
        payload, details, stats = fetch_many([
            lambda: fetch_medium(medium, locale),
            lambda: fetch_medium_details(medium),
            lambda: fetch_medium_stats(medium),
        ])
        user_id = parsers.g(payload, "data", "attributes", "user", "id")
        photographer = _user_record(user_id) if user_id else None
        record = parsers.parse_medium_record(payload, details, stats, photographer, locale)
        if record is None:
            raise PexelsNotFound(f"medium {medium} not found")
        return record
    return cached_call("pexels.medium", {"medium": medium, "locale": locale}, load, ttl.MEDIUM_CACHE)


def _expect_kind(record, kind, medium):
    if record["type"] != kind:
        other = "videos" if record["type"] == "video" else "photos"
        raise PexelsNotFound(f"{medium} is a {record['type']}, not a {kind}; use /pexels/{other}/details")
    return record


# ---- photos|videos/search -------------------------------------------------------------


def _search_filters(data):
    filters = {
        "orientation": data.get("orientation"),
        "size": data.get("size"),
        "people_count": data.get("people_count"),
        "people_age": data.get("people_age"),
        "date_from": data.get("date_from"),
        # the API's range names (the UI's duration / width / height sliders
        # are transformed to these by the client's transformForApi)
        "min_width": data.get("min_width"),
        "max_width": data.get("max_width"),
        "min_height": data.get("min_height"),
        "max_height": data.get("max_height"),
        "min_duration": data.get("min_duration"),
        "max_duration": data.get("max_duration"),
        "frame_rate": data.get("frame_rate"),
        "resolution_name": data.get("resolution"),
        "user_id": _user_id(data.get("user")),
    }
    return {k: v for k, v in filters.items() if v is not None}


def _search(mode, **data):
    page, locale = data["page"], data.get("locale") or refs.API_LOCALE_DEFAULT
    payload = fetch_search(mode, data["query"], page, locale, **_search_filters(data))
    results = parsers.parse_media_list(payload, locale)
    block = parsers.page_block(payload, page, refs.SEARCH_PAGE_SIZE, max_pages=refs.SEARCH_MAX_PAGES)
    total = block["total_count"]
    # `totals` and `related_searches` ride the site's page-1 meta only
    return {
        "query": data["query"],
        "type": mode,
        "locale": locale,
        "max_results": refs.SEARCH_MAX_RESULTS,
        "is_total_capped": bool(total is not None and total >= refs.SEARCH_TOTAL_CAP),
        "totals": parsers.parse_search_totals(payload.get("meta")),
        "related_searches": parsers.parse_related_searches(payload.get("meta"), mode),
        "results": results,
        "pagination": block,
    }


def photos_search(**data):
    return cached_call("pexels.photos_search", data, lambda **d: _search("photos", **d), ttl.SEARCH_CACHE)


def videos_search(**data):
    return cached_call("pexels.videos_search", data, lambda **d: _search("videos", **d), ttl.SEARCH_CACHE)


# ---- photos|videos/details -----------------------------------------------------------


def photo_details(photo, locale=refs.API_LOCALE_DEFAULT):
    """Everything the photo page shows: the record, image sizes and download
    link, tags and colours, EXIF / file size / content safety, views /
    downloads / likes, the full photographer profile with stats, and the
    localized page links."""
    return _expect_kind(_medium_record(photo, locale), "photo", photo)


def video_details(video, locale=refs.API_LOCALE_DEFAULT):
    """Everything the video page shows: every MP4 rendition with its download
    link, thumbnails, duration / fps, views / downloads / likes, the full
    creator profile with stats, and the localized page links."""
    return _expect_kind(_medium_record(video, locale), "video", video)


# ---- photos|videos/similar -----------------------------------------------------------


def _similar(medium, page, per_page, locale):
    payload = fetch_similar(medium, page, per_page, locale)
    return {
        "medium_id": medium,
        "results": parsers.parse_media_list(payload, locale),
        "pagination": parsers.page_block(payload, page, per_page),
    }


def photo_similar(**data):
    data = {"medium": data["photo"], "page": data["page"], "per_page": data["per_page"], "locale": data["locale"]}
    return cached_call("pexels.similar", data, _similar, ttl.SIMILAR_CACHE)


def video_similar(**data):
    data = {"medium": data["video"], "page": data["page"], "per_page": data["per_page"], "locale": data["locale"]}
    return cached_call("pexels.similar", data, _similar, ttl.SIMILAR_CACHE)


# ---- users -----------------------------------------------------------------------------


def _users_search(query, page):
    payload = fetch_users_search(query, page, refs.SEARCH_PAGE_SIZE)
    return {
        "query": query,
        "totals": parsers.parse_search_totals(payload.get("meta")),
        "related_searches": parsers.parse_related_searches(payload.get("meta")),
        "results": parsers.parse_user_list(payload),
        "pagination": parsers.page_block(payload, page, refs.SEARCH_PAGE_SIZE),
    }


def users_search(**data):
    return cached_call("pexels.users_search", data, _users_search, ttl.SEARCH_CACHE)


def user_details(user):
    """The public profile: name, bio, socials, donation links, hero badges,
    upload / follower counts, all-time views / downloads / likes,
    leaderboard positions and four preview photos."""
    return _user_record(user)


def _user_media(user, type, sort, page, per_page, locale):
    user_id = _user_id(user)
    payload = fetch_user_media(user_id, sort, type, page, per_page, locale)
    return {
        "user_id": user_id,
        "type": type,
        "sort": sort,
        "results": parsers.parse_media_list(payload, locale),
        "pagination": parsers.page_block(payload, page, per_page),
    }


def user_media(**data):
    return cached_call("pexels.user_media", data, _user_media, ttl.USER_MEDIA_CACHE)


def _user_followers(user, direction, page, per_page):
    user_id = _user_id(user)
    payload = fetch_user_follows(user_id, direction, page, per_page)
    return {
        "user_id": user_id,
        "direction": "following" if direction == "followings" else "followers",
        "results": parsers.parse_user_list(payload),
        "pagination": parsers.page_block(payload, page, per_page),
    }


def user_followers(**data):
    return cached_call("pexels.user_followers", data, _user_followers, ttl.FOLLOWERS_CACHE)


def _leaderboard(metric, span, heroes_only, page, per_page):
    payload = fetch_leaderboard(metric, span, heroes_only, page, per_page)
    results = parsers.parse_user_list(payload)
    for offset, user in enumerate(results):
        user["rank"] = (page - 1) * per_page + offset + 1
    return {
        "metric": "uploads" if metric == "approved_uploads" else metric,
        "span": span,
        "is_heroes_only": bool(heroes_only),
        "results": results,
        "pagination": parsers.page_block(payload, page, per_page),
    }


def users_leaderboard(**data):
    return cached_call("pexels.leaderboard", data, _leaderboard, ttl.LEADERBOARD_CACHE)


# ---- collections -------------------------------------------------------------------------


def _collections_list(page, per_page):
    payload = fetch_collections(page, per_page)
    return {"results": parsers.parse_collection_list(payload),
            "pagination": parsers.page_block(payload, page, per_page)}


def collections_list(**data):
    return cached_call("pexels.collections_list", data, _collections_list, ttl.COLLECTIONS_CACHE)


def _collection_details(collection):
    payload, tags = fetch_many([lambda: fetch_collection(collection), lambda: fetch_collection_tags(collection)])
    record = parsers.parse_collection(payload.get("data"), tags)
    if record is None:
        raise PexelsNotFound(f"collection {collection} not found")
    return record


def collection_details(**data):
    return cached_call("pexels.collection", data, _collection_details, ttl.COLLECTIONS_CACHE)


def _collection_media(collection, page, per_page, locale):
    payload = fetch_collection_media(collection, page, per_page, locale)
    return {
        "collection_id": collection,
        "results": parsers.parse_media_list(payload, locale),
        "pagination": parsers.page_block(payload, page, per_page),
    }


def collection_media(**data):
    return cached_call("pexels.collection_media", data, _collection_media, ttl.COLLECTION_MEDIA_CACHE)


# ---- search extras / challenges ----------------------------------------------------------


def _suggestions(query):
    return {"query": query, "suggestions": parsers.parse_suggestions(fetch_suggestions(query))}


def search_suggestions(**data):
    return cached_call("pexels.suggestions", data, _suggestions, ttl.SUGGESTIONS_CACHE)


def _trending(type, media_type, country):
    payload = fetch_trending(type, media_type, (country or "").lower() or None)
    kind = "videos" if media_type == "video" else "photos"
    return {
        "type": type,
        "media_type": {"photo": "photos", "video": "videos"}.get(media_type),
        "country": country.lower() if country else None,
        "results": parsers.parse_trending(payload, kind),
    }


def search_trending(**data):
    return cached_call("pexels.trending", data, _trending, ttl.TRENDING_CACHE)


def _challenges_list(page, per_page):
    payload = fetch_challenges(page, per_page)
    return {"results": parsers.parse_challenge_list(payload),
            "pagination": parsers.page_block(payload, page, per_page)}


def challenges_list(**data):
    return cached_call("pexels.challenges_list", data, _challenges_list, ttl.CHALLENGES_CACHE)
