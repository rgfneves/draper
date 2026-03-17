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

You MUST reply with ONLY a raw JSON object — no markdown, no explanation, no code fences.
Use exactly these two keys:
- "pass": boolean (true if the creator matches the criteria, false otherwise)
- "reason": string (one sentence explaining your decision)

Your entire response must be exactly like this example:
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
    display_name: str = "",
    followers: int = 0,
    category: str = "",
    location: str = "",
    link_in_bio: str = "",
    business_account: bool = False,
    avg_engagement: float = 0.0,
    posts_last_30_days: int = 0,
    posts_detail: list[dict] | None = None,
    criteria: str | None = None,
) -> tuple[bool | None, str]:
    """
    Calls the configured GPT model with a full creator profile for evaluation.
    Returns (ai_pass: bool, ai_reason: str) on success.
    Returns (None, 'evaluation_failed') on API/network errors — caller should skip persisting.
    """
    from config.settings import GPT_FILTER_MODEL, OPENAI_API_KEY

    client = OpenAI(api_key=OPENAI_API_KEY)

    top_hashtags = " ".join((h or "") for h in hashtags[:20])[:300]

    posts_lines = ""
    if posts_detail:
        lines = []
        for i, p in enumerate(posts_detail[:10], 1):
            date = (p.get("published_at") or "")[:10]
            ptype = p.get("post_type") or "post"
            likes = p.get("likes") or 0
            comments = p.get("comments") or 0
            views = p.get("views") or 0
            caption = (p.get("caption") or "")[:100]
            lines.append(
                f"{i}. [{date}] {ptype} | ❤️{likes} 💬{comments} 👁{views}\n"
                f"   Caption: {caption or '(empty)'}"
            )
        posts_lines = "\n".join(lines)

    user_message = (
        f"Creator: {display_name or '(unknown)'}\n"
        f"Followers: {followers or 0}\n"
        f"Category: {category or '(none)'}\n"
        f"Location: {location or '(none)'}\n"
        f"Business account: {'yes' if business_account else 'no'}\n"
        f"Link in bio: {link_in_bio or '(none)'}\n"
        f"Bio: {bio or '(empty)'}\n"
        f"Niche: {niche or '(unknown)'}\n"
        f"Avg engagement: {avg_engagement:.2%}\n"
        f"Posts last 30 days: {posts_last_30_days}\n"
        f"Top hashtags: {top_hashtags or '(none)'}\n"
        f"\nRecent posts:\n{posts_lines or '(no posts)'}"
    )

    try:
        logger.debug("AI filter sending prompt [%d chars user_msg]", len(user_message))
        response = client.chat.completions.create(
            model=GPT_FILTER_MODEL,
            messages=[
                {"role": "system", "content": _build_system_prompt(criteria)},
                {"role": "user", "content": user_message},
            ],
            max_completion_tokens=200,
        )
        content = response.choices[0].message.content or "{}"
        logger.info("AI filter raw response [model=%s]: %r", GPT_FILTER_MODEL, content)
        # Strip markdown code fences if present (e.g. ```json ... ```)
        import re as _re
        json_match = _re.search(r"\{.*?\}", content, _re.DOTALL)
        if not json_match:
            logger.warning("AI filter: no JSON object found in response. raw=%r", content)
            return None, "invalid_json"
        raw_json = json_match.group()
        logger.debug("AI filter extracted JSON: %s", raw_json)
        data = json.loads(raw_json)
        # Accept common key variations in case model renames the key
        for key in ("pass", "passed", "result", "approved", "matches"):
            if key in data:
                pass_value = data[key]
                break
        else:
            logger.warning("AI filter response missing 'pass' key. parsed=%s raw=%r", data, content)
            return False, "invalid_response"
        ai_pass = bool(pass_value)
        ai_reason = str(data.get("reason", data.get("explanation", "")))
        logger.info("AI filter result: pass=%s reason=%s", ai_pass, ai_reason)
        return ai_pass, ai_reason

    except json.JSONDecodeError as exc:
        logger.warning("AI filter JSON parse failed: %s — raw content: %r", exc, locals().get('content', ''))
        return None, "invalid_json"
    except Exception as exc:
        logger.warning("AI filter evaluation failed: %s", exc)
        return None, "evaluation_failed"


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
            display_name=creator.get("display_name") or "",
            followers=creator.get("followers") or 0,
            category=creator.get("category") or "",
            location=creator.get("location") or "",
            link_in_bio=creator.get("link_in_bio") or "",
            business_account=bool(creator.get("business_account")),
            avg_engagement=creator.get("avg_engagement") or 0.0,
            posts_last_30_days=creator.get("posts_last_30_days") or 0,
            posts_detail=creator.get("posts_detail"),
            criteria=criteria,
        )
        updated = {**creator, "ai_filter_pass": ai_pass, "ai_filter_reason": ai_reason, "_eval_failed": ai_pass is None}
        results.append(updated)
        if i < len(creators) - 1 and delay > 0:
            time.sleep(delay)
    return results
