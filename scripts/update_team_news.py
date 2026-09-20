import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
# NAL TEAM NEWS SCRAPER
# ============================================================

TEAMS = [
    {
        "slug": "amarillo-warbirds",
        "name": "Amarillo Warbirds",
        "url": "https://www.amarillowarbirds.com/",
    },
    {
        "slug": "dallas-apex",
        "name": "Dallas Apex",
        "url": "https://www.dallasapex.com/",
    },
    {
        "slug": "louisiana-rouxgaroux",
        "name": "Louisiana Rouxgaroux",
        "url": "https://www.geauxrouxgaroux.com/",
    },
    {
        "slug": "omaha-beef",
        "name": "Omaha Beef",
        "url": "https://www.beeffootball.com/",
    },
    {
        "slug": "pueblo-punishers",
        "name": "Pueblo Punishers",
        "url": "https://www.pueblopunishers.com/",
    },
    {
        "slug": "salina-liberty",
        "name": "Salina Liberty",
        "url": "https://www.salinaliberty.com/",
    },
    {
        "slug": "sioux-city-bandits",
        "name": "Sioux City Bandits",
        "url": "https://www.gobandits.fun/",
    },
    {
        "slug": "southwest-kansas-storm",
        "name": "Southwest Kansas Storm",
        "url": "https://www.swkstormfootball.com/",
    },
    {
        "slug": "wheeling-miners",
        "name": "Wheeling Miners",
        "url": "https://www.wheelingminers.com/",
    },
]

OUTPUT_DIR = Path("team-news")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    )
}


def clean_text(value):
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def get_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def find_image(article, base_url):
    # First try OpenGraph image
    og_image = article.find(
        "meta",
        attrs={"property": "og:image"}
    )

    if og_image and og_image.get("content"):
        return urljoin(
            base_url,
            og_image["content"].strip()
        )

    # Then Twitter image
    twitter_image = article.find(
        "meta",
        attrs={"name": "twitter:image"}
    )

    if twitter_image and twitter_image.get("content"):
        return urljoin(
            base_url,
            twitter_image["content"].strip()
        )

    # Fallback: first useful article image
    for img in article.find_all("img"):
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-lazy-src")
        )

        if not src:
            continue

        src_lower = src.lower()

        if any(
            bad in src_lower
            for bad in [
                "logo",
                "icon",
                "avatar",
                "favicon",
                "sponsor",
            ]
        ):
            continue

        return urljoin(base_url, src)

    return ""


def find_title(article):
    # OpenGraph title is usually the cleanest
    og_title = article.find(
        "meta",
        attrs={"property": "og:title"}
    )

    if og_title and og_title.get("content"):
        return clean_text(og_title["content"])

    h1 = article.find("h1")

    if h1:
        return clean_text(h1.get_text(" ", strip=True))

    title = article.find("title")

    if title:
        return clean_text(title.get_text(" ", strip=True))

    return ""


def find_description(article):
    # OpenGraph description
    og_description = article.find(
        "meta",
        attrs={"property": "og:description"}
    )

    if og_description and og_description.get("content"):
        return clean_text(
            og_description["content"]
        )

    # Standard description
    description = article.find(
        "meta",
        attrs={"name": "description"}
    )

    if description and description.get("content"):
        return clean_text(
            description["content"]
        )

    # Fallback to first substantial paragraph
    for paragraph in article.find_all("p"):
        text = clean_text(
            paragraph.get_text(" ", strip=True)
        )

        if len(text) >= 80:
            return text[:300]

    return ""


def find_date(article):
    # Published-time metadata
    selectors = [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "date"}),
        ("meta", {"name": "publish-date"}),
        ("meta", {"itemprop": "datePublished"}),
    ]

    for tag_name, attrs in selectors:
        tag = article.find(tag_name, attrs=attrs)

        if tag:
            value = (
                tag.get("content")
                or tag.get_text(" ", strip=True)
            )

            if value:
                return clean_text(value)

    # HTML time element
    time_tag = article.find("time")

    if time_tag:
        return clean_text(
            time_tag.get("datetime")
            or time_tag.get_text(" ", strip=True)
        )

    return ""


def collect_article_links(team):
    base_url = team["url"]

    # FootballShift sites commonly expose news at /news
    possible_pages = [
        urljoin(base_url, "news"),
        base_url,
    ]

    links = []

    for page_url in possible_pages:
        try:
            html = get_page(page_url)
        except Exception as exc:
            print(
                f"  Could not load {page_url}: {exc}"
            )
            continue

        soup = BeautifulSoup(html, "html.parser")

        for link in soup.find_all("a", href=True):
            href = link["href"].strip()

            absolute_url = urljoin(
                base_url,
                href
            )

            # Only accept this team's /news/ article URLs
            if "/news/" not in absolute_url.lower():
                continue

            # Keep articles on the team's own domain
            team_domain = re.sub(
                r"^https?://(www\.)?",
                "",
                base_url
            ).rstrip("/")

            article_domain = re.sub(
                r"^https?://(www\.)?",
                "",
                absolute_url
            ).split("/")[0]

            if team_domain != article_domain:
                continue

            # Remove fragments
            absolute_url = absolute_url.split("#")[0]

            if absolute_url not in links:
                links.append(absolute_url)

        # If /news gave us results, no need to rely on homepage
        if links:
            break

    return links


def scrape_article(url, team):
    html = get_page(url)
    soup = BeautifulSoup(html, "html.parser")

    title = find_title(soup)

    if not title:
        return None

    article = {
        "title": title,
        "url": url,
        "image": find_image(soup, team["url"]),
        "description": find_description(soup),
        "date": find_date(soup),
        "team": team["name"],
        "teamSlug": team["slug"],
    }

    return article


def scrape_team(team):
    print()
    print(
        f"Scraping {team['name']}..."
    )

    links = collect_article_links(team)

    print(
        f"  Found {len(links)} article links"
    )

    articles = []

    # Keep the feed lightweight.
    # We only need the most recent cards in the app.
    for url in links[:15]:
        try:
            article = scrape_article(
                url,
                team
            )

            if article:
                articles.append(article)

                print(
                    f"  + {article['title']}"
                )

        except Exception as exc:
            print(
                f"  Article failed: {url}"
            )
            print(
                f"    {exc}"
            )

        time.sleep(0.15)

    return articles


def save_team_news(team, articles):
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        OUTPUT_DIR
        / f"{team['slug']}.json"
    )

    with output_file.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            articles,
            file,
            indent=2,
            ensure_ascii=False,
        )

        file.write("\n")

    print(
        f"  Saved {len(articles)} articles "
        f"to {output_file}"
    )


def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    total_articles = 0

    print(
        "===================================="
    )
    print(
        "NAL TEAM NEWS UPDATE"
    )
    print(
        "===================================="
    )

    for team in TEAMS:
        try:
            articles = scrape_team(team)

            save_team_news(
                team,
                articles
            )

            total_articles += len(articles)

        except Exception as exc:
            print()
            print(
                f"ERROR: {team['name']}"
            )
            print(exc)

            # Important:
            # Don't destroy an existing feed just
            # because a team website temporarily fails.
            output_file = (
                OUTPUT_DIR
                / f"{team['slug']}.json"
            )

            if not output_file.exists():
                save_team_news(
                    team,
                    []
                )

    print()
    print(
        "===================================="
    )
    print(
        "TEAM NEWS UPDATE COMPLETE"
    )
    print(
        f"Total articles collected: "
        f"{total_articles}"
    )
    print(
        "===================================="
    )


if __name__ == "__main__":
    main()
