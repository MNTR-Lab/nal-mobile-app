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

# DigitalShift configuration for the 2025-2026 NAL stats section.
# These values are season-specific and should NOT be treated as
# permanent league identifiers.
STATS_SECTION_ID = 1200
SEASON_ID = 9264
DIVISION_ID = 41958

BASE_URL = "https://web.api.digitalshift.ca/partials/stats"

# Omaha Beef is used to discover the complete list of teams
# attached to the current NAL division.
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
        print(
            "ERROR: DIGITALSHIFT_AUTH_TICKET is not set."
        )
        sys.exit(1)

    # Normalize the GitHub secret into the exact authorization
    # format expected by DigitalShift.
    #
    # These formats are supported:
    #
    # actual-ticket-value
    #
    # ticket="actual-ticket-value"
    #
    # Authorization: ticket="actual-ticket-value"

    if ticket.lower().startswith(
        "authorization:"
    ):
        ticket = ticket.split(
            ":",
            1,
        )[1].strip()

    if ticket.lower().startswith(
        "ticket="
    ):
        authorization_value = ticket

    else:
        ticket = ticket.strip(
            '"'
        ).strip(
            "'"
        )

        authorization_value = (
            f'ticket="{ticket}"'
        )

    session = requests.Session()

    session.headers.update({
        "Authorization": authorization_value,
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "NAL-Stats-Updater/1.0",
        "Referer": "https://www.thenationalarenaleague.com/",
        "Origin": "https://www.thenationalarenaleague.com",
    })

    return session


def get_content(
    session,
    url,
    params=None,
):
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

    content = payload.get(
        "content"
    )

    if not isinstance(
        content,
        str,
    ):
        raise RuntimeError(
            "DigitalShift response did not contain "
            f"HTML content: {response.url}"
        )

    return content


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    return " ".join(
        str(value).split()
    )


def extract_player_id(link):
    if not link:
        return None

    href = link.get(
        "href",
        "",
    )

    match = PLAYER_ID_RE.search(
        href
    )

    if not match:
        return None

    return int(
        match.group(1)
    )


def normalize_key(text):
    text = clean_text(
        text
    ).lower()

    replacements = {
        "#": "number",
        "%": "pct",
        "/": "_per_",
    }

    for old, new in replacements.items():
        text = text.replace(
            old,
            new,
        )

    text = re.sub(
        r"[^a-z0-9]+",
        "_",
        text,
    )

    text = text.strip(
        "_"
    )

    return text or "value"


def unique_headers(headers):
    seen = {}
    result = []

    for header in headers:
        key = normalize_key(
            header
        )

        if key not in seen:
            seen[key] = 1
            result.append(
                key
            )

        else:
            seen[key] += 1

            result.append(
                f"{key}_{seen[key]}"
            )

    return result


# ============================================================
# TEAM DISCOVERY
# ============================================================

