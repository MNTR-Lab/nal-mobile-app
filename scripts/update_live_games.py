import json
import os
from pathlib import Path

import requests


# ============================================================
# NAL LIVE GAMES - LIGHTCAST LIVE EVENTS
# ============================================================

LIGHTCAST_URL = "https://www.lightcast.com/api/public/v1/events"

# First test channel:
# Pueblo Punishers Live Events Channel
CHANNEL_ID = "72165"

# GitHub Actions will provide this securely.
CHANNEL_API_KEY = os.environ.get("LIGHTCAST_PUEBLO_API_KEY", "").strip()

OUTPUT_FILE = Path("data/live-games.json")


def get_live_events():
    if not CHANNEL_API_KEY:
        raise RuntimeError(
            "Missing LIGHTCAST_PUEBLO_API_KEY environment variable."
        )

    params = {
        "action": "getEvents",
        "channelId": CHANNEL_ID,
        "channelApiKey": CHANNEL_API_KEY,
        "count": 250,
        "timezone": "US/Eastern",
        "ssl": "true",
        "playerResponsive": "true",
    }

    response = requests.get(
        LIGHTCAST_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    return data


def normalize_events(data):
    """
    Convert the Lightcast response into a simple format
    for the NAL mobile app.
    """

    # Lightcast may return the event list directly or
    # inside another response object. Handle both forms.
    if isinstance(data, list):
        events = data

    elif isinstance(data, dict):
        if isinstance(data.get("events"), list):
            events = data["events"]
        elif isinstance(data.get("data"), list):
            events = data["data"]
        else:
            # If a single event object is returned
            events = [data]

    else:
        events = []

    games = []

    for event in events:
        if not isinstance(event, dict):
            continue

        game = {
            "event_id": event.get("event_id"),
            "title": event.get("name", ""),
            "description": event.get("description", ""),
            "start_time": event.get("start_time", ""),
            "end_time": event.get("end_time", ""),
            "start_time_utc": event.get("start_time_utc", ""),
            "end_time_utc": event.get("end_time_utc", ""),
            "timezone": event.get("timezone", ""),
            "seconds_until_start": event.get("seconds_until_start"),
            "simulated_live": event.get("simulated_live"),
            "player_landing_url": event.get("player_landing_url", ""),
            "embed_code": event.get("embed_code", ""),
            "embed_code_adaptive": event.get(
                "embed_code_adaptive", ""
            ),
            "event_image": event.get(
                "event_image_16x9_1280w", ""
            ),
            "channel_id": CHANNEL_ID,
        }

        games.append(game)

    return games


def save_games(games):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "source": "Lightcast Live Events",
        "channel_id": CHANNEL_ID,
        "games": games,
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"Saved {len(games)} live event(s) "
        f"to {OUTPUT_FILE}"
    )


def main():
    print(
        f"Fetching Lightcast Live Events "
        f"for channel {CHANNEL_ID}..."
    )

    data = get_live_events()

    games = normalize_events(data)

    save_games(games)

    for game in games:
        print(
            f'Event: {game["title"]} '
            f'({game["event_id"]})'
        )


if __name__ == "__main__":
    main()
