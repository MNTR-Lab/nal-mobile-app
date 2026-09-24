import json
import time
from pathlib import Path

import requests


# ============================================================
# NAL / DIGITALSHIFT SETTINGS
# ============================================================

LEAGUE_ID = 1200
DIVISION_ID = 41958
SEASON_ID = 9264

LIMIT = 25

BASE_URL = (
    "https://web.api.digitalshift.ca/"
    "partials/stats/transactions/table"
)

OUTPUT_FILE = Path("data/transactions.json")


# ============================================================
# REQUEST SESSION
# ============================================================

session = requests.Session()

session.headers.update(
    {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "NAL-Mobile-App/1.0",
    }
)


def fetch_transaction_page(start_id=None, offset=None):
    """
    Fetch one page of NAL transactions from DigitalShift.
    """

    params = {
        "division_id": DIVISION_ID,
        "season_id": SEASON_ID,
        "league_id": LEAGUE_ID,
        "limit": LIMIT,
    }

    if start_id is not None:
        params["start_id"] = start_id

    if offset is not None:
        params["offset"] = offset

    print(f"Fetching transactions: {params}")

    response = session.get(
        BASE_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def normalize_transaction(txn):
    """
    Preserve the useful DigitalShift fields while creating
    a predictable structure for the NAL app.
    """

    team = txn.get("team") or {}
    person = txn.get("person") or {}
    coach = txn.get("coach") or {}
    traded_team = txn.get("traded_team") or {}

    return {
        "id": txn.get("id"),
        "date": txn.get("date"),
        "description": txn.get("description"),

        "team": {
            "id": team.get("id"),
            "name": team.get("name"),
            "logo": team.get("logo"),
        },

        "person": {
            "id": person.get("id"),
            "name": person.get("name"),
        },

        "coach": {
            "id": coach.get("id"),
            "name": coach.get("name"),
        } if coach else None,

        "traded_team": {
            "id": traded_team.get("id"),
            "name": traded_team.get("name"),
            "logo": traded_team.get("logo"),
        } if traded_team else None,
    }


def main():

    print("==========================================")
    print("NAL TRANSACTION UPDATE")
    print("==========================================")

    all_transactions = []
    seen_ids = set()

    start_id = None
    offset = None
    page_number = 1

    while True:

        print()
        print(f"--- Page {page_number} ---")

        payload = fetch_transaction_page(
            start_id=start_id,
            offset=offset,
        )

        transactions = payload.get("transactions", [])

        if not transactions:
            print("No additional transactions returned.")
            break

        new_count = 0

        for txn in transactions:

            txn_id = txn.get("id")

            if txn_id is None:
                continue

            if txn_id in seen_ids:
                continue

            seen_ids.add(txn_id)

            all_transactions.append(
                normalize_transaction(txn)
            )

            new_count += 1

        print(
            f"Received {len(transactions)} transactions "
            f"({new_count} new)."
        )

        # ----------------------------------------------------
        # If DigitalShift returns fewer than LIMIT records,
        # we have reached the end.
        # ----------------------------------------------------

        if len(transactions) < LIMIT:
            print("Reached final transaction page.")
            break

        # ----------------------------------------------------
        # DigitalShift infinite-scroll pagination
        #
        # The browser uses the final transaction ID from the
        # previous batch as start_id and increments offset.
        # ----------------------------------------------------

        last_transaction = transactions[-1]

        next_start_id = last_transaction.get("id")

        if not next_start_id:
            print("Unable to determine next start_id.")
            break

        start_id = next_start_id

        if offset is None:
            offset = 1
        else:
            offset += 1

        page_number += 1

        # Small delay so we do not hammer DigitalShift.
        time.sleep(0.25)

        # Safety guard.
        if page_number > 100:
            raise RuntimeError(
                "Pagination exceeded 100 pages. "
                "Stopping to prevent an infinite loop."
            )

    # ========================================================
    # SORT NEWEST FIRST
    # ========================================================

    all_transactions.sort(
        key=lambda txn: (
            txn.get("date") or "",
            txn.get("id") or 0,
        ),
        reverse=True,
    )

    # ========================================================
    # BUILD FINAL JSON
    # ========================================================

    output = {
        "league_id": LEAGUE_ID,
        "division_id": DIVISION_ID,
        "season_id": SEASON_ID,
        "count": len(all_transactions),
        "transactions": all_transactions,
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("==========================================")
    print(
        f"Saved {len(all_transactions)} transactions "
        f"to {OUTPUT_FILE}"
    )
    print("==========================================")


if __name__ == "__main__":
    main()
