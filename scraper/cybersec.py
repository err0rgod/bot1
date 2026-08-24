import requests
import feedparser
import time
import random
import json
import logging
from newspaper import Article


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


CYBERSEC_NEWS_FEED = [
    "https://feeds.feedburner.com/TheHackersNews", # The Hacker News  - direct image link available 
    "https://www.bleepingcomputer.com/feed/",   #bleeping computer working 
    "https://krebsonsecurity.com/feed/",    # XML feed 
    "https://www.darkreading.com/rss.xml",     #image available
    "https://www.securityweek.com/rss",
    "https://techcrunch.com/category/artificial-intelligence/feed/", # TechCrunch AI
    "https://feeds.arstechnica.com/arstechnica/technology-lab" # Ars Technica IT/Tech
]


# NVD api for CVE's
NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"


# Multiple user agents to avoid getting blocked
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"
]


# random delays to avoid blocking 
def random_delay():
    time.sleep(random.uniform(1,3))


# picking random header
def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }


#extract article content using newspaper3k for HTML pages 
def extract_article(url : str):
    try:
        random_delay()

        headers = get_headers()
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text

        from newspaper import Config
        config = Config()
        config.browser_user_agent = headers["User-Agent"] 
        config.request_timeout = 10

        article = Article(url, config=config)
        article.set_html(html)
        article.parse()

        return article.text
    except Exception as e:
        logging.warning(f" Failed to parse arcticle : {url} | Error : {e}")
        return ""

# scrape news from RSS feeds
def scrape_rss_feed(max_items=10):
    news_data = []
    seen_links = []
    for feed_url in CYBERSEC_NEWS_FEED:
        logging.info(f"Reading RSS Feed : {feed_url}")

        feed = feedparser.parse(feed_url)

        count = 0

        for entry in feed.entries:
            if count >=  max_items:
                break
            link = entry.link

            if link in seen_links:
                break
            seen_links.add(link)

            title = entry.title
            date = entry.get("published", "")
            summary = entry.get("summary", "")

            logging.info(f"Scraping article: {title}")

            content = extract_article(link)
            if not content: 
                continue

            news_data.append({
                "id":link,
                "title":title,
                "link":link,
                "date":date,
                "summary":summary,
                "content":content
            })

            count += 1

        return news_data

