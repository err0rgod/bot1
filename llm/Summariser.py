import os 
import time
import re
from openai import OpenAI
import logging
import dotenv
import json
import boto3

dotenv.load_dotenv()

# Boolean flag to toggle between AWS Bedrock and direct DeepSeek API
useBedrock = True

# Initialize DeepSeek direct client
deepseek_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

# Initialize AWS Bedrock client
bedrock_client = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-east-1")
)

systemPrompt = """
You are a cynical, highly intelligent tech journalist. 
Analyze the provided tech news article and return a JSON object with EXACTLY these three fields:

1. "roasted_heading": A funny, sarcastic, or slightly roasted catchy headline.
2. "short_roast_summary": A 2-3 sentence summary delivered with a sarcastic tone.
3. "full_summary": A serious, accurate, and comprehensive summary of the actual facts(80-100 words).

You MUST return ONLY valid JSON matching this structure.
"""

def generateContent(rawContent, use_bedrock: bool = None):
    """Sends raw article to either AWS Bedrock or DeepSeek with Exponential Backoff Retry"""
    if not rawContent or len(rawContent) < 50:
        return None
    
    # Use function parameter if provided, otherwise fall back to global flag
    is_bedrock = useBedrock if use_bedrock is None else use_bedrock

    max_retries = 3
    base_delay = 2  # Starts at 2 seconds

    for attempt in range(max_retries):
        try:
            if is_bedrock:
                # AWS Bedrock Converse call
                response = bedrock_client.converse(
                    modelId="deepseek.v3.2",
                    system=[{"text": systemPrompt}],
                    messages=[
                        {
                            "role": "user",
                            "content": [{"text": rawContent[:2000]}]
                        }
                    ],
                    inferenceConfig={
                        "temperature": 0.8
                    }
                )
                resultText = response["output"]["message"]["content"][0]["text"].strip()
                
                # Clean off markdown code fences if present (e.g. ```json ... ```)
                if resultText.startswith("```"):
                    resultText = re.sub(r"^```(?:json)?\s*", "", resultText)
                    resultText = re.sub(r"\s*```$", "", resultText)

                return json.loads(resultText)
            else:
                # Direct DeepSeek API call
                response = deepseek_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": systemPrompt},
                        {"role": "user", "content": rawContent[:2000]}
                    ],
                    response_format={
                        "type": "json_object"
                    },
                    temperature=0.8
                )
                resultText = response.choices[0].message.content
                return json.loads(resultText)
            
        except Exception as e:
            provider_name = "AWS Bedrock" if is_bedrock else "DeepSeek"
            logging.warning(f"{provider_name} API Error on attempt {attempt + 1}: {e}")
            
            # If we haven't hit the max retries yet, sleep and try again
            if attempt < max_retries - 1:
                sleep_time = base_delay * (2 ** attempt) 
                logging.info(f"{provider_name} rate limited or disconnected. Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                logging.error(f"{provider_name} call completely failed after {max_retries} attempts.")
                return None