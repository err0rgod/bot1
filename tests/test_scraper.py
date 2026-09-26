import pytest
from unittest.mock import patch, MagicMock
from scraper.Scraper import is_already_scraped, extract_article

class TestScraper:

    @patch("scraper.Scraper.is_article_scraped")
    def test_is_already_scraped_calls_db(self, mock_is_scraped):
        mock_is_scraped.return_value = True
        assert is_already_scraped("https://example.com/test") is True
        mock_is_scraped.assert_called_once_with("https://example.com/test")

    @patch("cloudscraper.create_scraper")
    @patch("scraper.Scraper.Article")
    @patch("scraper.Scraper.random_delay")
    def test_extract_article_success(self, mock_delay, mock_article_cls, mock_cloudscraper):
        # Mock cloudscraper response
        mock_scraper_inst = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Article body content that is long enough.</p></body></html>"
        mock_scraper_inst.get.return_value = mock_response
        mock_cloudscraper.return_value = mock_scraper_inst

        # Mock Newspaper Article
        mock_article_inst = MagicMock()
        mock_article_inst.text = "This is the extracted body text of the article with sufficient length."
        mock_article_inst.top_image = "https://example.com/top.jpg"
        mock_article_cls.return_value = mock_article_inst

        result = extract_article("https://example.com/post")

        assert isinstance(result, dict)
        assert result["content"] == "This is the extracted body text of the article with sufficient length."
        assert result["image_url"] == "https://example.com/top.jpg"

    @patch("cloudscraper.create_scraper")
    @patch("scraper.Scraper.extract_article_with_firecrawl")
    @patch("scraper.Scraper.random_delay")
    def test_extract_article_fallback_to_firecrawl(self, mock_delay, mock_firecrawl, mock_cloudscraper):
        # When cloudscraper/newspaper fails, fallback to firecrawl
        mock_scraper_inst = MagicMock()
        mock_scraper_inst.get.side_effect = Exception("Cloudflare 403 Forbidden")
        mock_cloudscraper.return_value = mock_scraper_inst

        mock_firecrawl.return_value = {
            "content": "Content extracted via Firecrawl fallback",
            "image_url": None
        }

        result = extract_article("https://example.com/protected")
        assert result["content"] == "Content extracted via Firecrawl fallback"
        assert mock_firecrawl.called

    def test_is_thumbnail_url(self):
        from scraper.Scraper import is_thumbnail_url
        assert is_thumbnail_url("https://etimg.etb2bimg.com/thumb/img-size-89860/134479118.cms") is True
        assert is_thumbnail_url("https://example.com/images/thumb_100.jpg") is True
        assert is_thumbnail_url("https://example.com/avatar.png") is True
        assert is_thumbnail_url(None) is True
        assert is_thumbnail_url("") is True
        assert is_thumbnail_url("https://etimg.etb2bimg.com/thumb/msid-134489987,width-1600,height-900.jpg") is False
        assert is_thumbnail_url("https://example.com/hero.jpg") is False

    @patch("cloudscraper.create_scraper")
    @patch("scraper.Scraper.random_delay")
    def test_extract_article_json_ld(self, mock_delay, mock_cloudscraper):
        # Mock HTML with JSON-LD NewsArticle
        html = """
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "http://schema.org",
                "@type": "NewsArticle",
                "headline": "Historic Spacecraft Launch",
                "articleBody": "This is the complete and pristine news story from JSON-LD schema without ads or popups.",
                "image": [{"@type": "ImageObject", "url": "https://example.com/hero-1600.jpg"}]
            }
            </script>
        </head>
        <body><p>Some ignored body text</p></body>
        </html>
        """
        mock_scraper_inst = MagicMock()
        mock_response = MagicMock()
        mock_response.text = html
        mock_scraper_inst.get.return_value = mock_response
        mock_cloudscraper.return_value = mock_scraper_inst

        result = extract_article("https://example.com/jsonld-news")
        assert result["content"] == "This is the complete and pristine news story from JSON-LD schema without ads or popups."
        assert result["image_url"] == "https://example.com/hero-1600.jpg"

    @patch("cloudscraper.create_scraper")
    @patch("scraper.Scraper.extract_article_with_firecrawl")
    @patch("scraper.Scraper.random_delay")
    def test_extract_article_boilerplate_only_triggers_firecrawl(self, mock_delay, mock_firecrawl, mock_cloudscraper):
        # Mock HTML containing ONLY the Economic Times newsletter prompt
        html = """
        <html><body><p>Join the community of 2M+ industry professionals. Subscribe to Newsletter to get latest insights & analysis in your inbox.</p></body></html>
        """
        mock_scraper_inst = MagicMock()
        mock_response = MagicMock()
        mock_response.text = html
        mock_scraper_inst.get.return_value = mock_response
        mock_cloudscraper.return_value = mock_scraper_inst

        mock_firecrawl.return_value = {
            "content": "Real news content extracted from Firecrawl headless browser.",
            "image_url": "https://example.com/real_hero.jpg"
        }

        result = extract_article("https://manufacturing.economictimes.indiatimes.com/news/test")
        # Should fallback to Firecrawl because boilerplate was stripped leaving < 50 chars
        assert result["content"] == "Real news content extracted from Firecrawl headless browser."
        assert mock_firecrawl.called

