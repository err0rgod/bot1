import pytest
from unittest.mock import MagicMock, patch
from db.database import (
    format_iso_date,
    is_article_scraped,
    save_article,
    get_articles_by_category,
    get_latest_feed
)

class TestDatabaseModule:

    def test_format_iso_date_valid_rfc2822(self):
        rfc_date = "Wed, 09 Sep 2026 12:05:34 +0000"
        iso_result = format_iso_date(rfc_date)
        assert iso_result == "2026-09-09T12:05:34Z"

    def test_format_iso_date_with_none_or_empty(self):
        result_none = format_iso_date(None)
        result_empty = format_iso_date("")
        assert result_none.endswith("Z")
        assert result_empty.endswith("Z")
        assert len(result_none) == 20  # YYYY-MM-DDTHH:MM:SSZ

    def test_format_iso_date_invalid_fallback(self):
        result = format_iso_date("invalid-date-string")
        assert result.endswith("Z")
        assert len(result) == 20

    @patch("db.database.articles_table")
    def test_is_article_scraped_found(self, mock_table):
        mock_table.get_item.return_value = {"Item": {"id": "https://example.com/news1"}}
        assert is_article_scraped("https://example.com/news1") is True
        mock_table.get_item.assert_called_once_with(
            Key={"id": "https://example.com/news1"},
            ProjectionExpression="id"
        )

    @patch("db.database.articles_table")
    def test_is_article_scraped_not_found(self, mock_table):
        mock_table.get_item.return_value = {}
        assert is_article_scraped("https://example.com/unscraped") is False

    @patch("db.database.articles_table")
    def test_is_article_scraped_handles_exception(self, mock_table):
        mock_table.get_item.side_effect = Exception("AWS DynamoDB Unavailable")
        assert is_article_scraped("https://example.com/error") is False

    @patch("db.database.articles_table")
    def test_save_article_success(self, mock_table):
        article = {
            "id": "https://example.com/news1",
            "title": "Sample AI Breakthrough",
            "date": "Wed, 09 Sep 2026 12:05:34 +0000",
            "link": "https://example.com/news1",
            "image_url": "https://example.com/img.jpg"
        }
        summary_data = {
            "roasted_heading": "AI Breakthrough Roast",
            "short_roast_summary": "Very funny sarcastic summary.",
            "full_summary": "Factual 100-word summary."
        }

        result = save_article(article, "ai", summary_data)
        assert result is True
        assert mock_table.put_item.called
        call_args = mock_table.put_item.call_args[1]["Item"]

        assert call_args["id"] == "https://example.com/news1"
        assert call_args["category"] == "ai"
        assert call_args["published_at"] == "2026-09-09T12:05:34Z"
        assert call_args["feed_bucket"] == "ALL"
        assert call_args["heading"] == "AI Breakthrough Roast"
        assert call_args["shortSummary"] == "Very funny sarcastic summary."
        assert call_args["fullSummary"] == "Factual 100-word summary."
        assert call_args["image_url"] == "https://example.com/img.jpg"
        assert call_args["is_breaking"] is False
        assert call_args["push_punchline"] == ""

    @patch("db.database.articles_table")
    def test_save_article_breaking_news(self, mock_table):
        article = {
            "id": "https://example.com/breaking1",
            "title": "Major Tech Outage",
            "date": "Wed, 09 Sep 2026 12:05:34 +0000",
            "link": "https://example.com/breaking1",
            "image_url": "https://example.com/breaking.webp"
        }
        summary_data = {
            "roasted_heading": "Global Outage",
            "short_roast_summary": "Everything is on fire.",
            "full_summary": "Factual outage summary.",
            "is_breaking": True,
            "push_punchline": "Massive outage takes down services worldwide."
        }

        result = save_article(article, "dev", summary_data)
        assert result is True
        assert mock_table.put_item.called
        call_args = mock_table.put_item.call_args[1]["Item"]

        assert call_args["is_breaking"] is True
        assert call_args["push_punchline"] == "Massive outage takes down services worldwide."

    @patch("db.database.articles_table")
    def test_save_article_failure(self, mock_table):
        mock_table.put_item.side_effect = Exception("Write Capacity Exceeded")
        result = save_article({"id": "https://example.com/bad"}, "ai", {})
        assert result is False

    @patch("db.database.articles_table")
    def test_get_articles_by_category(self, mock_table):
        mock_table.query.return_value = {
            "Items": [{"id": "art1", "category": "cybersec"}, {"id": "art2", "category": "cybersec"}]
        }
        items = get_articles_by_category("cybersec", limit=10)
        assert len(items) == 2
        assert mock_table.query.called
        kwargs = mock_table.query.call_args[1]
        assert kwargs["IndexName"] == "CategoryIndex"
        assert kwargs["Limit"] == 10
        assert kwargs["ScanIndexForward"] is False

    @patch("db.database.articles_table")
    def test_get_latest_feed(self, mock_table):
        mock_table.query.return_value = {
            "Items": [{"id": "global1"}, {"id": "global2"}, {"id": "global3"}]
        }
        items = get_latest_feed(limit=5)
        assert len(items) == 3
        kwargs = mock_table.query.call_args[1]
        assert kwargs["IndexName"] == "GlobalFeedIndex"
        assert kwargs["Limit"] == 5
        assert kwargs["ScanIndexForward"] is False
