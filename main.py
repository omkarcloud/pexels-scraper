"""Use the scraper straight from Python — no server needed.

    python main.py

Every function returns the same JSON the API does; results are written to
output/*.json. Params go through the same schemas the API uses, so defaults
are filled in and a media id or link both work.
"""
import json
import os

from pexels import api, schemas

os.makedirs("output", exist_ok=True)


def save(name, data):
    path = os.path.join("output", name)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


def run(schema_cls, fn, **params):
    return fn(**schema_cls().load(params))


if __name__ == "__main__":
    # a photo id or any pexels.com photo link — image sizes, download link, EXIF, views, downloads, photographer
    save("photo_691668.json",
         run(schemas.PhotoSchema, api.photo_details, photo="691668"))

    # 24 photos per page, filter by orientation, size, people, upload date and photographer
    save("search_new_york_city.json",
         run(schemas.PhotosSearchSchema, api.photos_search, query="new york city", orientation="landscape"))

    # a video id or link — every MP4 rendition with its download link, duration, fps and stats
    save("video_2169880.json",
         run(schemas.VideoSchema, api.video_details, video="2169880"))
