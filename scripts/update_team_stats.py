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

STATS_SECTION_ID = 1200
SEASON_ID = 9264
DIVISION_ID = 41958

BASE_URL = "https://web.api.digitalshift.ca/partials/stats"

# Omaha Beef is used only to discover all teams
# belonging to the current division.
DISCOVERY_TEAM_ID = 566774

OUTPUT_FILE = Path(f"data/stats/{YEAR}/teams.json")

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

ANGULAR_EXPRESSION_RE = re.compile(
    r"\{\{.*?\}\}",
    re.DOTALL,
)

REQUEST_TIMEOUT = 30


# ============================================================
# HTTP / AUTHORIZATION
# ============================================================

def build_session():
    ticket = os.environ.get(
        "DIGITALSHIFT_AUTH_TICKET",
        "",
    ).strip()

    if not ticket:
        print("ERROR: DIGITALSHIFT_AUTH_TICKET is not set.")
        sys.exit(1)

    if ticket.lower().startswith("authorization:"):
        ticket = ticket.split(":", 1)[1].strip()

    if ticket.lower().startswith("ticket="):
        authorization_value = ticket
    else:
        ticket = ticket.strip('"').strip("'")
        authorization_value = f'ticket="{ticket}"'

    session = requests.Session()

    session.headers.update({
        "Authorization": authorization_value,
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "NAL-Team-Stats-Updater/1.0",
        "Referer": "https://www.thenationalarenaleague.com/",
        "Origin": "https://www.thenationalarenaleague.com",
    })

    return session


