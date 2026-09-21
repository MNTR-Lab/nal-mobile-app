import re
from pathlib import Path
from urllib.request import Request, urlopen

PARTNERS_URL = "https://www.thenationalarenaleague.com/partners"
OUTPUT_FILE = Path("partners-debug.txt")

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


def main():
    print("Downloading raw NAL Partners page...")

    html = download_page(PARTNERS_URL)

    print(f"Downloaded {len(html):,} characters.")

    checks = {
        "ctrl.photos": "ctrl.photos" in html,
        "sponsors-wrap": "sponsors-wrap" in html,
        "ng-repeat entry in b": 'ng-repeat="entry in b"' in html,
        "Pixellot URL": "pixellot.tv" in html.lower(),
        "Vet Tix URL": "vettix.org" in html.lower(),
        "SNHU URL": "snhu.edu" in html.lower(),
        "Scripps URL": "scrippsnetworks.com" in html.lower(),
        "DigitalShift CDN": "digitalshift-assets" in html.lower(),
    }

    print("")
    print("RAW HTML CHECKS")
    print("----------------")

    for name, found in checks.items():
        print(f"{name}: {'YES' if found else 'NO'}")

    print("")
    print("Searching for useful sponsor-related fragments...")

    patterns = [
        r'.{0,500}ctrl\.photos.{0,3000}',
        r'.{0,500}sponsors-wrap.{0,3000}',
        r'.{0,500}pixellot\.tv.{0,1500}',
        r'.{0,500}vettix\.org.{0,1500}',
        r'.{0,500}snhu\.edu.{0,1500}',
        r'.{0,500}scrippsnetworks\.com.{0,1500}',
        r'.{0,500}digitalshift-assets.{0,3000}',
    ]

    fragments = []

    for pattern in patterns:
        matches = re.findall(
            pattern,
            html,
            flags=re.I | re.S,
        )

        for match in matches[:3]:
            fragments.append(match)

    debug_text = (
        "NAL PARTNERS RAW HTML DIAGNOSTIC\n"
        "================================\n\n"
    )

    for name, found in checks.items():
        debug_text += (
            f"{name}: {'YES' if found else 'NO'}\n"
        )

    debug_text += (
        "\n\nMATCHED RAW HTML FRAGMENTS\n"
        "==========================\n\n"
    )

    if fragments:
        for number, fragment in enumerate(
            fragments,
            start=1,
        ):
            debug_text += (
                f"\n--- FRAGMENT {number} ---\n"
                f"{fragment}\n"
            )
    else:
        debug_text += "NO USEFUL FRAGMENTS FOUND.\n"

    OUTPUT_FILE.write_text(
        debug_text,
        encoding="utf-8",
    )

    print("")
    print(
        f"Diagnostic information saved to "
        f"{OUTPUT_FILE}"
    )

    print("")
    print("IMPORTANT:")
    print(
        "This diagnostic does NOT change "
        "data/partners.json."
    )


if __name__ == "__main__":
    main()
