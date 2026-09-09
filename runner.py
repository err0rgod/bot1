from scraper.ScraperDistributer import lambda_handler as run_scraper
from llm.SummariserDistributer import lambdaHandler as run_summarizer

# All your categories
# CATEGORIES = ["ai"]
CATEGORIES = ["cybersec", "ai", "programming", "robotics", "defense_aerospace",
  "hardware"]

def run_full_pipeline():
    for cat in CATEGORIES:
        print(f"\n========================================")
        print(f" STARTING PIPELINE FOR: {cat.upper()}")
        print(f"========================================")
        
        # Step 1: Fake an AWS Event and trigger the Scraper
        aws_event = {"category": cat}
        print("-> Running Scraper...")
        run_scraper(aws_event, None)
        
        # Step 2: Fake an AWS Event and trigger the Summarizer
        print("-> Running Summarizer...")
        run_summarizer(aws_event, None)
        
        print(f" Finished full pipeline for {cat}\n")
if __name__ == "__main__":
    run_full_pipeline()