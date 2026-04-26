"""C3 Resolution Risk Scoring — hybrid LLM + rules."""

import json
from datetime import UTC, datetime

import anthropic
import structlog

from polybot.db.connection import connect as db_connect, db_write_with_retry

logger = structlog.get_logger()

HAIKU_MODEL = "claude-haiku-4-5-20251001"
HAIKU_TIMEOUT = 10.0

RELIABLE_SOURCES = [
    "reuters", "associated press", "ap news", "bls.gov",
    "federalreserve.gov", "sec.gov", "official", "government",
    "bea.gov", "treasury.gov", "whitehouse.gov",
]
UNRELIABLE_INDICATORS = [
    "twitter", "x.com", "blog", "reddit", "telegram",
    "youtube", "tiktok", "rumor", "unnamed",
]

LLM_PROMPT = (
    "You are a prediction market resolution risk analyst. "
    "Assess the risk that this market question resolves ambiguously, "
    "gets disputed, or has unclear resolution criteria.\n\n"
    "Market question: {question}\n"
    "Description: {description}\n"
    "Resolution source: {resolution_source}\n"
    "Possible outcomes: {outcomes}\n"
    "Category: {category}\n"
    "End date: {end_date}\n\n"
    "Analyze:\n"
    "1. Is the question unambiguous? Could reasonable people disagree "
    "on what constitutes a YES vs NO resolution?\n"
    "2. Is the resolution source reliable and authoritative?\n"
    "3. Are there edge cases that could lead to disputes?\n"
    "4. Is there time sensitivity that could cause resolution issues?\n\n"
    "Respond ONLY with this JSON (no markdown, no preamble).\n"
    "IMPORTANT: reasons and red_flags must be ultra-short labels, "
    "6-8 words MAX each. No full sentences. "
    'Examples: "Outcome binaire objectif", "Source officielle (FOMC)", '
    '"Date limite floue".\n\n'
    '{{"ambiguity_score": <float 0-1>, '
    '"reasons": [<1-3 ultra-short labels>], '
    '"red_flags": [<0-3 ultra-short risk labels>]}}'
)


# --- Oracle reliability ---


def oracle_reliability_score(resolution_source: str | None) -> float:
    """Score the reliability of a resolution source (0=reliable, 1=risky)."""
    source_lower = (resolution_source or "").lower()
    if any(r in source_lower for r in RELIABLE_SOURCES):
        return 0.1
    if any(u in source_lower for u in UNRELIABLE_INDICATORS):
        return 0.9
    if not resolution_source:
        return 0.7
    return 0.5


def time_risk_score(end_date: datetime | None) -> float:
    """Score resolution timing risk."""
    if end_date is None:
        return 0.3
    now = datetime.now(UTC)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=UTC)
    hours_left = (end_date - now).total_seconds() / 3600
    if hours_left < 24:
        return 0.7
    if hours_left < 72:
        return 0.4
    return 0.1


def categorize(score: float) -> str:
    """Categorize a risk score."""
    if score < 0.25:
        return "LOW"
    if score < 0.50:
        return "MEDIUM"
    if score < 0.75:
        return "HIGH"
    return "CRITICAL"


# --- Main scorer ---


