import json
import re
import sys
import html as html_lib
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
        return response.read().decode("utf-8", errors="replace")


def clean_url(value):
    if not value:
        return ""

    value = html_lib.unescape(str(value)).strip()

    if value.startswith("//"):
        return "https:" + value

    return urljoin(PARTNERS_URL, value)


def partner_name_from_url(url):
    """
    The NAL page does not consistently provide partner names,
    so create readable names from known partner URLs.
    """

    known_names = {
        "pixellot.tv": "Pixellot",
        "goat-sportsmarketing.com": "GOAT Sports",
        "snapclothing.com": "Snaps Clothing",
        "loudcup.com": "LoudCup",
        "snhu.edu": "Southern New Hampshire University",
        "blackriflecoffee.com": "Black Rifle Coffee Company",
        "mybookie.ag": "MyBookie",
        "1stphorm.com": "1st Phorm",
        "stokedsportsent.com": "Stoked Sports & Entertainment",
        "scrippsnetworks.com": "Scripps Sports",
        "t-mobile.com": "T-Mobile",
        "vettix.org": "Vet Tix",
        "vetthe.vote": "Vet the Vote",
    }

    lowered = url.lower()

    for domain, name in known_names.items():
        if domain in lowered:
            return name

    return "NAL Partner"


def extract_data_settings(raw_html):
    """
    Find the sponsor widget's data-settings attribute and
    decode its JSON.
    """

    pattern = re.compile(
        r'<article\b[^>]*'
        r'class=["\'][^"\']*widget-sponsors[^"\']*["\']'
        r'[^>]*data-settings=["\'](.*?)["\']',
        re.I | re.S,
    )

    match = pattern.search(raw_html)

    if not match:
        raise RuntimeError(
            "Could not locate the NAL sponsor data-settings."
        )

    encoded = match.group(1)

    decoded = html_lib.unescape(encoded)

    try:
        return json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Could not decode sponsor data-settings: {exc}"
        )


def extract_photo_paths(raw_html):
    """
    The NAL page stores partner image paths separately inside
    the Angular ctrl.photos object.

    Example:
        "PHOTO-ID": {
            "path": "p-PHOTO-ID/123456-grid.png"
        }
    """

    decoded_html = html_lib.unescape(raw_html)

    photo_paths = {}

    pattern = re.compile(
        r'["\']'
        r'([0-9a-fA-F-]{36})'
        r'["\']\s*:\s*\{'
        r'[^{}]*?'
        r'["\']path["\']\s*:\s*'
        r'["\']([^"\']+?grid\.png)["\']',
        re.I | re.S,
    )

    for match in pattern.finditer(decoded_html):
        photo_id = match.group(1)
        path = match.group(2)

        photo_paths[photo_id] = path

    return photo_paths


def build_logo_url(photo_id, path):
    """
    Construct the public DigitalShift CDN URL from the actual
    path supplied by ctrl.photos.
    """

    path = path.lstrip("/")

    return (
        "https://digitalshift-assets.sfo2.cdn.digitaloceanspaces.com/"
        f"pw/{path}"
    )


def extract_partners(raw_html):
    settings = extract_data_settings(raw_html)

    entries = settings.get("entries", [])

    if not isinstance(entries, list):
        raise RuntimeError(
            "Sponsor entries were not returned as a list."
        )

    photo_paths = extract_photo_paths(raw_html)

    print(
        f"Found {len(entries)} partner record(s) "
        f"and {len(photo_paths)} photo record(s)."
    )

    partners = []
    seen = set()

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        photo_id = str(entry.get("photo_id", "")).strip()
        website = clean_url(entry.get("url"))

        # Ignore sponsor records without a destination URL.
        if not photo_id or not website:
            continue

        path = photo_paths.get(photo_id)

        if not path:
            print(
                "WARNING: No photo path found for "
                f"{website} ({photo_id})"
            )
            continue

        logo = build_logo_url(photo_id, path)

        supplied_name = entry.get("name")

        if supplied_name:
            name = str(supplied_name).strip()
        else:
            name = partner_name_from_url(website)

        key = (
            website.lower(),
            photo_id.lower(),
        )

        if key in seen:
            continue

        seen.add(key)

        partners.append(
            {
                "name": name,
                "logo": logo,
                "url": website,
                "photo_id": photo_id,
            }
        )

    return partners


def save_partners(partners):
    """
    Only replace partners.json after we have a healthy result.
    This prevents a temporary website change from wiping the
    app's partner list.
    """

    if len(partners) < 5:
        raise RuntimeError(
            "Partner count is suspiciously low. "
            "Existing partners.json was NOT changed."
        )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = OUTPUT_FILE.with_suffix(".json.tmp")

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

    raw_html = download_page(PARTNERS_URL)

    print(
        f"Downloaded {len(raw_html):,} characters."
    )

    print("Reading NAL sponsor data...")

    try:
        partners = extract_partners(raw_html)
    except Exception as exc:
        print()
        print(f"ERROR: {exc}")
        print(
            "Existing data/partners.json was preserved."
        )
        sys.exit(1)

    print(
        f"Built {len(partners)} complete partner record(s)."
    )

    try:
        save_partners(partners)
    except Exception as exc:
        print()
        print(f"ERROR: {exc}")
        print(
            "Existing data/partners.json was preserved."
        )
        sys.exit(1)

    print()
    print(
        f"Saved {len(partners)} partners "
        f"to {OUTPUT_FILE}."
    )

    print()
    print("PARTNERS")
    print("=" * 70)

    for number, partner in enumerate(
        partners,
        start=1,
    ):
        print(
            f"{number}. "
            f"{partner['name']} | "
            f"{partner['url']}"
        )
        print(
            f"   LOGO: {partner['logo']}"
        )


if __name__ == "__main__":
    main()
