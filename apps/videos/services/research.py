"""Trend research — asks an online-capable LLM for currently-viral content ideas.

Uses OpenRouter's `:online` web-search suffix so the model can ground its answer in
live search results instead of stale training data. No extra API key required.
"""
import json
import re

import requests
from django.conf import settings

API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Niche is locked (STRATEGY.md): AI tools for content creators.
NICHE = "AI tools for content creators (faceless short-form / TikTok)"


class NotConfigured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.OPENROUTER_API_KEY)


SYSTEM = (
    "You are a short-form content strategist. You find topics that are trending RIGHT NOW "
    "and are a strong fit for a faceless TikTok channel about AI tools for content creators. "
    "Use live web results. Prefer concrete, specific, timely angles over evergreen generalities."
)


def _online_model() -> str:
    """Force web search by appending the :online suffix if not already present."""
    model = settings.OPENROUTER_MODEL or "openai/gpt-4o-mini"
    return model if model.endswith(":online") else f"{model}:online"


def _extract_json_array(text: str) -> list:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            raise ValueError("Could not parse a JSON array from the model response.")
        data = json.loads(match.group(0))
    return data if isinstance(data, list) else []


def find_trending_topics(n: int = 5, niche: str = NICHE, keyword: str = "") -> list[dict]:
    """Return up to `n` trending ideas: [{headline, why_viral, angle}].

    Pass `keyword` to steer the search toward a specific tool, theme, or trend
    (e.g. "Sora", "AI thumbnails", "faceless YouTube"). Blank = whatever's hot.
    """
    if not is_configured():
        raise NotConfigured("Set OPENROUTER_API_KEY in your .env")

    focus = (
        f"Focus the search on this keyword/theme: \"{keyword.strip()}\". "
        "Stay within the niche but make every idea clearly relevant to it.\n"
        if keyword.strip()
        else ""
    )
    user = (
        f"Niche: {niche}.\n"
        f"{focus}"
        f"Find {n} topics trending in the last ~2 weeks that this channel could ride.\n"
        "Return ONLY a JSON array of objects with keys:\n"
        '  "headline"  – the scroll-stopping topic/title (<=12 words)\n'
        '  "why_viral" – one sentence on why it is trending / will perform\n'
        '  "angle"     – how to tie it to a specific AI tool for creators\n'
        "No prose outside the JSON."
    )
    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": _online_model(),
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            "temperature": 0.8,
        },
        timeout=120,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    ideas = _extract_json_array(content)

    out = []
    for item in ideas:
        if not isinstance(item, dict):
            continue
        headline = str(item.get("headline", "")).strip()[:300]
        if not headline:
            continue
        out.append(
            {
                "headline": headline,
                "why_viral": str(item.get("why_viral", "")).strip(),
                "angle": str(item.get("angle", "")).strip(),
            }
        )
    return out[:n]
