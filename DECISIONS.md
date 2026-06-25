# DECISIONS — append-only log

> One line per decision: date — decision — why. Never edit past entries; add a new one to reverse.
> Only Mayke's actual decisions go here.

- **≤2026-06-18** — Niche = Lane A, AI tools for content creators — recurring-commission affiliate
  programs pay monthly, fits a faceless content angle.
- **≤2026-06-18** — Stack = Python + Django, Neon, fal.ai, OpenRouter, ElevenLabs, Resend — doubles
  as Mayke's Django/web-dev practice.
- **≤2026-06-18** — Automations native in Django, NO n8n — keep one codebase, learn Django deeper.
- **≤2026-06-18** — TikTok posting is MANUAL — no posting API; app generates, Mayke uploads.
- **2026-06-19** — Faceless video = captioned image slideshow over voiceover (not text-to-video) —
  cheaper, more controllable, proven to render valid vertical MP4.
- **2026-06-21** — OpenRouter model = openai/gpt-4o-mini (was anthropic/claude-opus-4-8) — Opus is
  overkill for a 90-word script; gpt-4o-mini is far cheaper, reliable JSON, good short-form copy.
- **2026-06-21** — Video look = FLAT cartoon illustration + Ken Burns pan/zoom motion (was
  photoreal static slideshow, which looked terrible). Matches the AI cartoon-explainer style of
  Mayke's reference videos. Implementation: (a) flat-illustration IMAGE_STYLE, (b) LLM generates
  text-free VISUAL scene prompts so flux stops baking gibberish words into images, (c) fixed seed
  per video for a consistent mascot, (d) proper ASS captions (short word-chunks, lower third).

- **2026-06-23** — Content front-end redesigned: research trending ideas → pick one → AI suggests
  talking points → Mayke records a Portuguese voice memo (his real take) → STT + translate/adapt
  into the English script → existing images/voice/render pipeline. Replaces cold AI-only scripts so
  the content carries Mayke's actual perspective. Built full flow now (accepted the ship-before-first-post
  risk). Providers: research via OpenRouter `:online`, STT via fal.ai Whisper (reuse FAL key).
- **2026-06-23** — Narration = Mayke's own cloned voice (ElevenLabs instant clone, `eleven_multilingual_v2`,
  cross-lingual: PT samples → English narration). One-time `python manage.py clone_voice` mints the
  voice_id → goes in ELEVENLABS_VOICE_ID. Was default 'Rachel' TTS.

## Still OPEN (Mayke to decide — do not fill in for him)
- First affiliate offer (which specific program to promote first)
- First lead magnet / freebie
- Domain name
- Final host: Railway vs Render
- Whether/when to productize for other users (currently: not before first $100/mo per RULES #2)
