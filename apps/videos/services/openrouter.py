"""OpenRouter client — generates the video script package via an LLM."""
import json
import re

import requests
from django.conf import settings

API_URL = "https://openrouter.ai/api/v1/chat/completions"


class NotConfigured(Exception):
    """Raised when the OpenRouter API key is missing."""


def is_configured() -> bool:
    return bool(settings.OPENROUTER_API_KEY)


SYSTEM_PROMPT = (
    "You are a short-form video scriptwriter for a faceless TikTok/Reels/Shorts channel. "
    "You write punchy, high-retention scripts (20-40 seconds spoken) that hook in the "
    "first 2 seconds, deliver one concrete value point, and end with a soft CTA to the "
    "link in bio for a free resource. Tone: energetic, plain-spoken, no fluff. "
    "Stay relevant to whatever niche/topic the user gives — never assume one."
)

USER_TEMPLATE = (
    "{niche_clause}"
    "Create a short-form video about: \"{subject}\".\n\n"
    "Return ONLY valid JSON with these keys:\n"
    "{{\n"
    '  "title": "internal title",\n'
    '  "hook": "the first spoken line (<=12 words, scroll-stopping)",\n'
    '  "script": "the full voiceover script, 60-110 words, ready to read aloud",\n'
    '  "caption": "the caption with a CTA and 4-6 relevant hashtags"\n'
    "}}"
)


def _niche_clause(niche: str) -> str:
    """A leading instruction line that pins the niche — or explicitly stays open."""
    niche = (niche or "").strip()
    if niche:
        return f'The channel niche/topic is: "{niche}". Keep everything relevant to it.\n'
    return "The channel has no fixed niche — match the given subject.\n"


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM response."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("Could not parse JSON from model response.")


SCENE_SYSTEM = (
    "You are an art director. You turn a short video script into concise VISUAL scene "
    "descriptions for an illustrator to draw. Each description says only what to DRAW — "
    "characters, objects, setting, action, mood. NEVER include words, letters, signage, "
    "UI text, logos, or anything to be written on screen. Keep a consistent recurring "
    "character/mascot across scenes."
)


def generate_scene_prompts(script: str, n: int) -> list[str]:
    """Turn a script into exactly `n` text-free visual scene descriptions."""
    if not is_configured():
        raise NotConfigured("Set OPENROUTER_API_KEY in your .env")

    user = (
        f"Script:\n{script}\n\n"
        f"Return ONLY a JSON array of exactly {n} short strings, each a visual scene "
        f"description (no words/letters/text to display in the image)."
    )
    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": SCENE_SYSTEM},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
        },
        timeout=90,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    try:
        arr = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", content, re.DOTALL)
        arr = json.loads(match.group(0)) if match else []
    prompts = [str(s).strip() for s in arr if str(s).strip()]
    # Make the list exactly n long (pad by repeating last, or truncate).
    if not prompts:
        return []
    while len(prompts) < n:
        prompts.append(prompts[-1])
    return prompts[:n]


def _extract_json_array(text: str) -> list:
    """Pull the first JSON array out of an LLM response."""
    try:
        value = json.loads(text)
        if isinstance(value, list):
            return value
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[.*\]", text, re.DOTALL)
    return json.loads(match.group(0)) if match else []


BEAT_ART_SYSTEM = (
    "You are an art director for a faceless short-form video. You receive the video's "
    "ordered spoken beats (each a phrase said aloud). For EACH beat, write ONE concise "
    "visual scene that illustrates what's being said. Be CONCEPTUAL and figurative, not "
    "literal or photoreal — e.g. 'a pile of wasteful gadgets with a big red X over them', "
    "'a wallet stuffed with cash'. NEVER put words, letters, captions, logos, or UI text "
    "in the image. For each beat decide whether the channel's recurring avatar character "
    "should appear — use it for emotional / payoff / personal beats, NOT every beat. Keep "
    "the avatar and the overall look consistent across beats."
)


