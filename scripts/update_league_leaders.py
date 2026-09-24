import os
import re
import json
import html
from pathlib import Path

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------
# NAL / DigitalShift settings
# ---------------------------------------------------------

YEAR = 2026
LEAGUE_ID = 1200
DIVISION_ID = 41958
GAME_TYPE = "Regular Season"

BASE_URL = "https://web.api.digitalshift.ca/partials/stats/leaders/grid"

OUTPUT_FILE = Path("data/stats/2026/leaders.json")


# ---------------------------------------------------------
# Authorization
# ---------------------------------------------------------

AUTH_TICKET = os.environ.get("DIGITALSHIFT_AUTH_TICKET")

if not AUTH_TICKET:
    raise RuntimeError(
        "DIGITALSHIFT_AUTH_TICKET environment variable is not set."
    )


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def clean_text(value):
    if value is None:
        return None

    value = html.unescape(str(value))
    value = re.sub(r"\s+", " ", value).strip()

    return value or None


def numeric_value(value):
    """
    Convert a displayed stat to int/float when possible.
    Otherwise preserve the original text.
    """
    value = clean_text(value)

    if value is None:
        return None

    cleaned = value.replace(",", "").replace("%", "")

    try:
        if "." in cleaned:
            return float(cleaned)

        return int(cleaned)

    except ValueError:
        return value


def extract_player_id(href):
    if not href:
        return None

    match = re.search(r"/player/(\d+)", href)

    if match:
        return int(match.group(1))

    return None


def extract_team_id(href):
    if not href:
        return None

    match = re.search(r"/team/(\d+)", href)

    if match:
        return int(match.group(1))

    return None


def parse_number_position(text):
    """
    DigitalShift examples:

        #8 Quarterback
        #11 Wide Receiver
        #34 Linebacker

    Returns:
        ("8", "Quarterback")
    """

    text = clean_text(text)

    if not text:
        return None, None

    match = re.match(r"#?([^\s]+)\s*(.*)", text)

    if not match:
        return None, text

    number = clean_text(match.group(1))
    position = clean_text(match.group(2))

    return number, position


def parse_stat_display(stat_element):
    """
    Example:

        <div class="stat bh-black">
            <span class="big">1481</span> Yards
        </div>

    Returns:

        value = 1481
        unit = "Yards"
    """

    if not stat_element:
        return None, None

    big = stat_element.select_one(".big")

    if not big:
        return None, None

    value_text = clean_text(big.get_text(" ", strip=True))

    full_text = clean_text(stat_element.get_text(" ", strip=True)) or ""

    unit = full_text

    if value_text and unit.startswith(value_text):
        unit = unit[len(value_text):].strip()

    return numeric_value(value_text), clean_text(unit)


def team_name_from_link(team_link):
    if not team_link:
        return None

    aria = clean_text(team_link.get("aria-label"))

    if aria:
        match = re.match(r"(.+?)\s+team page$", aria, flags=re.I)

        if match:
            return clean_text(match.group(1))

    text = clean_text(team_link.get_text(" ", strip=True))

    return text


# ---------------------------------------------------------
# Featured leader
# ---------------------------------------------------------

def parse_featured_leader(featured):
    if not featured:
        return None

    person_link = featured.select_one("a.person-inline")

    if not person_link:
        return None

    team_link = featured.select_one("a.team-inline")

    numpos = featured.select_one(".numpos")

    number, position = parse_number_position(
        numpos.get_text(" ", strip=True) if numpos else None
    )

    stat_element = featured.select_one(".stat")

    value, unit = parse_stat_display(stat_element)

    player_image = None

    photo = featured.select_one(".photo img")

    if photo:
        player_image = clean_text(photo.get("src"))

    team_logo = None

    if team_link:
        team_img = team_link.select_one("img")

        if team_img:
            team_logo = clean_text(team_img.get("src"))

    return {
        "rank": 1,
        "player_id": extract_player_id(person_link.get("href")),
        "name": clean_text(person_link.get_text(" ", strip=True)),
        "number": number,
        "position": position,
        "team_id": extract_team_id(
            team_link.get("href") if team_link else None
        ),
        "team": team_name_from_link(team_link),
        "value": value,
        "unit": unit,
        "player_image": player_image,
        "source_team_logo": team_logo,
    }


# ---------------------------------------------------------
# Remaining leader table
# ---------------------------------------------------------

