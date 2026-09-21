import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

PARTNERS_URL = "https://www.thenationalarenaleague.com/partners"
OUTPUT_FILE = Path("data/partners.json")

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
    """
    Find the widget-sponsors article and extract its
    HTML-encoded data-settings attribute.
    """

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

    encoded_settings = match.group(1)

    # Convert &quot; and other HTML entities back into
    # normal JSON characters.
    decoded_settings = html.unescape(encoded_settings)

    return decoded_settings


def parse_partner_entries(settings_text):
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


def build_logo_url(photo_id):
    """
    DigitalShift sponsor images use the photo UUID in the
    generated image path. The rendered site exposes the
    final image as a grid.png asset.
    """

    if not photo_id:
        return ""

    photo_id = str(photo_id).strip()

    return (
        "https://digitalshift-assets.sfo2.cdn.digitaloceanspaces.com/"
        f"pw/{photo_id}/"
        f"p-{photo_id}/"
        "1755860346-grid.png"
    )


def normalize_url(value):
    if not value:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    return urljoin(PARTNERS_URL, value)


def extract_partners(source):
    settings_text = find_sponsor_settings(source)
    entries = parse_partner_entries(settings_text)

    partners = []
    seen = set()

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        photo_id = entry.get("photo_id")
        website = normalize_url(entry.get("url"))
        name = entry.get("name")

        if not photo_id or not website:
            continue

        logo = build_logo_url(photo_id)

        # The NAL site's partner records often have name=null.
        # We keep a clean fallback name so the app always has
        # something usable for accessibility/debugging.
        if name:
            name = str(name).strip()
        else:
            name = "NAL Partner"

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

    # Safety check:
    # If the website structure changes or suddenly returns
    # too few partners, do NOT destroy the last good feed.
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
            f"{partner['photo_id']}"
        )


if __name__ == "__main__":
    main()
