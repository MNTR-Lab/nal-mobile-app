import os
import json
import urllib.request

MONDAY_API_URL = "https://api.monday.com/v2"
BOARD_ID = 18431997692

token = os.environ.get("MONDAY_API_TOKEN")

if not token:
    raise RuntimeError("MONDAY_API_TOKEN is not available.")

query = """
query ($boardId: [ID!]) {
  boards(ids: $boardId) {
    id
    name

    columns {
      id
      title
      type
    }

    items_page(limit: 25) {
      items {
        id
        name

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
        f"Board {BOARD_ID} was not returned. Check board access."
    )

board = boards[0]

print("=" * 70)
print("MONDAY CONNECTION SUCCESSFUL")
print("=" * 70)

print(f"\nBOARD: {board['name']}")
print(f"BOARD ID: {board['id']}")

print("\n--- COLUMNS ---")

for column in board.get("columns", []):
    print(
        f"{column['title']} | "
        f"ID: {column['id']} | "
        f"TYPE: {column['type']}"
    )

print("\n--- SUBMISSIONS ---")

items = board.get("items_page", {}).get("items", [])

print(f"FOUND {len(items)} SUBMISSION(S)\n")

for item in items:
    print("=" * 70)
    print(f"ITEM: {item['name']}")
    print(f"ITEM ID: {item['id']}")

    for value in item.get("column_values", []):
        title = value.get("column", {}).get("title", value["id"])
        text = value.get("text") or ""

        print(f"{title}: {text}")

print("\nTEST COMPLETE")
