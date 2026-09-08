import os 
from openai import OpenAI
import logging
import dotenv
import json

dotenv.load_dotenv()

# llm call parameters
BASE_URL="https://api.deepseek.com"
API_KEY=os.getenv("DEEPSEEK_API_KEY")
MODEL="deepseek-v4-flash"

client = OpenAI(
    api_key = API_KEY,
    base_url = BASE_URL
)


systemPrompt = """
        You are a cynical, highly intelligent tech journalist. 
        Analyze the provided tech news article and return a JSON object with EXACTLY these three fields:
        
        1. "roasted_heading": A funny, sarcastic, or slightly roasted catchy headline.
        2. "short_roast_summary": A 2-3 sentence summary delivered with a sarcastic tone.
        3. "full_summary": A serious, accurate, and comprehensive summary of the actual facts(80-100 words).
        
        You MUST return ONLY valid JSON matching this structure.
        """

def generateContent(rawContent):
    """ sends raw article to deepseek and request a strucuture json response"""
    if not rawContent or len(rawContent) < 50 :
        return None
    

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role" : "system", "content" : systemPrompt},
                {"role" : "user", "content" : rawContent[:4000]}
            ],
            response_format={
                "type" : "json_object"
            },
            temperature=0.8
        )

        resultText = response.choices[0].message.content
        return json.loads(resultText)
    except Exception as e:
        logging.error(f"LLM Api call Error : {e}")
        return None