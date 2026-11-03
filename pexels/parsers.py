"""pexels.com JSON -> clean dicts for every /pexels/* endpoint. Pure
functions, no I/O; every parser tolerates a partial payload.

Every surface is the JSON the site's own Next.js client calls
(www.pexels.com/<locale>/api/v3/..., JSON:API-ish: {data: [{id, type,
attributes, meta}], meta, pagination}). The record shapes:

  * medium       a photo or a video (one id space, `type` tells them apart):
                 identity, dimensions, tags, colours, image sizes or video
                 renditions, the photographer card, dates
  * details      medium + its EXIF / file / content-safety row
                 (api/v3/media/<id>/details), its views / downloads / likes
                 (/stats) and the full photographer profile + stats
  * user         the 47-attribute profile the site renders on /@<slug>/
  * collection   a curated collection card (+ tags on the details route)
  * challenge    a photo challenge card

Value conventions (shared with the other scraper packages):
  * keys snake_case; `link` not `url`; booleans read as questions
  * dates ISO UTC to the second ("2017-11-17T10:51:26Z"); plain dates stay
    "YYYY-MM-DD"
  * numbers as numbers; "" / missing -> null, never omitted
  * colours as "#rrggbb" (the site mixes [r, g, b] lists and hex strings)

Dropped on purpose (login state, moderation state or presentation only):
status / published / pending / processing / feed_at (moderation pipeline),
liked / following / reactions.reacted / collection_ids / meta.policy /
submissions_opened_to_user (the anonymous caller's own state), donate_url
(a copy of donation_links), canva_tools, seo templates, the `translations`
of a search query, video_provider ("self_hosted" everywhere), the details
row's own created_at / updated_at / fingerprint / copyright constant, and
`image_views` (a copy of `views`).

Fixtures captured 2026-11-03 (pexels/fixtures/): search pages (photos,
filtered videos, empty), a photo and a video with their details and stats,
similar media, a full and a sparse user profile, user media, followers (and
an empty followings page), the leaderboard, the collections directory, one
collection with its media and tags, suggestions, trending searches,
challenges, the three 404 bodies, a 422 and the Cloudflare challenge page.
"""
import math

from pexels.shared import as_dict, as_list, g, iso_datetime, num, text, to_int  # noqa: F401

from pexels import refs

# ---- small values -----------------------------------------------------------------


def _hex(value):
    """[157, 161, 167] / "#2f4f4f" / "2F4F4F" -> "#9da1a7"; junk -> None."""
    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            return "#" + "".join(f"{max(0, min(255, int(c))):02x}" for c in value)
        except (TypeError, ValueError):
            return None
    value = text(value)
    if not value:
        return None
    value = value.lstrip("#").lower()
    if len(value) == 6 and all(ch in "0123456789abcdef" for ch in value):
        return "#" + value
    return None


def _date(value):
    """"2017-04-26" stays a date; a full timestamp is cut to its date."""
    value = text(value)
    return value[:10] if value and len(value) >= 10 else None


def _orientation(width, height):
    if not width or not height:
        return None
    if width == height:
        return "square"
    return "landscape" if width > height else "portrait"


def _blank_to_none(value):
    return text(value)


def _handle(value):
    """"@name" / "name" -> "name"; "" -> None."""
    value = text(value)
    return value.lstrip("@") or None if value else None


def _url(value):
    """A link as the site sent it: whitespace-stripped, NOT html-unescaped
    (pexels.shared.text would turn "&currency_code" into "¤cy_code"); "" -> None."""
    if value is None or isinstance(value, (dict, list)):
        return None
    value = str(value).strip()
    return value or None


def _strip_query(link):
    link = _url(link)
    return link.split("?", 1)[0] if link else None


def _attrs(record):
    """A JSON:API record {id, type, attributes} -> its attributes (+ id)."""
    record = as_dict(record)
    attrs = dict(as_dict(record.get("attributes")))
    attrs.setdefault("id", record.get("id"))
    if "type" not in attrs:
        attrs["type"] = record.get("type")
    return attrs


# ---- photographer card (the 15-attribute user object inside a medium) -------------