def get_content(session, url, params=None):
    response = session.get(
        url,
        params=params,
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code == 401:
        raise RuntimeError(
            "DigitalShift returned 401 Unauthorized. "
            "Check DIGITALSHIFT_AUTH_TICKET."
        )

    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError(
            "DigitalShift returned a non-JSON response "
            f"for {response.url}"
        )

    content = payload.get("content")

    if not isinstance(content, str):
        raise RuntimeError(
            "DigitalShift response did not contain "
            f"HTML content: {response.url}"
        )

    return content


# ============================================================
# TEXT / DATA HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    text = str(value)

    # Remove DigitalShift Angular UI expressions.
    text = ANGULAR_EXPRESSION_RE.sub("", text)

    # Normalize whitespace.
    text = " ".join(text.split())

    return text.strip()


def normalize_key(text):
    text = clean_text(text).lower()

    replacements = {
        "#": "number",
        "%": "pct",
        "/": "_per_",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(
        r"[^a-z0-9]+",
        "_",
        text,
    )

    return text.strip("_") or "value"


def unique_headers(headers):
    seen = {}
    result = []

    for header in headers:
        key = normalize_key(header)

        if key not in seen:
            seen[key] = 1
            result.append(key)
        else:
            seen[key] += 1
            result.append(
                f"{key}_{seen[key]}"
            )

    return result


def extract_player_id(link):
    if not link:
        return None

    href = link.get("href", "")

    match = PLAYER_ID_RE.search(href)

    if not match:
        return None

    return int(match.group(1))


# ============================================================
# TEAM DISCOVERY
# ============================================================

def discover_teams(session):
    print("Discovering teams from DigitalShift...")

    html = get_content(
        session,
        f"{BASE_URL}/team",
        params={
            "team_id": DISCOVERY_TEAM_ID,
        },
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    container = soup.find(
        attrs={
            "ng-init": re.compile(
                r"teams_by_division"
            )
        }
    )

    if not container:
        raise RuntimeError(
            "Could not find teams_by_division "
            "in the DigitalShift team response."
        )

    ng_init = container.get(
        "ng-init",
        "",
    )

    start_marker = "ctrl.teams_by_division ="

    if start_marker not in ng_init:
        raise RuntimeError(
            "Could not locate DigitalShift team JSON."
        )

    raw = ng_init.split(
        start_marker,
        1,
    )[1].strip()

    depth = 0
    in_string = False
    escaped = False
    end_index = None

    for index, char in enumerate(raw):
        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
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
                end_index = index + 1
                break

    if end_index is None:
        raise RuntimeError(
            "Could not determine the end of "
            "DigitalShift team JSON."
        )

    team_json = raw[:end_index]

    try:
        divisions = json.loads(team_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Could not decode DigitalShift "
            f"team list: {exc}"
        )

    teams = []

    for division in divisions:
        try:
            division_id = int(
                division.get("id", 0)
            )
        except (TypeError, ValueError):
            continue

        if division_id != DIVISION_ID:
            continue

        for team in division.get(
            "teams",
            [],
        ):
            try:
                team_id = int(team["id"])
            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

            teams.append({
                "team_id": team_id,
                "team": clean_text(
                    team.get("name")
                ),
                "short_name": clean_text(
                    team.get("short_name")
                ),
            })

    if not teams:
        raise RuntimeError(
            f"No teams found for division {DIVISION_ID}."
        )

    teams.sort(
        key=lambda item:
        item["team"].lower()
    )

    return teams


# ============================================================
# STAT TABLE IDENTIFICATION
# ============================================================

def category_from_table(table):
    classes = table.get(
        "class",
        [],
    )

    for category in STAT_CATEGORIES:
        if f"team_{category}" in classes:
            return category

    table_id = table.get(
        "id",
        "",
    ).lower()

    for category in STAT_CATEGORIES:
        if category in table_id:
            return category

    return None


def get_stat_period(table):
    heading = table.find_previous("h3")

    if not heading:
        return None

    heading_text = clean_text(
        heading.get_text(
            " ",
            strip=True,
        )
    ).lower()

    if "regular season" in heading_text:
        return "Regular Season"

    if "playoff" in heading_text:
        return "Playoffs"

    return None


# ============================================================
# PARSE ONE STAT TABLE
# ============================================================

def parse_stat_table(table):
    category = category_from_table(table)

    if not category:
        return None, []

    period = get_stat_period(table)

    # 2026 Team Stats currently represents
    # Regular Season only.
    if period != "Regular Season":
        return category, []

    header_cells = table.select(
        "thead th"
    )

    if not header_cells:
        return category, []

    raw_headers = [
        clean_text(
            cell.get_text(
                " ",
                strip=True,
            )
        )
        for cell in header_cells
    ]

    headers = unique_headers(
        raw_headers
    )

    tbody = table.find("tbody")

    if not tbody:
        return category, []

    rows = []

    for row in tbody.find_all(
        "tr",
        recursive=False,
    ):
        cells = row.find_all(
            "td",
            recursive=False,
        )

        if not cells:
            continue

        player_link = row.select_one(
            'a.person-inline[href*="/player/"]'
        )

        if not player_link:
            continue

        player_id = extract_player_id(
            player_link
        )

        if not player_id:
            continue

        player_name = clean_text(
            player_link.get_text(
                " ",
                strip=True,
            )
        )

        values = [
            clean_text(
                cell.get_text(
                    " ",
                    strip=True,
                )
            )
            for cell in cells
        ]

        if len(values) < len(headers):
            values.extend(
                [""] * (
                    len(headers) - len(values)
                )
            )

        if len(values) > len(headers):
            values = values[:len(headers)]

        stats = dict(
            zip(headers, values)
        )

        rows.append({
            "player_id": player_id,
            "name": player_name,
            "number": stats.get(
                "number",
                "",
            ),
            "position": stats.get(
                "pos",
                "",
            ),
            "stats": stats,
        })

    return category, rows


# ============================================================
# FETCH ONE TEAM
# ============================================================

def fetch_team_stats(
    session,
    team,
):
    html = get_content(
        session,
        f"{BASE_URL}/team/stats",
        params={
            "team_id": team["team_id"],
        },
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    categories = {
        category: []
        for category in STAT_CATEGORIES
    }

    tables = soup.select(
        "table.stats-table"
    )

    for table in tables:

        # Ignore DigitalShift responsive duplicate tables.
        if table.find_parent(
            class_="table-fixed"
        ):
            continue

        category, rows = parse_stat_table(
            table
        )

        if (
            category
            and rows
        ):
            categories[
                category
            ].extend(rows)

    # Remove duplicate rows if DigitalShift returns
    # duplicate markup outside the fixed-table wrapper.
    for category in STAT_CATEGORIES:
        unique_rows = []
        seen = set()

        for row in categories[category]:
            fingerprint = json.dumps(
                row,
                sort_keys=True,
                ensure_ascii=False,
            )

            if fingerprint in seen:
                continue

            seen.add(fingerprint)
            unique_rows.append(row)

        categories[category] = unique_rows

    player_ids = set()

    for rows in categories.values():
        for row in rows:
            player_ids.add(
                row["player_id"]
            )

    available_categories = [
        category
        for category in STAT_CATEGORIES
        if categories[category]
    ]

    return {
        "team_id": team["team_id"],
        "team": team["team"],
        "short_name": team["short_name"],
        "player_count": len(player_ids),
        "categories": available_categories,
        "stats": categories,
    }


# ============================================================
# VALIDATION
# ============================================================

def validate_results(teams):
    if len(teams) < 2:
        raise RuntimeError(
            "Fewer than 2 teams were returned. "
            "Refusing to overwrite Team Stats."
        )

    teams_with_stats = [
        team
        for team in teams
        if team["player_count"] > 0
    ]

    if not teams_with_stats:
        raise RuntimeError(
            "No team statistics were found. "
            "Refusing to overwrite Team Stats."
        )

    kicking_teams = sum(
        1
        for team in teams
        if team["stats"]["kicking"]
    )

    returning_teams = sum(
        1
        for team in teams
        if team["stats"]["returning"]
    )

    if kicking_teams == 0:
        raise RuntimeError(
            "No kicking statistics were found. "
            "Refusing to overwrite Team Stats."
        )

    if returning_teams == 0:
        raise RuntimeError(
            "No returning statistics were found. "
            "Refusing to overwrite Team Stats."
        )


# ============================================================
# MAIN
# ============================================================

def main():
    print(
        f"Updating NAL {YEAR} Team Stats"
    )

    print(
        f"Stats section: {STATS_SECTION_ID}"
    )

    print(
        f"Season ID: {SEASON_ID}"
    )

    print(
        f"Division ID: {DIVISION_ID}"
    )

    print()

    session = build_session()

    discovered_teams = discover_teams(
        session
    )

    print(
        f"Found {len(discovered_teams)} teams:"
    )

    for team in discovered_teams:
        print(
            f"  {team['team_id']} - "
            f"{team['team']}"
        )

    print()

    team_stats = []

    for team in discovered_teams:
        print(
            f"Fetching stats: "
            f"{team['team']}..."
        )

        result = fetch_team_stats(
            session,
            team,
        )

        team_stats.append(
            result
        )

        category_text = (
            ", ".join(
                result["categories"]
            )
            if result["categories"]
            else "NO CATEGORIES"
        )

        print(
            f"  {result['player_count']} "
            f"players with stats | "
            f"{category_text}"
        )

    validate_results(
        team_stats
    )

    teams_with_stats = sum(
        1
        for team in team_stats
        if team["player_count"] > 0
    )

    category_team_counts = {
        category: sum(
            1
            for team in team_stats
            if team["stats"][category]
        )
        for category in STAT_CATEGORIES
    }

    output = {
        "year": YEAR,
        "season_label": "2025-2026",
        "stats_section_id": STATS_SECTION_ID,
        "season_id": SEASON_ID,
        "division_id": DIVISION_ID,
        "game_type": "Regular Season",
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "team_count": len(
            team_stats
        ),
        "teams_with_stats": (
            teams_with_stats
        ),
        "category_team_counts": (
            category_team_counts
        ),
        "teams": team_stats,
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
        )

        file.write("\n")

    print()
    print(
        "======================================"
    )
    print(
        "NAL TEAM STATS UPDATE COMPLETE"
    )
    print(
        "======================================"
    )

    print(
        f"Teams: {len(team_stats)}"
    )

    print(
        f"Teams with stats: "
        f"{teams_with_stats}"
    )

    print()
    print("Category team counts:")

    for category in STAT_CATEGORIES:
        print(
            f"  {category.title()}: "
            f"{category_team_counts[category]}"
        )

    print()

    print(
        f"Saved: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
