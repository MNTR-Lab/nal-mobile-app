import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


# ============================================================
# NAL / DIGITALSHIFT CONFIGURATION
# ============================================================

YEAR = 2026

# These values are specific to the 2025-2026 NAL stats section.
# When DigitalShift creates the next season, create/update the
# configuration for that season rather than replacing archived data.
STATS_SECTION_ID = 1200
SEASON_ID = 9264
DIVISION_ID = 41958

BASE_URL = "https://web.api.digitalshift.ca/partials/stats"

# Omaha is used only to discover the complete list of teams that
# DigitalShift has attached to this stats section/division.
DISCOVERY_TEAM_ID = 566774

OUTPUT_FILE = Path(f"data/stats/{YEAR}/players.json")

STAT_CATEGORIES = (
    "passing",
    "rushing",
    "receiving",
    "offensive",
    "defensive",
    "returning",
    "kicking",
)

PLAYER_ID_RE = re.compile(r"/player/(\d+)")
TEAM_ID_RE = re.compile(r"/team/(\d+)")

REQUEST_TIMEOUT = 30


# ============================================================
# HTTP
# ============================================================

def build_session():
    ticket = os.environ.get("DIGITALSHIFT_AUTH_TICKET", "").strip()

    if not ticket:
        print("ERROR: DIGITALSHIFT_AUTH_TICKET is not set.")
        sys.exit(1)

    session = requests.Session()

    # The GitHub secret should contain the authorization value
    # already used by the other DigitalShift updater scripts.
    session.headers.update({
        "Authorization": ticket,
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "NAL-Stats-Updater/1.0",
    })

    return session


