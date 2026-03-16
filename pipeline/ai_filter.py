from __future__ import annotations

import json
import logging
import time

from openai import OpenAI

logger = logging.getLogger(__name__)

_SYSTEM_WRAPPER = "You are a lead qualification assistant. You will follow the criteria below and select only creators who conform to it."

_DEFAULT_CRITERIA = """Authentic budget travel creators (mochileros/backpackers) from Latin America who:
- Document real, independent travel experiences
- Inspire low-cost, accessible travel — NOT luxury, resorts, or aspirational content
- Are individual creators, NOT travel agencies, brands, or commercial accounts
- Post original content, not reposts"""

_JSON_INSTRUCTION = """

Reply with a JSON object with exactly two keys:
- "pass": boolean (true if the creator conforms to the criteria, false otherwise)
- "reason": string (one sentence explaining your decision)

Example:
{"pass": true, "reason": "Authentic mochilero sharing budget tips across Latin America."}
"""


def _build_system_prompt(criteria: str | None = None) -> str:
    body = criteria.strip() if criteria and criteria.strip() else _DEFAULT_CRITERIA
    return f"{_SYSTEM_WRAPPER}\n\nCriteria:\n{body}{_JSON_INSTRUCTION}"


def evaluate_creator(
    bio: str,
    captions: list[str],
    hashtags: list[str],
    niche: str,
    *,
    criteria: str | None = None,
) -> tuple[bool, str]:
    """
    Calls GPT-4o-mini with an authenticity evaluation prompt.
    Returns (ai_pass: bool, ai_reason: str).
    Handles API errors gracefully (returns True, 'evaluation_failed' on error).
    """
    from config.settings import GPT_FILTER_MODEL, OPENAI_API_KEY

    client = OpenAI(api_key=OPENAI_API_KEY)

    sample_captions = " | ".join((c or "") for c in captions[:5])[:600]
    sample_hashtags = " ".join((h or "") for h in hashtags[:30])[:300]

    user_message = (
        f"Bio: {bio or '(empty)'}\n"
        f"Niche: {niche or '(unknown)'}\n"
        f"Recent captions: {sample_captions or '(none)'}\n"
        f"Hashtags: {sample_hashtags or '(none)'}"
    )

    try:
        response = client.chat.completions.create(
            model=GPT_FILTER_MODEL,
            messages=[
                {"role": "system", "content": _build_system_prompt(criteria)},
                {"role": "user", "content": user_message},
            ],
            max_tokens=80,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        if "pass" not in data:
            logger.warning("AI filter response missing 'pass' key: %s", content)
            return False, "invalid_response"
        ai_pass = bool(data["pass"])
        ai_reason = str(data.get("reason", ""))
        logger.debug("AI filter result: pass=%s reason=%s", ai_pass, ai_reason)
        return ai_pass, ai_reason

    except json.JSONDecodeError as exc:
        logger.warning("AI filter returned non-JSON: %s", exc)
        return False, "invalid_json"
    except Exception as exc:
        logger.warning("AI filter evaluation failed: %s", exc)
        return False, "evaluation_failed"


def evaluate_batch(
    creators: list[dict],
    delay: float = 0.5,
    *,
    criteria: str | None = None,
) -> list[dict]:
    """
    Applies evaluate_creator to each creator dict.
    Adds 'ai_filter_pass' and 'ai_filter_reason' keys.
    Rate-limited with delay between calls.
    """
    results: list[dict] = []
    for i, creator in enumerate(creators):
        ai_pass, ai_reason = evaluate_creator(
            bio=creator.get("bio") or "",
            captions=creator.get("captions") or [],
            hashtags=creator.get("hashtags") or [],
            niche=creator.get("niche") or "",
            criteria=criteria,
        )
        updated = {**creator, "ai_filter_pass": ai_pass, "ai_filter_reason": ai_reason}
        results.append(updated)
        if i < len(creators) - 1 and delay > 0:
            time.sleep(delay)
    return results
