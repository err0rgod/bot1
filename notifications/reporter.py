import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import requests
import dotenv

from db.metrics import (
    get_metrics_for_last_24_hours,
    get_article_counts_by_category,
)

dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_TO_EMAIL = "ndgaming458@gmail.com"
DEFAULT_FROM_EMAIL = "ZeroDaily Ops <news@zerodaily.in>"


def build_metrics_summary() -> Dict:
    """
    Compiles scraping metrics from the last 24 hours into an aggregated summary.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    raw_metrics = get_metrics_for_last_24_hours()
    verified_db_counts = get_article_counts_by_category(cutoff_iso)

    total_scrapes = len(raw_metrics)
    total_articles_scraped = sum(int(m.get("articles_scraped", 0)) for m in raw_metrics)
    total_articles_summarized = sum(int(m.get("articles_summarized", 0)) for m in raw_metrics)
    total_duration_seconds = sum(float(m.get("duration_seconds", 0.0)) for m in raw_metrics)
    total_gb_seconds = sum(float(m.get("gb_seconds", 0.0)) for m in raw_metrics)

    # Breakdown by category
    categories = [
        "cybersec",
        "ai",
        "programming",
        "robotics",
        "defense_aerospace",
        "hardware"
    ]
    category_breakdown = {
        cat: {
            "scrape_runs": 0,
            "articles_scraped": 0,
            "articles_summarized": 0,
            "duration_seconds": 0.0,
            "gb_seconds": 0.0,
            "verified_in_db": verified_db_counts.get(cat, 0)
        }
        for cat in categories
    }

    for m in raw_metrics:
        cat = m.get("category", "unknown")
        if cat in category_breakdown:
            category_breakdown[cat]["scrape_runs"] += 1
            category_breakdown[cat]["articles_scraped"] += int(m.get("articles_scraped", 0))
            category_breakdown[cat]["articles_summarized"] += int(m.get("articles_summarized", 0))
            category_breakdown[cat]["duration_seconds"] += float(m.get("duration_seconds", 0.0))
            category_breakdown[cat]["gb_seconds"] += float(m.get("gb_seconds", 0.0))

    # Round floats for clean reporting
    for cat, data in category_breakdown.items():
        data["duration_seconds"] = round(data["duration_seconds"], 2)
        data["gb_seconds"] = round(data["gb_seconds"], 4)

    return {
        "report_generated_at": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "window": "Last 24 Hours",
        "total_scrapes": total_scrapes,
        "total_articles_scraped": total_articles_scraped,
        "total_articles_summarized": total_articles_summarized,
        "total_duration_seconds": round(total_duration_seconds, 2),
        "total_gb_seconds": round(total_gb_seconds, 4),
        "category_breakdown": category_breakdown,
        "granular_runs": raw_metrics
    }


def generate_report_html(summary: Dict) -> str:
    """
    Renders an HTML email report with responsive CSS and clean tables.
    """
    cat_rows = ""
    for cat, data in summary["category_breakdown"].items():
        cat_rows += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; font-weight: 600; text-transform: capitalize;">{cat}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: center;">{data['scrape_runs']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: center; color: #2563eb; font-weight: bold;">{data['articles_scraped']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: center;">{data['articles_summarized']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right;">{data['duration_seconds']:.2f}s</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right;">{data['gb_seconds']:.4f}</td>
        </tr>
        """

    run_rows = ""
    if summary["granular_runs"]:
        for run in summary["granular_runs"][-15:]:  # show up to 15 most recent runs
            run_rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #edf2f7; font-size: 12px; font-family: monospace;">{run.get('timestamp', '')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #edf2f7; text-transform: capitalize;">{run.get('category', '')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #edf2f7; text-align: center;">{run.get('articles_scraped', 0)}</td>
                <td style="padding: 8px; border-bottom: 1px solid #edf2f7; text-align: center;">{run.get('articles_summarized', 0)}</td>
                <td style="padding: 8px; border-bottom: 1px solid #edf2f7; text-align: right;">{float(run.get('duration_seconds', 0)):.2f}s</td>
                <td style="padding: 8px; border-bottom: 1px solid #edf2f7; text-align: right;">{float(run.get('gb_seconds', 0)):.4f}</td>
                <td style="padding: 8px; border-bottom: 1px solid #edf2f7; text-align: center; font-size: 12px;">{run.get('status', 'success')}</td>
            </tr>
            """
    else:
        run_rows = """
        <tr>
            <td colspan="7" style="padding: 16px; text-align: center; color: #718096;">No scrape executions recorded in the last 24 hours.</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #f7fafc; color: #1a202c; margin: 0; padding: 24px; }}
    .container {{ max-width: 760px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; }}
    .header {{ background-color: #0f172a; color: #ffffff; padding: 24px 32px; }}
    .header h1 {{ margin: 0 0 6px 0; font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }}
    .header p {{ margin: 0; font-size: 13px; color: #94a3b8; }}
    .content {{ padding: 32px; }}
    .metrics-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }}
    .card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; text-align: center; }}
    .card-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; margin-bottom: 6px; }}
    .card-value {{ font-size: 24px; font-weight: 700; color: #0f172a; }}
    .section-title {{ font-size: 16px; font-weight: 700; color: #0f172a; margin: 28px 0 12px 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ background: #f1f5f9; padding: 10px; font-weight: 600; text-align: left; color: #475569; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
    .footer {{ background: #f8fafc; padding: 16px 32px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8; text-align: center; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>ZeroDaily Scraping & Telemetry Report</h1>
        <p>Execution Window: {summary['window']} | Generated: {summary['report_generated_at']}</p>
    </div>
    <div class="content">
        <table style="width: 100%; margin-bottom: 24px; border: none;">
            <tr>
                <td style="width: 25%; padding: 8px;">
                    <div class="card">
                        <div class="card-label">Articles Scraped</div>
                        <div class="card-value" style="color: #2563eb;">{summary['total_articles_scraped']}</div>
                    </div>
                </td>
                <td style="width: 25%; padding: 8px;">
                    <div class="card">
                        <div class="card-label">Summarized</div>
                        <div class="card-value" style="color: #10b981;">{summary['total_articles_summarized']}</div>
                    </div>
                </td>
                <td style="width: 25%; padding: 8px;">
                    <div class="card">
                        <div class="card-label">Total Duration</div>
                        <div class="card-value">{summary['total_duration_seconds']:.1f}s</div>
                    </div>
                </td>
                <td style="width: 25%; padding: 8px;">
                    <div class="card">
                        <div class="card-label">GB-Seconds</div>
                        <div class="card-value">{summary['total_gb_seconds']:.2f}</div>
                    </div>
                </td>
            </tr>
        </table>

        <div class="section-title">Category Breakdown (Last 24 Hours)</div>
        <table>
            <thead>
                <tr>
                    <th>Category</th>
                    <th style="text-align: center;">Runs</th>
                    <th style="text-align: center;">Scraped</th>
                    <th style="text-align: center;">Summarized</th>
                    <th style="text-align: right;">Duration</th>
                    <th style="text-align: right;">GB-Seconds</th>
                </tr>
            </thead>
            <tbody>
                {cat_rows}
            </tbody>
        </table>

        <div class="section-title">Granular Scrape Execution History</div>
        <table>
            <thead>
                <tr>
                    <th>Timestamp</th>
                    <th>Category</th>
                    <th style="text-align: center;">Scraped</th>
                    <th style="text-align: center;">Summarized</th>
                    <th style="text-align: right;">Duration</th>
                    <th style="text-align: right;">GB-Seconds</th>
                    <th style="text-align: center;">Status</th>
                </tr>
            </thead>
            <tbody>
                {run_rows}
            </tbody>
        </table>
    </div>
    <div class="footer">
        ZeroDaily Automated Telemetry &copy; {datetime.now().year} | AWS us-east-1
    </div>
</div>
</body>
</html>
"""
    return html


def send_morning_digest(
    recipient: Optional[str] = None,
    from_email: Optional[str] = None
) -> Dict:
    """
    Compiles scraping metrics and delivers the daily report via Resend.
    """
    resend_api_key = os.getenv("RESEND_API_KEY")
    if not resend_api_key:
        logging.warning("[REPORTER] RESEND_API_KEY environment variable is not set. Skipping email dispatch.")
        return {
            "sent": False,
            "status": "skipped",
            "reason": "missing_api_key"
        }

    to_addr = recipient or os.getenv("REPORT_TO_EMAIL") or DEFAULT_TO_EMAIL
    sender = from_email or os.getenv("FROM_EMAIL") or DEFAULT_FROM_EMAIL

    summary = build_metrics_summary()
    html_body = generate_report_html(summary)
    subject = (
        f"ZeroDaily Morning Scraping Report - "
        f"{summary['total_articles_scraped']} Articles Scraped ({summary['total_gb_seconds']:.2f} GB-s)"
    )

    payload = {
        "from": sender,
        "to": [to_addr],
        "subject": subject,
        "html": html_body
    }

    try:
        response = requests.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {resend_api_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=15
        )

        if response.status_code in (200, 201):
            res_data = response.json()
            email_id = res_data.get("id")
            logging.info(f"[REPORTER] Morning digest successfully sent to {to_addr} (Email ID: {email_id})")
            return {
                "sent": True,
                "status": "success",
                "email_id": email_id,
                "recipient": to_addr,
                "summary": summary
            }
        else:
            logging.error(f"[REPORTER ERROR] Resend API returned status {response.status_code}: {response.text}")
            return {
                "sent": False,
                "status": "error",
                "status_code": response.status_code,
                "response": response.text
            }
    except Exception as e:
        logging.error(f"[REPORTER ERROR] Failed to deliver morning digest via Resend: {e}")
        return {
            "sent": False,
            "status": "exception",
            "error": str(e)
        }