def _badges(value):
    out = []
    for badge in as_list(value):
        badge = as_dict(badge)
        if not badge:
            continue
        out.append({"kind": text(badge.get("kind")), "year": to_int(badge.get("year")),
                    "is_active": bool(badge.get("active")) if badge.get("active") is not None else None})
    return out


def _donation_links(value):
    out = []
    for item in as_list(value):
        item = as_dict(item)
        if not item:
            continue
        out.append({"provider": text(item.get("provider")), "type": text(item.get("link_type")),
                    "value": text(item.get("link_value")), "link": _url(item.get("donation_url"))})
    return out


def _avatar(value):
    if isinstance(value, str):
        return {"small": _url(value), "medium": None}
    value = as_dict(value)
    return {"small": _url(value.get("small")), "medium": _url(value.get("medium"))}


def _full_name(attrs):
    parts = [text(attrs.get("first_name")), text(attrs.get("last_name"))]
    name = " ".join(p for p in parts if p)
    return name or text(attrs.get("username")) or None


def parse_user_card(user):
    """The photographer object a medium carries (id, name, handle, avatar,
    hero status, socials, donation links)."""
    user = as_dict(user)
    if not user:
        return None
    slug = text(user.get("slug"))
    return {
        "id": to_int(user.get("id")),
        "name": _full_name(user),
        "username": text(user.get("username")),
        "slug": slug,
        "link": refs.user_link(slug),
        "location": text(user.get("location")),
        "avatar": _avatar(user.get("avatar")),
        "is_hero": bool(user.get("hero")),
        "is_superhero": bool(user.get("superhero")),
        "is_active_hero": bool(user.get("active_hero")),
        "badges": _badges(user.get("badges")),
        "socials": {"instagram": _handle(user.get("instagram")), "twitter": _handle(user.get("twitter"))},
        "donation_links": _donation_links(user.get("donation_links")),
    }


# ---- medium (photo / video) --------------------------------------------------------


def _video_files(files):
    out = []
    for item in as_list(files):
        item = as_dict(item)
        if not item:
            continue
        out.append({
            "quality": text(item.get("quality")),
            "width": to_int(item.get("width")),
            "height": to_int(item.get("height")),
            "fps": num(item.get("fps")),
            "file_type": text(item.get("file_type")),
            "link": _url(item.get("link")),
            "download_link": _url(item.get("download_link")),
        })
    out.sort(key=lambda f: ((f["width"] or 0) * (f["height"] or 0), f["fps"] or 0), reverse=True)
    return out


def parse_medium(record, locale=None):
    """One photo / video record (a search hit, a similar item, a user's or a
    collection's medium, or api/v3/media/<id>) -> the clean medium dict.
    `locale` is the API prefix the record was fetched under: a localized
    slug gets its locale-prefixed page link."""
    attrs = _attrs(record)
    if not attrs or attrs.get("id") is None:
        return None
    medium_id = to_int(attrs.get("id"))
    kind = "video" if (attrs.get("type") == "video" or attrs.get("video") is not None) else "photo"
    slug = text(attrs.get("slug"))
    width, height = to_int(attrs.get("width")), to_int(attrs.get("height"))
    tags = [text(as_dict(t).get("name")) for t in as_list(attrs.get("tags"))]
    tags = [t for t in tags if t]
    out = {
        "id": medium_id,
        "type": kind,
        "title": text(attrs.get("title")),
        "slug": slug,
        "link": refs.medium_link(kind, slug, medium_id, locale),
        "description": text(attrs.get("description")) or text(attrs.get("alt")),
        "width": width,
        "height": height,
        "aspect_ratio": round(num(attrs.get("aspect_ratio")), 4) if num(attrs.get("aspect_ratio")) is not None else None,
        "orientation": _orientation(width, height),
        "license": text(attrs.get("license")),
        "is_featured": bool(attrs.get("starred")),
        "tags": tags,
        "colors": [c for c in (_hex(c) for c in as_list(attrs.get("colors"))) if c],
        "main_color": _hex(attrs.get("main_color")),
    }
    if kind == "video":
        video = as_dict(attrs.get("video"))
        thumb = as_dict(video.get("thumbnail"))
        out["thumbnail"] = {"small": _url(thumb.get("small")), "medium": _url(thumb.get("medium")),
                            "large": _url(thumb.get("large")), "original": _strip_query(thumb.get("small"))}
        out["download_link"] = _url(video.get("download_link"))
        out["video"] = {
            "duration_seconds": num(attrs.get("duration")),
            "fps": num(attrs.get("fps")),
            "source_link": _url(video.get("src")),
            "preview_link": _url(video.get("preview_src")),
            "vimeo_id": text(attrs.get("vimeo_id")),
            "files": _video_files(video.get("video_files")),
        }
    else:
        image = as_dict(attrs.get("image"))
        out["image"] = {"small": _url(image.get("small")), "medium": _url(image.get("medium")),
                        "large": _url(image.get("large")), "original": _strip_query(image.get("download_link"))}
        out["download_link"] = _url(image.get("download_link"))
    out["photographer"] = parse_user_card(attrs.get("user"))
    out["challenges_won"] = attrs.get("challenges_won") if isinstance(attrs.get("challenges_won"), list) else None
    out["created_at"] = iso_datetime(attrs.get("created_at"))
    out["published_at"] = iso_datetime(attrs.get("publish_at"))
    out["updated_at"] = iso_datetime(attrs.get("updated_at"))
    return out


