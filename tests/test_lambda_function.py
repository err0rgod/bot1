import pytest
import json
from unittest.mock import patch, MagicMock
from lambdaFunction import run_pipeline_for_category, lambda_handler, ALL_CATEGORIES


class TestLambdaFunction:

    @patch("lambdaFunction.NewsFeeds.get_feeds")
    def test_run_pipeline_no_feeds(self, mock_get_feeds):
        mock_get_feeds.return_value = []
        result = run_pipeline_for_category("unknown_category")
        assert result["status"] == "no_feeds"
        assert result["scraped"] == 0
        assert result["summarized"] == 0

    @patch("lambdaFunction.scrape_rss_feed")
    @patch("lambdaFunction.NewsFeeds.get_feeds")
    def test_run_pipeline_no_articles(self, mock_get_feeds, mock_scrape):
        mock_get_feeds.return_value = ["https://example.com/rss"]
        mock_scrape.return_value = []
        result = run_pipeline_for_category("ai")
        assert result["status"] == "no_new_articles"
        assert result["scraped"] == 0
        assert result["summarized"] == 0

    @patch("lambdaFunction.process_single_article")
    @patch("lambdaFunction.scrape_rss_feed")
    @patch("lambdaFunction.NewsFeeds.get_feeds")
    def test_run_pipeline_success(self, mock_get_feeds, mock_scrape, mock_process):
        mock_get_feeds.return_value = ["https://example.com/rss"]
        mock_scrape.return_value = [
            {"id": "http://example.com/1", "title": "Article 1", "content": "Content 1"},
            {"id": "http://example.com/2", "title": "Article 2", "content": "Content 2"}
        ]
        mock_process.side_effect = [
            {"id": "http://example.com/1", "heading": "Roast 1"},
            {"id": "http://example.com/2", "heading": "Roast 2"}
        ]

        result = run_pipeline_for_category("ai")
        assert result["status"] == "success"
        assert result["scraped"] == 2
        assert result["summarized"] == 2

    @patch("lambdaFunction.scrape_handler")
    def test_lambda_handler_action_scrape(self, mock_scrape_handler):
        mock_scrape_handler.return_value = {"statusCode": 200, "body": "Scraped"}
        event = {"action": "scrape", "category": "ai"}
        res = lambda_handler(event, None)
        assert res["statusCode"] == 200
        mock_scrape_handler.assert_called_once_with(event, None)

    @patch("lambdaFunction.summarize_handler")
    def test_lambda_handler_action_summarize(self, mock_summarize_handler):
        mock_summarize_handler.return_value = {"statusCode": 200, "body": "Summarized"}
        event = {"action": "summarize", "category": "ai"}
        res = lambda_handler(event, None)
        assert res["statusCode"] == 200
        mock_summarize_handler.assert_called_once_with(event, None)

    @patch("lambdaFunction.run_pipeline_for_category")
    def test_lambda_handler_single_category(self, mock_pipeline):
        mock_pipeline.return_value = {"category": "cybersec", "scraped": 1, "summarized": 1, "status": "success"}
        event = {"category": "cybersec"}
        res = lambda_handler(event, None)
        assert res["statusCode"] == 200
        body = json.loads(res["body"])
        assert len(body["results"]) == 1
        assert body["results"][0]["category"] == "cybersec"
        mock_pipeline.assert_called_once_with("cybersec")

    @patch("lambdaFunction.run_pipeline_for_category")
    def test_lambda_handler_all_categories_default(self, mock_pipeline):
        mock_pipeline.return_value = {"status": "success"}
        event = {}
        res = lambda_handler(event, None)
        assert res["statusCode"] == 200
        body = json.loads(res["body"])
        assert len(body["results"]) == len(ALL_CATEGORIES)
        assert mock_pipeline.call_count == len(ALL_CATEGORIES)