def discover_teams(session):
    print(
        "Discovering teams from DigitalShift..."
    )

    # CONFIRMED DIGITALSHIFT ENDPOINT:
    #
    # https://web.api.digitalshift.ca/
    # partials/stats/team?team_id=566774

    url = (
        f"{BASE_URL}/team"
    )

    html = get_content(
        session,
        url,
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

    start_marker = (
        "ctrl.teams_by_division ="
    )

    if start_marker not in ng_init:
        raise RuntimeError(
            "Could not locate DigitalShift team JSON."
        )

    raw = ng_init.split(
        start_marker,
        1,
    )[1].strip()

    # Locate the complete JSON array embedded in ng-init.

    depth = 0
    in_string = False
    escaped = False
    end_index = None

    for index, char in enumerate(
        raw
    ):
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
                end_index = (
                    index + 1
                )
                break

    if end_index is None:
        raise RuntimeError(
            "Could not determine the end of "
            "DigitalShift team JSON."
        )

    team_json = raw[
        :end_index
    ]

    try:
        divisions = json.loads(
            team_json
        )

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Could not decode DigitalShift "
            f"team list: {exc}"
        )

    teams = []

    for division in divisions:
        try:
            division_id = int(
                division.get(
                    "id",
                    0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if division_id != DIVISION_ID:
            continue

        for team in division.get(
            "teams",
            [],
        ):
            try:
                team_id = int(
                    team["id"]
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

            teams.append({
                "id": team_id,
                "name": clean_text(
                    team.get(
                        "name"
                    )
                ),
                "short_name": clean_text(
                    team.get(
                        "short_name"
                    )
                ),
            })

    if not teams:
        raise RuntimeError(
            f"No teams found for division {DIVISION_ID}."
        )

    teams.sort(
        key=lambda item:
        item["name"].lower()
    )

    return teams


# ============================================================
# TEAM STAT TABLE IDENTIFICATION
# ============================================================

def category_from_table(table):
    classes = table.get(
        "class",
        [],
    )

    for category in STAT_CATEGORIES:
        if (
            f"team_{category}"
            in classes
        ):
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
    """
    DigitalShift returns both Regular Season and Playoff
    tables in the same team stats response.

    The nearest preceding H3 identifies which statistical
    period owns the table.
    """

    heading = table.find_previous(
        "h3"
    )

    if not heading:
        return None

    heading_text = clean_text(
        heading.get_text(
            " ",
            strip=True,
        )
    ).lower()

    if (
        "regular season"
        in heading_text
    ):
        return "Regular Season"

    if (
        "playoff"
        in heading_text
    ):
        return "Playoffs"

    return None


# ============================================================
# STAT TABLE PARSER
# ============================================================

def parse_stat_table(
    table,
    team,
):
    category = category_from_table(
        table
    )

    if not category:
        return []

    period = get_stat_period(
        table
    )

    # For the initial 2026 Player Stats database,
    # collect Regular Season statistics only.

    if period != "Regular Season":
        return []

    header_cells = table.select(
        "thead th"
    )

    if not header_cells:
        return []

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

    records = []

    tbody = table.find(
        "tbody"
    )

    if not tbody:
        return []

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

        if (
            len(values)
            < len(headers)
        ):
            values.extend(
                [""] * (
                    len(headers)
                    - len(values)
                )
            )

        if (
            len(values)
            > len(headers)
        ):
            values = values[
                :len(headers)
            ]

        stats = dict(
            zip(
                headers,
                values,
            )
        )

        jersey_number = stats.get(
            "number",
            "",
        )

        position = stats.get(
            "pos",
            "",
        )

        records.append({
            "player_id": player_id,
            "name": player_name,
            "number": jersey_number,
            "position": position,
            "team_id": team["id"],
            "team": team["name"],
            "category": category,
            "game_type": period,
            "stats": stats,
        })

    return records


# ============================================================
# FETCH TEAM STATS
# ============================================================

def fetch_team_stats(
    session,
    team,
):
    # CONFIRMED DIGITALSHIFT ENDPOINT:
    #
    # https://web.api.digitalshift.ca/
    # partials/stats/team/stats?team_id=566774
    #
    # This response contains:
    #
    # Passing
    # Rushing
    # Receiving
    # Offensive
    # Defensive
    # Returning
    # Kicking

    url = (
        f"{BASE_URL}/team/stats"
    )

    html = get_content(
        session,
        url,
        params={
            "team_id": team["id"],
        },
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    records = []

    tables = soup.select(
        "table.stats-table"
    )

    for table in tables:

        # DigitalShift generates duplicate fixed tables for
        # its responsive/mobile presentation.
        #
        # Ignore the duplicate aria-hidden/fixed copy.

        if table.find_parent(
            class_="table-fixed"
        ):
            continue

        category = category_from_table(
            table
        )

        if not category:
            continue

        table_records = parse_stat_table(
            table,
            team,
        )

        records.extend(
            table_records
        )

    return records


# ============================================================
# MERGE / DEDUPLICATE PLAYERS
# ============================================================

def merge_players(records):
    """
    A player can appear in several statistical categories.

    A player may also have statistics for more than one team
    during the same season.

    DigitalShift player_id is therefore our unique player key.
    """

    players = {}

    for record in records:
        player_id = record[
            "player_id"
        ]

        player_key = str(
            player_id
        )

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

        player = players[
            player_key
        ]

        # Some tables provide better player information
        # than others. Fill missing values when available.

        if (
            not player["number"]
            and record["number"]
        ):
            player["number"] = (
                record["number"]
            )

        if (
            not player["position"]
            and record["position"]
        ):
            player["position"] = (
                record["position"]
            )

        team_entry = {
            "team_id": record[
                "team_id"
            ],
            "team": record[
                "team"
            ],
        }

        if (
            team_entry
            not in player["teams"]
        ):
            player["teams"].append(
                team_entry
            )

        category = record[
            "category"
        ]

        if (
            category
            not in player["categories"]
        ):
            player["categories"].append(
                category
            )

        player["stats"].setdefault(
            category,
            [],
        )

        stat_record = {
            "team_id": record[
                "team_id"
            ],
            "team": record[
                "team"
            ],
            **record["stats"],
        }

        if (
            stat_record
            not in player[
                "stats"
            ][category]
        ):
            player[
                "stats"
            ][category].append(
                stat_record
            )

    output = list(
        players.values()
    )

    for player in output:
        player["teams"].sort(
            key=lambda item:
            item["team"].lower()
        )

        player["categories"].sort()

    output.sort(
        key=lambda item:
        item["name"].lower()
    )

    return output


# ============================================================
# VALIDATION
# ============================================================

def validate_results(
    teams,
    players,
    category_counts,
):
    if not teams:
        raise RuntimeError(
            "No teams were discovered."
        )

    if len(teams) < 2:
        raise RuntimeError(
            "DigitalShift returned fewer than "
            "2 teams. Refusing to overwrite "
            "Player Stats."
        )

    if not players:
        raise RuntimeError(
            "No players with statistics were found. "
            "Refusing to overwrite the existing "
            "Player Stats file."
        )

    # Kicking is a critical validation check because
    # special-teams players were the reason we chose the
    # team-stat source instead of relying only on the
    # league-wide leader tables.

    if (
        category_counts.get(
            "kicking",
            0,
        )
        == 0
    ):
        raise RuntimeError(
            "No kicking statistics were found. "
            "Refusing to overwrite Player Stats "
            "because the DigitalShift team-stat "
            "response is not being parsed correctly."
        )

    if (
        category_counts.get(
            "returning",
            0,
        )
        == 0
    ):
        print(
            "WARNING: No returning statistics were found."
        )


# ============================================================
# MAIN
# ============================================================

def main():
    print(
        f"Updating NAL {YEAR} Player Stats"
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

    # --------------------------------------------------------
    # DISCOVER TEAMS
    # --------------------------------------------------------

    teams = discover_teams(
        session
    )

    print(
        f"Found {len(teams)} teams:"
    )

    for team in teams:
        print(
            f"  {team['id']} - "
            f"{team['name']}"
        )

    print()

    # --------------------------------------------------------
    # FETCH TEAM STAT TABLES
    # --------------------------------------------------------

    all_records = []
    team_results = []

    for team in teams:
        print(
            f"Fetching stats: "
            f"{team['name']}..."
        )

        records = fetch_team_stats(
            session,
            team,
        )

        categories_found = sorted({
            record["category"]
            for record in records
        })

        player_ids = {
            record["player_id"]
            for record in records
        }

        category_text = (
            ", ".join(
                categories_found
            )
            if categories_found
            else "NO CATEGORIES"
        )

        print(
            f"  {len(player_ids)} players "
            f"with stats | {category_text}"
        )

        team_results.append({
            "team_id": team["id"],
            "team": team["name"],
            "player_count": len(
                player_ids
            ),
            "categories": categories_found,
        })

        all_records.extend(
            records
        )

    # --------------------------------------------------------
    # BUILD PLAYER DATABASE
    # --------------------------------------------------------

    players = merge_players(
        all_records
    )

    category_counts = {}

    for category in STAT_CATEGORIES:
        category_counts[
            category
        ] = sum(
            1
            for player in players
            if category
            in player["categories"]
        )

    # --------------------------------------------------------
    # VALIDATE BEFORE WRITING
    # --------------------------------------------------------

    validate_results(
        teams,
        players,
        category_counts,
    )

    # --------------------------------------------------------
    # BUILD OUTPUT
    # --------------------------------------------------------

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
            teams
        ),
        "player_count": len(
            players
        ),
        "category_counts": (
            category_counts
        ),
        "teams": team_results,
        "players": players,
    }

    # --------------------------------------------------------
    # SAVE JSON
    # --------------------------------------------------------

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

        file.write(
            "\n"
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()
    print(
        "======================================"
    )

    print(
        "NAL PLAYER STATS UPDATE COMPLETE"
    )

    print(
        "======================================"
    )

    print(
        f"Teams: {len(teams)}"
    )

    print(
        f"Unique players with stats: "
        f"{len(players)}"
    )

    print()

    print(
        "Category counts:"
    )

    for (
        category,
        count,
    ) in category_counts.items():
        print(
            f"  {category.title()}: "
            f"{count}"
        )

    print()

    print(
        f"Saved: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
