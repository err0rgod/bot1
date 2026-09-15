from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock, patch

from db.metrics import (
    calculate_gb_seconds,
    record_scrape_metric,
    get_metrics_for_date,
    get_metrics_for_last_24_hours,
    get_article_counts_by_category,
)


class TestMetricsModule:
    def test_calculate_gb_seconds(self):
        # 1024 MB is 1.0 GB -> 1.0 GB * 30.0s = 30.0 GB-s
        assert calculate_gb_seconds(1024, 30.0) == 30.0
        # 512 MB is 0.5 GB -> 0.5 GB * 10.0s = 5.0 GB-s
        assert calculate_gb_seconds(512, 10.0) == 5.0
        # 2048 MB is 2.0 GB -> 2.0 GB * 12.5s = 25.0 GB-s
        assert calculate_gb_seconds(2048, 12.5) == 25.0

    @patch("db.metrics.metrics_table")
    def test_record_scrape_metric_success(self, mock_table):
        mock_table.put_item.return_value = {}
        success = record_scrape_metric(
            category="cybersec",
            duration_seconds=14.5,
            memory_mb=1024,
            articles_scraped=5,
            articles_summarized=5,
            status="success"
        )
        assert success is True
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["category"] == "cybersec"
        assert item["duration_seconds"] == 14.5
        assert item["gb_seconds"] == 14.5
        assert item["articles_scraped"] == 5
        assert item["articles_summarized"] == 5
        assert item["status"] == "success"

    @patch("db.metrics.metrics_table")
    def test_record_scrape_metric_exception_handling(self, mock_table):
        mock_table.put_item.side_effect = Exception("DynamoDB error")
        success = record_scrape_metric("ai", 10.0)
        assert success is False

    @patch("db.metrics.metrics_table")
    def test_get_metrics_for_date(self, mock_table):
        mock_table.query.return_value = {
            "Items": [
                {"metric_id": "1", "category": "cybersec", "duration_seconds": 12.0}
            ]
        }
        results = get_metrics_for_date("2026-09-15")
        assert len(results) == 1
        assert results[0]["category"] == "cybersec"

    @patch("db.metrics.get_metrics_for_date")
    def test_get_metrics_for_last_24_hours(self, mock_get_by_date):
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        mock_get_by_date.return_value = [
            {"timestamp": now_iso, "category": "ai", "articles_scraped": 3}
        ]
        results = get_metrics_for_last_24_hours()
        assert len(results) >= 1
        assert results[0]["category"] == "ai"

    @patch("db.metrics.articles_table")
    def test_get_article_counts_by_category(self, mock_table):
        mock_table.query.return_value = {"Count": 4}
        counts = get_article_counts_by_category("2026-09-15T00:00:00Z")
        assert isinstance(counts, dict)
        assert counts["cybersec"] == 4
        assert counts["ai"] == 4
