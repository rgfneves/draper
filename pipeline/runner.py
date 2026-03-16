from __future__ import annotations

import argparse
import json
import logging
import sys

from db.connection import get_connection

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline.runner",
        description="Draper influencer pipeline",
    )
    parser.add_argument(
        "--platform",
        choices=["instagram", "tiktok"],
        default="instagram",
        help="Platform to run (default: instagram)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max usernames to discover (default: 200)",
    )
    parser.add_argument(
        "--profiles-only",
        action="store_true",
        help="Only discover and scrape profiles. Stop before initial filter, post scraping, and analysis.",
    )
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="Only discover + scrape + save to DB. Skip all analysis and GPT.",
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip Apify scraping — analyze creators already in DB",
    )
    parser.add_argument(
        "--skip-ai-filter",
        action="store_true",
        help="Skip the GPT AI filter step",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making any API calls",
    )
    parser.add_argument(
        "--max-scrape",
        type=int,
        default=50,
        help="Max profiles to scrape via Apify (cost control, default: 50)",
    )
    parser.add_argument(
        "--max-ai-filter",
        type=int,
        default=30,
        help="Max creators to send to AI filter per run (cost control, default: 30)",
    )
    parser.add_argument(
        "--seed-ids",
        type=str,
        default=None,
        help="Comma-separated seed IDs to run (default: all active seeds for platform)",
    )
    parser.add_argument(
        "--min-followers",
        type=int,
        default=None,
        help="Override config min_followers for initial filter",
    )
    parser.add_argument(
        "--max-followers",
        type=int,
        default=None,
        help="Override config max_followers for initial filter",
    )
    parser.add_argument(
        "--excluded-keywords",
        type=str,
        default=None,
        help="Pipe-separated list of bio keywords to exclude (overrides config defaults)",
    )
    parser.add_argument(
        "--exclude-business",
        action="store_true",
        help="Exclude creators with business_account=True",
    )
    parser.add_argument(
        "--min-total-posts",
        type=int,
        default=0,
        help="Minimum total posts published on profile (default: 0 = no filter)",
    )
    parser.add_argument(
        "--min-follower-ratio",
        type=float,
        default=0.0,
        help="Minimum followers/following ratio (default: 0.0 = no filter)",
    )
    parser.add_argument(
        "--require-email",
        action="store_true",
        help="Only keep creators with a public email on their profile",
    )
    parser.add_argument(
        "--excluded-categories",
        type=str,
        default=None,
        help="Pipe-separated Instagram business categories to exclude (e.g. 'Travel Agency|Hotel')",
    )
    parser.add_argument(
        "--ai-criteria",
        type=str,
        default=None,
        help="Custom criteria text for the AI filter system prompt (JSON instruction appended automatically)",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=30,
        help="Max posts to scrape per creator via Apify (default: 30)",
    )
    parser.add_argument(
        "--skip-with-posts",
        action="store_true",
        help="Skip creators that already have posts in DB — only scrape new ones",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    platform: str = args.platform
    limit: int = args.limit
    profiles_only: bool = args.profiles_only
    scrape_only: bool = args.scrape_only
    skip_scrape: bool = args.skip_scrape
    skip_ai_filter: bool = args.skip_ai_filter
    dry_run: bool = args.dry_run
    max_scrape: int = args.max_scrape
    max_ai_filter: int = args.max_ai_filter
    seed_ids_raw = args.seed_ids
    seed_ids = [int(x.strip()) for x in seed_ids_raw.split(",") if x.strip()] if seed_ids_raw else None
    max_posts: int = args.max_posts
    skip_with_posts: bool = args.skip_with_posts
    filter_min_followers: int | None = args.min_followers
    filter_max_followers: int | None = args.max_followers
    filter_excluded_kw_raw = args.excluded_keywords
    filter_excluded_kw: list[str] | None = (
        [k.strip() for k in filter_excluded_kw_raw.split("|") if k.strip()]
        if filter_excluded_kw_raw else None
    )
    filter_exclude_business: bool = args.exclude_business
    filter_min_total_posts: int = args.min_total_posts
    filter_min_follower_ratio: float = args.min_follower_ratio
    filter_require_email: bool = args.require_email
    filter_excluded_cats_raw = args.excluded_categories
    filter_excluded_cats: list[str] | None = (
        [k.strip() for k in filter_excluded_cats_raw.split("|") if k.strip()]
        if filter_excluded_cats_raw else None
    )
    ai_criteria: str | None = args.ai_criteria

    if dry_run:
        # profiles: ~$0.0026/each; posts: ~$0.0023/post × max_posts; AI: ~$0.001/creator
        est_profiles = limit * 0.0026
        est_posts    = max_scrape * max_posts * 0.0023
        est_openai   = max_ai_filter * 0.001
        print(
            f"[DRY RUN] platform={platform} discover_limit={limit} "
            f"max_scrape={max_scrape} max_posts={max_posts} max_ai_filter={max_ai_filter}\n"
            f"  Profiles (~{limit}): ~${est_profiles:.2f}\n"
            f"  Posts    (up to {max_scrape} × {max_posts}): ~${est_posts:.2f}\n"
            f"  OpenAI   (up to {max_ai_filter}): ~${est_openai:.2f}\n"
            f"  Total ~${est_profiles + est_posts + est_openai:.2f}"
        )

    from config.filters import EXCLUDED_KEYWORDS
    from config.seeds import SEEDS
    from db.repository import (
        finish_run,
        get_all_creators,
        get_score_history,
        insert_score_history,
        start_run,
        update_creator_ai_filter,
        update_creator_score,
        update_creator_status,
        upsert_creator,
        upsert_post,
    )
    from pipeline.analysis import analyze_creator, is_irrelevant_by_keywords
    from pipeline.scoring import compute_epic_trip_score

    conn = get_connection()
    seeds = SEEDS.get(platform, {})
    run_id = start_run(conn, platform, seeds)
    logger.info("Pipeline run started: run_id=%d platform=%s", run_id, platform)

    creators_found = 0
    creators_qualified = 0
    apify_cost = 0.0
    openai_cost = 0.0

    try:
        # ---------------------------------------------------------------
        # Step 1: Discovery
        # ---------------------------------------------------------------
        if not skip_scrape:
            from pipeline.discovery import discover
            from pipeline.initial_filter import apply_initial_filter
            from pipeline.scraping import scrape_posts_only, scrape_profiles_only

            discoveries = discover(platform, limit=limit, dry_run=dry_run, conn=conn, seed_ids=seed_ids)
            if dry_run:
                finish_run(conn, run_id, "completed", stats={}, error=None)
                return

            source_map: dict[str, tuple[str, str]] = {
                d["username"]: (d["search_type"], d["seed_value"]) for d in discoveries
            }
            all_usernames = [d["username"] for d in discoveries]

            # ---------------------------------------------------------------
            # Step 2: Profile scraping (cheap — all discovered usernames)
            # ---------------------------------------------------------------
            logger.info("Step 2: Scraping %d profiles [%s]", len(all_usernames), platform)
            raw_creators, profile_cost = scrape_profiles_only(platform, all_usernames)
            apify_cost += profile_cost

            username_to_id: dict[str, int] = {}
            for creator in raw_creators:
                if creator.username:
                    stype, sval = source_map.get(creator.username.lower(), (None, None))
                    creator.discovered_via_type = stype
                    creator.discovered_via_value = sval
                cid = upsert_creator(conn, creator)
                if creator.username:
                    username_to_id[creator.username.lower()] = cid
            creators_found = len(raw_creators)

            if profiles_only:
                logger.info("Profiles collected: %d. Stopping (--profiles-only).", creators_found)
                finish_run(conn, run_id, "completed", stats={"creators_found": creators_found})
                return

            # ---------------------------------------------------------------
            # Step 3: Initial filter (followers range + bio keywords, no posts)
            # ---------------------------------------------------------------
            logger.info("Step 3: Applying initial filter to %d profiles", creators_found)
            passed, failed = apply_initial_filter(
                raw_creators, platform,
                min_followers=filter_min_followers,
                max_followers=filter_max_followers,
                excluded_keywords=filter_excluded_kw,
                exclude_business=filter_exclude_business,
                min_total_posts=filter_min_total_posts,
                min_follower_ratio=filter_min_follower_ratio,
                require_email=filter_require_email,
                excluded_categories=filter_excluded_cats,
            )
            for c in failed:
                if c.id or c.username in username_to_id:
                    cid = c.id or username_to_id.get(c.username.lower() if c.username else "", None)
                    if cid:
                        update_creator_status(conn, cid, "excluded")

            # Optionally skip creators that already have posts in DB
            if skip_with_posts:
                ids_with_posts = {
                    row[0] for row in conn.execute(
                        "SELECT DISTINCT creator_id FROM posts"
                    ).fetchall()
                }
                passed = [
                    c for c in passed
                    if not (c.id and c.id in ids_with_posts)
                    and not (c.username and username_to_id.get(c.username.lower()) in ids_with_posts)
                ]
                logger.info("skip-with-posts: %d candidates after excluding already-scraped", len(passed))

            # Cap post scraping to max_scrape creators
            to_post_scrape = passed[:max_scrape]
            post_usernames = [c.username for c in to_post_scrape if c.username]
            logger.info(
                "Initial filter: %d passed / %d excluded → scraping posts for %d (cap=%d)",
                len(passed), len(failed), len(post_usernames), max_scrape,
            )

            # ---------------------------------------------------------------
            # Step 4: Post scraping (expensive — filtered subset only)
            # ---------------------------------------------------------------
            if post_usernames:
                logger.info("Step 4: Scraping posts for %d creators [%s]", len(post_usernames), platform)
                raw_posts, posts_cost = scrape_posts_only(platform, post_usernames, max_posts=max_posts)
                apify_cost += posts_cost

                for post in raw_posts:
                    owner = getattr(post, "_owner_username", None) or ""
                    cid = username_to_id.get(owner.lower())
                    if cid:
                        post.creator_id = cid
                        upsert_post(conn, post)
                    else:
                        logger.warning("Post descartado: username '%s' não encontrado no mapa de IDs", owner)

            if scrape_only:
                logger.info(
                    "Scrape complete: %d profiles, %d with posts. Stopping (--scrape-only).",
                    creators_found, len(post_usernames),
                )
                finish_run(conn, run_id, "completed", stats={"creators_found": creators_found})
                return

        else:
            logger.info("Skipping scrape — loading creators from DB")

        # ---------------------------------------------------------------
        # Step 2: Analyze creators
        # ---------------------------------------------------------------
        from db.models import Post as PostModel
        db_creators = get_all_creators(conn, platform=platform)
        creators_found = creators_found or len(db_creators)

        for creator in db_creators:
            if creator.id is None:
                continue

            # Load posts for this creator
            posts_rows = conn.execute(
                "SELECT * FROM posts WHERE creator_id=%s ORDER BY published_at DESC",
                (creator.id,),
            ).fetchall()
            posts = [
                PostModel(
                    id=r["id"],
                    creator_id=r["creator_id"],
                    platform=r["platform"],
                    post_id=r["post_id"],
                    post_type=r["post_type"],
                    published_at=r["published_at"],
                    engagement_rate=r["engagement_rate"],
                )
                for r in posts_rows
            ]

            metrics = analyze_creator(creator, posts)

            # Check keyword irrelevance
            captions = [
                dict(r)["caption"] or ""
                for r in conn.execute(
                    "SELECT caption FROM posts WHERE creator_id=%s", (creator.id,)
                ).fetchall()
            ]
            if is_irrelevant_by_keywords(creator.bio or "", captions, EXCLUDED_KEYWORDS):
                logger.info("Marking irrelevant by keywords: %s", creator.username)
                update_creator_status(conn, creator.id, "excluded")
                continue

            # Update creator with analysis metrics
            creator.avg_engagement = metrics["avg_engagement"]
            creator.posts_last_30_days = metrics["posts_last_30_days"]
            creator.posting_frequency = metrics["posting_frequency"]
            creator.is_active = metrics["is_active"]
            upsert_creator(conn, creator)

        # ---------------------------------------------------------------
        # Step 3: Niche classification
        # ---------------------------------------------------------------
        db_creators = get_all_creators(conn, platform=platform)
        for creator in db_creators:
            if creator.status == "excluded" or creator.id is None:
                continue
            if creator.niche:
                continue  # already classified

            captions = [
                dict(r)["caption"] or ""
                for r in conn.execute(
                    "SELECT caption FROM posts WHERE creator_id=%s LIMIT 10", (creator.id,)
                ).fetchall()
            ]
            hashtags_rows = conn.execute(
                "SELECT hashtags FROM posts WHERE creator_id=%s LIMIT 10", (creator.id,)
            ).fetchall()
            hashtags: list[str] = []
            for row in hashtags_rows:
                try:
                    tags = json.loads(row["hashtags"] or "[]")
                    hashtags.extend(tags)
                except (json.JSONDecodeError, TypeError):
                    pass

            try:
                from pipeline.niche_classifier import classify_niche, is_niche_irrelevant
                niche = classify_niche(captions, hashtags)
                if is_niche_irrelevant(niche, EXCLUDED_KEYWORDS):
                    update_creator_status(conn, creator.id, "excluded")
                    continue
                creator.niche = niche
                upsert_creator(conn, creator)
            except Exception as exc:
                logger.warning("Niche classification error for %s: %s", creator.username, exc)

        # ---------------------------------------------------------------
        # Step 4: AI Filter
        # ---------------------------------------------------------------
        if not skip_ai_filter and not dry_run:
            from pipeline.ai_filter import evaluate_batch
            db_creators = get_all_creators(conn, platform=platform)
            to_filter = []
            for c in db_creators:
                if c.status == "excluded" or c.ai_filter_pass is not None:
                    continue
                
                # Only evaluate creators that have posts (i.e., passed initial filter)
                post_count = conn.execute(
                    "SELECT COUNT(*) FROM posts WHERE creator_id=%s", (c.id,)
                ).fetchone()[0]
                if post_count == 0:
                    logger.debug("Skipping AI filter for creator %s — no posts (didn't pass initial filter)", c.id)
                    continue
                
                captions_ai = [
                    dict(r)["caption"] or ""
                    for r in conn.execute(
                        "SELECT caption FROM posts WHERE creator_id=%s LIMIT 10", (c.id,)
                    ).fetchall()
                ]
                hashtags_ai: list[str] = []
                for row in conn.execute(
                    "SELECT hashtags FROM posts WHERE creator_id=%s LIMIT 10", (c.id,)
                ).fetchall():
                    try:
                        tags = json.loads(row["hashtags"] or "[]")
                        hashtags_ai.extend(tags)
                    except (json.JSONDecodeError, TypeError):
                        pass
                to_filter.append(
                    {
                        "id": c.id,
                        "bio": c.bio or "",
                        "niche": c.niche or "",
                        "captions": captions_ai,
                        "hashtags": hashtags_ai,
                    }
                )

            # Apply AI filter cap — hard limit to control OpenAI cost
            if len(to_filter) > max_ai_filter:
                logger.info(
                    "Capping AI filter from %d to %d creators (--max-ai-filter)",
                    len(to_filter), max_ai_filter,
                )
                to_filter = to_filter[:max_ai_filter]

            if to_filter:
                evaluated = evaluate_batch(to_filter, criteria=ai_criteria)
                saved = 0
                for item in evaluated:
                    if item.get("_eval_failed"):
                        logger.warning("Skipping ai_filter persist for creator %s — evaluation_failed", item["id"])
                        continue
                    update_creator_ai_filter(
                        conn,
                        item["id"],
                        item["ai_filter_pass"],
                        item["ai_filter_reason"],
                    )
                    saved += 1
                openai_cost += saved * 0.0001  # rough estimate

        # ---------------------------------------------------------------
        # Step 5: Scoring
        # ---------------------------------------------------------------
        db_creators = get_all_creators(conn, platform=platform)
        for creator in db_creators:
            if creator.status == "excluded" or creator.id is None:
                continue

            history = get_score_history(conn, creator.id)
            metrics = {
                "avg_engagement": creator.avg_engagement or 0.0,
                "niche": creator.niche or "",
                "ai_filter_pass": creator.ai_filter_pass,
                "followers": creator.followers or 0,
                "score_history": history,
                "posts_last_30_days": creator.posts_last_30_days or 0,
            }
            scores = compute_epic_trip_score(metrics)
            update_creator_score(conn, creator.id, scores)
            insert_score_history(
                conn,
                creator.id,
                run_id,
                scores["epic_trip_score"],
                creator.followers or 0,
                creator.avg_engagement or 0.0,
            )

            if creator.ai_filter_pass is True:
                creators_qualified += 1

        # ---------------------------------------------------------------
        # Finish
        # ---------------------------------------------------------------
        finish_run(
            conn,
            run_id,
            "completed",
            stats={
                "creators_found": creators_found,
                "creators_qualified": creators_qualified,
                "apify_cost_usd": apify_cost,
                "openai_cost_usd": openai_cost,
            },
        )
        logger.info(
            "Pipeline completed: run_id=%d found=%d qualified=%d",
            run_id, creators_found, creators_qualified,
        )

    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        finish_run(conn, run_id, "failed", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
