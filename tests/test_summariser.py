import pytest
import json
from unittest.mock import patch, MagicMock
from llm.Summariser import generateContent

class TestSummariser:

    def test_generate_content_too_short(self):
        assert generateContent(None) is None
        assert generateContent("") is None
        assert generateContent("Too short article.") is None

    @patch("llm.Summariser.bedrock_client")
    def test_generate_content_bedrock_success(self, mock_bedrock):
        expected_json = {
            "roasted_heading": "Funny Roast Headline",
            "short_roast_summary": "Sarcastic short summary.",
            "full_summary": "Serious factual 80-100 word summary."
        }
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [
                        {"text": json.dumps(expected_json)}
                    ]
                }
            }
        }

        content = "A" * 100  # Valid length
        result = generateContent(content, use_bedrock=True)
        assert result == expected_json
        assert mock_bedrock.converse.called

    @patch("llm.Summariser.deepseek_client")
    def test_generate_content_deepseek_success(self, mock_deepseek):
        expected_json = {
            "roasted_heading": "DeepSeek Roast Headline",
            "short_roast_summary": "DeepSeek sarcastic summary.",
            "full_summary": "DeepSeek serious summary."
        }
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps(expected_json)
        mock_deepseek.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        content = "B" * 100
        result = generateContent(content, use_bedrock=False)
        assert result == expected_json
        assert mock_deepseek.chat.completions.create.called

    @patch("llm.Summariser.bedrock_client")
    def test_generate_content_markdown_fence_cleaning(self, mock_bedrock):
        expected_json = {
            "roasted_heading": "Cleaned Roast",
            "short_roast_summary": "Cleaned short summary.",
            "full_summary": "Cleaned full summary."
        }
        # Wrapped in ```json ... ```
        wrapped_text = f"```json\n{json.dumps(expected_json)}\n```"
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [
                        {"text": wrapped_text}
                    ]
                }
            }
        }

        content = "C" * 100
        result = generateContent(content, use_bedrock=True)
        assert result == expected_json

    @patch("llm.Summariser.bedrock_client")
    @patch("time.sleep")
    def test_generate_content_retry_and_failure(self, mock_sleep, mock_bedrock):
        # All 3 attempts fail
        mock_bedrock.converse.side_effect = Exception("AWS Service Unavailable")
        content = "D" * 100
        result = generateContent(content, use_bedrock=True)
        assert result is None
        assert mock_bedrock.converse.call_count == 3
