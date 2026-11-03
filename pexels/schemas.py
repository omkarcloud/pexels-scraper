"""Marshmallow request schemas for every /pexels/* route.

ONE param per input (tripadvisor QueryOrIdField convention, never a sibling
`url`/`id` pair; pexels/refs.py resolves):

    photo / video   a media id (691668) OR any pexels.com photo / video link
    user            a user id, @handle, profile slug OR a profile link
    collection      a collection id, slug OR a /collections/ link
    query           free text (search) / a prefix (suggestions)
    locale          a pexels.com UI locale (de-DE, pt-BR, …): localizes the
                    titles, tags and slugs of media

Search filters are the site's own (pexels/refs.py vocabularies): photos and
videos share orientation / size / people_count / people_age /
date_from / user; photos add min_width / min_height, videos add
min_duration / max_duration (seconds) / frame_rate / resolution. The site
serves 24 results a page and 20 pages per query (480 results), so `page`
is capped at 20 there; every other list takes per_page up to 80.

Every field carries a `description` because it becomes the public docs.
"""
import re

from marshmallow import ValidationError, validates, validates_schema

from schema_fields import (BaseSchema, ChoiceField, Flag, PageField, PageSizeField, PositiveInt,
                           QueryField, RefField, StrippedString)
from pexels import refs


class PhotoRefField(RefField):
    resolver = staticmethod(refs.resolve_photo)


class VideoRefField(RefField):
    resolver = staticmethod(refs.resolve_video)


class UserRefField(RefField):
    resolver = staticmethod(refs.resolve_user)


class CollectionRefField(RefField):
    resolver = staticmethod(refs.resolve_collection)