def parse_media_list(payload, locale=None):
    """{data: [media]} -> [medium], skipping records the parser cannot read."""
    out = []
    for record in as_list(as_dict(payload).get("data")):
        medium = parse_medium(record, locale)
        if medium:
            out.append(medium)
    return out


def _translations(meta, kind, medium_id):
    out = []
    for item in as_list(as_dict(meta).get("translations")):
        item = as_dict(item)
        locale, slug = text(item.get("locale")), text(item.get("slug"))
        if not locale or not slug:
            continue
        out.append({"locale": locale, "slug": slug,
                    "link": f"{refs.SITE}/{locale.lower()}/{'video' if kind == 'video' else 'photo'}/{slug}-{medium_id}/"})
    return out


def parse_medium_details(details_payload):
    """api/v3/media/<id>/details -> {camera, file_size_bytes, photographed_at,
    exif_orientation, location, content_safety}. A video's row carries only
    fps / duration, which the medium already has, so it yields nulls."""
    attrs = _attrs(as_dict(details_payload).get("data"))
    camera = {
        "model": text(attrs.get("camera")),
        "make": text(attrs.get("manufacturer")),
        "aperture": text(attrs.get("aperture")),
        "focal_length": text(attrs.get("focal_length")),
        "iso": to_int(attrs.get("iso")),
        "shutter_speed": text(attrs.get("shutter_speed")),
        "software": text(attrs.get("software")),
    }
    safety_keys = ("adult", "racy", "violence", "medical", "spoof")
    safety = {k: (text(attrs.get(k)) if text(attrs.get(k)) not in (None, "unknown") else None) for k in safety_keys}
    location = {
        "name": text(attrs.get("location")),
        "latitude": num(attrs.get("latitude")),
        "longitude": num(attrs.get("longitude")),
        "google_place_id": text(attrs.get("google_place_id")),
    }
    return {
        "camera": camera if any(v is not None for v in camera.values()) else None,
        "file_size_bytes": to_int(attrs.get("size")),
        "photographed_at": iso_datetime(attrs.get("photographed_at")),
        "exif_orientation": to_int(attrs.get("orientation")),
        "location": location if any(v is not None for v in location.values()) else None,
        "content_safety": safety if any(v is not None for v in safety.values()) else None,
    }


def parse_medium_stats(stats_payload):
    """api/v3/media/<id>/stats -> {views, downloads, likes}."""
    attrs = _attrs(as_dict(stats_payload).get("data"))
    return {"views": to_int(attrs.get("views")), "downloads": to_int(attrs.get("downloads")),
            "likes": to_int(attrs.get("likes"))}