def direct_beats(beats: list[str], subject: str = "", avatar_name: str = "") -> list[dict]:
    """For each spoken beat, return `{"prompt", "uses_avatar"}` — a conceptual image
    scene and whether the avatar features. Output aligns 1:1 with `beats`."""
    if not is_configured():
        raise NotConfigured("Set OPENROUTER_API_KEY in your .env")
    if not beats:
        return []

    numbered = "\n".join(f"{i + 1}. {b}" for i, b in enumerate(beats))
    avatar_clause = (
        f'The recurring avatar character is "{avatar_name}". '
        if avatar_name
        else "There is a recurring avatar character. "
    )
    user = (
        (f'Video subject: "{subject}".\n' if subject else "")
        + avatar_clause
        + f"The spoken beats, in order:\n{numbered}\n\n"
        + f"Return ONLY a JSON array of exactly {len(beats)} objects, one per beat in "
        "order:\n"
        '[{"prompt": "visual scene to draw, no words/letters", "uses_avatar": true|false}]'
    )
    content = _chat(BEAT_ART_SYSTEM, user, temperature=0.7)
    arr = _extract_json_array(content)
    out = []
    for i in range(len(beats)):
        item = arr[i] if i < len(arr) and isinstance(arr[i], dict) else {}
        out.append(
            {
                "prompt": (str(item.get("prompt", "")).strip() or beats[i]),
                "uses_avatar": bool(item.get("uses_avatar", False)),
            }
        )
    return out


def _chat(system: str, user: str, temperature: float = 0.8) -> str:
    """Single-turn chat completion; returns the raw assistant text."""
    if not is_configured():
        raise NotConfigured("Set OPENROUTER_API_KEY in your .env")
    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        },
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


TALKING_POINTS_SYSTEM = (
    "You are a short-form content coach for a faceless TikTok/Reels/Shorts channel. "
    "Given a trending topic, you suggest concrete, specific points the creator could "
    "speak about — angles, examples, contrarian takes, a concrete tip. These are prompts "
    "to help them record their own take, not a finished script."
)


def generate_talking_points(topic: str, angle: str = "", niche: str = "") -> str:
    """Return a short bulleted list of points Mayke could cover on `topic`."""
    user = (
        _niche_clause(niche)
        + f"Topic: {topic}\n"
        + (f"Suggested angle: {angle}\n" if angle else "")
        + "Give 5-7 short bullet points (one line each, start each with '- ') of things "
        "I could say about this in a 20-40s video. Be specific and concrete. "
        "Return ONLY the bullets, no preamble."
    )
    return _chat(TALKING_POINTS_SYSTEM, user, temperature=0.8).strip()


ADAPT_SYSTEM = (
    "You are a bilingual (Portuguese↔English) short-form scriptwriter for a faceless "
    "TikTok/Reels/Shorts channel. You receive a creator's "
    "raw spoken notes in Portuguese. You must: (1) understand their actual point and "
    "personality, (2) translate and adapt it into natural, punchy ENGLISH, (3) shape it "
    "into a high-retention 20-40 second script that hooks in the first 2 seconds, keeps "
    "the creator's real opinion/voice, delivers one concrete value point, and ends with a "
    "soft CTA to the link in bio for a free resource. Keep it human, not corporate. "
    "Preserve THEIR idea — do not replace it with a generic take."
)


def adapt_transcript_to_script(
    transcript_pt: str, topic: str = "", talking_points: str = "", niche: str = ""
) -> dict:
    """Translate+adapt a Portuguese voice-memo transcript into the script package.

    Returns {title, hook, script, caption} — same shape as generate_script, so the
    rest of the pipeline (voice → scenes → render) is unchanged.
    """
    user = (
        _niche_clause(niche)
        + (f"Topic: {topic}\n" if topic else "")
        + (f"Planned talking points:\n{talking_points}\n\n" if talking_points else "")
        + "Creator's raw spoken notes (Portuguese):\n"
        f'"""{transcript_pt}"""\n\n'
        "Return ONLY valid JSON with these keys:\n"
        "{\n"
        '  "title": "internal title",\n'
        '  "hook": "first spoken line in English (<=12 words, scroll-stopping)",\n'
        '  "script": "full English voiceover, 60-110 words, ready to read aloud",\n'
        '  "caption": "TikTok caption with a CTA and 4-6 relevant hashtags"\n'
        "}"
    )
    content = _chat(ADAPT_SYSTEM, user, temperature=0.85)
    data = _extract_json(content)
    return {
        "title": data.get("title", "")[:300],
        "hook": data.get("hook", "")[:300],
        "script": data.get("script", ""),
        "caption": data.get("caption", ""),
    }


def generate_script(subject: str, niche: str = "") -> dict:
    """Return {title, hook, script, caption} for the given subject, in any niche."""
    if not is_configured():
        raise NotConfigured("Set OPENROUTER_API_KEY in your .env")

    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": USER_TEMPLATE.format(
                        subject=subject, niche_clause=_niche_clause(niche)
                    ),
                },
            ],
            "temperature": 0.9,
        },
        timeout=90,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    data = _extract_json(content)
    return {
        "title": data.get("title", "")[:300],
        "hook": data.get("hook", "")[:300],
        "script": data.get("script", ""),
        "caption": data.get("caption", ""),
    }
