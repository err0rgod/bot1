import json
import logging
import os 
from datetime import datetime, timezone
from llm.Summariser import generateContent
from db.database import save_article


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def lambdaHandler(event, context):
    targetCategory = event.get("category", "ai")
    today = datetime.now(timezone.utc).date()

    workspaceInputFilename = f"D:/bot1/tmp/scraped_{targetCategory}_{today}.json"
    lambdaInputFilename = f"/tmp/scraped_{targetCategory}_{today}.json"

    if os.path.exists(workspaceInputFilename):
        inputFilename = workspaceInputFilename
    elif os.path.exists(lambdaInputFilename):
        inputFilename = lambdaInputFilename
    else:
        logging.error(f"Could not find input file: {workspaceInputFilename} or {lambdaInputFilename}")
        return {"statusCode": 404, "body": "Input file not found"}

    outputFilename = os.path.join(os.path.dirname(inputFilename), f"final_{targetCategory}_{today}.json")

    os.makedirs(os.path.dirname(outputFilename), exist_ok=True)

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
            save_article(article, targetCategory, resultant)
            processed = {
                "id": article['id'],
                "link": article['link'],
                "date": article['date'],
                "title": article['title'],
                "image_url": article.get('image_url', ''),
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
