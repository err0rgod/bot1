import pytest
from unittest.mock import patch, MagicMock
from scraper.security import is_safe_url, sanitize_text
from scraper.images import download_image
from llm.Summariser import sanitize_summary_output


class TestSecurityHardening:

    def test_is_safe_url_valid_public_urls(self):
        valid_urls = [
            "https://thehackernews.com/2026/09/sample.html",
            "https://techcrunch.com/article?id=123",
            "http://arstechnica.com/information-technology/",
            "https://news.ycombinator.com/",
        ]
        for url in valid_urls:
            assert is_safe_url(url, resolve_dns=False) is True

    def test_is_safe_url_blocks_ssrf_and_private_ips(self):
        forbidden_urls = [
            "http://127.0.0.1/admin",
            "http://localhost:8000/internal",
            "http://0.0.0.0:80/",
            "http://169.254.169.254/latest/meta-data/",
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
            "http://10.0.0.5/api",
            "http://172.16.0.1:8080/",
            "http://192.168.1.1/router",
            "http://[::1]/",
            "http://metadata.google.internal/computeMetadata/v1/",
        ]
        for url in forbidden_urls:
            assert is_safe_url(url, resolve_dns=False) is False

    def test_is_safe_url_blocks_disallowed_protocols_and_credentials(self):
        invalid_urls = [
            "file:///etc/passwd",
            "file:///C:/Windows/System32/drivers/etc/hosts",
            "ftp://files.example.com/dump",
            "gopher://evil.com/",
            "javascript:alert(1)",
            "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
            "http://admin:password@thehackernews.com/",
            "",
            None,
            "not-a-url",
            "http://" + "a" * 2500,  # URL length limit
        ]
        for url in invalid_urls:
            assert is_safe_url(url, resolve_dns=False) is False

    def test_sanitize_text_strips_dangerous_html(self):
        malicious_input = (
            "Breaking news: <script>alert('pwned')</script> "
            "<iframe src='http://evil.com'></iframe> "
            "<object data='bad.swf'></object> "
            "Normal content remains."
        )
        cleaned = sanitize_text(malicious_input)
        assert "<script>" not in cleaned
        assert "alert" not in cleaned
        assert "<iframe>" not in cleaned
        assert "<object>" not in cleaned
        assert "Normal content remains." in cleaned

    def test_sanitize_text_strips_null_bytes_and_bounds_length(self):
        input_with_null = "Hello\x00World" + "A" * 500
        cleaned = sanitize_text(input_with_null, max_length=100)
        assert "\x00" not in cleaned
        assert len(cleaned) <= 100

    def test_download_image_blocks_ssrf(self):
        assert download_image("http://169.254.169.254/latest/meta-data/") is None
        assert download_image("http://127.0.0.1:8000/secret.png") is None
        assert download_image("file:///etc/shadow") is None

    @patch("requests.get")
    def test_download_image_enforces_payload_size_limit(self, mock_get):
        # Simulate an oversized chunk stream (> 10MB)
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {}
        # Return 11 chunks of 1MB each
        mock_response.iter_content.return_value = [b"A" * (1024 * 1024)] * 11
        mock_get.return_value = mock_response

        result = download_image("https://example.com/huge_bomb.jpg")
        assert result is None

    def test_sanitize_summary_output_validates_and_bounds_fields(self):
        raw_output = {
            "roasted_heading": "<script>alert('xss')</script> " + "Headline " * 50,
            "short_roast_summary": "<iframe src='bad.com'></iframe> " + "Short roast " * 80,
            "full_summary": "Factual summary content.",
            "is_breaking": "true",  # String truthy
            "push_punchline": "Critical 0-day in OpenSSH dropped!" + " Extra text" * 20
        }
        cleaned = sanitize_summary_output(raw_output)

        assert "<script>" not in cleaned["roasted_heading"]
        assert "<iframe" not in cleaned["short_roast_summary"]
        assert len(cleaned["roasted_heading"]) <= 200
        assert len(cleaned["short_roast_summary"]) <= 600
        assert cleaned["is_breaking"] is True
        assert len(cleaned["push_punchline"]) <= 50

    def test_is_economic_times_url(self):
        from scraper.security import is_economic_times_url
        assert is_economic_times_url("https://manufacturing.economictimes.indiatimes.com/news/123") is True
        assert is_economic_times_url("https://electronics.economictimes.indiatimes.com/news/456") is True
        assert is_economic_times_url("https://etimg.etb2bimg.com/thumb/photo.jpg") is True
        assert is_economic_times_url("https://techcrunch.com/article") is False
        assert is_economic_times_url("https://thehackernews.com/") is False
        assert is_economic_times_url(None) is False
        assert is_economic_times_url("") is False

    def test_strip_newsletter_boilerplate(self):
        from scraper.security import strip_newsletter_boilerplate
        sample_et_text = (
            "Advt\n\n"
            "Join the community of 2M+ industry professionals. Subscribe to Newsletter to get latest insights & analysis in your inbox. "
            "All about ETManufacturing industry right on your smartphone! Download the ETManufacturing App and get the Realtime updates and Save your favourite articles.\n\n"
            "This is the actual breaking news story about satellite launches."
        )
        cleaned = strip_newsletter_boilerplate(sample_et_text)
        assert "Join the community" not in cleaned
        assert "Subscribe to Newsletter" not in cleaned
        assert "in your inbox" not in cleaned
        assert "Download the ETManufacturing App" not in cleaned
        assert "Advt" not in cleaned
        assert cleaned == "This is the actual breaking news story about satellite launches."

