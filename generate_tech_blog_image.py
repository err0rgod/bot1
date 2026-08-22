#!/usr/bin/env python3
"""Generate a real PNG hero image for a technology blog with Amazon Bedrock.

The script uses a Bedrock bearer API key from ``.env`` and calls Amazon Nova
Canvas through ``InvokeModel``. Nova Canvas is the default model; another model
can be selected with ``--model`` when it is available in your region.

Example:
    python generate_tech_blog_image.py \
        --title "How edge AI is changing mobile apps" \
        --summary "An accessible introduction to on-device inference." \
        --style "clean editorial, futuristic but realistic"
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import sys
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_REGION = "us-east-1"
DEFAULT_MODEL = "amazon.nova-canvas-v1:0"


def load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE entries without requiring python-dotenv."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def build_prompt(title: str, summary: str, style: str, audience: str) -> tuple[str, str]:
    """Build a focused prompt and negative prompt accepted by Bedrock models."""
    prompt = (
        f"Landscape hero image for a technology blog titled '{title}'. "
        f"Show the core idea from this article: {summary}. "
        f"Audience: {audience}. Visual direction: {style}. "
        "Premium editorial composition, clear focal point, realistic lighting, "
        "layered depth, cohesive palette, sophisticated and original. No readable text."
    )
    # Keep the prompt within the conservative limit shared by Bedrock image models.
    prompt = prompt[:512]
    negative = "readable text, letters, logos, watermark, border, low resolution, blurry, distorted, duplicate objects"
    return prompt, negative


def build_request_body(
    prompt: str,
    negative_prompt: str,
    model: str,
    seed: Optional[int],
) -> dict:
    image_config = {
        "width": 1280,
        "height": 720,
        "quality": "standard",
        "cfgScale": 7.0,
        "numberOfImages": 1,
    }
    if seed is not None:
        image_config["seed"] = seed

    # Amazon image models such as Nova Canvas use this text-to-image shape.
    return {
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {
            "text": prompt,
            "negativeText": negative_prompt,
        },
        "imageGenerationConfig": image_config,
    }


def call_bedrock(
    api_key: str,
    region: str,
    model: str,
    body: dict,
) -> bytes:
    model_path = quote(model, safe=":._-")
    endpoint = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model_path}/invoke"
    request = Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=180) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if "marked by provider as Legacy" in detail:
            raise RuntimeError(
                "Nova Canvas is a legacy Bedrock model and this AWS account is not "
                "eligible to start using it. AWS only permits accounts that used the "
                "model recently; this cannot be fixed in the script."
            ) from exc
        raise RuntimeError(f"Bedrock returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Bedrock: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Bedrock returned a non-JSON response") from exc

    if response_body.get("error"):
        raise RuntimeError(f"Bedrock image generation failed: {response_body['error']}")

    images = response_body.get("images")
    if not isinstance(images, list) or not images or not isinstance(images[0], str):
        raise RuntimeError(f"Bedrock response did not contain an image: {response_body}")

    try:
        image_bytes = base64.b64decode(images[0], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError("Bedrock returned invalid base64 image data") from exc
    if not image_bytes:
        raise RuntimeError("Bedrock returned an empty image")
    return image_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True, help="The tech blog article title")
    parser.add_argument("--summary", required=True, help="One- or two-sentence article summary")
    parser.add_argument(
        "--style",
        default="modern editorial illustration, premium technology publication",
        help="Visual style and mood",
    )
    parser.add_argument("--audience", default="general technology readers", help="Target audience")
    parser.add_argument("--region", default=None, help="AWS region, e.g. us-east-1")
    parser.add_argument(
        "--model",
        default=None,
        help=f"Bedrock image model ID (default: {DEFAULT_MODEL})",
    )
    parser.add_argument("--seed", type=int, help="Optional deterministic seed")
    parser.add_argument(
        "--negative-prompt",
        default=None,
        help="Optional replacement for the default negative prompt",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tech_blog_image.png"),
        help="Path for the generated PNG image",
    )
    args = parser.parse_args()

    load_dotenv(Path(__file__).with_name(".env"))
    api_key = os.environ.get("BEDROCK_API_KEY") or os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
    if not api_key:
        print(
            "Missing BEDROCK_API_KEY. Add your Amazon Bedrock bearer API key to .env.",
            file=sys.stderr,
        )
        return 2

    region = (
        args.region
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or DEFAULT_REGION
    )
    model = args.model or os.environ.get("BEDROCK_IMAGE_MODEL") or DEFAULT_MODEL
    prompt, default_negative = build_prompt(args.title, args.summary, args.style, args.audience)
    body = build_request_body(prompt, args.negative_prompt or default_negative, model, args.seed)

    try:
        image_bytes = call_bedrock(api_key, region, model, body)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image_bytes)
    alt_text = f"Editorial technology illustration for '{args.title}'."
    alt_path = args.output.with_suffix(".alt.txt")
    alt_path.write_text(alt_text + "\n", encoding="utf-8")
    print(f"PNG image saved to {args.output}")
    print(f"Alt text saved to {alt_path}")
    print(f"Model: {model} | Region: {region}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
