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


def show_context(source, search_term, before=2500, after=3500):
    position = source.lower().find(search_term.lower())

    if position == -1:
        print(f"NOT FOUND: {search_term}")
        return

    start = max(0, position - before)
    end = min(len(source), position + after)

    print("")
    print("=" * 80)
    print(f"RAW SOURCE AROUND: {search_term}")
    print("=" * 80)
    print(source[start:end])
    print("=" * 80)
    print("END RAW SOURCE")
    print("=" * 80)
    print("")


def main():
    print("Downloading raw NAL Partners page...")

    source = download_page(PARTNERS_URL)

    print(f"Downloaded {len(source):,} characters.")

    show_context(
        source,
        "pixellot.tv",
    )

    show_context(
        source,
        "ctrl.photos",
    )

    print("")
    print("Diagnostic complete.")
    print("No files were changed.")


if __name__ == "__main__":
    main()
