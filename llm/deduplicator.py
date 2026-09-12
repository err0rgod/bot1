import json
import logging
import re
from typing import List, Dict
import boto3
import os
import dotenv
from openai import OpenAI

dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Bedrock & DeepSeek Clients
REGION = os.getenv("AWS_REGION", "us-east-1")
bedrock_client = boto3.client("bedrock-runtime", region_name=REGION)

deepseek_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY") or "mock-key",
    base_url="https://api.deepseek.com/v1"
)

# Reuse the useBedrock toggle from Summariser
from llm.Summariser import useBedrock

DEDUP_SYSTEM_PROMPT = """
You are a senior tech news editor.
You are given a JSON list of news headlines and short snippets published today in the same category.
Multiple publications often cover the EXACT SAME news story, CVE, or security incident.

Your task:
1. Identify articles that cover the exact same event, CVE, acquisition, or product announcement.
2. For each duplicate cluster, keep only the SINGLE best, most informative article.
3. Keep all unique, standalone articles.
4. Return ONLY a JSON object containing a list of the selected article indices.

Format:
{
  "selected_indices": [0, 2, 5, 8]
}
"""

def filter_duplicate_articles(candidates: List[Dict]) -> List[Dict]:
    """
    Takes a list of raw RSS candidate items and returns only semantically unique articles.
    """
    if not candidates or len(candidates) <= 1:
        return candidates

    # Build a lightweight payload with only index, title, and short summary
    payload = []
    for idx, item in enumerate(candidates):
        payload.append({
            "index": idx,
            "title": item.get("title", ""),
            "summary": item.get("summary", "")[:200]
        })

    user_prompt = f"Analyze these {len(payload)} news items and filter out duplicate coverage:\n" + json.dumps(payload, indent=2)

    try:
        if useBedrock:
            response = bedrock_client.converse(
                modelId="deepseek.v3.2",
                system=[{"text": DEDUP_SYSTEM_PROMPT}],
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                inferenceConfig={"temperature": 0.2}  # Low temperature for strict clustering
            )
            raw_text = response["output"]["message"]["content"][0]["text"].strip()
        else:
            response = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": DEDUP_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            raw_text = response.choices[0].message.content

        # Clean markdown fences if present
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)

        result = json.loads(raw_text)
        selected_indices = set(result.get("selected_indices", []))

        # If model returned no indices or invalid result, fallback to all candidates
        if not selected_indices:
            logging.warning("[DEDUP] Model returned empty selected_indices. Keeping all candidates.")
            return candidates

        # Filter candidates based on selected indices (preserving original order)
        unique_articles = [candidates[i] for i in sorted(selected_indices) if i < len(candidates)]
        
        logging.info(f"[DEDUP] Reduced {len(candidates)} candidates down to {len(unique_articles)} unique stories.")
        return unique_articles

    except Exception as e:
        logging.warning(f"[DEDUP] Semantic deduplication failed: {e}. Falling back to all candidates.")
        return candidates
