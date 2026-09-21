import html
import re
from urllib.request import Request, urlopen

PARTNERS_URL = "https://www.thenationalarenaleague.com/partners"

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

    source = download_page(PARTNERS_URL)
    decoded = html.unescape(source)

    print(f"Downloaded {len(source):,} characters.")

    # Locate the actual ctrl.photos assignment.
    position = decoded.find("ctrl.photos")

    if position == -1:
        print("ERROR: ctrl.photos was not found.")
        raise SystemExit(1)

    # Print a large section beginning at ctrl.photos.
    # This should contain the photo records and their real paths.
    start = position
    end = min(
        len(decoded),
        position + 18000,
    )

    block = decoded[start:end]

    print("")
    print("=" * 90)
    print("CTRL.PHOTOS RAW DATA")
    print("=" * 90)
    print(block)
    print("=" * 90)
    print("END CTRL.PHOTOS RAW DATA")
    print("=" * 90)

    # Also specifically locate the known Pixellot photo UUID.
    pixellot_id = (
        "cb227857-21e3-49e9-864b-32241c9ea905"
    )

    pix_pos = decoded.find(pixellot_id)

    if pix_pos != -1:
        pix_start = max(0, pix_pos - 1500)
        pix_end = min(
            len(decoded),
            pix_pos + 3000,
        )

        print("")
        print("=" * 90)
        print("PIXELLOT PHOTO RECORD")
        print("=" * 90)
        print(decoded[pix_start:pix_end])
        print("=" * 90)
        print("END PIXELLOT PHOTO RECORD")
        print("=" * 90)
    else:
        print("")
        print("Pixellot photo UUID was not found.")

    # Find and print UUID-looking values near the sponsor data.
    uuids = re.findall(
        r"[0-9a-fA-F]{8}-"
        r"[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{12}",
        block,
    )

    unique_uuids = []

    for value in uuids:
        if value not in unique_uuids:
            unique_uuids.append(value)

    print("")
    print("UUID VALUES FOUND IN CTRL.PHOTOS BLOCK")
    print("=" * 90)

    for value in unique_uuids:
        print(value)

    print("")
    print("Diagnostic complete.")
    print("No partner data was changed.")


if __name__ == "__main__":
    main()
