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
        return response.read().decode("utf-8", errors="replace")


def clean_text(value):
    if not value:
        return ""

    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def absolute_url(url):
    if not url:
        return ""

    return urljoin(PARTNERS_URL, url.strip())


def find_image(tag):
    patterns = [
        r'data-src=["\']([^"\']+)["\']',
        r'data-lazy-src=["\']([^"\']+)["\']',
        r'src=["\']([^"\']+)["\']',
    ]

    for pattern in patterns:
        match = re.search(pattern, tag, re.I)

        if match:
            return absolute_url(match.group(1))

    return ""


def find_name(img_tag):
    patterns = [
        r'alt=["\']([^"\']+)["\']',
        r'title=["\']([^"\']+)["\']',
    ]

    for pattern in patterns:
        match = re.search(pattern, img_tag, re.I)

        if match:
            name = clean_text(match.group(1))

            if name:
                return name

    return "NAL Partner"


def extract_partners(html):
    partners = []
    seen = set()

    # Locate the NAL Partners portion of the page.
    marker = re.search(
        r"NAL\s+Partners",
        html,
        re.I,
    )

    if not marker:
        raise RuntimeError(
            "Could not locate the NAL Partners section."
        )

    section = html[marker.start():]

    # Stop before the site's footer/news navigation when possible.
    stop_markers = [
        r"News\s*&amp;\s*Events",
        r"News\s*&\s*Events",
        r"<footer",
    ]

    for stop_pattern in stop_markers:
        stop = re.search(stop_pattern, section, re.I)

        if stop:
            section = section[:stop.start()]
            break

    # Partner logos should normally be clickable images.
    link_pattern = re.compile(
        r'<a\b([^>]*)href=["\']([^"\']+)["\']([^>]*)>'
        r'([\s\S]*?)</a>',
        re.I,
    )

    for link_match in link_pattern.finditer(section):
        website = absolute_url(link_match.group(2))
        inside = link_match.group(4)

        img_match = re.search(
            r"<img\b[^>]*>",
            inside,
            re.I,
        )

        if not img_match:
            continue

        img_tag = img_match.group(0)
        logo = find_image(img_tag)

        if not logo:
            continue

        name = find_name(img_tag)

        # Ignore obvious site/navigation assets.
        combined = f"{name} {logo}".lower()

        ignored_terms = [
            "nal-only",
            "national arena league",
            "menu",
            "facebook",
            "instagram",
            "twitter",
            "youtube",
            "icon",
        ]

        if any(term in combined for term in ignored_terms):
            continue

        key = (website.lower(), logo.lower())

        if key in seen:
            continue

        seen.add(key)

        partners.append(
            {
                "name": name,
                "logo": logo,
                "url": website,
            }
        )

    return partners


def save_partners(partners):
    if not partners:
        raise RuntimeError(
            "No partners were found. Existing partners.json "
            "was NOT changed."
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

    html = download_page(PARTNERS_URL)

    print("Reading NAL Partners section...")

    partners = extract_partners(html)

    print(
        f"Found {len(partners)} potential partner(s)."
    )

    if not partners:
        print(
            "ERROR: No partners found. "
            "Existing data was preserved."
        )
        sys.exit(1)

    save_partners(partners)

    print(f"Saved partners to {OUTPUT_FILE}")

    for partner in partners:
        print(
            f"- {partner['name']} | "
            f"{partner['url']}"
        )


if __name__ == "__main__":
    main()