class LocaleField(StrippedString):
    """A pexels.com UI locale ("de-DE", "de", "pt-BR") -> the API prefix ("de-de")."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", refs.API_LOCALE_DEFAULT)
        kwargs.setdefault("metadata", {"description": (
            "language of titles, tags and slugs: a pexels.com locale such as de-DE, pt-BR, "
            "ja-JP or just the language (de); default en-US")})
        super().__init__(**kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)
        if value is None:
            return refs.API_LOCALE_DEFAULT
        try:
            return refs.resolve_locale(value)
        except ValueError as e:
            raise ValidationError(str(e))


def _page(max_page=1000, description="1-based page"):
    return PageField(max_page=max_page, metadata={"description": description})


def _per_page(default=24, description="results per page (max 80)"):
    return PageSizeField(default=default, max_size=refs.LIST_MAX_PAGE_SIZE, metadata={"description": description})


# ---- search ---------------------------------------------------------------------------------


class _SearchSchema(BaseSchema):
    query = QueryField(metadata={"description": "what to search for, e.g. mountain lake, coffee shop"})
    page = _page(refs.SEARCH_MAX_PAGES, "1-based page of 24 results; the site serves 20 pages (480 results) per query")
    orientation = ChoiceField(list(refs.ORIENTATIONS), metadata={"description": "landscape, portrait or square"})
    size = ChoiceField(list(refs.SIZES), metadata={"description": (
        "minimum original size: small (4 MP photos / SD videos), medium (12 MP / HD), large (24 MP / 4K)")})
    people_count = ChoiceField(dict(refs.PEOPLE_COUNTS), metadata={"description": "people in frame: 0, 1, 2 or 3+"})
    people_age = ChoiceField(list(refs.PEOPLE_AGES), metadata={"description": (
        "age group of the people shown: baby, child, teenager, adult or senior_adult")})
    date_from = ChoiceField(list(refs.DATE_FROM), metadata={"description": (
        "uploaded within: last_24_hours, last_week, last_month or last_year")})
    user = UserRefField(required=False, load_default=None, metadata={"description": (
        "only this photographer's media: a user id, @handle, profile slug or profile link")})
    locale = LocaleField()


class PhotosSearchSchema(_SearchSchema):
    min_width = PositiveInt(max_value=50000, metadata={"description": "minimum width in pixels"})
    max_width = PositiveInt(max_value=50000, metadata={"description": "maximum width in pixels"})
    min_height = PositiveInt(max_value=50000, metadata={"description": "minimum height in pixels"})
    max_height = PositiveInt(max_value=50000, metadata={"description": "maximum height in pixels"})

    @validates_schema
    def _ranges_in_order(self, data, **kwargs):
        for lo_key, hi_key in (("min_width", "max_width"), ("min_height", "max_height")):
            lo, hi = data.get(lo_key), data.get(hi_key)
            if lo is not None and hi is not None and lo > hi:
                raise ValidationError(f"{lo_key} must not exceed {hi_key}.", hi_key)


class VideosSearchSchema(_SearchSchema):
    min_duration = PositiveInt(max_value=3600, metadata={"description": "minimum length in seconds"})
    max_duration = PositiveInt(max_value=3600, metadata={"description": "maximum length in seconds (the site caps the filter at 120)"})
    frame_rate = ChoiceField(dict(refs.FRAME_RATES), metadata={"description": "frames per second: 24, 25, 30, 50 or 60+"})
    resolution = ChoiceField({"1080p": "1080p", "4k": "4K", "8k": "8K"}, metadata={"description": "1080p, 4K or 8K"})

    @validates_schema
    def _duration_order(self, data, **kwargs):
        lo, hi = data.get("min_duration"), data.get("max_duration")
        if lo is not None and hi is not None and lo > hi:
            raise ValidationError("min_duration must not exceed max_duration.", "max_duration")


class UsersSearchSchema(BaseSchema):
    query = QueryField(metadata={"description": "photographer name or handle to search for"})
    page = _page(1000, "1-based page of 24 photographers")


class SuggestionsSchema(BaseSchema):
    query = QueryField(max_length=100, metadata={"description": "the first letters of a search term, e.g. mount"})


class TrendingSchema(BaseSchema):
    type = ChoiceField(list(refs.TRENDING_TYPES), load_default="popular", metadata={"description": (
        "popular (the all-time top searches, default) or trending (rising this week)")})
    media_type = ChoiceField(dict(refs.TRENDING_MEDIA_TYPES), metadata={"description": "photos or videos; default both"})
    country = StrippedString(required=False, load_default=None,
                             metadata={"description": "2-letter country code for that country's trending terms (br, in, de, …)"})

    @validates("country")
    def _country_code(self, value, **kwargs):
        # StrippedString turns "" into None, which a Regexp validator would
        # choke on (TypeError -> HTML 500); None simply means "not given"
        if value is not None and not re.fullmatch(r"[A-Za-z]{2}", value):
            raise ValidationError("Must be a 2-letter ISO country code (br, in, de, ...).")


# ---- media ----------------------------------------------------------------------------------


class PhotoSchema(BaseSchema):
    photo = PhotoRefField(metadata={"description": "photo id (691668) or a pexels.com photo link"})
    locale = LocaleField()


class VideoSchema(BaseSchema):
    video = VideoRefField(metadata={"description": "video id (855986) or a pexels.com video link"})
    locale = LocaleField()


class PhotoSimilarSchema(BaseSchema):
    photo = PhotoRefField(metadata={"description": "photo id (691668) or a pexels.com photo link"})
    page = _page(200)
    per_page = _per_page()
    locale = LocaleField()


class VideoSimilarSchema(BaseSchema):
    video = VideoRefField(metadata={"description": "video id (855986) or a pexels.com video link"})
    page = _page(200)
    per_page = _per_page()
    locale = LocaleField()


# ---- users ----------------------------------------------------------------------------------


class UserSchema(BaseSchema):
    user = UserRefField(metadata={"description": "user id (121938), @handle, profile slug or a pexels.com profile link"})


class UserMediaSchema(BaseSchema):
    user = UserRefField(metadata={"description": "user id (121938), @handle, profile slug or a pexels.com profile link"})
    type = ChoiceField(list(refs.USER_MEDIA_TYPES), load_default="all", metadata={"description": "photos, videos or all (default)"})
    sort = ChoiceField(dict(refs.USER_MEDIA_SORTS), load_default="recent", metadata={"description": "recent (default) or popular"})
    page = _page(5000)
    per_page = _per_page()
    locale = LocaleField()


class UserFollowersSchema(BaseSchema):
    user = UserRefField(metadata={"description": "user id (121938), @handle, profile slug or a pexels.com profile link"})
    direction = ChoiceField(dict(refs.FOLLOW_DIRECTIONS), load_default="followers", metadata={"description": (
        "followers (who follows this user, default) or following (who this user follows)")})
    page = _page(50000)
    per_page = _per_page()


class LeaderboardSchema(BaseSchema):
    metric = ChoiceField(dict(refs.LEADERBOARD_METRICS), load_default="views", metadata={"description": (
        "views (default) or uploads (approved uploads)")})
    span = ChoiceField(list(refs.LEADERBOARD_SPANS), load_default="all_time", metadata={"description": "all_time (default) or last_30_days"})
    heroes_only = Flag(load_default=False, metadata={"description": "true: only Pexels Heroes"})
    page = _page(50000)
    per_page = _per_page()


# ---- collections / challenges ---------------------------------------------------------------


class CollectionsListSchema(BaseSchema):
    page = _page(1000)
    per_page = _per_page()


class CollectionSchema(BaseSchema):
    collection = CollectionRefField(metadata={"description": (
        "collection id (cwgidat), its slug (mighty-mountains-cwgidat) or a pexels.com collection link")})


class CollectionMediaSchema(BaseSchema):
    collection = CollectionRefField(metadata={"description": (
        "collection id (cwgidat), its slug (mighty-mountains-cwgidat) or a pexels.com collection link")})
    page = _page(1000)
    per_page = _per_page()
    locale = LocaleField()


class ChallengesListSchema(BaseSchema):
    page = _page(1000)
    per_page = _per_page()
