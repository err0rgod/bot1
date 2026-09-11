import pytest
import json
from unittest.mock import patch, MagicMock
from llm.deduplicator import filter_duplicate_articles

class TestDeduplicator:

    def test_filter_duplicate_articles_empty_and_single(self):
        assert filter_duplicate_articles([]) == []
        single = [{"title": "Only One Story", "summary": "Snippet"}]
        assert filter_duplicate_articles(single) == single

    @patch("llm.deduplicator.useBedrock", True)
    @patch("llm.deduplicator.bedrock_client")
    def test_filter_duplicate_articles_bedrock_success(self, mock_bedrock):
        # Mock Bedrock Converse output selecting items 0 and 2
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [
                        {"text": json.dumps({"selected_indices": [0, 2]})}
                    ]
                }
            }
        }

        candidates = [
            {"title": "MS Zero Day Exploited", "summary": "Bugs in Windows"},
            {"title": "Microsoft Patches 900 Bugs", "summary": "Same Patch Tuesday story"},
            {"title": "SpaceX Launches Rocket", "summary": "Completely different news"}
        ]

        result = filter_duplicate_articles(candidates)
        assert len(result) == 2
        assert result[0]["title"] == "MS Zero Day Exploited"
        assert result[1]["title"] == "SpaceX Launches Rocket"

    @patch("llm.deduplicator.useBedrock", False)
    @patch("llm.deduplicator.deepseek_client")
    def test_filter_duplicate_articles_deepseek_success(self, mock_deepseek):
        # Mock OpenAI chat completions output
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({"selected_indices": [1]})
        mock_deepseek.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        candidates = [
            {"title": "Story A", "summary": "Snippet A"},
            {"title": "Story B", "summary": "Snippet B"}
        ]

        result = filter_duplicate_articles(candidates)
        assert len(result) == 1
        assert result[0]["title"] == "Story B"

    @patch("llm.deduplicator.useBedrock", True)
    @patch("llm.deduplicator.bedrock_client")
    def test_filter_duplicate_articles_markdown_fence_cleaning(self, mock_bedrock):
        # Model returns JSON wrapped in markdown code blocks
        raw_markdown = "```json\n{\"selected_indices\": [0]}\n```"
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [
                        {"text": raw_markdown}
                    ]
                }
            }
        }

        candidates = [
            {"title": "Story 1", "summary": "Snippet 1"},
            {"title": "Story 2", "summary": "Snippet 2"}
        ]

        result = filter_duplicate_articles(candidates)
        assert len(result) == 1
        assert result[0]["title"] == "Story 1"

    @patch("llm.deduplicator.useBedrock", True)
    @patch("llm.deduplicator.bedrock_client")
    def test_filter_duplicate_articles_error_fallback(self, mock_bedrock):
        # When an API exception occurs, gracefully fallback to keeping all candidates
        mock_bedrock.converse.side_effect = Exception("Bedrock Rate Limited")

        candidates = [
            {"title": "Story 1", "summary": "Snippet 1"},
            {"title": "Story 2", "summary": "Snippet 2"}
        ]

        result = filter_duplicate_articles(candidates)
        assert len(result) == 2
        assert result == candidates
