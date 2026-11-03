"""Offline tests for the /pexels/* request schemas.

    python -m pytest pexels/test_schemas.py -q
"""
import os
import sys

import pytest
from marshmallow import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pexels import schemas  # noqa: E402

PHOTO_LINK = "https://www.pexels.com/photo/landscape-photography-of-mountains-covered-in-snow-691668/"


def _error(schema, data):
    with pytest.raises(ValidationError) as info:
        schema().load(data)
    return info.value.normalized_messages()


# ---- media refs ----------------------------------------------------------------------------

def test_photo_schema_accepts_id_and_link():
    assert schemas.PhotoSchema().load({"photo": "691668"}) == {"photo": 691668, "locale": "en-us"}
    assert schemas.PhotoSchema().load({"photo": PHOTO_LINK, "locale": "de-DE"}) == {"photo": 691668, "locale": "de-de"}
    assert schemas.VideoSchema().load({"video": "https://www.pexels.com/video/beach-huts-855986/"})["video"] == 855986


@pytest.mark.parametrize("value", ["", "mountain", "https://example.com/photo/691668/"])
def test_photo_schema_rejects(value):
    errors = _error(schemas.PhotoSchema, {"photo": value})
    assert "photo" in errors


def test_photo_schema_rejects_sibling_params():
    errors = _error(schemas.PhotoSchema, {"photo": "691668", "id": "691668"})
    assert "id" in errors
    errors = _error(schemas.PhotoSchema, {"photo": "691668", "url": PHOTO_LINK})
    assert "url" in errors


def test_photo_schema_requires_photo():
    assert "photo" in _error(schemas.PhotoSchema, {})


def test_locale_rejects_unknown():
    errors = _error(schemas.PhotoSchema, {"photo": "691668", "locale": "xx-YY"})
    assert "locale" in errors and "de-DE" in errors["locale"][0]


def test_similar_schema():
    loaded = schemas.PhotoSimilarSchema().load({"photo": "691668", "page": "2", "per_page": "50"})
    assert loaded == {"photo": 691668, "page": 2, "per_page": 50, "locale": "en-us"}
    assert "per_page" in _error(schemas.PhotoSimilarSchema, {"photo": "691668", "per_page": "81"})
    assert "page" in _error(schemas.VideoSimilarSchema, {"video": "855986", "page": "0"})


# ---- search --------------------------------------------------------------------------------

def test_photos_search_defaults():
    loaded = schemas.PhotosSearchSchema().load({"query": " mountain  lake "})
    assert loaded["query"] == "mountain lake" and loaded["page"] == 1 and loaded["locale"] == "en-us"
    assert loaded["orientation"] is None and loaded["user"] is None
    assert loaded["min_width"] is None and loaded["min_height"] is None


def test_photos_search_filters_map_to_site_tokens():
    loaded = schemas.PhotosSearchSchema().load({
        "query": "mountain", "orientation": "Portrait", "size": "LARGE", "people_count": "3+",
        "people_age": "senior_adult", "date_from": "last_week", "min_width": "4000", "min_height": "3000",
        "user": "@eberhardgross", "locale": "de", "page": "20",
    })
    assert loaded["orientation"] == "portrait" and loaded["size"] == "large"
    assert loaded["people_count"] == "3_plus"
    assert loaded["people_age"] == "senior_adult" and loaded["date_from"] == "last_week"
    assert loaded["min_width"] == 4000 and loaded["min_height"] == 3000 and loaded["max_width"] is None
    assert "max_width" in _error(schemas.PhotosSearchSchema, {"query": "x", "min_width": "5000", "max_width": "4000"})
    assert loaded["user"] == "eberhardgross" and loaded["locale"] == "de-de" and loaded["page"] == 20


def test_photos_search_rejections():
    assert "query" in _error(schemas.PhotosSearchSchema, {})
    assert "page" in _error(schemas.PhotosSearchSchema, {"query": "x", "page": "21"})     # the site serves 20 pages
    errors = _error(schemas.PhotosSearchSchema, {"query": "x", "orientation": "wide"})
    assert "landscape" in errors["orientation"][0]
    assert "color" in _error(schemas.PhotosSearchSchema, {"query": "x", "color": "red"})   # the site ignores it; not offered
    assert "people_count" in _error(schemas.PhotosSearchSchema, {"query": "x", "people_count": "5"})
    assert "min_width" in _error(schemas.PhotosSearchSchema, {"query": "x", "min_width": "0"})
    assert "min_duration" in _error(schemas.PhotosSearchSchema, {"query": "x", "min_duration": "5"})   # videos only
    assert "user" in _error(schemas.PhotosSearchSchema, {"query": "x", "user": "https://example.com/@x"})


