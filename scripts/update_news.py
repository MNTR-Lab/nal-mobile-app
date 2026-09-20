import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://www.thenationalarenaleague.com"
HOME_URL = BASE_URL + "/"

# Number of newest stories we want available to the app.
MAX_ARTICLES = 5

# Where the finished feed will be stored.
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "news.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 30


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    """Collapse extra spaces/newlines into clean text."""
    if not value:
        return ""

    return re.sub(r"\s+", " ", value).strip()


def absolute_url(url):
    """Convert relative FootballShift URLs into full URLs."""
    if not url:
        return ""

    return urljoin(BASE_URL, url)


def get_page(url):
    """Download a page from the NAL website."""
    print(f"Fetching: {url}")

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    return response.text


def meta_content(soup, property_name=None, name=None):
    """Read content from an HTML meta tag."""
    tag = None

    if property_name:
        tag = soup.find(
            "meta",
            attrs={"property": property_name},
        )

    if not tag and name:
        tag = soup.find(
            "meta",
            attrs={"name": name},
        )

    if tag and tag.get("content"):
        return clean_text(tag["content"])

    return ""


# ============================================================
# FIND ARTICLE LINKS ON HOMEPAGE
# ============================================================

def find_article_links(home_html):
    soup = BeautifulSoup(home_html, "html.parser")

    article_links = []

    for link in soup.find_all("a", href=True):

        href = clean_text(link.get("href"))

        if not href:
            continue

        full_url = absolute_url(href)

        # We only want actual NAL news article URLs.
        if "/news/" not in full_url:
            continue

        # Ignore generic news/category pages.
        if full_url.rstrip("/") in {
            BASE_URL + "/news",
            BASE_URL + "/news/latest",
            BASE_URL + "/news/transactions",
            BASE_URL + "/news/suspensions",
            BASE_URL + "/news/partners",
        }:
            continue

        # Keep only the NAL domain.
        if not full_url.startswith(BASE_URL + "/news/"):
            continue

        # Remove query strings/fragments if FootballShift adds them.
        full_url = full_url.split("#")[0]
        full_url = full_url.split("?")[0]

        if full_url not in article_links:
            article_links.append(full_url)

    return article_links[:MAX_ARTICLES]


# ============================================================
# ARTICLE INFORMATION
# ============================================================

def extract_json_ld(soup):
    """Find NewsArticle/Article structured data when available."""

    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"},
    ):

        raw = script.string

        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        candidates = []

        if isinstance(data, list):
            candidates.extend(data)

        elif isinstance(data, dict):

            if "@graph" in data and isinstance(data["@graph"], list):
                candidates.extend(data["@graph"])

            candidates.append(data)

        for item in candidates:

            if not isinstance(item, dict):
                continue

            article_type = item.get("@type", "")

            if isinstance(article_type, list):
                article_type = " ".join(article_type)

            article_type = str(article_type).lower()

            if (
                "newsarticle" in article_type
                or "article" in article_type
            ):
                return item

    return {}


def extract_title(soup, json_ld):
    title = meta_content(
        soup,
        property_name="og:title",
    )

    if not title:
        title = clean_text(
            json_ld.get("headline", "")
        )

    if not title:
        h1 = soup.find("h1")

        if h1:
            title = clean_text(
                h1.get_text(" ", strip=True)
            )

    if title:
        title = re.sub(
            r"\s*-\s*National Arena League\s*$",
            "",
            title,
            flags=re.IGNORECASE,
        )

    return title


def extract_description(soup, json_ld):
    description = meta_content(
        soup,
        property_name="og:description",
    )

    if not description:
        description = meta_content(
            soup,
            name="description",
        )

    if not description:
        description = clean_text(
            json_ld.get("description", "")
        )

    # FootballShift articles frequently use an H4
    # directly beneath the main headline as the subtitle.
    if not description:
        h1 = soup.find("h1")

        if h1:
            subtitle = h1.find_next(
                ["h2", "h3", "h4"]
            )

            if subtitle:
                description = clean_text(
                    subtitle.get_text(
                        " ",
                        strip=True,
                    )
                )

    return description


