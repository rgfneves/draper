from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_MAX_CAPTION_CHARS = 800
_MAX_HASHTAG_CHARS = 400


def classify_niche(captions: list[str], hashtags: list[str]) -> str:
    """
    Calls the fine-tuned GPT model to classify a creator's niche.
    Returns a niche label string.
    Truncates input to avoid token limits.
    """
    from config.settings import GPT_NICHE_MODEL, OPENAI_API_KEY
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)

    # Build a compact prompt
    captions_text = " | ".join((c or "") for c in captions[:10])[:_MAX_CAPTION_CHARS]
    hashtags_text = " ".join((h or "") for h in hashtags[:50])[:_MAX_HASHTAG_CHARS]

    prompt = (
        f"Captions: {captions_text}\n"
        f"Hashtags: {hashtags_text}\n"
        "Classify the creator niche in 2-4 words (e.g. 'budget travel', 'mochilero travel', 'food blogger')."
    )

    try:
        response = client.chat.completions.create(
            model=GPT_NICHE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.0,
        )
        niche = response.choices[0].message.content.strip()
        logger.debug("Classified niche: %s", niche)
        return niche
    except Exception as exc:
        logger.warning("Niche classification failed: %s", exc)
        return ""  # empty → score_niche returns 0.0, não aprova automaticamente


def is_niche_irrelevant(niche: str, excluded_keywords: list[str]) -> bool:
    """Case-insensitive check of niche against excluded_keywords."""
    niche_lower = (niche or "").lower()
    for kw in excluded_keywords:
        pattern = re.compile(r"\b" + re.escape(kw.lower()) + r"\b")
        if pattern.search(niche_lower):
            return True
    return False
