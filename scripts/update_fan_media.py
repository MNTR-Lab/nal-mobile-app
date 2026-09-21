import os
import json
import urllib.request
from pathlib import Path

MONDAY_API_URL = "https://api.monday.com/v2"
BOARD_ID = 18431997692

STATUS_COLUMN = "color_mm7dr2tm"
FEATURED_COLUMN = "color_mm7d8jkj"
DISPLAY_NAME_COLUMN = "text_mm7dmxb7"
DISPLAY_CAPTION_COLUMN = "text_mm7dp2jd"
MEDIA_TYPE_COLUMN = "dropdown_mm7dj1n4"
DATE_COLUMN = "date_mm7dex7q"
PERMISSION_COLUMN = "single_selectjw1o25k"

ASSET_DIR = Path("assets/fan-media")
DATA_DIR = Path("data")
JSON_FILE = DATA_DIR / "fan-media.json"

token = os.environ.get("MONDAY_API_TOKEN")

if not token:
    raise RuntimeError("MONDAY_API_TOKEN is not available.")

ASSET_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

query = """
query ($boardId: [ID!]) {
  boards(ids: $boardId) {
    id
    name

    items_page(limit: 100) {
      items {
        id
        name

        assets {
          id
          name
          url
          public_url
          file_extension
          file_size
        }

        column_values {
          id
          text
          value
        }
      }
    }
  }
}
"""

payload = json.dumps({
    "query": query,
    "variables": {
        "boardId": [str(BOARD_ID)]
    }
}).encode("utf-8")

request = urllib.request.Request(
    MONDAY_API_URL,
    data=payload,
    headers={
        "Authorization": token,
        "Content-Type": "application/json",
        "API-Version": "2025-04"
    },
    method="POST"
)

with urllib.request.urlopen(request, timeout=30) as response:
    result = json.loads(response.read().decode("utf-8"))

if result.get("errors"):
    print(json.dumps(result["errors"], indent=2))
    raise RuntimeError("Monday API returned an error.")

boards = result.get("data", {}).get("boards", [])

if not boards:
    raise RuntimeError(f"Board {BOARD_ID} was not returned.")

board = boards[0]
items = board.get("items_page", {}).get("items", [])

public_media = []
active_files = set()

print("=" * 70)
print("NAL FAN MEDIA PUBLISHER")
print("=" * 70)
print(f"BOARD: {board['name']}")
print(f"SUBMISSIONS FOUND: {len(items)}")

for item in items:

    values = {
        value["id"]: value
        for value in item.get("column_values", [])
    }

    status = (
        values.get(STATUS_COLUMN, {}).get("text", "") or ""
    ).strip()

    permission = (
        values.get(PERMISSION_COLUMN, {}).get("text", "") or ""
    ).strip()

    # Only approved submissions with permission can be public.
    if status.lower() != "approved":
        print(f"SKIPPING {item['id']} — status is {status or 'blank'}")
        continue

    if permission.lower() != "yes":
        print(f"SKIPPING {item['id']} — permission is not Yes")
        continue

    assets = item.get("assets", [])

    if not assets:
        print(f"SKIPPING {item['id']} — no media asset")
        continue

    display_name = (
        values.get(DISPLAY_NAME_COLUMN, {}).get("text", "") or ""
    ).strip()

    caption = (
        values.get(DISPLAY_CAPTION_COLUMN, {}).get("text", "") or ""
    ).strip()

    media_type = (
        values.get(MEDIA_TYPE_COLUMN, {}).get("text", "") or ""
    ).strip()

    featured = (
        values.get(FEATURED_COLUMN, {}).get("text", "") or ""
    ).strip()

    submission_date = (
        values.get(DATE_COLUMN, {}).get("text", "") or ""
    ).strip()

    # A submission may contain more than one uploaded file.
    for asset_index, asset in enumerate(assets):

        asset_id = str(asset.get("id", "")).strip()
        public_url = asset.get("public_url")

        if not asset_id or not public_url:
            print(
                f"SKIPPING ASSET ON {item['id']} — "
                "missing asset ID or public URL"
            )
            continue

        extension = (
            asset.get("file_extension")
            or Path(asset.get("name", "")).suffix
            or ""
        )

        if extension and not extension.startswith("."):
            extension = "." + extension

        # Safe, stable filename based on Monday IDs.
        filename = f"{item['id']}-{asset_id}{extension.lower()}"
        local_path = ASSET_DIR / filename
        relative_path = f"assets/fan-media/{filename}"

        active_files.add(filename)

        # Do not download the same asset every workflow run.
        if not local_path.exists():
            print(f"DOWNLOADING: {asset.get('name')}")

            download_request = urllib.request.Request(
                public_url,
                headers={
                    "User-Agent": "NAL-Fan-Media-Publisher/1.0"
                }
            )

            with urllib.request.urlopen(
                download_request,
                timeout=120
            ) as response:
                local_path.write_bytes(response.read())

            print(f"SAVED: {relative_path}")

        else:
            print(f"ALREADY SAVED: {relative_path}")

        # Never include email or private submission information here.
        public_media.append({
            "id": str(item["id"]),
            "assetId": asset_id,
            "type": media_type,
            "name": display_name,
            "caption": caption,
            "featured": featured,
            "date": submission_date,
            "media": relative_path
        })

# Remove local media that is no longer approved/publishable.
for existing_file in ASSET_DIR.iterdir():
    if (
        existing_file.is_file()
        and existing_file.name != ".gitkeep"
        and existing_file.name not in active_files
    ):
        print(f"REMOVING: {existing_file}")
        existing_file.unlink()

# Newest submissions first.
public_media.sort(
    key=lambda entry: entry.get("date", ""),
    reverse=True
)

with JSON_FILE.open("w", encoding="utf-8") as file:
    json.dump(
        public_media,
        file,
        indent=2,
        ensure_ascii=False
    )
    file.write("\n")

print("=" * 70)
print(f"PUBLISHED MEDIA ITEMS: {len(public_media)}")
print(f"JSON CREATED: {JSON_FILE}")
print("=" * 70)
