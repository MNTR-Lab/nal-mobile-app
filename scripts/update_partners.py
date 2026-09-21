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

CDN_PREFIX = (
    "https://digitalshift-assets.sfo2.cdn.digitaloceanspaces.com/"
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

    match = re.search(
        r"https?://(?:www\.)?([^/]+)",
        url,
        re.I,
    )

    if match:
        domain = match.group(1)
        return (
            domain.split(".")[0]
            .replace("-", " ")
            .title()
        )

    return "NAL Partner"


def clean_url(value):
    if not value:
        return ""

    value = html.unescape(value).strip()

    if value.startswith("//"):
        value = "https:" + value

    return value


def extract_partners(raw_html):
    """
    Extract the partner cards from the raw NAL Partners page.

    The raw page contains Angular markup where the real href and
    image values are already present alongside the template
    attributes.
    """

    decoded = html.unescape(raw_html)

    marker = re.search(
        r'aria-label=["\']NAL Partners["\']',
        decoded,
        re.I,
    )

    if marker:
        section = decoded[marker.start():]
    else:
        marker = re.search(
            r"NAL\s+Partners",
            decoded,
            re.I,
        )

        section = (
            decoded[marker.start():]
            if marker
            else decoded
        )

    partners = []
    seen = set()

    # Locate anchor blocks associated with the sponsor grid.
    anchor_pattern = re.compile(
        r"<a\b([^>]*)>(.*?)</a>",
        re.I | re.S,
    )

    for anchor_match in anchor_pattern.finditer(section):
        attrs = anchor_match.group(1)
        inside = anchor_match.group(2)

        # We only want sponsor-grid Angular entries.
        if (
            'ng-repeat="entry in b"' not in attrs
            and "ng-repeat='entry in b'" not in attrs
        ):
            continue

        href_matches = re.findall(
            r'(?:ng-href|href)=["\']([^"\']*)["\']',
            attrs,
            re.I,
        )

        website = ""

        for candidate in href_matches:
            candidate = clean_url(candidate)

            if (
                candidate
                and "{{" not in candidate
                and candidate.lower().startswith(
                    ("http://", "https://")
                )
            ):
                website = candidate
                break

        if not website:
            # The website currently has at least one logo with no
            # outbound URL. We intentionally omit it from the
            # clickable app feed.
            continue

        img_match = re.search(
            r"<img\b([^>]*)>",
            inside,
            re.I | re.S,
        )

        if not img_match:
            continue

        img_attrs = img_match.group(1)

        image_matches = re.findall(
            r'(?:ng-src|src)=["\']([^"\']+)["\']',
            img_attrs,
            re.I,
        )

        logo = ""

        for candidate in image_matches:
            candidate = clean_url(candidate)

            if (
                CDN_PREFIX in candidate
                and "{{" not in candidate
            ):
                logo = candidate
                break

        if not logo:
            continue

        key = (
            website.lower(),
            logo.lower(),
        )

        if key in seen:
            continue

        seen.add(key)

        partners.append(
            {
                "name": partner_name_from_url(
                    website
                ),
                "logo": logo,
                "url": website,
            }
        )

    return partners


def save_partners(partners):
    """
    Replace partners.json only after a believable partner set
    has been found.
    """

    if len(partners) < 5:
        raise RuntimeError(
            f"Only {len(partners)} valid partner(s) "
            "were found. Existing partners.json "
            "was NOT changed."
        )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_file = OUTPUT_FILE.with_suffix(
        ".json.tmp"
    )

    temp_file.write_text(
        json.dumps(
            partners,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    temp_file.replace(OUTPUT_FILE)


def main():
    print("Downloading NAL Partners page...")

    raw_html = download_page(
        PARTNERS_URL
    )

    print(
        f"Downloaded {len(raw_html):,} characters."
    )

    print(
        "Extracting rendered partner records "
        "from raw page..."
    )

    partners = extract_partners(
        raw_html
    )

    print(
        f"Found {len(partners)} valid partner(s)."
    )

    if len(partners) < 5:
        print("")
        print(
            "ERROR: Partner count is "
            "suspiciously low."
        )
        print(
            "Existing data/partners.json "
            "was preserved."
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
            f"{number}. "
            f"{partner['name']} | "
            f"{partner['url']} | "
            f"{partner['logo']}"
        )


if __name__ == "__main__":
    main()
