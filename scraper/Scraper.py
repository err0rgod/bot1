import requests
import cloudscraper
import feedparser
import time
import random
import json
import os
import dotenv
import logging
from newspaper import Article
from datetime import datetime, timezone
from db.database import is_article_scraped


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

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


def extract_article_with_firecrawl(url: str):
    """ Uses firecrawl to exract content for cloudflare restricted pages"""
    logging.info(f"triggerinng firecrawl for: {url}")

    api_key = os.getenv("FIRECRAWL_API_KEY")
    api_url = "https://api.firecrawl.dev/v0/scrape"

    header = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "url" : url,
        "pageOptions" : {
            "onlyMainContent" : True
        }
    }

    try:
        response = requests.post(api_url,headers=header, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        markdown_text = data.get('data', {}).get('markdown', "")
        
        # --- CLEANUP FIRECRAWL JUNK ---
        # Find where the actual article ends and chop off everything after it
        cutoff_phrases = ["### Related Articles:", "### You may also like:", "##### Post a Comment", "[Photo of"]
        
        for phrase in cutoff_phrases:
            if phrase in markdown_text:
                markdown_text = markdown_text.split(phrase)[0] # Keep only the text BEFORE the phrase
        
        return {
            "content": markdown_text.strip(),
            "image_url": None
        }

    except Exception as e:
        logging.warning(f"Firecrawl failed for: {url} | Error : {e}")
        return ""

#extract article content using newspaper3k for HTML pages 
def extract_article(url : str):
    try:
        # attempt 1 : direct scraping 
        random_delay()

        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, timeout=15)

        response.raise_for_status()
        html = response.text

        from newspaper import Config

        article = Article(url)
        article.set_html(html)
        article.parse()

        if not article.text or len(article.text) < 50 :
            raise ValueError("Newspaper3k return enmpty or malformed string.")

        image_url = article.top_image if article.top_image and article.top_image.startswith("http") else None

        return {
            "content": article.text,
            "image_url": image_url
        }

    except Exception as e:
        # attempt 2 : using firecrawl 
        logging.warning(f" Failed to parse arcticle : {url} | Error : {e} -> Falling back to firecrawl ")

        return extract_article_with_firecrawl(url=url)

from llm.deduplicator import filter_duplicate_articles

# scrape news from RSS feeds
def scrape_rss_feed(category_name, feeds_to_scrape):
    candidates = []
    seen_links = set()

    # get today's date in UTC
    today = datetime.now(timezone.utc).date()

    # Stage 1: Collect today's un-scraped headlines from feeds
    for feed_url in feeds_to_scrape:
        logging.info(f"Reading RSS Feed : {feed_url}")

        feed = feedparser.parse(feed_url)

        for entry in feed.entries:

            # Filter by Current Day Only
            parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
            if parsed_time:
                article_date = datetime(*parsed_time[:6]).date()
                if article_date != today:
                    continue  # Skip it if it wasn't published today!

            # check if already seen in links
            link = entry.link

            # check if article scanned today
            if is_already_scraped(link):
                logging.info(f"Skipping already parsed article {link}")
                continue

            if link in seen_links:
                continue
    
            seen_links.add(link)

            # extract thumbnail from RSS if available
            rss_image = None
            if "media_content" in entry and len(entry.media_content) > 0:
                rss_image = entry.media_content[0].get("url")
            elif "links" in entry:
                for link_item in entry.links:
                    if link_item.get("rel") == "enclosure" and "image" in link_item.get("type", ""):
                        rss_image = link_item.get("href")
                        break

            candidates.append({
                "title": entry.title,
                "link": link,
                "date": entry.get("published", ""),
                "summary": entry.get("summary", ""),
                "rss_image": rss_image
            })

    if not candidates:
        logging.info(f"No new candidates found today for category: {category_name}")
        return []

    # Stage 2: Semantic LLM Deduplication (clustering duplicate coverage)
    logging.info(f"Found {len(candidates)} candidates for {category_name}. Running semantic deduplication...")
    unique_candidates = filter_duplicate_articles(candidates)

    # Stage 3: Extract full content & images only for unique stories
    news_data = []
    for item in unique_candidates:
        link = item["link"]
        title = item["title"]

        logging.info(f"Scraping unique article: {title}")

        extracted_data = extract_article(link)
        if not extracted_data or not isinstance(extracted_data, dict) or not extracted_data.get("content"): 
            continue

        final_image_url = item["rss_image"] or extracted_data.get("image_url") or ""

        news_data.append({
            "id": link,
            "title": title,
            "link": link,
            "date": item["date"],
            "summary": item["summary"],
            "content": extracted_data["content"],
            "image_url": final_image_url
        })

    return news_data


def is_already_scraped(article_url : str) -> bool:
    """
    Checks if the article has already been parsed today.
    """
    return is_article_scraped(article_url)

