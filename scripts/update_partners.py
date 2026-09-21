import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

PARTNERS_URL = "https://www.thenationalarenaleague.com/partners"
OUTPUT_FILE = Path("data/partners.json")

ASSET_BASE = (
    "https://digitalshift-assets.sfo2.cdn.digitaloceanspaces.com/pw/"
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0 Safari/537.36"
)


def download_page(url):
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    with urlopen(request, timeout=30) as response:
        return response.read().decode(
            "utf-8",
            errors="replace",
        )


def find_sponsor_settings(source):
    pattern = re.compile(
        r'<article\b[^>]*class=["\'][^"\']*widget-sponsors[^"\']*["\']'
        r'[^>]*data-settings=["\'](.*?)["\']',
        re.I | re.S,
    )

    match = pattern.search(source)

    if not match:
        raise RuntimeError(
            "Could not locate the sponsor data-settings block."
        )

    return html.unescape(match.group(1))


def parse_settings(settings_text):
    try:
        settings = json.loads(settings_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Could not decode sponsor JSON: {exc}"
        ) from exc

    entries = settings.get("entries", [])

    if not isinstance(entries, list):
        raise RuntimeError(
            "Sponsor entries were not returned as a list."
        )

    return entries


def extract_photo_paths(source):
    """
    The sponsor widget also contains ctrl.photos data.

    Each photo record contains the real DigitalShift image
    path, for example:

    photo UUID -> p-OTHER-UUID/1755860346-grid.png

    Capture those mappings directly from the page.
    """

    decoded_source = html.unescape(source)

    photo_paths = {}

    pattern = re.compile(
        r'"([0-9a-fA-F-]{36})"\s*:\s*\{'
        r'.{0,500}?'
        r'"path"\s*:\s*"([^"]+)"',
        re.S,
    )

    for match in pattern.finditer(decoded_source):
        photo_id = match.group(1)
        path = match.group(2)

        if path:
            photo_paths[photo_id.lower()] = path

    return photo_paths


def build_logo_url(photo_id, photo_paths):
    if not photo_id:
        return ""

    photo_id = str(photo_id).strip()

    path = photo_paths.get(
        photo_id.lower(),
        "",
    )

    if not path:
        return ""

    path = path.lstrip("/")

    return ASSET_BASE + path


def normalize_url(value):
    if not value:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    return urljoin(PARTNERS_URL, value)


def clean_name(name):
    if not name:
        return "NAL Partner"

    name = str(name).strip()

    # Some records may contain a URL in the name field.
    # We don't need that for the app.
    if name.startswith("http://") or name.startswith("https://"):
        return "NAL Partner"

    return name or "NAL Partner"


def extract_partners(source):
    settings_text = find_sponsor_settings(source)
    entries = parse_settings(settings_text)

    photo_paths = extract_photo_paths(source)

    print(
        f"Found {len(photo_paths)} DigitalShift photo path(s)."
    )

    partners = []
    seen = set()

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        photo_id = entry.get("photo_id")
        website = normalize_url(entry.get("url"))
        name = clean_name(entry.get("name"))

        if not photo_id or not website:
            continue

        logo = build_logo_url(
            photo_id,
            photo_paths,
        )

        if not logo:
            print(
                f"WARNING: No image path found for {photo_id}"
            )
            continue

        key = (
            str(photo_id).lower(),
            website.lower(),
        )

        if key in seen:
            continue

        seen.add(key)

        partners.append(
            {
                "name": name,
                "logo": logo,
                "url": website,
                "photo_id": str(photo_id),
            }
        )

    return partners


def save_partners(partners):
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = OUTPUT_FILE.with_suffix(
        ".json.tmp"
    )

    temporary_file.write_text(
        json.dumps(
            partners,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary_file.replace(OUTPUT_FILE)


def main():
    print("Downloading NAL Partners page...")

    source = download_page(PARTNERS_URL)

    print(
        f"Downloaded {len(source):,} characters."
    )

    print(
        "Reading sponsor data-settings..."
    )

    try:
        partners = extract_partners(source)
    except Exception as exc:
        print("")
        print(f"ERROR: {exc}")
        print(
            "Existing data/partners.json was preserved."
        )
        sys.exit(1)

    print(
        f"Found {len(partners)} valid partner(s)."
    )

    if len(partners) < 4:
        print("")
        print(
            "ERROR: Partner count is suspiciously low."
        )
        print(
            "Existing data/partners.json was preserved."
        )
        sys.exit(1)

    save_partners(partners)

    print("")
    print(
        f"Saved {len(partners)} partners "
        f"to {OUTPUT_FILE}."
    )

    print("")
    print("PARTNERS")
    print("=" * 70)

    for number, partner in enumerate(
        partners,
        start=1,
    ):
        print(
            f"{number}. "
            f"{partner['url']} | "
            f"{partner['logo']}"
        )


if __name__ == "__main__":
    main()
