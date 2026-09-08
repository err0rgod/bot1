import os 
import time
from groq import Groq
import logging
import dotenv
import json

dotenv.load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

systemPrompt = """
You are a cynical, highly intelligent tech journalist. 
Analyze the provided tech news article and return a JSON object with EXACTLY these three fields:

1. "roasted_heading": A funny, sarcastic, or slightly roasted catchy headline.
2. "short_roast_summary": A 2-3 sentence summary delivered with a sarcastic tone.
3. "full_summary": A serious, accurate, and comprehensive summary of the actual facts(80-100 words).

You MUST return ONLY valid JSON matching this structure.
"""

def generateContent(rawContent):
    """ sends raw article to Groq with Exponential Backoff Retry """
    if not rawContent or len(rawContent) < 50:
        return None
    
    max_retries = 3
    base_delay = 2 # Starts at 2 seconds

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role" : "system", "content" : systemPrompt},
                    {"role" : "user", "content" : rawContent[:2000]}
                ],
                response_format={
                    "type" : "json_object"
                },
                temperature=0.8
            )

            resultText = response.choices[0].message.content
            return json.loads(resultText)
            
        except Exception as e:
            logging.warning(f"LLM API Error on attempt {attempt + 1}: {e}")
            
            # If we haven't hit the max retries yet, sleep and try again
            if attempt < max_retries - 1:
                # Exponential backoff formula: 2s, then 4s, etc.
                sleep_time = base_delay * (2 ** attempt) 
                logging.info(f"Rate limited or disconnected. Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                logging.error(f"LLM Call completely failed after {max_retries} attempts.")
                return None