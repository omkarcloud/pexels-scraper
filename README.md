# 📸 Pexels Scraper

Pexels Scraper is a **free and open-source** scraper that gets you **unlimited** detailed Pexels data for free.

## ✨ What Can I Get?

- 📸 **Full details on 1M+ royalty-free photos & videos** — download links, every 4K/HD MP4, EXIF camera data, tags, colors, views & downloads
- 🔍 **Search with 10 filters** — orientation, size, people, age, upload date, photographer, dimensions, length, frame rate & 4K
- 👩‍🎨 **600K+ creators** — profiles, socials, hero badges, follower counts, total views, downloads & every upload
- 🗂️ **1,150+ curated collections** — plus trending searches, the photographer leaderboard & photo challenges

## 🎥 Example: A Full Pexels Photo

```json
{
  "id": 691668,
  "type": "photo",
  "title": "Landscape Photography of Mountains Covered in Snow",
  "link": "https://www.pexels.com/photo/landscape-photography-of-mountains-covered-in-snow-691668/",
  "description": "A breathtaking view of snow-covered mountain peaks surrounded by dense fog, creating a mystical landscape.",
  "width": 5472,
  "height": 3648,
  "orientation": "landscape",
  "license": "Pexels",
  "tags": ["Misty Mountains", "Foggy Mountain", "Snow Mountain"],
  "colors": ["#2f4f4f", "#a9a9a9"],
  "image": {
    "large": "https://images.pexels.com/photos/691668/pexels-photo-691668.jpeg?auto=compress&cs=tinysrgb&w=1440",
    "original": "https://images.pexels.com/photos/691668/pexels-photo-691668.jpeg"
  },
  "download_link": "https://images.pexels.com/photos/691668/pexels-photo-691668.jpeg?cs=srgb&dl=pexels-eberhardgross-691668.jpg&fm=jpg",
  "stats": { "views": 243123544, "downloads": 1796416, "likes": 7236 },
  "camera": { "model": "Canon EOS 70D", "aperture": "8.0", "focal_length": "48.0", "iso": 160, "shutter_speed": "1/640" },
  "file_size_bytes": 13429458,
  "photographed_at": "2017-09-12T16:20:46Z",
  "photographer": {
    "id": 121938,
    "name": "eberhard grossgasteiger",
    "link": "https://www.pexels.com/@eberhardgross/",
    "is_hero": true,
    "socials": { "instagram": "eberhard_grossgasteiger" },
    "counts": { "photos": 1748, "followers": 66376 },
    "stats": { "views": 10223020084, "downloads": 45476902, "likes": 376069 },
    "leaderboard": { "all_time_position": 2 }
  },
  "created_at": "2017-11-17T10:51:26Z"
}
```

*Trimmed for readability.*

## 🚀 Unlimited Free Pexels Data — Get It in 60 Seconds

1️⃣ Clone and install:
```bash
git clone https://github.com/omkarcloud/pexels-scraper
cd pexels-scraper
python -m pip install -r requirements.txt
```

2️⃣ Start the API:
```bash
python run.py
```

3️⃣ Get your first data:
```bash
curl "http://localhost:8000/photos/details?photo=691668"
```

```json
{
  "id": 691668,
  "type": "photo",
  "title": "Landscape Photography of Mountains Covered in Snow",
  "link": "https://www.pexels.com/photo/landscape-photography-of-mountains-covered-in-snow-691668/",
  "width": 5472,
  "height": 3648,
  "license": "Pexels",
  "tags": ["Misty Mountains", "Foggy Mountain", "Foggy Mountains", "Mountain Clouds"],
  "download_link": "https://images.pexels.com/photos/691668/pexels-photo-691668.jpeg?cs=srgb&dl=pexels-eberhardgross-691668.jpg&fm=jpg",
  "stats": { "views": 243123544, "downloads": 1796416, "likes": 7236 },
  "camera": { "model": "Canon EOS 70D", "aperture": "8.0", "focal_length": "48.0", "iso": 160, "shutter_speed": "1/640" },
  "photographer": {
    "name": "eberhard grossgasteiger",
    "link": "https://www.pexels.com/@eberhardgross/"
  }
}
```

All 17 endpoints are now live at `http://localhost:8000`.

## 📚 Endpoints

17 endpoints cover everything you need.