def parse_medium_record(medium_payload, details_payload=None, stats_payload=None, user=None, locale=None):
    """The details response: the medium, its stats, EXIF / file / safety
    row, the full photographer profile (already parsed) and the localized
    page links."""
    data = as_dict(as_dict(medium_payload).get("data"))
    medium = parse_medium(data, locale)
    if medium is None:
        return None
    photographer = medium.pop("photographer")
    details = parse_medium_details(details_payload) if details_payload is not None else {}
    out = dict(medium)
    out["stats"] = parse_medium_stats(stats_payload) if stats_payload is not None else None
    if medium["type"] == "photo":
        out["camera"] = details.get("camera")
        out["file_size_bytes"] = details.get("file_size_bytes")
        out["photographed_at"] = details.get("photographed_at")
        out["exif_orientation"] = details.get("exif_orientation")
        out["location"] = details.get("location")
    out["content_safety"] = details.get("content_safety")
    out["photographer"] = user if user is not None else photographer
    out["is_searchable"] = bool(g(data, "meta", "searchable")) if g(data, "meta", "searchable") is not None else None
    out["translations"] = _translations(data.get("meta"), medium["type"], medium["id"])
    return out


# ---- users --------------------------------------------------------------------------


def _preview_photos(value):
    out = []
    for item in as_list(value):
        item = as_dict(item)
        if not item:
            continue
        photo_id = to_int(item.get("id"))
        out.append({"id": photo_id, "link": refs.medium_link("photo", None, photo_id) if photo_id else None,
                    "image": _url(item.get("url")), "average_color": _hex(item.get("avg_color"))})
    return out


def parse_user(record, stats_payload=None):
    """A full user record (api/v3/users/<id>, a search / leaderboard /
    followers row) -> the profile dict; `stats_payload` (api/v3/users/<id>/stats)
    fills downloads / likes when the caller fetched it."""
    attrs = _attrs(record)
    if not attrs or attrs.get("id") is None:
        return None
    stats = _attrs(as_dict(stats_payload).get("data")) if stats_payload is not None else {}
    slug = text(attrs.get("slug"))
    photos = to_int(attrs.get("photos_count"))
    media = to_int(attrs.get("media_count"))
    return {
        "id": to_int(attrs.get("id")),
        "name": _full_name(attrs),
        "first_name": text(attrs.get("first_name")),
        "last_name": text(attrs.get("last_name")),
        "username": text(attrs.get("username")),
        "slug": slug,
        "link": refs.user_link(slug),
        "bio": text(attrs.get("bio")),
        "location": text(attrs.get("location")),
        "website": _url(attrs.get("website")),
        "avatar": _avatar(attrs.get("avatar")),
        "is_hero": bool(attrs.get("hero")),
        "is_superhero": bool(attrs.get("superhero")),
        "is_active_hero": bool(attrs.get("active_hero")),
        "is_staff": bool(attrs.get("staff")),
        "is_open_to_messages": bool(attrs.get("open_to_receive_messages")),
        "badges": _badges(attrs.get("badges")),
        "socials": {
            "instagram": _handle(attrs.get("instagram")),
            "twitter": _handle(attrs.get("twitter")),
            "youtube": _handle(attrs.get("youtube")),
            "tiktok": _handle(attrs.get("tiktok")),
        },
        "donation_links": _donation_links(attrs.get("donation_links")),
        "counts": {
            "photos": photos,
            "videos": (media - photos) if media is not None and photos is not None else None,
            "media": media,
            "portfolio_media": to_int(attrs.get("portfolio_media_count")),
            "collections": to_int(attrs.get("collections_count")),
            "followers": to_int(attrs.get("followers_count")),
            "following": to_int(attrs.get("followings_count")),
            "challenges_won": to_int(attrs.get("challenges_won_count")),
            "challenges_participated": to_int(attrs.get("challenges_participated_count")),
            "homepage_featured": to_int(attrs.get("homepage_featured_count")),
            "meetups_attended": to_int(attrs.get("meetups_attended_count")),
            "shortlisted_collections": to_int(attrs.get("shortlist_collections_count")),
        },
        "stats": {
            "views": to_int(stats.get("views")) if stats.get("views") is not None else to_int(attrs.get("image_views_all_time")),
            "views_last_30_days": to_int(attrs.get("image_views_last_30_days")),
            "uploads_last_30_days": to_int(attrs.get("approved_uploads_last_30_days")),
            "downloads": to_int(stats.get("downloads")),
            "likes": to_int(stats.get("likes")),
        },
        "leaderboard": {
            "all_time_position": to_int(attrs.get("leaderboard_all_time_position")),
            "last_30_days_position": to_int(attrs.get("leaderboard_last_30_days_position")),
            "uploads_last_30_days_position": to_int(attrs.get("leaderboard_approved_uploads_last_30_days_position")),
            "is_hidden": bool(attrs.get("hide_from_leaderboard")),
        },
        "has_approved_media": bool(attrs.get("has_approved_media")),
        "preview_photos": _preview_photos(attrs.get("preview_photos")),
        "first_uploaded_on": _date(attrs.get("first_uploaded_on")),
        "last_uploaded_at": iso_datetime(attrs.get("last_uploaded_at")),
    }