class ResolutionRiskScorer:
    """Scores market resolution risk using cached LLM + dynamic rules."""

    def __init__(self, db_path: str, anthropic_api_key: str):
        self.db_path = db_path
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)

    def get_cached_llm_score(self, condition_id: str) -> dict | None:
        """Read from resolution_risk_cache. Returns None if not cached."""
        con = db_connect(self.db_path, read_only=True)
        row = con.execute(
            "SELECT llm_score, llm_reasons, llm_red_flags, llm_model_version "
            "FROM resolution_risk_cache WHERE condition_id = ?",
            [condition_id],
        ).fetchone()
        con.close()
        if not row:
            return None
        return {
            "ambiguity_score": float(row[0]) if row[0] else 0.5,
            "reasons": list(row[1]) if row[1] else [],
            "red_flags": list(row[2]) if row[2] else [],
            "model": row[3],
            "cached": True,
        }

    def call_haiku(self, market: dict) -> dict:
        """Call Claude Haiku for semantic ambiguity analysis."""
        prompt = LLM_PROMPT.format(
            question=market.get("question_text") or market.get("title") or "?",
            description=market.get("description") or "N/A",
            resolution_source=market.get("resolution_source") or "N/A",
            outcomes=market.get("outcomes") or "Yes, No",
            category=market.get("category") or "N/A",
            end_date=market.get("end_date") or market.get("resolution_date") or "N/A",
        )

        response = self.client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json.loads(text)
        return {
            "ambiguity_score": float(result.get("ambiguity_score", 0.5)),
            "reasons": result.get("reasons", [])[:3],
            "red_flags": result.get("red_flags", [])[:3],
        }

    def cache_llm_result(
        self, condition_id: str, result: dict
    ) -> None:
        """Store LLM result in resolution_risk_cache."""
        db_write_with_retry(
            self.db_path,
            lambda con: con.execute(
                """
                INSERT OR REPLACE INTO resolution_risk_cache
                    (condition_id, llm_score, llm_reasons, llm_red_flags,
                     llm_model_version, computed_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                [
                    condition_id,
                    result["ambiguity_score"],
                    result["reasons"],
                    result["red_flags"],
                    HAIKU_MODEL,
                ],
            ),
        )

    def compute_rules_score(
        self, category: str | None, end_date: datetime | None
    ) -> float:
        """Compute dynamic rules score from resolutions + market data."""
        con = db_connect(self.db_path, read_only=True)

        # Rule 1: dispute rate in category
        dispute_rate = 0.0
        if category:
            row = con.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE r.disputed = TRUE),
                    COUNT(*)
                FROM resolutions r
                JOIN markets m ON r.condition_id = m.condition_id
                WHERE m.category = ?
                """,
                [category],
            ).fetchone()
            if row and row[1] > 0:
                dispute_rate = min(row[0] / row[1] * 10, 1.0)

        # Rule 3: time risk
        t_risk = time_risk_score(end_date)

        # Rule 4: related markets clean resolution rate
        related_clean = 0.0
        if category:
            row = con.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE r.disputed = FALSE AND r.settled_outcome IS NOT NULL),
                    COUNT(*) FILTER (WHERE r.settled_outcome IS NOT NULL)
                FROM resolutions r
                JOIN markets m ON r.condition_id = m.condition_id
                WHERE m.category = ?
                  AND r.settled_at >= CURRENT_DATE - INTERVAL 30 DAY
                """,
                [category],
            ).fetchone()
            if row and row[1] > 0:
                related_clean = 1.0 - row[0] / row[1]

        con.close()

        return 0.4 * dispute_rate + 0.3 * t_risk + 0.3 * related_clean

    def _get_market(self, condition_id: str) -> dict | None:
        """Fetch market data from DB."""
        con = db_connect(self.db_path, read_only=True)
        row = con.execute(
            """
            SELECT condition_id, question_text, description, category,
                   outcomes, resolution_source, end_date, title
            FROM markets WHERE condition_id = ?
            """,
            [condition_id],
        ).fetchone()
        con.close()
        if not row:
            return None
        return {
            "condition_id": row[0],
            "question_text": row[1],
            "description": row[2],
            "category": row[3],
            "outcomes": row[4],
            "resolution_source": row[5],
            "end_date": row[6],
            "title": row[7],
        }

    def score_market(self, condition_id: str) -> dict:
        """Main entry. Returns full risk assessment."""
        market = self._get_market(condition_id)
        if not market:
            return {
                "score": 0.5, "category": "MEDIUM",
                "llm_score": None, "rules_score": 0.5,
                "oracle_score": 0.7, "reasons": ["Market not found"],
                "red_flags": [], "cached": False,
            }

        # LLM score (cached)
        cached = self.get_cached_llm_score(condition_id)
        llm_unavailable = False

        if cached:
            llm_score = cached["ambiguity_score"]
            reasons = cached["reasons"]
            red_flags = cached["red_flags"]
            was_cached = True
        else:
            from polybot.orchestrator.kill_switches import is_component_enabled
            if not is_component_enabled(self.db_path, "c3"):
                logger.info("c3_killed_rules_only", condition_id=condition_id[:16])
                return self.score_market_fallback(condition_id, market)
            try:
                result = self.call_haiku(market)
                llm_score = result["ambiguity_score"]
                reasons = result["reasons"]
                red_flags = result["red_flags"]
                self.cache_llm_result(condition_id, result)
                was_cached = False
            except Exception:
                logger.exception("haiku_call_failed", condition_id=condition_id[:16])
                return self.score_market_fallback(condition_id, market)

        # Rules score (dynamic)
        rules_score = self.compute_rules_score(
            market.get("category"), market.get("end_date")
        )

        # Oracle reliability
        oracle_score = oracle_reliability_score(market.get("resolution_source"))

        # Composite
        score = round(0.5 * llm_score + 0.3 * rules_score + 0.2 * oracle_score, 3)

        return {
            "score": score,
            "category": categorize(score),
            "llm_score": llm_score,
            "rules_score": round(rules_score, 3),
            "oracle_score": oracle_score,
            "reasons": reasons,
            "red_flags": red_flags,
            "cached": was_cached,
            "llm_unavailable": llm_unavailable,
        }

    def score_market_fallback(
        self, condition_id: str, market: dict | None = None
    ) -> dict:
        """Rules-only fallback when Haiku is unavailable."""
        if not market:
            market = self._get_market(condition_id) or {}

        rules_score = self.compute_rules_score(
            market.get("category"), market.get("end_date")
        )
        oracle_score = oracle_reliability_score(market.get("resolution_source"))

        # Without LLM, weight rules and oracle more
        score = round(0.6 * rules_score + 0.4 * oracle_score, 3)

        return {
            "score": score,
            "category": categorize(score),
            "llm_score": None,
            "rules_score": round(rules_score, 3),
            "oracle_score": oracle_score,
            "reasons": ["LLM unavailable — rules-only score"],
            "red_flags": [],
            "cached": False,
            "llm_unavailable": True,
        }
