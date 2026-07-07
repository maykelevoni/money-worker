"""Topic Explorer — an Ubersuggest-style research brain.

Given an optional seed keyword / niche, asks an LLM to return a set of related
content topics, each with estimated search data (volume, SEO difficulty, intent),
a momentum read, a plain-English description, and related/rising queries.

Uses OpenRouter WITHOUT the `:online` web-search suffix — Google Trends supplies the
real momentum signal on the topic detail page, so the LLM only estimates + describes.
That keeps a full search to roughly a fifth of a cent on gpt-4o-mini.
"""
import json
import re

import requests
from django.conf import settings

API_URL = "https://openrouter.ai/api/v1/chat/completions"


class NotConfigured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.OPENROUTER_API_KEY)


SYSTEM = (
    "You are a keyword & content research analyst — think Ubersuggest crossed with a "
    "trend spotter. For a seed topic (or an open brief) you surface real content topics "
    "people search for, mixing VIRAL/rising angles with STABLE/evergreen ones, and you "
    "estimate their search data. Be realistic and specific; ground estimates in what such "
    "a term plausibly gets. Never invent absurd numbers."
)


def _extract_json_array(text: str) -> list:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            raise ValueError("Could not parse a JSON array from the model response.")
        data = json.loads(match.group(0))
    return data if isinstance(data, list) else []


_INTENTS = {"how-to", "ideas", "question", "commercial", "news"}
_TRENDS = {"up", "flat", "down"}


def _clean_int(value, lo, hi):
    try:
        return max(lo, min(hi, int(round(float(value)))))
    except (TypeError, ValueError):
        return None


def explore_topics(seed: str = "", niche: str = "", n: int = 10) -> list[dict]:
    """Return up to `n` researched topics with estimated data.

    Each: {headline, description, angle, why_viral, search_volume, difficulty,
    intent, trend_dir, trend_pct, related}. Mixes rising and evergreen topics.
    `seed` steers it to a specific area; blank = surface fresh ideas.
    """
    if not is_configured():
        raise NotConfigured("Set OPENROUTER_API_KEY in your .env")

    niche_line = (
        f"Creator niche/context: \"{niche.strip()}\". Keep topics relevant to it.\n"
        if niche.strip()
        else "No fixed niche — surface broadly useful topics.\n"
    )
    seed_line = (
        f"Seed keyword to explore around: \"{seed.strip()}\".\n"
        if seed.strip()
        else "No seed given — surface a fresh mix of what's worth making content about.\n"
    )
    user = (
        niche_line
        + seed_line
        + f"Return {n} content topics. Include a MIX of viral/rising and stable/evergreen.\n"
        "Return ONLY a JSON array of objects with keys:\n"
        '  "headline"      – the topic / keyword phrase (<=10 words)\n'
        '  "description"   – 2-3 plain sentences: what this topic is and why people search it\n'
        '  "angle"         – one concrete content angle to take on it\n'
        '  "search_volume" – estimated monthly searches (integer, realistic)\n'
        '  "difficulty"    – estimated SEO difficulty 0-100 (integer)\n'
        '  "intent"        – one of: how-to, ideas, question, commercial, news\n'
        '  "trend_dir"     – one of: up (rising), flat (steady), down (cooling)\n'
        '  "trend_pct"     – estimated year-over-year interest change, integer (can be negative)\n'
        '  "related"       – array of 2-4 related/rising query strings\n'
        "No prose outside the JSON."
    )
    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.OPENROUTER_MODEL or "openai/gpt-4o-mini",
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
        },
        timeout=120,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    items = _extract_json_array(content)

    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        headline = str(item.get("headline", "")).strip()[:300]
        if not headline:
            continue
        intent = str(item.get("intent", "")).strip().lower()
        trend_dir = str(item.get("trend_dir", "")).strip().lower()
        related = item.get("related") or []
        if not isinstance(related, list):
            related = []
        out.append(
            {
                "headline": headline,
                "description": str(item.get("description", "")).strip(),
                "angle": str(item.get("angle", "")).strip(),
                "why_viral": str(item.get("why_viral", "")).strip(),
                "search_volume": _clean_int(item.get("search_volume"), 0, 100_000_000),
                "difficulty": _clean_int(item.get("difficulty"), 0, 100),
                "intent": intent if intent in _INTENTS else "",
                "trend_dir": trend_dir if trend_dir in _TRENDS else "",
                "trend_pct": _clean_int(item.get("trend_pct"), -100, 100000),
                "related": [str(r).strip() for r in related if str(r).strip()][:4],
            }
        )
    return out[:n]
