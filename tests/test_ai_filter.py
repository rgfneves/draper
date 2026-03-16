from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def _mock_openai_response(pass_val: bool, reason: str):
    """Build a mock OpenAI response object."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        "pass": pass_val,
        "reason": reason,
    })
    return mock_response


@patch("pipeline.ai_filter.OpenAI")
def test_evaluate_returns_bool_and_reason(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        True, "Authentic budget traveler sharing real experiences."
    )

    from pipeline.ai_filter import evaluate_creator
    ai_pass, ai_reason = evaluate_creator(
        bio="Mochilera viajando el mundo con presupuesto mínimo",
        captions=["5 días en Roma por 150 euros"],
        hashtags=["mochilero", "lowcost"],
        niche="budget travel",
    )
    assert ai_pass is True
    assert isinstance(ai_reason, str)
    assert len(ai_reason) > 0


@patch("pipeline.ai_filter.OpenAI")
def test_evaluate_handles_empty_bio(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        False, "Insufficient information to qualify."
    )

    from pipeline.ai_filter import evaluate_creator
    ai_pass, ai_reason = evaluate_creator(
        bio="",
        captions=[],
        hashtags=[],
        niche="",
    )
    assert isinstance(ai_pass, bool)
    assert isinstance(ai_reason, str)


@patch("pipeline.ai_filter.OpenAI")
def test_evaluate_handles_api_error_returns_none(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("Connection error")

    from pipeline.ai_filter import evaluate_creator
    ai_pass, ai_reason = evaluate_creator(
        bio="some bio",
        captions=["some caption"],
        hashtags=["travel"],
        niche="travel",
    )
    assert ai_pass is None
    assert ai_reason == "evaluation_failed"


@patch("pipeline.ai_filter.OpenAI")
@patch("pipeline.ai_filter.time.sleep")
def test_evaluate_batch_processes_all_creators(mock_sleep, mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        True, "Qualifies."
    )

    from pipeline.ai_filter import evaluate_batch

    creators = [
        {"id": 1, "bio": "traveler 1", "captions": [], "hashtags": [], "niche": "travel"},
        {"id": 2, "bio": "traveler 2", "captions": [], "hashtags": [], "niche": "mochilero"},
        {"id": 3, "bio": "traveler 3", "captions": [], "hashtags": [], "niche": "backpacker"},
    ]
    results = evaluate_batch(creators, delay=0.0)
    assert len(results) == 3
    assert mock_client.chat.completions.create.call_count == 3


@patch("pipeline.ai_filter.OpenAI")
@patch("pipeline.ai_filter.time.sleep")
def test_evaluate_batch_adds_required_fields(mock_sleep, mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        False, "Brand account detected."
    )

    from pipeline.ai_filter import evaluate_batch

    creators = [{"id": 10, "bio": "agency", "captions": [], "hashtags": [], "niche": "agency"}]
    results = evaluate_batch(creators, delay=0.0)
    assert len(results) == 1
    result = results[0]
    assert "ai_filter_pass" in result
    assert "ai_filter_reason" in result
    assert result["ai_filter_pass"] is False
    assert "Brand account" in result["ai_filter_reason"]
