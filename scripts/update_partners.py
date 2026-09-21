import html
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

PARTNERS_URL = "https://www.thenationalarenaleague.com/partners"
OUTPUT_FILE = Path("data/partners.json")

CDN_BASE = (
    "https://digitalshift-assets.sfo2.cdn.digitaloceanspaces.com/"
    "pw/2f77fc4a-2c6f-4835-8918-ed31460e3e56/"
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


def partner_name_from_url(url):
    """
    Creates a readable fallback name from the partner URL.

    The app primarily displays the logo, so this name is mainly
    for accessibility and debugging.
    """

    known_names = {
        "pixellot.tv": "Pixellot",
        "mybookie.ag": "MyBookie",
        "1stphorm.com": "1st Phorm",
        "blackriflecoffee.com": "Black Rifle Coffee Company",
        "vettix.org": "Vet Tix",
        "vetthe.vote": "Vet the Vote",
        "loudcup.com": "LoudCup",
        "t-mobile.com": "T-Mobile",
        "snapsclothing.com": "Snaps Clothing",
        "goat-sportsmarketing.com": "GOAT Sports",
        "snhu.edu": "Southern New Hampshire University",
        "stokedsportsent.com": "Stoked Sports & Entertainment",
        "scrippsnetworks.com": "Scripps Sports",
    }

    lower_url = url.lower()

    for domain, name in known_names.items():
        if domain in lower_url:
            return name

    domain_match = re.search(
        r"https?://(?:www\.)?([^/]+)",
        url,
        re.I,
    )

    if domain_match:
        domain = domain_match.group(1)
        return domain.split(".")[0].replace("-", " ").title()

    return "NAL Partner"


def extract_photos(raw_html):
    """
    Extract the ctrl.photos JSON object embedded in the
    sponsors-wrap ng-init attribute.
    """

    decoded = html.unescape(raw_html)

    match = re.search(
        r'ctrl\.photos\s*=\s*(\{.*?\})\s*["\']',
        decoded,
        re.I | re.S,
    )

    if not match:
        raise RuntimeError(
            "Could not locate ctrl.photos data."
        )

    photos_text = match.group(1)

    try:
        photos = json.loads(photos_text)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Could not decode ctrl.photos JSON: {error}"
        )

    if not photos:
        raise RuntimeError(
            "ctrl.photos was found but contained no photos."
        )

    return photos


def extract_partner_entries(raw_html):
    """
    Extract partner URL + photo_id pairs from the raw Angular
    partner data.

    The raw page contains entry records before Angular renders
    the visible sponsor grid.
    """

    decoded = html.unescape(raw_html)

    # Restrict our search to the NAL Partners area when possible.
    marker = re.search(
        r"NAL\s+Partners",
        decoded,
        re.I,
    )

    if marker:
        section = decoded[marker.start():]
    else:
        section = decoded

    entries = []

    # Partner records contain both a photo_id and a URL.
    # Their property order can vary, so check both directions.
    patterns = [
        re.compile(
            r'"photo_id"\s*:\s*"([^"]+)"'
            r'.{0,1200}?'
            r'"url"\s*:\s*"([^"]*)"',
            re.I | re.S,
        ),
        re.compile(
            r'"url"\s*:\s*"([^"]*)"'
            r'.{0,1200}?'
            r'"photo_id"\s*:\s*"([^"]+)"',
            re.I | re.S,
        ),
    ]

    seen = set()

    for pattern_number, pattern in enumerate(patterns):
        for match in pattern.finditer(section):

            if pattern_number == 0:
                photo_id = match.group(1).strip()
                url = match.group(2).strip()
            else:
                url = match.group(1).strip()
                photo_id = match.group(2).strip()

            key = (photo_id, url)

            if key in seen:
                continue

            seen.add(key)

            entries.append(
                {
                    "photo_id": photo_id,
                    "url": url,
                }
            )

    return entries


def extract_rendered_fallback(raw_html):
    """
    Fallback extraction.

    The diagnostic confirmed the raw page also contains partner
    URLs and DigitalShift references. If structured entry parsing
    changes, this provides a second extraction route.
    """

    decoded = html.unescape(raw_html)

    pattern = re.compile(
        r'<a\b[^>]*'
        r'(?:ng-href|href)="(https?://[^"]*)"'
        r'[^>]*>'
        r'.{0,1200}?'
        r'<img\b[^>]*'
        r'(?:ng-src|src)="'
        r'(https://digitalshift-assets[^"]+)"',
        re.I | re.S,
    )

    partners = []
    seen = set()

    for match in pattern.finditer(decoded):
        url = match.group(1).strip()
        logo = match.group(2).strip()

        if "{{" in url or "{{" in logo:
            continue

        key = (url.lower(), logo.lower())

        if key in seen:
            continue

        seen.add(key)

        partners.append(
            {
                "name": partner_name_from_url(url),
                "logo": logo,
                "url": url,
            }
        )

    return partners


def build_partners(raw_html):
    photos = extract_photos(raw_html)
    entries = extract_partner_entries(raw_html)

    partners = []
    seen = set()

    for entry in entries:
        photo_id = entry["photo_id"]
        url = entry["url"]

        if not url:
            # Keep logos with no destination out of the clickable
            # app partner rail until the website supplies a URL.
            continue

        if "{{" in url:
            continue

        photo = photos.get(photo_id)

        if not photo:
            continue

        path = photo.get("path", "").strip()

        if not path:
            continue

        logo = CDN_BASE + path

        key = (url.lower(), logo.lower())

        if key in seen:
            continue

        seen.add(key)

        partners.append(
            {
                "name": partner_name_from_url(url),
                "logo": logo,
                "url": url,
            }
        )

    # If structured parsing fails, try the rendered/raw markup.
    if not partners:
        print(
            "Structured partner parsing returned no results. "
            "Trying fallback extraction..."
        )

        partners = extract_rendered_fallback(raw_html)

    return partners


def save_partners(partners):
    """
    Only replace partners.json after we have a believable result.
    This protects the last good data if the NAL website changes.
    """

    if len(partners) < 5:
        raise RuntimeError(
            f"Only {len(partners)} partner(s) found. "
            "Existing partners.json was NOT changed."
        )

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

    raw_html = download_page(PARTNERS_URL)

    print(
        f"Downloaded {len(raw_html):,} characters."
    )

    print("Extracting NAL partner data...")

    partners = build_partners(raw_html)

    print(
        f"Found {len(partners)} valid partner(s)."
    )

    if len(partners) < 5:
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
        f"Saved partners to {OUTPUT_FILE}"
    )
    print("")

    for number, partner in enumerate(
        partners,
        start=1,
    ):
        print(
            f"{number}. {partner['name']} | "
            f"{partner['url']} | "
            f"{partner['logo']}"
        )


if __name__ == "__main__":
    main()
