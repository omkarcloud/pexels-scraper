"""Cache TTL per /pexels/* endpoint (cache.py, keyed on the validated
params). Pexels is a stock-media catalogue: a medium's record changes only
when its owner edits it, counts (views / downloads / likes / followers)
drift by the hour, and the search index gains ~thousands of approved
uploads a day but keeps its ranking for a given query for hours.
"""
from datetime import timedelta

# Search results: the ranking of a query is stable for hours; new uploads
# land at the end of the 480-result window.
SEARCH_CACHE = timedelta(hours=6)
# A photo / video record with its EXIF row, stats and photographer: the
# record is immutable in practice, the counts drift slowly.
MEDIUM_CACHE = timedelta(hours=12)
# Similar media is a model output that changes rarely.
SIMILAR_CACHE = timedelta(hours=24)
# A profile + its stats: follower / view counts move by the hour, nothing
# a client needs fresher than half a day.
USER_CACHE = timedelta(hours=12)
# A photographer's uploads: a new upload appears on page 1 within a day.
USER_MEDIA_CACHE = timedelta(hours=6)
# Follower lists grow slowly and are long; half a day keeps paging cheap.
FOLLOWERS_CACHE = timedelta(hours=12)
# Leaderboards are recomputed by the site a few times a day.
LEADERBOARD_CACHE = timedelta(hours=6)
# Curated collections are edited by staff a few times a week.
COLLECTIONS_CACHE = timedelta(hours=24)
COLLECTION_MEDIA_CACHE = timedelta(hours=12)
# Autocomplete suggestions and trending terms change daily.
SUGGESTIONS_CACHE = timedelta(hours=24)
TRENDING_CACHE = timedelta(hours=6)
# Challenges open and close on a monthly cadence; entry counts drift.
CHALLENGES_CACHE = timedelta(hours=12)