def parse_leader_table(table, featured_unit=None):
    leaders = []

    if not table:
        return leaders

    for row in table.select("tbody tr"):

        cells = row.find_all("td", recursive=False)

        if len(cells) < 4:
            continue

        person_link = row.select_one("a.person-inline")
        team_link = row.select_one("a.team-inline")

        if not person_link:
            continue

        # First column on DigitalShift leader grids is normally
        # the player's jersey number, not leaderboard rank.
        number_text = clean_text(cells[0].get_text(" ", strip=True))

        if number_text:
            number_text = number_text.lstrip("#")

        # DigitalShift also repeats jersey number in the player cell.
        jersey_span = cells[1].select_one(".st")

        if jersey_span:
            jersey = clean_text(jersey_span.get_text(" ", strip=True))

            if jersey:
                number_text = jersey.lstrip("#")

        value = numeric_value(
            cells[-1].get_text(" ", strip=True)
        )

        team_logo = None

        if team_link:
            team_img = team_link.select_one("img")

            if team_img:
                team_logo = clean_text(team_img.get("src"))

        leaders.append({
            "rank": None,
            "player_id": extract_player_id(person_link.get("href")),
            "name": clean_text(person_link.get_text(" ", strip=True)),
            "number": number_text,
            "position": None,
            "team_id": extract_team_id(
                team_link.get("href") if team_link else None
            ),
            "team": team_name_from_link(team_link),
            "value": value,
            "unit": featured_unit,
            "player_image": None,
            "source_team_logo": team_logo,
        })

    return leaders


# ---------------------------------------------------------
# Parse entire DigitalShift leader grid
# ---------------------------------------------------------

def parse_leaders(content):
    soup = BeautifulSoup(content, "html.parser")

    sections = []

    current_section = None

    for element in soup.find_all(["header", "div"], recursive=True):

        # -------------------------------------------------
        # Major section header
        # -------------------------------------------------

        if element.name == "header":

            heading = element.find("h2")

            if not heading:
                continue

            section_name = clean_text(
                heading.get_text(" ", strip=True)
            )

            if not section_name:
                continue

            current_section = {
                "name": section_name,
                "categories": []
            }

            sections.append(current_section)

            continue

        # -------------------------------------------------
        # Category blocks
        # -------------------------------------------------

        classes = element.get("class", [])

        if "col" not in classes or "pad-h2" not in classes:
            continue

        heading = element.find("h3", recursive=False)

        if not heading:
            continue

        if current_section is None:
            continue

        category_name = clean_text(
            heading.get_text(" ", strip=True)
        )

        if not category_name:
            continue

        featured = element.find(
            "div",
            class_="leader-featured",
            recursive=False
        )

        table = element.find("table", recursive=False)

        featured_leader = parse_featured_leader(featured)

        unit = (
            featured_leader.get("unit")
            if featured_leader
            else None
        )

        leaders = []

        if featured_leader:
            leaders.append(featured_leader)

        leaders.extend(
            parse_leader_table(
                table,
                featured_unit=unit
            )
        )

        # Assign actual leaderboard rank based on
        # DigitalShift's displayed ordering.
        for index, leader in enumerate(leaders, start=1):
            leader["rank"] = index

        current_section["categories"].append({
            "name": category_name,
            "unit": unit,
            "leaders": leaders
        })

    return sections


# ---------------------------------------------------------
# Fetch DigitalShift
# ---------------------------------------------------------

def fetch_leaders():

    headers = {
        "authorization": f'ticket="{AUTH_TICKET}"',
        "accept": "application/json, text/plain, */*",
        "origin": "https://www.thenationalarenaleague.com",
        "referer": "https://www.thenationalarenaleague.com/",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/140 Safari/537.36"
        ),
    }

    params = {
        "division_id": DIVISION_ID,
        "game_type": GAME_TYPE,
    }

    response = requests.get(
        BASE_URL,
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    content = payload.get("content")

    if not content:
        raise RuntimeError(
            "DigitalShift returned no League Leaders content."
        )

    return content


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    print("Fetching NAL League Leaders from DigitalShift...")

    content = fetch_leaders()

    sections = parse_leaders(content)

    if not sections:
        raise RuntimeError(
            "No League Leaders sections were parsed. "
            "Refusing to overwrite the existing archive."
        )

    category_count = sum(
        len(section["categories"])
        for section in sections
    )

    leader_count = sum(
        len(category["leaders"])
        for section in sections
        for category in section["categories"]
    )

    output = {
        "year": YEAR,
        "league_id": LEAGUE_ID,
        "division_id": DIVISION_ID,
        "game_type": GAME_TYPE,
        "section_count": len(sections),
        "category_count": category_count,
        "leader_count": leader_count,
        "sections": sections,
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8",
    )

    print(
        f"Saved {len(sections)} sections, "
        f"{category_count} categories and "
        f"{leader_count} leader records "
        f"to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
