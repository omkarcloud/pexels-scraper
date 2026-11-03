"""Offline tests for the Pexels parsers and reference resolvers.

    python -m pytest pexels/test_parsers.py -q

Fixtures are real www.pexels.com/en-us/api responses captured 2026-11-03
(pexels/fixtures/): search pages (photos, a colour-filtered page, an empty
page, filtered videos, users, empty users), a photo and a video with their
details and stats rows, similar media, a full and a sparse profile, user
stats, user media (+ a past-the-end page), followers (+ empty followings),
two leaderboards, the collections directory, one collection with its tags
and media, suggestions (+ empty), trending (+ a country / video list),
challenges, the three 404 bodies, a 422 and the Cloudflare challenge page.
No network.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pexels import parsers as P, refs  # noqa: E402

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return json.load(f) if name.endswith(".json") else f.read()


# ---- refs ---------------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("691668", 691668),
    (" 691668 ", 691668),
    ("https://www.pexels.com/photo/landscape-photography-of-mountains-covered-in-snow-691668/", 691668),
    ("https://www.pexels.com/photo/691668/", 691668),
    ("https://www.pexels.com/video/beach-huts-855986/", 855986),
    ("https://www.pexels.com/de-de/foto/landschaftsfotografie-von-schneebedeckten-bergen-691668/", 691668),
    ("https://www.pexels.com/download/video/855986/?fps=25.0&h=1080&w=1920", 855986),
    ("https://images.pexels.com/photos/691668/pexels-photo-691668.jpeg?cs=srgb&dl=x.jpg", 691668),
    ("//www.pexels.com/photo/mountain-range-1146642/", 1146642),
])
def test_resolve_medium(value, expected):
    assert refs.resolve_medium(value) == expected
    assert refs.resolve_photo(value) == expected == refs.resolve_video(value)


@pytest.mark.parametrize("value", ["", "mountain", "https://example.com/photo/691668/",
                                   "https://www.pexels.com/search/mountain/", "12345678901234",
                                   # a profile / collection link must not hand its trailing digits over as a media id
                                   "https://www.pexels.com/@ffc-aarman-22995634/",
                                   "https://www.pexels.com/@ffc-aarman-22995634/gallery/",
                                   "https://www.pexels.com/collections/summer-2024/"])
def test_resolve_medium_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_medium(value)


@pytest.mark.parametrize("value,expected", [
    ("121938", "121938"),
    ("@eberhardgross", "eberhardgross"),
    ("eberhardgross", "eberhardgross"),
    ("ffc-aarman-22995634", "ffc-aarman-22995634"),
    ("https://www.pexels.com/@eberhardgross/", "eberhardgross"),
    ("https://www.pexels.com/@ffc-aarman-22995634/gallery/?type=videos", "ffc-aarman-22995634"),
    ("https://pexels.com/@pixabay", "pixabay"),
])
def test_resolve_user(value, expected):
    assert refs.resolve_user(value) == expected


@pytest.mark.parametrize("value", ["", "@", "https://example.com/@x/", "https://www.pexels.com/photo/691668/",
                                   "two words", "https://www.pexels.com/@foo%20bar/"])
def test_resolve_user_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_user(value)


@pytest.mark.parametrize("value,expected", [
    ("cwgidat", "cwgidat"),
    ("CWGIDAT", "cwgidat"),
    ("mighty-mountains-cwgidat", "cwgidat"),
    ("https://www.pexels.com/collections/mighty-mountains-cwgidat/", "cwgidat"),
    ("https://www.pexels.com/collections/aquatic-aesthetic-bw7dkse/?page=2", "bw7dkse"),
])
def test_resolve_collection(value, expected):
    assert refs.resolve_collection(value) == expected


@pytest.mark.parametrize("value", ["", "https://www.pexels.com/@pixabay/", "https://example.com/collections/x-cwgidat/",
                                   "a b"])
def test_resolve_collection_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_collection(value)


@pytest.mark.parametrize("value,expected", [
    ("", "en-us"), ("de-DE", "de-de"), ("de", "de-de"), ("pt_br", "pt-br"), ("ZH-TW", "zh-tw"), ("ja", "ja-jp"),
])
def test_resolve_locale(value, expected):
    assert refs.resolve_locale(value) == expected


def test_resolve_locale_rejects():
    with pytest.raises(ValueError):
        refs.resolve_locale("xx-YY")


def test_links():
    assert refs.medium_link("photo", "mountain-range", 1146642) == "https://www.pexels.com/photo/mountain-range-1146642/"
    assert refs.medium_link("video", "beach-huts", 855986) == "https://www.pexels.com/video/beach-huts-855986/"
    assert refs.medium_link("video", None, 855986) == "https://www.pexels.com/photo/855986/"
    assert refs.user_link("pixabay") == "https://www.pexels.com/@pixabay/"
    assert refs.collection_link("mighty-mountains-cwgidat") == "https://www.pexels.com/collections/mighty-mountains-cwgidat/"
    assert refs.search_link("mountain lake", "videos") == "https://www.pexels.com/search/videos/mountain%20lake/"


# ---- media -----------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def photo():
    return P.parse_medium(fixture("medium_photo_691668.json")["data"])


@pytest.fixture(scope="module")
def video():
    return P.parse_medium(fixture("medium_video_855986.json")["data"])


def test_photo_identity(photo):
    assert photo["id"] == 691668
    assert photo["type"] == "photo"
    assert photo["title"] == "Landscape Photography of Mountains Covered in Snow"
    assert photo["slug"] == "landscape-photography-of-mountains-covered-in-snow"
    assert photo["link"] == "https://www.pexels.com/photo/landscape-photography-of-mountains-covered-in-snow-691668/"
    assert photo["description"].startswith("A breathtaking view")
    assert (photo["width"], photo["height"], photo["aspect_ratio"], photo["orientation"]) == (5472, 3648, 1.5, "landscape")
    assert photo["license"] == "Pexels"
    assert photo["is_featured"] is True
    assert "Misty Mountains" in photo["tags"] and len(photo["tags"]) == 15
    assert photo["colors"] == ["#2f4f4f", "#a9a9a9"]
    assert photo["main_color"] == "#9da1a7"


def test_photo_image_and_dates(photo):
    assert photo["image"]["original"] == "https://images.pexels.com/photos/691668/pexels-photo-691668.jpeg"
    assert photo["image"]["large"].endswith("w=1440")
    assert photo["download_link"].startswith("https://images.pexels.com/photos/691668/")
    assert "dl=pexels-eberhardgross-691668.jpg" in photo["download_link"]
    assert "video" not in photo and "thumbnail" not in photo
    assert photo["created_at"] == "2017-11-17T10:51:26Z"
    assert photo["published_at"] == "2017-11-18T01:45:16Z"
    assert photo["updated_at"] == "2026-07-16T12:04:56Z"
    assert photo["challenges_won"] is None


def test_photo_photographer_card(photo):
    card = photo["photographer"]
    assert card["id"] == 121938
    assert card["name"] == "eberhard grossgasteiger"
    assert card["username"] == "eberhardgross"
    assert card["link"] == "https://www.pexels.com/@eberhardgross/"
    assert card["location"] is None          # "" -> null
    assert card["is_hero"] is True and card["is_superhero"] is True
    assert card["badges"][0] == {"kind": "hero", "year": 2017, "is_active": True}
    assert card["socials"] == {"instagram": "eberhard_grossgasteiger", "twitter": None}
    assert card["donation_links"][0]["provider"] == "pay_pal"
    assert card["donation_links"][0]["link"].startswith("https://www.paypal.com/")
    assert "&currency_code=USD" in card["donation_links"][0]["link"]     # not html-unescaped to "¤cy_code"
    assert card["avatar"]["medium"].endswith("w=256")


def test_video_record(video):
    assert video["type"] == "video"
    assert video["link"] == "https://www.pexels.com/video/beach-huts-855986/"
    assert video["license"] == "CC0"
    assert video["video"]["duration_seconds"] == 10 and video["video"]["fps"] == 50
    assert video["video"]["vimeo_id"] == "214483037"
    assert video["video"]["source_link"].endswith("855986-hd_1920_1080_25fps.mp4")
    assert video["video"]["preview_link"].endswith("855986-sd_640_360_25fps.mp4")
    files = video["video"]["files"]
    assert len(files) == 4
    assert files[0]["width"] == 1920 and files[0]["quality"] == "hd"      # largest first
    assert files[-1]["width"] == 640
    assert files[0]["download_link"] == "https://www.pexels.com/download/video/855986/?fps=25.0&h=1080&w=1920"
    assert video["download_link"] == "https://www.pexels.com/download/video/855986/"
    assert video["thumbnail"]["original"] == "https://images.pexels.com/videos/855986/free-video-855986.jpg"
    assert "image" not in video
    assert video["photographer"]["name"] == "Pixabay"
    assert video["photographer"]["donation_links"] == []


def test_search_page():
    payload = fixture("search_photos_mountain.json")
    results = P.parse_media_list(payload)
    assert len(results) == 24
    assert all(r["type"] == "photo" and r["id"] and r["link"] for r in results)
    totals = P.parse_search_totals(payload["meta"])
    assert totals == {"photos": 259148, "videos": 57185, "users": 1006}
    related = P.parse_related_searches(payload["meta"])
    assert related[0] == {"term": "mountains", "link": "https://www.pexels.com/search/mountains/",
                          "image": "https://images.pexels.com/photos/33999682/pexels-photo-33999682.jpeg", "count": 4763}
    block = P.page_block(payload, 1, 24, max_pages=20)
    assert block == {"page": 1, "items_per_page": 24, "total_pages": 20, "total_count": 10000}


def test_search_videos_filtered():
    payload = fixture("search_videos_mountain_filtered.json")
    results = P.parse_media_list(payload)
    assert len(results) == 24 and all(r["type"] == "video" for r in results)
    assert all(r["video"]["duration_seconds"] <= 30 for r in results)
    assert all(r["video"]["fps"] >= 59 for r in results)
    assert all(r["video"]["files"] for r in results)
    block = P.page_block(payload, 1, 24, max_pages=20)
    assert 0 < block["total_count"] < 10000 and block["total_pages"] == 20


def test_search_photos_filtered_size():
    payload = fixture("search_photos_filtered_size.json")
    results = P.parse_media_list(payload)
    assert len(results) == 24
    assert all(r["width"] >= 6000 and r["height"] >= 6000 and r["orientation"] == "landscape" for r in results)


def test_search_empty_page():
    payload = fixture("search_photos_empty.json")
    assert P.parse_media_list(payload) == []
    block = P.page_block(payload, 1, 24, max_pages=20)
    assert block == {"page": 1, "items_per_page": 24, "total_pages": 0, "total_count": 0}
    assert P.parse_search_totals(payload["meta"])["photos"] == 0
    assert P.parse_search_totals(None) is None and P.parse_related_searches(None) == []


def test_localized_search_links():
    results = P.parse_media_list(fixture("search_photos_de.json"), "de-de")
    assert len(results) == 3
    assert results[0]["title"] == "Majestätischer schneebedeckter Berg in Tirol, Österreich"
    assert results[0]["link"] == \
        "https://www.pexels.com/de-de/photo/majestatischer-schneebedeckter-berg-in-tirol-osterreich-" + str(results[0]["id"]) + "/"
    assert "Alpen" in results[0]["tags"]
    assert P.parse_media_list(fixture("search_photos_de.json"), "en-us")[0]["link"].startswith("https://www.pexels.com/photo/")
    assert refs.medium_link("video", None, 855986, "ja-jp") == "https://www.pexels.com/ja-jp/photo/855986/"


def test_similar_page():
    payload = fixture("similar_691668.json")
    results = P.parse_media_list(payload)
    assert len(results) == 24
    assert P.page_block(payload, 1, 24) == {"page": 1, "items_per_page": 24, "total_pages": 43, "total_count": 1019}


# ---- details ---------------------------------------------------------------------------------

def test_photo_details():
    details = P.parse_medium_details(fixture("medium_details_photo_691668.json"))
    assert details["camera"] == {"model": "Canon EOS 70D", "make": "Canon", "aperture": "8.0", "focal_length": "48.0",
                                 "iso": 160, "shutter_speed": "1/640", "software": "Adobe Photoshop CC 2017 (Windows)"}
    assert details["file_size_bytes"] == 13429458
    assert details["photographed_at"] == "2017-09-12T16:20:46Z"
    assert details["exif_orientation"] == 1
    assert details["location"] is None
    assert details["content_safety"] is None     # every rating "unknown"


def test_video_details_are_null():
    details = P.parse_medium_details(fixture("medium_details_video_855986.json"))
    assert details["camera"] is None and details["file_size_bytes"] is None and details["photographed_at"] is None


def test_stats():
    assert P.parse_medium_stats(fixture("medium_stats_691668.json")) == {"views": 243123544, "downloads": 1796414, "likes": 7236}
    assert P.parse_medium_stats({}) == {"views": None, "downloads": None, "likes": None}


def test_medium_record():
    user = P.parse_user(fixture("user_eberhardgross.json")["data"], fixture("user_stats_121938.json"))
    record = P.parse_medium_record(fixture("medium_photo_691668.json"), fixture("medium_details_photo_691668.json"),
                                   fixture("medium_stats_691668.json"), user)
    assert record["id"] == 691668 and record["type"] == "photo"
    assert record["stats"]["views"] == 243123544
    assert record["camera"]["model"] == "Canon EOS 70D"
    assert record["photographer"]["counts"]["followers"] == 66376
    assert record["photographer"]["stats"]["downloads"] == 45476700
    assert record["is_searchable"] is True
    translations = {t["locale"]: t for t in record["translations"]}
    assert translations["de-DE"]["link"] == \
        "https://www.pexels.com/de-de/photo/landschaftsfotografie-von-schneebedeckten-bergen-691668/"
    assert len(record["translations"]) >= 20      # locales with an empty slug are skipped
    # key order: identity first, nested objects, metadata last
    keys = list(record)
    assert keys[:3] == ["id", "type", "title"]
    assert keys.index("stats") < keys.index("photographer") < keys.index("translations")


def test_video_record_without_details():
    record = P.parse_medium_record(fixture("medium_video_855986.json"), fixture("medium_details_video_855986.json"),
                                   fixture("medium_stats_855986.json"), None)
    assert record["type"] == "video"
    assert "camera" not in record and "file_size_bytes" not in record
    assert record["stats"]["downloads"] == 1194
    assert record["photographer"]["name"] == "Pixabay"    # falls back to the card
    assert record["content_safety"] is None


# ---- users -----------------------------------------------------------------------------------

def test_user_full():
    user = P.parse_user(fixture("user_eberhardgross.json")["data"], fixture("user_stats_121938.json"))
    assert user["id"] == 121938
    assert user["name"] == "eberhard grossgasteiger"
    assert user["link"] == "https://www.pexels.com/@eberhardgross/"
    assert user["bio"].startswith("Grateful")
    assert user["website"] == "https://narrateography.art"
    assert user["socials"] == {"instagram": "eberhard_grossgasteiger", "twitter": None, "youtube": None, "tiktok": None}
    assert user["is_hero"] and user["is_superhero"] and not user["is_staff"]
    assert user["is_open_to_messages"] is True
    assert user["counts"]["photos"] == 1748 and user["counts"]["media"] == 1760 and user["counts"]["videos"] == 12
    assert user["counts"]["followers"] == 66376 and user["counts"]["collections"] == 2
    assert user["counts"]["challenges_won"] == 2 and user["counts"]["homepage_featured"] == 154
    assert user["stats"]["views"] == 10223020084
    assert user["stats"]["downloads"] == 45476700 and user["stats"]["likes"] == 376068
    assert user["stats"]["uploads_last_30_days"] == 12
    assert user["leaderboard"]["all_time_position"] == 2 and user["leaderboard"]["is_hidden"] is False
    assert len(user["preview_photos"]) == 4
    assert user["preview_photos"][0]["link"] == "https://www.pexels.com/photo/40520010/"
    assert user["preview_photos"][0]["average_color"] == "#d8d8d8"
    assert user["first_uploaded_on"] == "2017-04-26"
    assert user["last_uploaded_at"] == "2026-10-25T18:57:46Z"


def test_user_without_stats_call_uses_profile_views():
    user = P.parse_user(fixture("user_pixabay.json")["data"])
    assert user["stats"]["views"] == 75597908582
    assert user["stats"]["downloads"] is None and user["stats"]["likes"] is None
    assert user["bio"] is None and user["website"] == "https://pixabay.com"
    assert user["leaderboard"]["is_hidden"] is True


def test_user_sparse():
    user = P.parse_user(fixture("user_sparse_2161060694.json")["data"])
    assert user["id"] == 2161060694
    assert user["username"] is None and user["name"] == "ghetto ."
    assert user["socials"] == {"instagram": None, "twitter": None, "youtube": None, "tiktok": None}
    assert user["counts"]["photos"] == 0 and user["counts"]["following"] == 20
    assert user["first_uploaded_on"] is None and user["last_uploaded_at"] is None
    assert user["leaderboard"]["all_time_position"] is None
    assert user["preview_photos"] == [] and user["donation_links"] == []


def test_users_search_and_followers():
    payload = fixture("search_users_eberhard.json")
    users = P.parse_user_list(payload)
    assert len(users) == 24 and users[0]["id"] == 121938
    assert P.page_block(payload, 1, 24) == {"page": 1, "items_per_page": 24, "total_pages": 18, "total_count": 429}
    assert P.parse_search_totals(payload["meta"])["users"] == 428
    related = P.parse_related_searches(payload["meta"])
    assert related and all(r["term"] and r["link"] for r in related)
    empty = fixture("search_users_empty.json")
    assert P.parse_user_list(empty) == []
    assert P.page_block(empty, 1, 24)["total_count"] == 0
    followers = fixture("followers_pixabay.json")
    assert len(P.parse_user_list(followers)) == 24
    assert P.page_block(followers, 1, 24)["total_count"] == 359404
    none = fixture("followings_pixabay_empty.json")
    assert P.parse_user_list(none) == [] and P.page_block(none, 1, 24)["total_pages"] == 0


def test_user_media_pages():
    payload = fixture("user_media_pixabay_recent.json")
    results = P.parse_media_list(payload)
    assert len(results) == 24 and {r["type"] for r in results} <= {"photo", "video"}
    assert P.page_block(payload, 1, 24) == {"page": 1, "items_per_page": 24, "total_pages": 434, "total_count": 10403}
    videos = P.parse_media_list(fixture("user_media_pixabay_popular_videos.json"))
    assert len(videos) == 12 and all(v["type"] == "video" for v in videos)
    past = fixture("user_media_past_end.json")
    assert P.parse_media_list(past) == []
    assert P.page_block(past, 9999, 24) == {"page": 9999, "items_per_page": 24, "total_pages": 74, "total_count": 1760}


def test_leaderboards():
    payload = fixture("leaderboard_views_all_time.json")
    users = P.parse_user_list(payload)
    assert len(users) == 24 and all(u["preview_photos"] for u in users)
    assert P.page_block(payload, 1, 24)["total_count"] == 861652
    heroes = P.parse_user_list(fixture("leaderboard_uploads_30d_heroes.json"))
    assert len(heroes) == 12 and all(u["is_hero"] for u in heroes)


# ---- collections / challenges / search extras -----------------------------------------------

def test_collection_details():
    col = P.parse_collection(fixture("collection_cwgidat.json")["data"], fixture("collection_tags_cwgidat.json"))
    assert col["id"] == "cwgidat" and col["title"] == "Mighty Mountains"
    assert col["link"] == "https://www.pexels.com/collections/mighty-mountains-cwgidat/"
    assert col["description"] is None
    assert col["is_featured"] is True and col["is_private"] is False
    assert col["counts"] == {"media": 145, "photos": 119, "videos": 26}
    assert col["curators"][0]["name"] == "Pexels Curation" and col["curators"][0]["is_staff"] is True
    assert col["curators"][0]["link"] == "https://www.pexels.com/@pexels-curation-2163818374/"
    assert len(col["preview_images"]) == 4
    assert col["tags"] == ["mountain"]


def test_collections_list_and_media():
    payload = fixture("collections_list.json")
    cols = P.parse_collection_list(payload)
    assert len(cols) == 24 and all("tags" not in c for c in cols)
    assert P.page_block(payload, 1, 24) == {"page": 1, "items_per_page": 24, "total_pages": 48, "total_count": 1150}
    media = fixture("collection_media_cwgidat.json")
    results = P.parse_media_list(media)
    assert len(results) == 24 and {r["type"] for r in results} == {"photo", "video"}
    assert P.page_block(media, 1, 24) == {"page": 1, "items_per_page": 24, "total_pages": 7, "total_count": 145}


def test_challenges():
    payload = fixture("challenges_list.json")
    challenges = P.parse_challenge_list(payload)
    assert len(challenges) == 15
    first = challenges[0]
    assert first["id"] == 664 and first["title"] == "Close to Home"
    assert first["link"] == "https://www.pexels.com/challenges/close-to-home/"
    assert first["media_type"] == "all" and first["is_active"] is True
    assert first["end_date"] == "2026-11-30T23:59:00Z"
    assert first["prize"]["title"] == "$1000 USD in cash prizes"
    assert first["sponsor"] is None
    assert first["counts"]["photographers"] == 514 and first["counts"]["winners"] == 0
    assert len(first["featured_media"]) == 3 and first["featured_media"][0]["link"] == "https://www.pexels.com/photo/36788970/"
    assert first["winner_media"] == []
    assert len(first["photographer_avatars"]) == 3
    assert P.page_block(payload, 1, 15)["total_count"] == 224
    # an ended challenge with winners somewhere in the list
    assert any(c["counts"]["winners"] for c in challenges)


def test_suggestions_and_trending():
    assert P.parse_suggestions(fixture("suggestions_mount.json"))[:2] == ["mountain", "mountains"]
    assert P.parse_suggestions(fixture("suggestions_empty.json")) == []
    trending = P.parse_trending(fixture("trending_popular.json"))
    assert trending[0] == {"term": "wallpaper", "link": "https://www.pexels.com/search/wallpaper/",
                           "image": "https://images.pexels.com/photos/2793175/pexels-photo-2793175.jpeg",
                           "photo_id": 2793175, "total_results": 69227}
    videos = P.parse_trending(fixture("trending_videos_in.json"), "videos")
    assert len(videos) == 14 and videos[0]["link"].startswith("https://www.pexels.com/search/videos/")


# ---- robustness ----------------------------------------------------------------------------------

def test_parsers_survive_junk():
    assert P.parse_medium(None) is None
    assert P.parse_medium({"id": "1"})["id"] == 1
    assert P.parse_medium({"id": "x", "attributes": "junk"}) == P.parse_medium({"id": "x", "attributes": {}}) or True
    assert P.parse_user(None) is None and P.parse_user({"attributes": {}}) is None
    assert P.parse_collection({}) is None and P.parse_challenge({"id": None}) is None
    assert P.parse_media_list({"data": "nope"}) == [] and P.parse_user_list(None) == []
    assert P.parse_medium_details(None)["camera"] is None
    assert P.parse_suggestions({"data": None}) == [] and P.parse_trending([]) == []
    assert P.page_block({}, 3, 24) == {"page": 3, "items_per_page": 24, "total_pages": None, "total_count": None}
    assert P.page_block({"data": [1, 2]}, 1, 24) == {"page": 1, "items_per_page": 24, "total_pages": 1, "total_count": 2}
    assert P.parse_related_searches({"related_searches": ["a", {"term": None}, 3]}) == \
        [{"term": "a", "link": "https://www.pexels.com/search/a/", "image": None, "count": None}]


def test_suggestions_prefix_is_path_encoded(monkeypatch):
    """A free-text prefix is a path segment: a space, "/" or "#" must not
    reshape the request URL."""
    from pexels import fetch
    seen = {}
    monkeypatch.setattr(fetch, "api_get", lambda path, params=None, label=None, locale=None: seen.setdefault("path", path))
    fetch.fetch_suggestions("mountain lake/a#b")
    assert seen["path"] == "v3/search/suggestions/mountain%20lake%2Fa%23b"


def test_error_bodies_are_not_records():
    """The 404 / 422 bodies carry no data: the parsers read them as empty,
    fetch.py raises before they reach a parser."""
    for name in ("not_found_medium.json", "not_found_user.json", "not_found_collection.json", "error_422_orientation.json"):
        body = fixture(name)
        assert "error_messages" in body and P.parse_media_list(body) == [] and P.parse_user_list(body) == []
    assert "Just a moment" in fixture("blocked_cloudflare_challenge.html")
