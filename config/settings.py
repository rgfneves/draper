from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

APIFY_API_TOKEN: str | None = os.getenv("APIFY_API_TOKEN") or None
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY") or None
GPT_NICHE_MODEL: str = os.getenv("GPT_NICHE_MODEL", "ft:gpt-3.5-turbo-0125:worldpackers:leads-ai-wp-4:BVTeAsTC")
GPT_FILTER_MODEL: str = os.getenv("GPT_FILTER_MODEL", "gpt-4o-mini")
DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://draper:draper@localhost:5432/draper")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
RUN_PASSWORD: str = os.getenv("RUN_PASSWORD", "123123")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

logger = logging.getLogger(__name__)
logger.debug("Settings loaded. DATABASE_URL=%s LOG_LEVEL=%s", DATABASE_URL, LOG_LEVEL)
