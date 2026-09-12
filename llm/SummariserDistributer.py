import json
import logging
import os 
from datetime import datetime, timezone
from llm.Summariser import generateContent
from db.database import save_article
from concurrent.futures import ThreadPoolExecutor, as_completed


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def process_single_article(article, targetCategory):
    """ worker process to process a single article in a thread"""
    try:
        logging.info(f"Summarising in parallel: {article['title']}")
        resultant = generateContent(article['content'])

        if resultant:
            # save to dynamoDB
            save_article(article, targetCategory, resultant )
            # return processed dict for local json logging
            return {
                "id": article['id'],
                "link": article['link'],
                "date": article['date'],
                "title": article['title'],
                "image_url": article.get('image_url', ''),
                "heading": resultant.get("roasted_heading"),
                "shortSummary": resultant.get("short_roast_summary"),
                "fullSummary": resultant.get("full_summary")
            }
        else:
            logging.warning(f"Failed to summarise: {article['title']}")
            return None
    except Exception as e:
        logging.error(f"Error processing article {article.get('title')}: {e}")
        return None

def lambdaHandler(event, context):
    targetCategory = event.get("category", "ai")
    today = datetime.now(timezone.utc).date()

    tmp_dir = os.environ.get("TMP_DIR")
    if not tmp_dir:
        tmp_dir = "/tmp" if os.name != "nt" else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp")

    inputFilename = os.path.join(tmp_dir, f"scraped_{targetCategory}_{today}.json")

    if not os.path.exists(inputFilename):
        # Fallback to alternate temporary locations
        alt_paths = [
            f"/tmp/scraped_{targetCategory}_{today}.json",
            os.path.join(os.getcwd(), "tmp", f"scraped_{targetCategory}_{today}.json")
        ]
        found = False
        for alt in alt_paths:
            if os.path.exists(alt):
                inputFilename = alt
                found = True
                break
        if not found:
            logging.error(f"Could not find input file: {inputFilename}")
            return {"statusCode": 404, "body": "Input file not found"}

    outputFilename = os.path.join(os.path.dirname(inputFilename), f"final_{targetCategory}_{today}.json")
    os.makedirs(os.path.dirname(outputFilename), exist_ok=True)

    with open(inputFilename, "r", encoding="utf-8") as f:
        articles = json.load(f)

    logging.info(f"Loaded {len(articles)} articles, generating roasted summaries...")

    finalData = []

    # Process up to 5 articles concurrently
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_article = {
            executor.submit(process_single_article, art, targetCategory): art
            for art in articles
        }

        for future in as_completed(future_to_article):
            result = future.result()
            if result:
                finalData.append(result)

    with open(outputFilename, "w", encoding="utf-8") as f:
        json.dump(finalData, f, indent=4)

    logging.info(f"Successfully summarized {len(finalData)} articles.")
    return {"statusCode": 200, "body": "summarisation complete"}

if __name__ == "__main__":
    lambdaHandler({"category": "ai"}, None)