def parse_user_list(payload):
    out = []
    for record in as_list(as_dict(payload).get("data")):
        user = parse_user(record)
        if user:
            out.append(user)
    return out


# ---- collections --------------------------------------------------------------------


def _curators(value):
    out = []
    for item in as_list(value):
        item = as_dict(item)
        if not item:
            continue
        slug = text(item.get("slug"))
        out.append({"id": to_int(item.get("id")), "name": _full_name(item), "username": text(item.get("username")),
                    "slug": slug, "link": refs.user_link(slug), "is_staff": bool(item.get("staff")),
                    "avatar": _url(item.get("avatar"))})
    return out


def parse_collection(record, tags_payload=None):
    attrs = _attrs(record)
    if not attrs or attrs.get("id") is None:
        return None
    slug = text(attrs.get("slug"))
    out = {
        "id": text(attrs.get("id")),
        "title": text(attrs.get("title")),
        "slug": slug,
        "link": refs.collection_link(slug),
        "description": text(attrs.get("description")),
        "is_featured": bool(attrs.get("featured")),
        "is_private": bool(attrs.get("private")),
        "counts": {
            "media": to_int(attrs.get("collection_media_count")),
            "photos": to_int(attrs.get("photos_count")),
            "videos": to_int(attrs.get("videos_count")),
        },
        "curators": _curators(attrs.get("users")),
        "preview_images": [t for t in (_url(i) for i in as_list(attrs.get("preview_images"))) if t],
    }
    if tags_payload is not None:
        tags = g(as_dict(tags_payload), "data", "attributes", "tags")
        out["tags"] = [t for t in (text(x) for x in as_list(tags)) if t]
    return out


def parse_collection_list(payload):
    out = []
    for record in as_list(as_dict(payload).get("data")):
        collection = parse_collection(record)
        if collection:
            out.append(collection)
    return out


# ---- challenges ----------------------------------------------------------------------


def _image_sizes(value):
    value = as_dict(value)
    return {"small": _url(value.get("small")), "medium": _url(value.get("medium")), "large": _url(value.get("large"))}


def _featured_media(value):
    out = []
    for item in as_list(value):
        item = as_dict(item)
        if not item:
            continue
        photo_id = to_int(item.get("id"))
        out.append({"id": photo_id, "link": refs.medium_link("photo", None, photo_id) if photo_id else None,
                    "image": _image_sizes(item.get("image"))})
    return out


