import os
import re
import json
import html as html_lib
from datetime import datetime, timezone
from pathlib import Path

import requests


# ============================================================
# NAL / DIGITALSHIFT SETTINGS
# ============================================================

DIVISION_ID = "41958"

ROSTER_ENDPOINT = (
    "https://web.api.digitalshift.ca/partials/stats/team/roster"
)

OUTPUT_FILE = Path("data/rosters/2026/rosters.json")

TEAMS = {
    "amarillo-warbirds": {
        "name": "Amarillo Warbirds",
        "team_id": "566773",
    },
    "colorado-spartans": {
        "name": "Colorado Spartans",
        "team_id": "570667",
    },
    "dallas-apex": {
        "name": "Dallas Apex",
        "team_id": "680252",
    },
    "louisiana-rouxgaroux": {
        "name": "Louisiana Rouxgaroux",
        "team_id": "573852",
    },
    "omaha-beef": {
        "name": "Omaha Beef",
        "team_id": "566774",
    },
    "pueblo-punishers": {
        "name": "Pueblo Punishers",
        "team_id": "577047",
    },
    "salina-liberty": {
        "name": "Salina Liberty",
        "team_id": "600411",
    },
    "sioux-city-bandits": {
        "name": "Sioux City Bandits",
        "team_id": "570666",
    },
    "southwest-kansas-storm": {
        "name": "Southwest Kansas Storm",
        "team_id": "600414",
    },
    "wheeling-miners": {
        "name": "Wheeling Miners",
        "team_id": "707897",
    },
}


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    value = html_lib.unescape(str(value))
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_value(value):
    value = clean_text(value)

    if value.upper() in {"NA", "N/A", "NONE", "-"}:
        return ""

    return value


def build_authorization_header(secret_value):
    """
    DigitalShift's browser request uses:

        Authorization: ticket="<credential>"

    The GitHub secret may contain:
      raw credential
      ticket=credential
      ticket="credential"
      "credential"

    Normalize all of those forms to the exact browser format.
    """

    value = (secret_value or "").strip()

    if not value:
        raise RuntimeError(
            "DIGITALSHIFT_AUTH_TICKET is empty."
        )

    if value.lower().startswith("ticket="):
        value = value[len("ticket="):].strip()

    if (
        len(value) >= 2
        and value[0] == '"'
        and value[-1] == '"'
    ):
        value = value[1:-1].strip()

    if not value:
        raise RuntimeError(
            "DIGITALSHIFT_AUTH_TICKET contains no ticket value."
        )

    return f'ticket="{value}"'


# ============================================================
# PARSE PLAYER ROSTER
# ============================================================

def parse_players(content):
    """
    DigitalShift returns rendered HTML.

    The roster table contains:
      Name
      #
      Weight
      Height
      Position
      College

    DigitalShift also includes duplicate/fixed table markup.
    We intentionally parse only the first complete roster table.
    """

    players = []

    table_match = re.search(
        r"<table[^>]*>.*?<thead[^>]*>.*?"
        r"<th[^>]*>\s*Name\s*</th>.*?"
        r"<th[^>]*>\s*#\s*</th>.*?"
        r"<th[^>]*>\s*Weight\s*</th>.*?"
        r"<th[^>]*>\s*Height\s*</th>.*?"
        r"<th[^>]*>\s*Position\s*</th>.*?"
        r"<th[^>]*>\s*College\s*</th>.*?"
        r"</thead>(.*?)</table>",
        content,
        re.IGNORECASE | re.DOTALL,
    )

    if not table_match:
        return players

    table_html = table_match.group(1)

    rows = re.findall(
        r"<tr[^>]*>(.*?)</tr>",
        table_html,
        re.IGNORECASE | re.DOTALL,
    )

    for row in rows:
        cells = re.findall(
            r"<td[^>]*>(.*?)</td>",
            row,
            re.IGNORECASE | re.DOTALL,
        )

        if len(cells) < 6:
            continue

        player_link = re.search(
            r'href=["\'][^"\']*#/player/(\d+)/bio["\']',
            cells[0],
            re.IGNORECASE,
        )

        player_id = (
            player_link.group(1)
            if player_link
            else ""
        )

        name = normalize_value(cells[0])
        number = normalize_value(cells[1])
        weight = normalize_value(cells[2])
        height = normalize_value(cells[3])
        position = normalize_value(cells[4])
        college = normalize_value(cells[5])

        if not name:
            continue

        players.append(
            {
                "player_id": player_id,
                "name": name,
                "number": number,
                "position": position,
                "height": height,
                "weight": weight,
                "college": college,
            }
        )

    return players


# ============================================================
# PARSE TEAM STAFF
# ============================================================

