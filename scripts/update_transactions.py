import html
import json
import os
import re
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
# DIGITALSHIFT AUTHORIZATION
# ============================================================

DIGITALSHIFT_AUTH_TICKET = os.environ.get(
    "DIGITALSHIFT_AUTH_TICKET"
)

if not DIGITALSHIFT_AUTH_TICKET:
    raise RuntimeError(
        "DIGITALSHIFT_AUTH_TICKET environment variable is missing."
    )


# ============================================================
# REQUEST SESSION
# ============================================================

session = requests.Session()

session.headers.update(
    {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f'ticket="{DIGITALSHIFT_AUTH_TICKET}"',
        "Origin": "https://www.thenationalarenaleague.com",
        "Referer": "https://www.thenationalarenaleague.com/",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/153.0.0.0 Safari/537.36"
        ),
    }
)


# ============================================================
# FETCH DIGITALSHIFT
# ============================================================

def fetch_transaction_page(start_id=None, offset=None):
    """
    Fetch one DigitalShift transaction response.
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

    if response.status_code != 200:
        print(
            f"DigitalShift returned HTTP "
            f"{response.status_code}"
        )
        print(response.text[:500])

    response.raise_for_status()

    return response.json()


# ============================================================
# EXTRACT TRANSACTIONS
# ============================================================

def extract_transactions(payload):
    """
    DigitalShift uses two response formats.

    Initial request:
        {
            "content": "<HTML containing ng-init='ctrl.txns = [...]'>"
        }

    Infinite-scroll requests:
        {
            "transactions": [...]
        }

    This function handles both.
    """

    # --------------------------------------------------------
    # FORMAT 1:
    # Clean infinite-scroll JSON
    # --------------------------------------------------------

    transactions = payload.get("transactions")

    if isinstance(transactions, list):
        return transactions

    # --------------------------------------------------------
    # FORMAT 2:
    # Initial page HTML inside "content"
    # --------------------------------------------------------

    content = payload.get("content")

    if not isinstance(content, str):
        return []

    # Convert HTML entities such as &quot; back to quotes.
    decoded = html.unescape(content)

    # We previously confirmed DigitalShift initializes the
    # transaction table using:
    #
    # ctrl.txns = [...]
    #
    # inside an ng-init attribute.
    marker = "ctrl.txns"

    marker_position = decoded.find(marker)

    if marker_position == -1:
        print(
            "Could not locate ctrl.txns in "
            "DigitalShift initial response."
        )
        return []

    # Find the "=" following ctrl.txns
    equals_position = decoded.find(
        "=",
        marker_position
    )

    if equals_position == -1:
        return []

    # Find beginning of JSON array.
    array_start = decoded.find(
        "[",
        equals_position
    )

    if array_start == -1:
        return []

    # --------------------------------------------------------
    # Locate the matching closing bracket.
    #
    # We cannot simply regex .*? because descriptions or
    # embedded JSON may contain brackets or quoted text.
    # --------------------------------------------------------

    depth = 0
    in_string = False
    escape_next = False
    array_end = None

    for index in range(
        array_start,
        len(decoded)
    ):

        char = decoded[index]

        if escape_next:
            escape_next = False
            continue

        if char == "\\" and in_string:
            escape_next = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "[":
            depth += 1

        elif char == "]":
            depth -= 1

            if depth == 0:
                array_end = index + 1
                break

    if array_end is None:
        print(
            "Could not locate end of "
            "DigitalShift transaction array."
        )
        return []

    raw_json = decoded[
        array_start:array_end
    ]

    try:
        transactions = json.loads(raw_json)

    except json.JSONDecodeError as error:
        print(
            "Unable to decode initial "
            "DigitalShift transaction JSON."
        )
        print(error)
        print(raw_json[:1000])
        return []

    if not isinstance(transactions, list):
        return []

    return transactions


# ============================================================
# NORMALIZE TRANSACTION
# ============================================================

def normalize_transaction(txn):
    """
    Preserve DigitalShift data in a predictable structure
    for the NAL app.
    """

    team = txn.get("team") or {}
    person = txn.get("person") or {}
    coach = txn.get("coach") or {}
    traded_team = txn.get("traded_team") or {}

    normalized = {
        "id": txn.get("id"),
        "date": txn.get("date"),
        "description": txn.get("description"),

        "team": {
            "id": team.get("id"),
            "name": team.get("name"),
            "logo": team.get("logo"),
        } if team else None,

        "person": {
            "id": person.get("id"),
            "name": person.get("name"),
        } if person else None,

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

    return normalized


# ============================================================
# MAIN
# ============================================================

def main():

    print("==========================================")
    print("NAL TRANSACTION UPDATE")
    print("==========================================")

    all_transactions = []
    seen_ids = set()

    # ========================================================
    # PAGE 1
    # ========================================================

    print()
    print("--- Initial Page ---")

    payload = fetch_transaction_page()

    transactions = extract_transactions(
        payload
    )

    print(
        f"Initial page returned "
        f"{len(transactions)} transactions."
    )

    if not transactions:
        raise RuntimeError(
            "DigitalShift returned no transactions "
            "from the initial transaction table."
        )

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

    # ========================================================
    # PAGINATION
    # ========================================================

    #
    # DigitalShift's infinite-scroll request observed in
    # DevTools uses:
    #
    # start_id=<transaction id>
    # offset=<page offset>
    # limit=25
    #

    last_transaction = transactions[-1]

    start_id = last_transaction.get("id")

    offset = 1

    page_number = 2

    while (
        start_id is not None
        and len(transactions) >= LIMIT
    ):

        print()
        print(f"--- Page {page_number} ---")

        payload = fetch_transaction_page(
            start_id=start_id,
            offset=offset,
        )

        transactions = extract_transactions(
            payload
        )

        if not transactions:
            print(
                "No additional transactions returned."
            )
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
            f"Received {len(transactions)} "
            f"transactions "
            f"({new_count} new)."
        )

        # ----------------------------------------------------
        # If the API gives us records but every record was
        # already seen, stop rather than loop forever.
        # ----------------------------------------------------

        if new_count == 0:
            print(
                "No new transaction IDs returned. "
                "Pagination complete."
            )
            break

        # ----------------------------------------------------
        # Fewer than 25 means final page.
        # ----------------------------------------------------

        if len(transactions) < LIMIT:
            print(
                "Reached final transaction page."
            )
            break

        next_start_id = (
            transactions[-1].get("id")
        )

        if next_start_id is None:
            print(
                "Unable to determine next start_id."
            )
            break

        # Prevent accidental pagination loop.
        if next_start_id == start_id:
            print(
                "DigitalShift returned the same "
                "pagination anchor. Stopping."
            )
            break

        start_id = next_start_id
        offset += 1
        page_number += 1

        time.sleep(0.25)

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
        f"Saved {len(all_transactions)} "
        f"transactions to {OUTPUT_FILE}"
    )
    print("==========================================")


if __name__ == "__main__":
    main()
