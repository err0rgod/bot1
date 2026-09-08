import json
import logging
import os 
from datetime import datetime, timezone
from Summariser import generateContent

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def lambdaHandler(event, context):
    targetCategory = event.get("category", "ai")
    today = datetime.now(timezone.utc).date()

    inputFilename = f"D:/bot1/tmp/scraped_{targetCategory}_{today}.json"
    # chaneg to temp when in lambda
    if not os.path.exists(inputFilename):
        input_filename = f"/tmp/scraped_{targetCategory}_{today}.json"

    outputFilename = f"D:/bot1/tmp/final_{targetCategory}_{today}.json"

    if "/tmp/" in inputFilename:
        outputFilename = f"/tmp/final_{targetCategory}_{today}.json"

    # load raw scraped data
    if not os.path.exists(inputFilename):
        logging.error(f"Could not find input file: {inputFilename}")
        return {"statusCode" : 404, "body" : "Input file not found"}

    with open(inputFilename, "r", encoding = 'utf-8') as f:
        articles = json.load(f)

    logging.info(f"loaded {len(articles)} articles, Hitting deepseek now....")

    finalData = []

    # process each article through deepseek 
    for article in articles:
        logging.info(f"Pinching: {article['title']}")

        resultant = generateContent(article['content'])

        if resultant:
            # combine pieces
            processed = {
                "id": article['id'],
                "link": article['link'],
                "date": article['date'],
                "title": article['title'],
                "heading": resultant.get("roasted_heading"),
                "shortSummary": resultant.get("short_roast_summary"),
                "fullSummary": resultant.get("full_summary")
            }
            finalData.append(processed)
        else:
            logging.warning(f"Failed to summarise: {article['title']}")

        with open(outputFilename, "w", encoding="utf-8") as f:
            json.dump(finalData, f, indent=4)

        logging.info(f"Successfully sumarised {len(finalData)} articles.")
    return {"status_code": 200, "body": "summarisation complete"}

if __name__ == "__main__":
    lambdaHandler({"category": "ai"}, None)
