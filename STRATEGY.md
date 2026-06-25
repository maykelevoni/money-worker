# STRATEGY — the locked plan (don't re-litigate)

> These are decisions Mayke already made. Don't reopen them mid-work.
> To change anything here, do it deliberately and log it in DECISIONS.md.

## Business model
Faceless short-form video (TikTok-first, also Reels/Shorts) → "link in bio" → lead page with a
freebie → email capture → nurture drip → affiliate sales page.

## Niche (locked)
**Lane A — AI tools for content creators.** Promote recurring-commission AI affiliate programs
(Jasper, Writesonic, Pictory, Speechify, TubeBuddy — 30–50% recurring).

## Tech stack (locked)
- Backend: Python + Django (this build IS Mayke's Django practice)
- DB: Neon (Postgres) in prod; SQLite locally
- Video + images: fal.ai
- Text AI: OpenRouter
- Voice/TTS: ElevenLabs
- Email: Resend
- Automations: native Django (cron/scheduler) — NO n8n
- TikTok: app generates video, Mayke posts MANUALLY (no posting API)
- Hosting: Railway or Render (NOT Vercel — it's Django). Not yet final.

## Render approach (locked)
Faceless video = captioned image slideshow over voiceover (NOT single text-to-video).
fal.ai scene images → ffmpeg stitches images + voiceover + burned captions → 1080×1920 H.264/AAC MP4.

## Phases
0. Pick lane ✅ done
1. One asset end-to-end (first lead → first sale) ← we are here
2. Automate
3. Scale what earned
4. Own products

## The flywheel (the goals are ONE loop)
Build app (= Python practice + portfolio + content engine + income) → faceless content builds
audience → audience + portfolio → studio clients + paid community → funds next build.
