# STATE — read me FIRST every session

> Live snapshot of where money-worker actually is. Update at the END of every session.
> Last updated: 2026-06-23 (new content front-end built: research→idea→PT voice→adapt→cloned voice)

## Current phase
**Phase 1 — one asset end-to-end (first lead → first sale).**
App is code-complete AND every external service now works. Remaining blockers are decisions + deploy + posting.

## 🎯 THE ONE NEXT ACTION
**Pick the first affiliate offer + lead magnet** (a decision — yours). Everything technical is proven;
the pipeline can't aim at a real CTA until there's an offer to promote and a freebie to capture for.

_(Then: generate the real first video → deploy so `/free/` is public → put link in TikTok bio → post.)_

## API test results (2026-06-21, live calls — ALL PASS)
- Neon Postgres: ✅ connected, migrations applied (fresh DB)
- OpenRouter (script): ✅ now openai/gpt-4o-mini (switched off Opus — see DECISIONS)
- fal.ai (images): ✅
- ElevenLabs (voice): ✅ (credits added; uses default 'Rachel' voice — VOICE_ID still blank)
- Resend (email): ✅ test email delivered from contact@pukalab.com
- FULL PIPELINE: ✅ created Video pk2, script→voice→images→render = valid 1080x1920 H.264/AAC MP4, ~27s

## Live assets
- App: built, runs locally (`python3 manage.py runserver`). NOT deployed.
- Database: Neon Postgres (live), migrated. Fresh/empty.
- Public capture page `/free/`: works locally, no public URL yet.
- Content posted: none.

## Money
- In: $0
- Out: $0 (keys not yet purchased)

## New content pipeline (built 2026-06-23, NOT yet run live)
Research → pick idea → AI talking points → upload PT voice memo → fal.ai Whisper transcribes →
OpenRouter translates+adapts → English script → images → cloned-voice narration → render.
Code complete, migrations applied, imports/routes/template all verified. UNTESTED live (costs +
needs Mayke's audio). To activate the cloned voice: run `python manage.py clone_voice <samples>` and
put the printed id in ELEVENLABS_VOICE_ID. New files: services/research.py, services/stt.py,
management/commands/clone_voice.py; new model TopicIdea + Video fields (topic_idea, talking_points,
source_audio, transcript_pt).

## Open loops (max 3 — close before adding more)
1. Live-test the new pipeline end-to-end: clone voice (1-3 samples), run research, pick an idea,
   record a PT memo, generate script → render. First real spend on these keys.
2. Decide first affiliate offer + lead magnet (see DECISIONS "Still OPEN").
3. Decide host (Railway vs Render) + deploy so `/free/` is public; then post first real video.

## Known gaps (not blockers to first lead)
- Analytics `clicked`/`converted` stages never get set — no offer-click tracking exists yet.
- Empty states show blank tables instead of "do this first" guidance.
- Video auto-scheduling not wired (Scheduler page shows cron instructions only).