def parse_staff(content):
    staff = []

    staff_section = re.search(
        r"Team Staff.*?<table[^>]*>(.*?)</table>",
        content,
        re.IGNORECASE | re.DOTALL,
    )

    if not staff_section:
        return staff

    rows = re.findall(
        r"<tr[^>]*>(.*?)</tr>",
        staff_section.group(1),
        re.IGNORECASE | re.DOTALL,
    )

    for row in rows:
        cells = re.findall(
            r"<td[^>]*>(.*?)</td>",
            row,
            re.IGNORECASE | re.DOTALL,
        )

        if len(cells) < 2:
            continue

        staff_link = re.search(
            r'href=["\'][^"\']*#/team-staff/(\d+)["\']',
            cells[0],
            re.IGNORECASE,
        )

        staff_id = (
            staff_link.group(1)
            if staff_link
            else ""
        )

        name = normalize_value(cells[0])
        position = normalize_value(cells[1])

        if not name:
            continue

        staff.append(
            {
                "staff_id": staff_id,
                "name": name,
                "position": position,
            }
        )

    return staff


# ============================================================
# FETCH ONE TEAM
# ============================================================

def fetch_team_roster(session, slug, team):
    print(
        f"Fetching {team['name']} "
        f"(team_id={team['team_id']})..."
    )

    response = session.get(
        ROSTER_ENDPOINT,
        params={
            "division_id": DIVISION_ID,
            "team_id": team["team_id"],
        },
        timeout=30,
    )

    if response.status_code == 401:
        raise RuntimeError(
            "DigitalShift returned 401 Unauthorized."
        )

    response.raise_for_status()

    payload = response.json()

    content = payload.get("content", "")

    if not content:
        raise RuntimeError(
            "DigitalShift returned no roster content."
        )

    players = parse_players(content)
    staff = parse_staff(content)

    print(
        f"  Players: {len(players)} | "
        f"Staff: {len(staff)}"
    )

    return {
        "slug": slug,
        "team": team["name"],
        "team_id": team["team_id"],
        "players": players,
        "staff": staff,
        "player_count": len(players),
        "staff_count": len(staff),
    }


# ============================================================
# MAIN
# ============================================================

def main():
    authorization_ticket = os.environ.get(
        "DIGITALSHIFT_AUTH_TICKET",
        ""
    )

    authorization_header = build_authorization_header(
        authorization_ticket
    )

    session = requests.Session()

    session.headers.update(
        {
            "Accept": "application/json, text/plain, */*",
            "Authorization": authorization_header,
            "Origin": "https://www.thenationalarenaleague.com",
            "Referer": "https://www.thenationalarenaleague.com/",
            "User-Agent": (
                "Mozilla/5.0 "
                "(Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            ),
        }
    )

    rosters = []

    successful_teams = 0
    failed_teams = 0

    for slug, team in TEAMS.items():
        try:
            roster = fetch_team_roster(
                session,
                slug,
                team,
            )

            rosters.append(roster)
            successful_teams += 1

        except Exception as exc:
            failed_teams += 1

            print(
                f"ERROR fetching {team['name']}: {exc}"
            )

            rosters.append(
                {
                    "slug": slug,
                    "team": team["name"],
                    "team_id": team["team_id"],
                    "players": [],
                    "staff": [],
                    "player_count": 0,
                    "staff_count": 0,
                    "error": str(exc),
                }
            )

    # ========================================================
    # SAFETY CHECK
    #
    # Never overwrite good roster data if authentication or
    # DigitalShift fails for every team.
    # ========================================================

    if successful_teams == 0:
        raise RuntimeError(
            "All DigitalShift roster requests failed. "
            "Existing roster JSON was not replaced."
        )

    total_players = sum(
        team["player_count"]
        for team in rosters
    )

    total_staff = sum(
        team["staff_count"]
        for team in rosters
    )

    output = {
        "year": 2026,
        "season_label": "2025-2026",
        "stats_section_id": "1200",
        "division_id": DIVISION_ID,
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "team_count": len(rosters),
        "successful_teams": successful_teams,
        "failed_teams": failed_teams,
        "total_players": total_players,
        "total_staff": total_staff,
        "teams": rosters,
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
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("========================================")
    print("NAL ROSTER UPDATE COMPLETE")
    print("========================================")
    print(f"Teams checked: {len(rosters)}")
    print(f"Successful teams: {successful_teams}")
    print(f"Failed teams: {failed_teams}")
    print(f"Players: {total_players}")
    print(f"Staff: {total_staff}")
    print(f"Saved: {OUTPUT_FILE}")
    print("========================================")


if __name__ == "__main__":
    main()
