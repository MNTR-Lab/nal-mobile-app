import json
import os
from pathlib import Path

import requests


# ============================================================
# NAL LIVE GAMES - ALL LIGHTCAST TEAM CHANNELS
# ============================================================

LIGHTCAST_URL = "https://www.lightcast.com/api/public/v1/events"
OUTPUT_FILE = Path("data/live-games.json")


# ============================================================
# LIGHTCAST TEAM CHANNELS
# ============================================================

CHANNELS = [
    (
        "Amarillo Warbirds",
        "72160",
        "LIGHTCAST_AMARILLO_API_KEY",
    ),
    (
        "Colorado Spartans",
        "72161",
        "LIGHTCAST_COLORADO_API_KEY",
    ),
    (
        "Dallas Apex",
        "72162",
        "LIGHTCAST_DALLAS_API_KEY",
    ),
    (
        "Louisiana Rouxgaroux",
        "72163",
        "LIGHTCAST_LOUISIANA_API_KEY",
    ),
    (
        "Omaha Beef",
        "72164",
        "LIGHTCAST_OMAHA_API_KEY",
    ),
    (
        "Pueblo Punishers",
        "72165",
        "LIGHTCAST_PUEBLO_API_KEY",
    ),
    (
        "Salina Liberty",
        "72166",
        "LIGHTCAST_SALINA_API_KEY",
    ),
    (
        "Sioux City Bandits",
        "72167",
        "LIGHTCAST_SIOUX_CITY_API_KEY",
    ),
    (
        "Southwest Kansas Storm",
        "72168",
        "LIGHTCAST_SW_KANSAS_API_KEY",
    ),
    (
        "Wheeling Miners",
        "72158",
        "LIGHTCAST_WHEELING_API_KEY",
    ),
]


# ============================================================
# GET LIGHTCAST EVENTS
# ============================================================

def get_live_events(channel_id, api_key):
    params = {
        "action": "getEvents",
        "channelId": channel_id,
        "channelApiKey": api_key,
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

    return response.json()


# ============================================================
# NORMALIZE LIGHTCAST RESPONSE
# ============================================================

def event_list(data):
    """
    Lightcast may return events directly as a list,
    under an 'events' key, under a 'data' key,
    or as a single event object.
    """

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        if isinstance(data.get("events"), list):
            return data["events"]

        if isinstance(data.get("data"), list):
            return data["data"]

        return [data]

    return []


# ============================================================
# BUILD NAL GAME RECORDS
# ============================================================

def normalize_events(
    data,
    team_name,
    channel_id,
):
    games = []

    for event in event_list(data):

        if not isinstance(event, dict):
            continue

        game = {
            # --------------------------------------------
            # LIGHTCAST EVENT INFORMATION
            # --------------------------------------------

            "event_id": event.get("event_id"),

            "title": event.get(
                "name",
                "",
            ),

            "description": event.get(
                "description",
                "",
            ),

            "start_time": event.get(
                "start_time",
                "",
            ),

            "end_time": event.get(
                "end_time",
                "",
            ),

            "start_time_utc": event.get(
                "start_time_utc",
                "",
            ),

            "end_time_utc": event.get(
                "end_time_utc",
                "",
            ),

            "timezone": event.get(
                "timezone",
                "",
            ),

            "seconds_until_start": event.get(
                "seconds_until_start"
            ),

            "simulated_live": event.get(
                "simulated_live"
            ),

            # --------------------------------------------
            # LIGHTCAST PLAYER INFORMATION
            # --------------------------------------------

            "player_landing_url": event.get(
                "player_landing_url",
                "",
            ),

            "embed_code": event.get(
                "embed_code",
                "",
            ),

            "embed_code_adaptive": event.get(
                "embed_code_adaptive",
                "",
            ),

            "event_image": event.get(
                "event_image_16x9_1280w",
                "",
            ),

            # --------------------------------------------
            # LIGHTCAST CHANNEL OWNERSHIP
            # --------------------------------------------

            "channel_id": channel_id,

            "channel_team": team_name,

            # --------------------------------------------
            # FUTURE GAME CENTER / FOOTBALLSHIFT LINKAGE
            #
            # These intentionally remain null until the
            # official 2027 FootballShift game data is
            # available.
            #
            # Lightcast remains responsible for video.
            # FootballShift will later provide official
            # matchup / score / statistics information.
            # --------------------------------------------

            "footballshift_game_id": None,

            "away_team": None,

            "home_team": None,
        }

        games.append(game)

    return games


# ============================================================
# REMOVE DUPLICATE EVENTS
# ============================================================

def dedupe(games):
    seen = set()
    output = []

    for game in games:

        key = (
            str(
                game.get(
                    "channel_id",
                    "",
                )
            ),
            str(
                game.get(
                    "event_id",
                    "",
                )
            ),
        )

        if key in seen:
            continue

        seen.add(key)

        output.append(game)

    return output


# ============================================================
# MAIN
# ============================================================

def main():

    all_games = []

    configured = 0

    # --------------------------------------------------------
    # FETCH EVERY CONFIGURED TEAM CHANNEL
    # --------------------------------------------------------

    for (
        team_name,
        channel_id,
        env_name,
    ) in CHANNELS:

        api_key = os.environ.get(
            env_name,
            "",
        ).strip()

        if not api_key:

            print(
                f"Skipping {team_name} "
                f"({channel_id}): "
                f"missing {env_name}"
            )

            continue

        configured += 1

        print(
            f"Fetching {team_name} "
            f"live events from "
            f"channel {channel_id}..."
        )

        try:

            data = get_live_events(
                channel_id,
                api_key,
            )

            games = normalize_events(
                data,
                team_name,
                channel_id,
            )

            all_games.extend(
                games
            )

            print(
                f"  Found "
                f"{len(games)} "
                f"event(s)."
            )

        except Exception as exc:

            # One team channel failing should not prevent
            # the other team channels from updating.

            print(
                f"  ERROR for "
                f"{team_name}: "
                f"{exc}"
            )

    # --------------------------------------------------------
    # MAKE SURE AT LEAST ONE CHANNEL WAS CONFIGURED
    # --------------------------------------------------------

    if configured == 0:

        raise RuntimeError(
            "No Lightcast channel API keys "
            "were configured."
        )

    # --------------------------------------------------------
    # CLEAN AND SORT RESULTS
    # --------------------------------------------------------

    all_games = dedupe(
        all_games
    )

    all_games.sort(
        key=lambda game:
        game.get(
            "start_time_utc"
        )
        or ""
    )

    # --------------------------------------------------------
    # CREATE DATA DIRECTORY IF NECESSARY
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # FINAL JSON FEED
    # --------------------------------------------------------

    payload = {

        "source":
            "Lightcast Live Events",

        "channels": [
            {
                "team": team_name,
                "channel_id": channel_id,
            }
            for (
                team_name,
                channel_id,
                _
            ) in CHANNELS
        ],

        "games":
            all_games,
    }

    # --------------------------------------------------------
    # WRITE data/live-games.json
    # --------------------------------------------------------

    OUTPUT_FILE.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        f"Saved "
        f"{len(all_games)} "
        f"total live event(s) "
        f"to {OUTPUT_FILE}"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
