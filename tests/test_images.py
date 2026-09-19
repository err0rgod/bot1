import io
from unittest.mock import patch, MagicMock
import pytest
from PIL import Image

from scraper.images import (
    generate_image_key,
    download_image,
    optimize_image,
    upload_to_s3,
    process_and_upload_image,
)


class TestImagePipeline:
    def test_generate_image_key(self):
        key = generate_image_key("CyberSec", "https://example.com/cve-1.html")
        assert key.startswith("images/cybersec/")
        assert key.endswith(".webp")

    def test_optimize_image_resizes_and_converts_to_webp(self):
        # Create a 1200x800 RGB test image
        test_img = Image.new("RGB", (1200, 800), color=(255, 0, 0))
        input_buf = io.BytesIO()
        test_img.save(input_buf, format="JPEG")
        input_bytes = input_buf.getvalue()

        output_bytes = optimize_image(input_bytes, max_width=800, quality=80)
        assert output_bytes is not None

        # Verify output is a valid WebP image with width <= 800
        with Image.open(io.BytesIO(output_bytes)) as result_img:
            assert result_img.format == "WEBP"
            assert result_img.width == 800
            assert result_img.height == 533

    def test_optimize_image_handles_rgba(self):
        test_img = Image.new("RGBA", (400, 300), color=(0, 255, 0, 128))
        input_buf = io.BytesIO()
        test_img.save(input_buf, format="PNG")
        output_bytes = optimize_image(input_buf.getvalue())
        assert output_bytes is not None
        with Image.open(io.BytesIO(output_bytes)) as result_img:
            assert result_img.format == "WEBP"

    @patch("scraper.images.requests.get")
    def test_download_image_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"x" * 1024
        mock_get.return_value = mock_resp

        data = download_image("https://example.com/test.jpg")
        assert data == b"x" * 1024

    @patch("scraper.images.requests.get")
    def test_download_image_failure(self, mock_get):
        mock_get.side_effect = Exception("Connection timeout")
        data = download_image("https://example.com/bad.jpg")
        assert data is None

    @patch("scraper.images.s3_client")
    def test_upload_to_s3_success(self, mock_s3):
        mock_s3.put_object.return_value = {}
        success = upload_to_s3(b"fake_webp", "images/ai/test.webp", "test-bucket")
        assert success is True
        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"] == "images/ai/test.webp"
        assert call_kwargs["ContentType"] == "image/webp"

    def test_process_and_upload_image_empty_or_invalid(self):
        assert process_and_upload_image(None, "ai", "https://example.com") == ""
        assert process_and_upload_image("", "ai", "https://example.com") == ""
        assert process_and_upload_image("not_a_url", "ai", "https://example.com") == ""

    def test_process_and_upload_image_already_cdn_url(self):
        existing = "https://media.zerodaily.in/images/ai/abc12345.webp"
        assert process_and_upload_image(existing, "ai", "https://example.com") == existing

    @patch("scraper.images.upload_to_s3")
    @patch("scraper.images.optimize_image")
    @patch("scraper.images.download_image")
    def test_process_and_upload_image_full_success(self, mock_down, mock_opt, mock_up):
        mock_down.return_value = b"raw_img"
        mock_opt.return_value = b"webp_img"
        mock_up.return_value = True

        result = process_and_upload_image(
            image_url="https://publisher.com/hero.png",
            category="cybersec",
            article_url="https://publisher.com/story1"
        )
        assert result.startswith("https://media.zerodaily.in/images/cybersec/")
        assert result.endswith(".webp")

    @patch("scraper.images.download_image")
    def test_process_and_upload_image_fallback_on_download_error(self, mock_down):
        mock_down.return_value = None
        raw_url = "https://publisher.com/hero.png"
        result = process_and_upload_image(
            image_url=raw_url,
            category="cybersec",
            article_url="https://publisher.com/story1"
        )
        assert result == "https://media.zerodaily.in/images/defaults/cybersec.webp"

    @patch("scraper.images.optimize_image")
    @patch("scraper.images.download_image")
    def test_process_and_upload_image_fallback_on_optimization_error(self, mock_down, mock_opt):
        mock_down.return_value = b"some_bytes"
        mock_opt.return_value = None
        result = process_and_upload_image(
            image_url="https://publisher.com/hero.png",
            category="ai",
            article_url="https://publisher.com/story1"
        )
        assert result == "https://media.zerodaily.in/images/defaults/ai.webp"

    @patch("scraper.images.upload_to_s3")
    @patch("scraper.images.optimize_image")
    @patch("scraper.images.download_image")
    def test_process_and_upload_image_fallback_on_s3_error(self, mock_down, mock_opt, mock_up):
        mock_down.return_value = b"some_bytes"
        mock_opt.return_value = b"webp_bytes"
        mock_up.return_value = False
        result = process_and_upload_image(
            image_url="https://publisher.com/hero.png",
            category="programming",
            article_url="https://publisher.com/story1"
        )
        assert result == "https://media.zerodaily.in/images/defaults/programming.webp"