def get_content(session, url, params=None):
    response = session.get(
        url,
        params=params,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError(
            f"DigitalShift returned a non-JSON response for {response.url}"
        )

    content = payload.get("content")

    if not isinstance(content, str):
        raise RuntimeError(
            f"DigitalShift response did not contain HTML content: {response.url}"
        )

    return content


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    return " ".join(str(value).split())


def extract_player_id(link):
    if not link:
        return None

    href = link.get("href", "")
    match = PLAYER_ID_RE.search(href)

    if not match:
        return None

    return int(match.group(1))


def extract_team_id(link):
    if not link:
        return None

    href = link.get("href", "")
    match = TEAM_ID_RE.search(href)

    if not match:
        return None

    return int(match.group(1))


def normalize_key(text):
    text = clean_text(text)
    text = text.lower()

    replacements = {
        "#": "number",
        "%": "pct",
        "/": "_per_",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")

    return text or "value"


def unique_headers(headers):
    """
    Prevent duplicate JSON keys if DigitalShift ever repeats
    a column heading.
    """
    seen = {}
    result = []

    for header in headers:
        key = normalize_key(header)

        if key not in seen:
            seen[key] = 1
            result.append(key)
        else:
            seen[key] += 1
            result.append(f"{key}_{seen[key]}")

    return result


def category_from_table(table):
    classes = table.get("class", [])

    for category in STAT_CATEGORIES:
        if f"team_{category}" in classes:
            return category

    table_id = table.get("id", "").lower()

    for category in STAT_CATEGORIES:
        if category in table_id:
            return category

    return None


def is_regular_season_table(table):
    """
    DigitalShift returns both Regular Season and Playoff tables
    in the same team stats response.

    Determine which block the table belongs to by walking
    backward to the nearest meaningful H3 heading.
    """
    heading = table.find_previous("h3")

    if not heading:
        return False

    heading_text = clean_text(heading.get_text(" ", strip=True)).lower()

    return "regular season" in heading_text


# ============================================================
# TEAM DISCOVERY
# ============================================================

def discover_teams(session):
    """
    DigitalShift embeds the season/division team selector in the
    team shell response.

    We extract only teams belonging to DIVISION_ID.
    """

    url = f"{BASE_URL}/team"

    html = get_content(
        session,
        url,
        params={"team_id": DISCOVERY_TEAM_ID},
    )

    # The team list is embedded inside ng-init as HTML-escaped JSON.
    # BeautifulSoup decodes the HTML entities for us.
    soup = BeautifulSoup(html, "html.parser")

    container = soup.find(attrs={"ng-init": re.compile(r"teams_by_division")})

    if not container:
        raise RuntimeError(
            "Could not find teams_by_division in DigitalShift team response."
        )

    ng_init = container.get("ng-init", "")

    match = re.search(
        r"ctrl\.teams_by_division\s*=\s*(\[.*\])",
        ng_init,
        flags=re.DOTALL,
    )

    if not match:
        raise RuntimeError(
            "Could not parse teams_by_division from DigitalShift."
        )

    try:
        divisions = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Could not decode DigitalShift team list: {exc}"
        )

    teams = []

    for division in divisions:
        if int(division.get("id", 0)) != DIVISION_ID:
            continue

        for team in division.get("teams", []):
            teams.append({
                "id": int(team["id"]),
                "name": clean_text(team.get("name")),
                "short_name": clean_text(team.get("short_name")),
            })

    if not teams:
        raise RuntimeError(
            f"No teams found for division {DIVISION_ID}."
        )

    teams.sort(key=lambda item: item["name"])

    return teams


# ============================================================
# TEAM STAT PARSING
# ============================================================

def parse_stat_table(table, team):
    category = category_from_table(table)

    if not category:
        return []

    if not is_regular_season_table(table):
        return []

    header_cells = table.select("thead th")

    if not header_cells:
        return []

    raw_headers = [
        clean_text(cell.get_text(" ", strip=True))
        for cell in header_cells
    ]

    headers = unique_headers(raw_headers)

    records = []

    for row in table.select("tbody tr"):
        cells = row.find_all("td", recursive=False)

        if not cells:
            continue

        player_link = row.select_one('a.person-inline[href*="/player/"]')

        if not player_link:
            # Not a player statistical row.
            continue

        player_id = extract_player_id(player_link)

        if not player_id:
            continue

        player_name = clean_text(player_link.get_text(" ", strip=True))

        values = [
            clean_text(cell.get_text(" ", strip=True))
            for cell in cells
        ]

        # Defensive protection if DigitalShift changes a table.
        if len(values) < len(headers):
            values.extend([""] * (len(headers) - len(values)))

        if len(values) > len(headers):
            values = values[:len(headers)]

        stats = dict(zip(headers, values))

        # We store these separately because they are useful for
        # the native Player Stats UI.
        jersey_number = stats.get("number", "")
        position = stats.get("pos", "")

        records.append({
            "player_id": player_id,
            "name": player_name,
            "number": jersey_number,
            "position": position,
            "team_id": team["id"],
            "team": team["name"],
            "category": category,
            "stats": stats,
        })

    return records


def fetch_team_stats(session, team):
    url = f"{BASE_URL}/stats"

    html = get_content(
        session,
        url,
        params={"team_id": team["id"]},
    )

    soup = BeautifulSoup(html, "html.parser")

    records = []

    # DigitalShift includes duplicate "table-fixed" copies for
    # responsive layouts. We only parse tables that are not inside
    # the aria-hidden fixed clone.
    for table in soup.select("table.stats-table"):
        if table.find_parent(class_="table-fixed"):
            continue

        category = category_from_table(table)

        if not category:
            continue

        records.extend(parse_stat_table(table, team))

    return records


# ============================================================
# PLAYER DATABASE
# ============================================================

def merge_players(records):
    """
    One player may appear in several categories and may even
    appear for more than one team during the season.

    Deduplicate by DigitalShift player_id while preserving every
    statistical category/team record.
    """

    players = {}

    for record in records:
        player_id = record["player_id"]
        player_key = str(player_id)

        if player_key not in players:
            players[player_key] = {
                "player_id": player_id,
                "name": record["name"],
                "number": record["number"],
                "position": record["position"],
                "teams": [],
                "categories": [],
                "stats": {},
            }

        player = players[player_key]

        # Prefer a populated value if an earlier table did not
        # provide jersey number or position.
        if not player["number"] and record["number"]:
            player["number"] = record["number"]

        if not player["position"] and record["position"]:
            player["position"] = record["position"]

        team_entry = {
            "team_id": record["team_id"],
            "team": record["team"],
        }

        if team_entry not in player["teams"]:
            player["teams"].append(team_entry)

        category = record["category"]

        if category not in player["categories"]:
            player["categories"].append(category)

        # Keep separate records by team because a player may have
        # played for multiple organizations during the same season.
        player["stats"].setdefault(category, [])

        stat_record = {
            "team_id": record["team_id"],
            "team": record["team"],
            **record["stats"],
        }

        # Avoid duplicates caused by responsive/mobile markup.
        if stat_record not in player["stats"][category]:
            player["stats"][category].append(stat_record)

    # Clean/sort output.
    output = list(players.values())

    for player in output:
        player["teams"].sort(key=lambda item: item["team"])
        player["categories"].sort()

    output.sort(key=lambda item: item["name"].lower())

    return output


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"Updating NAL {YEAR} Player Stats")
    print(f"Stats section: {STATS_SECTION_ID}")
    print(f"Season ID: {SEASON_ID}")
    print(f"Division ID: {DIVISION_ID}")
    print()

    session = build_session()

    print("Discovering teams...")
    teams = discover_teams(session)

    print(f"Found {len(teams)} teams:")

    for team in teams:
        print(f"  {team['id']} - {team['name']}")

    print()

    all_records = []
    team_results = []

    for team in teams:
        print(f"Fetching stats: {team['name']}...")

        records = fetch_team_stats(session, team)

        categories_found = sorted({
            record["category"]
            for record in records
        })

        player_ids = {
            record["player_id"]
            for record in records
        }

        print(
            f"  {len(player_ids)} players with stats | "
            f"{', '.join(categories_found) if categories_found else 'NO CATEGORIES'}"
        )

        team_results.append({
            "team_id": team["id"],
            "team": team["name"],
            "player_count": len(player_ids),
            "categories": categories_found,
        })

        all_records.extend(records)

    players = merge_players(all_records)

    if not players:
        raise RuntimeError(
            "No players with statistics were found. "
            "Refusing to overwrite the existing Player Stats file."
        )

    # Safety check: we know the 2026 DigitalShift section should
    # contain multiple teams. This prevents a bad API response from
    # silently replacing good data.
    if len(teams) < 2:
        raise RuntimeError(
            "DigitalShift returned fewer than 2 teams. "
            "Refusing to overwrite Player Stats."
        )

    category_counts = {}

    for category in STAT_CATEGORIES:
        category_counts[category] = sum(
            1
            for player in players
            if category in player["categories"]
        )

    output = {
        "year": YEAR,
        "season_label": "2025-2026",
        "stats_section_id": STATS_SECTION_ID,
        "season_id": SEASON_ID,
        "division_id": DIVISION_ID,
        "game_type": "Regular Season",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "team_count": len(teams),
        "player_count": len(players),
        "category_counts": category_counts,
        "teams": team_results,
        "players": players,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
        )

        file.write("\n")

    print()
    print("SUCCESS")
    print(f"Teams: {len(teams)}")
    print(f"Unique players with stats: {len(players)}")

    for category, count in category_counts.items():
        print(f"{category.title()}: {count}")

    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
