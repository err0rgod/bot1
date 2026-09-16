import io
import os
import hashlib
import logging
from typing import Optional
import requests
import boto3
from PIL import Image
from scraper.security import is_safe_url
import dotenv

dotenv.load_dotenv()

# Prevent Pillow decompression bombs (max 25 megapixels)
Image.MAX_IMAGE_PIXELS = 25_000_000

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

REGION = os.getenv("AWS_REGION", "us-east-1")
S3_IMAGE_BUCKET = os.getenv("S3_IMAGE_BUCKET", "zerodaily-article-images")
MEDIA_BASE_URL = os.getenv("MEDIA_BASE_URL", "https://media.zerodaily.in").rstrip("/")
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB maximum payload

s3_client = boto3.client("s3", region_name=REGION)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def generate_image_key(category: str, article_url: str) -> str:
    """Generates a deterministic S3 key based on the category and article URL hash."""
    url_hash = hashlib.md5(article_url.strip().encode("utf-8")).hexdigest()[:16]
    clean_category = category.strip().lower()
    return f"images/{clean_category}/{url_hash}.webp"


def download_image(image_url: str, timeout: int = 10) -> Optional[bytes]:
    """Downloads an external image with SSRF protection, size caps, and error resilience."""
    if not is_safe_url(image_url):
        logging.warning(f"[SECURITY] Rejected unsafe image URL: {image_url}")
        return None

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    try:
        response = requests.get(image_url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()

        # Check content-length header if provided
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > MAX_IMAGE_BYTES:
                    logging.warning(f"[SECURITY] Image exceeds size limit ({content_length} bytes): {image_url}")
                    return None
            except ValueError:
                pass

        # Read stream up to MAX_IMAGE_BYTES in 64KB chunks
        content = bytearray()
        if hasattr(response, "iter_content"):
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    content.extend(chunk)
                if len(content) > MAX_IMAGE_BYTES:
                    logging.warning(f"[SECURITY] Image exceeded max size during streaming: {image_url}")
                    return None

        # Fallback to response.content if iter_content yielded nothing (e.g. mocked responses)
        if not content and hasattr(response, "content") and response.content:
            if len(response.content) > MAX_IMAGE_BYTES:
                logging.warning(f"[SECURITY] Image exceeds max size ({len(response.content)} bytes): {image_url}")
                return None
            content = bytearray(response.content)

        if len(content) < 500:
            logging.warning(f"[IMAGE] Downloaded payload too small ({len(content)} bytes) for {image_url}")
            return None
        return bytes(content)
    except Exception as e:
        logging.warning(f"[IMAGE] Failed downloading image from {image_url}: {e}")
        return None


def optimize_image(
    image_bytes: bytes,
    max_width: int = 800,
    quality: int = 80
) -> Optional[bytes]:
    """
    Resizes image to max_width preserving aspect ratio, converts to RGB,
    and encodes as high-efficiency WebP.
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Handle animated GIFs / WebPs by seeking first frame
            if getattr(img, "is_animated", False):
                img.seek(0)

            # Convert to RGB (handles RGBA, P, CMYK, etc.)
            if img.mode in ("RGBA", "LA"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Resize if larger than max_width
            if img.width > max_width:
                aspect_ratio = img.height / img.width
                new_height = int(max_width * aspect_ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

            output_buffer = io.BytesIO()
            img.save(output_buffer, format="WEBP", quality=quality, method=6)
            return output_buffer.getvalue()
    except Exception as e:
        logging.warning(f"[IMAGE] Image optimization failed: {e}")
        return None


def upload_to_s3(
    image_bytes: bytes,
    s3_key: str,
    bucket_name: Optional[str] = None
) -> bool:
    """Uploads optimized WebP image to S3 with public cache headers."""
    bucket = bucket_name or S3_IMAGE_BUCKET
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=image_bytes,
            ContentType="image/webp",
            CacheControl="public, max-age=2592000"  # 30 days
        )
        logging.info(f"[IMAGE] Uploaded {len(image_bytes)} bytes to s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        logging.error(f"[IMAGE ERROR] Failed uploading to S3 ({bucket}/{s3_key}): {e}")
        return False


def process_and_upload_image(
    image_url: Optional[str],
    category: str,
    article_url: str
) -> str:
    """
    Orchestrates downloading, WebP compression, S3 upload, and Cloudflare CDN URL generation.
    Falls back gracefully to the original image_url if any step fails.
    """
    if not image_url or not isinstance(image_url, str) or not image_url.startswith("http"):
        return ""

    # If already served from media.zerodaily.in, keep as is
    if MEDIA_BASE_URL in image_url:
        return image_url

    s3_key = generate_image_key(category, article_url)
    raw_bytes = download_image(image_url)
    if not raw_bytes:
        return image_url

    webp_bytes = optimize_image(raw_bytes)
    if not webp_bytes:
        return image_url

    success = upload_to_s3(webp_bytes, s3_key)
    if success:
        cdn_url = f"{MEDIA_BASE_URL}/{s3_key}"
        logging.info(f"[IMAGE] Successfully converted to CDN WebP: {cdn_url}")
        return cdn_url

    return image_url