def extract_image(soup, json_ld):
    # Best source: Open Graph featured image.
    image = meta_content(
        soup,
        property_name="og:image",
    )

    if image:
        return absolute_url(image)

    # Next try Twitter card image.
    image = meta_content(
        soup,
        name="twitter:image",
    )

    if image:
        return absolute_url(image)

    # Next try JSON-LD.
    json_image = json_ld.get("image")

    if isinstance(json_image, str):
        return absolute_url(json_image)

    if isinstance(json_image, list) and json_image:
        first_image = json_image[0]

        if isinstance(first_image, str):
            return absolute_url(first_image)

        if isinstance(first_image, dict):
            image_url = first_image.get("url", "")

            if image_url:
                return absolute_url(image_url)

    if isinstance(json_image, dict):
        image_url = json_image.get("url", "")

        if image_url:
            return absolute_url(image_url)

    # FootballShift/Digital Shift fallback.
    # Search images on the article page for likely
    # uploaded content images.
    image_candidates = []

    for img in soup.find_all("img"):

        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-lazy-src")
            or ""
        )

        src = absolute_url(src)

        if not src:
            continue

        src_lower = src.lower()

        if "digitalshift" not in src_lower:
            continue

        # Avoid common site graphics where possible.
        if any(
            unwanted in src_lower
            for unwanted in [
                "logo",
                "icon",
                "favicon",
                "sponsor",
                "partner",
            ]
        ):
            continue

        image_candidates.append(src)

    if image_candidates:
        return image_candidates[0]

    return ""


def extract_date(soup, json_ld):
    date_value = clean_text(
        json_ld.get("datePublished", "")
    )

    if not date_value:
        date_value = meta_content(
            soup,
            property_name="article:published_time",
        )

    if not date_value:
        time_tag = soup.find("time")

        if time_tag:
            date_value = clean_text(
                time_tag.get("datetime")
                or time_tag.get_text(
                    " ",
                    strip=True,
                )
            )

    # Preserve whatever FootballShift supplies.
    return date_value


def extract_canonical_url(soup, fallback_url):
    canonical = soup.find(
        "link",
        attrs={"rel": "canonical"},
    )

    if canonical and canonical.get("href"):
        return absolute_url(
            canonical["href"]
        )

    return fallback_url


def parse_article(url):
    html = get_page(url)

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    json_ld = extract_json_ld(soup)

    title = extract_title(
        soup,
        json_ld,
    )

    if not title:
        raise ValueError(
            f"No article title found for {url}"
        )

    article = {
        "title": title,
        "url": extract_canonical_url(
            soup,
            url,
        ),
        "image": extract_image(
            soup,
            json_ld,
        ),
        "description": extract_description(
            soup,
            json_ld,
        ),
        "date": extract_date(
            soup,
            json_ld,
        ),
        "category": "NAL NEWS",
    }

    return article


# ============================================================
# BUILD NEWS FEED
# ============================================================

def build_feed():
    home_html = get_page(HOME_URL)

    article_links = find_article_links(
        home_html
    )

    print(
        f"Found {len(article_links)} "
        "candidate article links."
    )

    if not article_links:
        raise RuntimeError(
            "No FootballShift news articles were found. "
            "Existing news.json will NOT be overwritten."
        )

    articles = []

    for url in article_links:

        try:
            article = parse_article(url)

            articles.append(article)

            print(
                "Added:",
                article["title"],
            )

            if article["image"]:
                print(
                    "  Image:",
                    article["image"],
                )
            else:
                print(
                    "  WARNING: No image found."
                )

        except Exception as error:
            print(
                f"WARNING: Could not parse {url}: {error}"
            )

    if not articles:
        raise RuntimeError(
            "Article links were found, but none could "
            "be parsed. Existing news.json will NOT "
            "be overwritten."
        )

    feed = {
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),
        "source": HOME_URL,
        "articles": articles,
    }

    return feed


# ============================================================
# SAVE NEWS.JSON
# ============================================================

def save_feed(feed):
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = OUTPUT_FILE.with_suffix(
        ".json.tmp"
    )

    with temporary_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            feed,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")

    temporary_file.replace(
        OUTPUT_FILE
    )

    print()
    print(
        f"Successfully wrote "
        f"{len(feed['articles'])} articles"
    )
    print(
        f"Output: {OUTPUT_FILE}"
    )


# ============================================================
# RUN
# ============================================================

def main():
    try:
        feed = build_feed()

        save_feed(feed)

    except Exception as error:

        print()
        print(
            "NEWS UPDATE FAILED:",
            error,
            file=sys.stderr,
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