def parse_challenge(record):
    attrs = _attrs(record)
    if not attrs or attrs.get("id") is None:
        return None
    slug = text(attrs.get("slug"))
    medium_type = text(attrs.get("medium_type"))
    prize = {
        "title": text(attrs.get("prize_title")),
        "description": text(attrs.get("prize_description")),
        "category": text(attrs.get("prize_category")),
        "link": _url(attrs.get("prize_link")),
        "image": _url(attrs.get("prize_image")),
    }
    sponsor = {
        "name": text(attrs.get("sponsor_name")),
        "link": _url(attrs.get("sponsor_link")),
        "description": text(attrs.get("sponsor_description")),
        "image": _url(attrs.get("sponsor_image")),
    }
    return {
        "id": to_int(attrs.get("id")),
        "title": text(attrs.get("title")),
        "slug": slug,
        "link": refs.challenge_link(slug),
        "subtitle": text(attrs.get("subtitle")),
        "short_description": text(attrs.get("short_description")),
        "description": text(attrs.get("description")),
        "media_type": medium_type.lower() if medium_type else None,
        "is_active": bool(attrs.get("active")),
        "is_heroes_only": bool(attrs.get("heroes_only")),
        "is_superheroes_only": bool(attrs.get("superheroes_only")),
        "start_date": iso_datetime(attrs.get("start_date")),
        "end_date": iso_datetime(attrs.get("end_date")),
        "prize": prize if any(v is not None for v in prize.values()) else None,
        "sponsor": sponsor if any(v is not None for v in sponsor.values()) else None,
        "counts": {
            "media": to_int(attrs.get("media_count")),
            "photographers": to_int(attrs.get("photographers_count")),
            "winners": to_int(attrs.get("winner_media_count")),
        },
        "featured_media": _featured_media(attrs.get("featured_media")),
        "winner_media": _featured_media(attrs.get("winner_media_preview")),
        "photographer_avatars": [t for t in (_url(a) for a in as_list(attrs.get("photographers_avatars"))) if t],
        "terms_and_conditions_link": _url(attrs.get("terms_and_conditions_url")),
        "tips_and_conditions": text(attrs.get("tips_and_conditions")),
    }


def parse_challenge_list(payload):
    out = []
    for record in as_list(as_dict(payload).get("data")):
        challenge = parse_challenge(record)
        if challenge:
            out.append(challenge)
    return out


# ---- search extras --------------------------------------------------------------------


def parse_related_searches(meta, kind="photos"):
    out = []
    for item in as_list(as_dict(meta).get("related_searches")):
        if isinstance(item, str):   # the users search answers bare strings
            term = text(item)
            if term:
                out.append({"term": term, "link": refs.search_link(term, kind), "image": None, "count": None})
            continue
        item = as_dict(item)
        term = text(item.get("term"))
        if not term:
            continue
        out.append({"term": term, "link": refs.search_link(term, kind), "image": _url(item.get("image")),
                    "count": to_int(item.get("count"))})
    return out


def parse_search_totals(meta):
    """meta.total_results -> {photos, videos, users}; None when the page
    carries no meta (the site sends it on page 1 only)."""
    totals = as_dict(as_dict(meta).get("total_results"))
    if not totals:
        return None
    return {"photos": to_int(totals.get("photos")), "videos": to_int(totals.get("videos")),
            "users": to_int(totals.get("users"))}


def parse_suggestions(payload):
    """api/v3/search/suggestions/<prefix> -> [term]."""
    terms = g(as_dict(payload), "data", "attributes", "suggestions")
    return [t for t in (text(x) for x in as_list(terms)) if t]


def parse_trending(payload, kind="photos"):
    """api/v3/search/trending -> [{term, link, image, photo_id, total_results}]."""
    out = []
    for record in as_list(as_dict(payload).get("data")):
        attrs = _attrs(record)
        term = text(attrs.get("term")) or text(attrs.get("id"))
        if not term:
            continue
        photo_id = to_int(attrs.get("photo_id"))
        out.append({"term": term, "link": refs.search_link(term, kind), "image": _url(attrs.get("image_url")),
                    "photo_id": photo_id, "total_results": to_int(attrs.get("total_results"))})
    return out


# ---- pagination -------------------------------------------------------------------------


def page_block(payload, page, per_page, max_pages=None):
    """The site's {current_page, total_pages, total_results} -> our
    {page, items_per_page, total_pages, total_count} (route_glue.paginate
    lifts it). `max_pages` clamps total_pages to what the site really serves
    (search: 20 pages)."""
    pagination = as_dict(as_dict(payload).get("pagination"))
    total = to_int(pagination.get("total_results"))
    items = as_list(as_dict(payload).get("data"))
    if total is None:
        total = len(items) if page == 1 else None
    if total is not None:
        total_pages = math.ceil(total / per_page) if per_page else 0
        if max_pages is not None:
            total_pages = min(total_pages, max_pages)
    else:
        total_pages = None
    return {"page": page, "items_per_page": per_page, "total_pages": total_pages, "total_count": total}