def test_videos_search_filters():
    loaded = schemas.VideosSearchSchema().load({"query": "ocean", "min_duration": "5", "max_duration": "30",
                                                "frame_rate": "60+", "resolution": "4k"})
    assert loaded["min_duration"] == 5 and loaded["max_duration"] == 30
    assert loaded["frame_rate"] == "60_plus" and loaded["resolution"] == "4K"
    assert "max_duration" in _error(schemas.VideosSearchSchema, {"query": "x", "min_duration": "40", "max_duration": "30"})
    assert "resolution" in _error(schemas.VideosSearchSchema, {"query": "x", "resolution": "720p"})
    assert "min_width" in _error(schemas.VideosSearchSchema, {"query": "x", "min_width": "100"})   # photos only


def test_users_search_and_suggestions():
    assert schemas.UsersSearchSchema().load({"query": "eberhard"}) == {"query": "eberhard", "page": 1}
    assert "query" in _error(schemas.UsersSearchSchema, {"page": "2"})
    assert schemas.SuggestionsSchema().load({"query": "mount"}) == {"query": "mount"}
    assert "query" in _error(schemas.SuggestionsSchema, {"query": "x" * 101})


def test_trending_schema():
    assert schemas.TrendingSchema().load({}) == {"type": "popular", "media_type": None, "country": None}
    loaded = schemas.TrendingSchema().load({"type": "Trending", "media_type": "videos", "country": "br"})
    assert loaded == {"type": "trending", "media_type": "video", "country": "br"}
    assert "country" in _error(schemas.TrendingSchema, {"country": "bra"})
    assert schemas.TrendingSchema().load({"country": ""})["country"] is None     # empty = not given, not a 500
    assert "media_type" in _error(schemas.TrendingSchema, {"media_type": "gifs"})


# ---- users ---------------------------------------------------------------------------------

def test_user_schemas():
    assert schemas.UserSchema().load({"user": "https://www.pexels.com/@pixabay/"}) == {"user": "pixabay"}
    assert schemas.UserSchema().load({"user": "2659"}) == {"user": "2659"}
    assert "user" in _error(schemas.UserSchema, {"user": ""})
    loaded = schemas.UserMediaSchema().load({"user": "@pixabay", "type": "Videos", "sort": "popular"})
    assert loaded == {"user": "pixabay", "type": "videos", "sort": "popular", "page": 1, "per_page": 24, "locale": "en-us"}
    assert "type" in _error(schemas.UserMediaSchema, {"user": "pixabay", "type": "gifs"})
    loaded = schemas.UserFollowersSchema().load({"user": "pixabay", "direction": "following", "per_page": "80"})
    assert loaded["direction"] == "followings" and loaded["per_page"] == 80
    assert "direction" in _error(schemas.UserFollowersSchema, {"user": "pixabay", "direction": "friends"})


def test_leaderboard_schema():
    assert schemas.LeaderboardSchema().load({}) == {"metric": "views", "span": "all_time", "heroes_only": False,
                                                    "page": 1, "per_page": 24}
    loaded = schemas.LeaderboardSchema().load({"metric": "uploads", "span": "last_30_days", "heroes_only": "yes"})
    assert loaded["metric"] == "approved_uploads" and loaded["span"] == "last_30_days" and loaded["heroes_only"] is True
    assert "metric" in _error(schemas.LeaderboardSchema, {"metric": "downloads"})
    assert "heroes_only" in _error(schemas.LeaderboardSchema, {"heroes_only": "maybe"})


# ---- collections / challenges --------------------------------------------------------------

def test_collection_schemas():
    for value in ("cwgidat", "mighty-mountains-cwgidat", "https://www.pexels.com/collections/mighty-mountains-cwgidat/"):
        assert schemas.CollectionSchema().load({"collection": value}) == {"collection": "cwgidat"}
    assert "collection" in _error(schemas.CollectionSchema, {"collection": "https://www.pexels.com/@pixabay/"})
    loaded = schemas.CollectionMediaSchema().load({"collection": "cwgidat", "page": "2"})
    assert loaded == {"collection": "cwgidat", "page": 2, "per_page": 24, "locale": "en-us"}
    assert schemas.CollectionsListSchema().load({}) == {"page": 1, "per_page": 24}
    assert schemas.ChallengesListSchema().load({"per_page": "10"}) == {"page": 1, "per_page": 10}
    assert "per_page" in _error(schemas.ChallengesListSchema, {"per_page": "0"})


def test_every_field_is_documented():
    for name in dir(schemas):
        cls = getattr(schemas, name)
        if isinstance(cls, type) and issubclass(cls, schemas.BaseSchema) and cls is not schemas.BaseSchema:
            for field_name, field in cls().fields.items():
                assert field.metadata.get("description"), f"{name}.{field_name} has no description"
