from unittest.mock import patch, MagicMock
import pytest
from notifications.reporter import (
    build_metrics_summary,
    generate_report_html,
    send_morning_digest,
)


class TestReporterModule:
    @patch("notifications.reporter.get_metrics_for_last_24_hours")
    @patch("notifications.reporter.get_article_counts_by_category")
    def test_build_metrics_summary(self, mock_counts, mock_metrics):
        mock_metrics.return_value = [
            {
                "category": "cybersec",
                "articles_scraped": 4,
                "articles_summarized": 4,
                "duration_seconds": 20.0,
                "gb_seconds": 20.0,
                "status": "success",
                "timestamp": "2026-09-15T06:00:00Z"
            },
            {
                "category": "ai",
                "articles_scraped": 6,
                "articles_summarized": 6,
                "duration_seconds": 30.0,
                "gb_seconds": 30.0,
                "status": "success",
                "timestamp": "2026-09-15T09:00:00Z"
            }
        ]
        mock_counts.return_value = {"cybersec": 4, "ai": 6}

        summary = build_metrics_summary()
        assert summary["total_scrapes"] == 2
        assert summary["total_articles_scraped"] == 10
        assert summary["total_articles_summarized"] == 10
        assert summary["total_duration_seconds"] == 50.0
        assert summary["total_gb_seconds"] == 50.0
        assert summary["category_breakdown"]["cybersec"]["articles_scraped"] == 4
        assert summary["category_breakdown"]["ai"]["articles_scraped"] == 6

    def test_generate_report_html(self):
        sample_summary = {
            "window": "Last 24 Hours",
            "report_generated_at": "2026-09-15 12:00:00 UTC",
            "total_scrapes": 1,
            "total_articles_scraped": 5,
            "total_articles_summarized": 5,
            "total_duration_seconds": 15.2,
            "total_gb_seconds": 15.2,
            "category_breakdown": {
                "cybersec": {
                    "scrape_runs": 1,
                    "articles_scraped": 5,
                    "articles_summarized": 5,
                    "duration_seconds": 15.2,
                    "gb_seconds": 15.2
                }
            },
            "granular_runs": [
                {
                    "timestamp": "2026-09-15T10:00:00Z",
                    "category": "cybersec",
                    "articles_scraped": 5,
                    "articles_summarized": 5,
                    "duration_seconds": 15.2,
                    "gb_seconds": 15.2,
                    "status": "success"
                }
            ]
        }
        html = generate_report_html(sample_summary)
        assert "<!DOCTYPE html>" in html
        assert "ZeroDaily Scraping &amp; Telemetry Report" in html or "ZeroDaily Scraping & Telemetry Report" in html
        assert "cybersec" in html
        assert "15.2" in html

    @patch.dict("os.environ", {}, clear=True)
    def test_send_morning_digest_missing_api_key(self):
        result = send_morning_digest()
        assert result["sent"] is False
        assert result["status"] == "skipped"
        assert result["reason"] == "missing_api_key"

    @patch("notifications.reporter.requests.post")
    @patch("notifications.reporter.build_metrics_summary")
    @patch.dict("os.environ", {"RESEND_API_KEY": "test_resend_key", "REPORT_TO_EMAIL": "test@example.com"})
    def test_send_morning_digest_success(self, mock_summary, mock_post):
        mock_summary.return_value = {
            "window": "Last 24 Hours",
            "report_generated_at": "2026-09-15 12:00:00 UTC",
            "total_scrapes": 2,
            "total_articles_scraped": 10,
            "total_articles_summarized": 10,
            "total_duration_seconds": 45.0,
            "total_gb_seconds": 45.0,
            "category_breakdown": {},
            "granular_runs": []
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "resend_email_12345"}
        mock_post.return_value = mock_resp

        result = send_morning_digest()
        assert result["sent"] is True
        assert result["status"] == "success"
        assert result["email_id"] == "resend_email_12345"
        mock_post.assert_called_once()

    @patch("notifications.reporter.requests.post")
    @patch("notifications.reporter.build_metrics_summary")
    @patch.dict("os.environ", {"RESEND_API_KEY": "test_resend_key"})
    def test_send_morning_digest_api_error(self, mock_summary, mock_post):
        mock_summary.return_value = {
            "window": "Last 24 Hours",
            "report_generated_at": "2026-09-15 12:00:00 UTC",
            "total_scrapes": 0,
            "total_articles_scraped": 0,
            "total_articles_summarized": 0,
            "total_duration_seconds": 0.0,
            "total_gb_seconds": 0.0,
            "category_breakdown": {},
            "granular_runs": []
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden"
        mock_post.return_value = mock_resp

        result = send_morning_digest()
        assert result["sent"] is False
        assert result["status"] == "error"
        assert result["status_code"] == 403
