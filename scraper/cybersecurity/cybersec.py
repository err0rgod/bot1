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
        
        return markdown_text.strip()

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

        return article.text
    except Exception as e:
        # attempt 2 : using firecrawl 
        logging.warning(f" Failed to parse arcticle : {url} | Error : {e} -> Falling back to firecrawl ")

        return extract_article_with_firecrawl(url=url)

# scrape news from RSS feeds
def scrape_rss_feed():
    news_data = []
    seen_links = set()

    # get today's date in UTC
    today = datetime.now(timezone.utc).date()

    for feed_url in CYBERSEC_NEWS_FEED:
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

    return news_data

# to scrape the cves from NVD api
def scrape_cves():

    logging.info("Scraping latest CVES.")

    # retry mechs
    for attempt in range(3):
        try:
            response = requests.get(NVD_API,headers=get_headers(),timeout=20)
            response.raise_for_status()
            data = response.json()

            cves = []
            for vuln in data.get("vulnerebilities", []):
                cve = vuln["cve"]
                cve_id = vuln["id"]

                descritions = cve.get("description", [])
                description = ""
                for d in descritions:
                    if d["lang"] == "en":
                        description = d["value"]
                        break


        except Exception as e:
            logging.error(f"Error Occured : {e}.")

def is_already_scraped(article_url : str) -> bool:
    """
    Checks if the article has already been parsed today.
    """
    return False


def main():
    logging.info("Scraping Cybersecurity Category.")

    news = scrape_rss_feed()
    cves = scrape_cves()

    with open("scraped_content.json", "w", encoding="utf-8") as f:
        json.dump(news, f, indent=4)
    logging.info("Successfully completed Cybersecurity news scraping and content saved to json.")

main()