| Endpoint | Path | Returns |
|---|---|---|
| Photo & Video Details | `/photos/details` · `/videos/details` | Everything about one photo or video, with views, downloads and EXIF |
| Search Suggestions | `/search/suggestions` | Typeahead terms exactly as the Pexels search bar suggests them |
| Search Photos & Videos | `/photos/search` · `/videos/search` | 24 per page; filter by orientation, size, people, length, 4K |
| Similar Photos & Videos | `/photos/similar` · `/videos/similar` | Up to 1,000 lookalikes for any photo or video |
| Search Photographers | `/users/search` | Photographers by name with socials, follower counts and previews |
| Photographer Details | `/users/details` | Bio, socials, hero badges, total views, downloads and likes |
| Photographer Media | `/users/media` | Every photo and video they uploaded, newest or most popular |
| Photographer Followers | `/users/followers` | Who follows them, or who they follow, with full profiles |
| Photographer Leaderboard | `/users/leaderboard` | Top photographers by views or uploads, all time or 30 days |
| Featured Collections | `/collections/list` | 1,150+ curated collections with counts and preview images |
| Collection Details | `/collections/details` | Title, description, photo and video counts, curators and tags |
| Collection Media | `/collections/media` | Every photo and video in a collection, with download links |
| Trending Searches | `/search/trending` | Popular and trending search terms, worldwide or per country |
| Photo Challenges | `/challenges/list` | Prizes, deadlines, entry counts, winners and featured shots |

## 🔍 Exploring Parameters

The same API is published on RapidAPI, and its playground is the easiest place to try parameters and see raw responses. Once a request looks right, run it locally for **unlimited free** data.

1. [Subscribe to the free plan](https://rapidapi.com/OmkarCloud/api/best-pexels-scraper-free-1000-calls/pricing) — 1,000 calls/month, no credit card.
2. [Try the endpoints in the playground](https://rapidapi.com/OmkarCloud/api/best-pexels-scraper-free-1000-calls/playground) — every param is pre-filled, so you see real data in one click.
3. Copy the generated code and replace `https://best-pexels-scraper-free-1000-calls.p.rapidapi.com` with `http://localhost:8000`. It will now run against your local API.

```python
import requests

# generated by the playground, host swapped for the local API
response = requests.get(
    "http://localhost:8000/photos/search",
    params={"query": "new york city", "orientation": "landscape", "size": "large"},
)
print(response.json())
```

## 💬 Have Questions? We Have Answers.

You're a developer — we know how hard completing a project can be. So we offer full support: just message us and we'll reply ✅ with a solution within 1 working day.

[![Message Us on WhatsApp about Pexels Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/whatsapp-us.png)](https://api.whatsapp.com/send?phone=918178804274&text=I%20need%20help%20using%20the%20Pexels%20Scraper%20API.)

[![Ask Us by Email about Pexels Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/ask-on-email.png)](mailto:happy.to.help@omkar.cloud?subject=Help%20with%20Pexels%20Scraper%20API&body=I%20need%20help%20using%20the%20Pexels%20Scraper%20API.)

## ⚡ Popular Scrapers by Omkar Cloud

- [**Google Maps Scraper (3,100+ GitHub Stars)**](https://github.com/omkarcloud/google-maps-scraper) — type "dentists in New York", get every business as a ready-to-call lead list: phones, emails, websites & reviews. Up to 100K free leads/month.
- [**G2 Scraper**](https://www.omkar.cloud/tools/g2-scraper) — G2 product details, ratings & AI-found contacts
- [**Website Email Contact Scraper**](https://www.omkar.cloud/tools/website-email-contact-scraper) — emails, phones & socials from any website
- [**AliExpress Scraper**](https://www.omkar.cloud/tools/aliexpress-scraper-api) — live product details, SKU variants, stock & shipping
- [**Booking Scraper**](https://www.omkar.cloud/tools/booking-scraper) — Booking.com hotels: prices, ratings, rooms & amenities
- [**Etsy Scraper**](https://www.omkar.cloud/tools/etsy-scraper) — Etsy products: prices, discounts, shops & variations

## ⭐ Love It? [Star It ⭐!](https://github.com/omkarcloud/pexels-scraper)

Star the repo ⭐ and become my star hero!

It's just 1 click, but it means the world to me.

[![Star us on GitHub](https://raw.githubusercontent.com/omkarcloud/google-maps-scraper/master/screenshots/star-us.png)](https://github.com/omkarcloud/pexels-scraper)
