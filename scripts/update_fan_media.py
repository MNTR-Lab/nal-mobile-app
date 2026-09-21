import os
import json
import urllib.request
import urllib.parse

MONDAY_API_URL = "https://api.monday.com/v2"
BOARD_ID = 18431997692

MEDIA_COLUMN = "filebw4oz6i9"
STATUS_COLUMN = "color_mm7dr2tm"
FEATURED_COLUMN = "color_mm7d8jkj"
DISPLAY_NAME_COLUMN = "text_mm7dmxb7"
DISPLAY_CAPTION_COLUMN = "text_mm7dp2jd"
MEDIA_TYPE_COLUMN = "dropdown_mm7dj1n4"
DATE_COLUMN = "date_mm7dex7q"
PERMISSION_COLUMN = "single_selectjw1o25k"

token = os.environ.get("MONDAY_API_TOKEN")

if not token:
    raise RuntimeError("MONDAY_API_TOKEN is not available.")

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

          column {
            title
            type
          }
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

with urllib.request.urlopen(request) as response:
    result = json.loads(response.read().decode("utf-8"))

if result.get("errors"):
    print(json.dumps(result["errors"], indent=2))
    raise RuntimeError("Monday API returned an error.")

boards = result.get("data", {}).get("boards", [])

if not boards:
    raise RuntimeError(
        f"Board {BOARD_ID} was not returned."
    )

board = boards[0]
items = board.get("items_page", {}).get("items", [])

print("=" * 70)
print("MONDAY FAN MEDIA ASSET TEST")
print("=" * 70)

print(f"\nBOARD: {board['name']}")
print(f"FOUND {len(items)} SUBMISSION(S)")

for item in items:

    values = {
        value["id"]: value
        for value in item.get("column_values", [])
    }

    status = values.get(STATUS_COLUMN, {}).get("text", "")
    permission = values.get(PERMISSION_COLUMN, {}).get("text", "")
    media_type = values.get(MEDIA_TYPE_COLUMN, {}).get("text", "")
    featured = values.get(FEATURED_COLUMN, {}).get("text", "")
    display_name = values.get(DISPLAY_NAME_COLUMN, {}).get("text", "")
    caption = values.get(DISPLAY_CAPTION_COLUMN, {}).get("text", "")
    submission_date = values.get(DATE_COLUMN, {}).get("text", "")

    print("\n" + "=" * 70)
    print(f"ITEM ID: {item['id']}")
    print(f"STATUS: {status}")
    print(f"PERMISSION: {permission}")
    print(f"MEDIA TYPE: {media_type}")
    print(f"FEATURED: {featured}")
    print(f"DISPLAY NAME: {display_name}")
    print(f"CAPTION: {caption}")
    print(f"DATE: {submission_date}")

    assets = item.get("assets", [])

    print(f"\nASSETS FOUND: {len(assets)}")

    for asset in assets:
        print("-" * 50)
        print(f"ASSET ID: {asset.get('id')}")
        print(f"NAME: {asset.get('name')}")
        print(f"EXTENSION: {asset.get('file_extension')}")
        print(f"SIZE: {asset.get('file_size')}")
        print(f"URL: {asset.get('url')}")
        print(f"PUBLIC URL: {asset.get('public_url')}")

print("\n" + "=" * 70)
print("ASSET TEST COMPLETE")
print("=" * 70)
