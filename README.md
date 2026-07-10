<div align="center">

# 💸 Money Worker

**One app to run a content business — from a trend to a sale.**

Research what to make → create it with AI → publish it to sites you own →
capture leads → nurture them → sell your products. Multi-tenant from day one.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.x-092E20?logo=django&logoColor=white)
![Postgres](https://img.shields.io/badge/Postgres-S3--ready-4169E1?logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/license-private-lightgrey)

</div>

---

## ✨ What it is

Money Worker is a **content-creation machine**. Instead of juggling ten tools, it walks
one workflow end to end: discover a topic, generate the content (text, image, article,
short video), push it to conversion-focused websites you own, collect email leads, keep
in touch through sequences, and drive them to your products — all under one roof, and
built **multi-tenant** so it can become a product for other people without a rewrite.

```mermaid
flowchart LR
    R[🔎 Research<br/>topics & trends] --> S[🎨 Studio<br/>text · image · article · video]
    S --> A[🏗️ Assets<br/>websites · social · lists]
    A --> G[🌱 Grow<br/>sequences · scheduler]
    G --> P[🛒 Products<br/>offers & sales]
    A -. opt-in .-> L[(📥 Leads)]
    L --> G
```

---

## 🧭 The five pillars

### 🔎 Research — *what should I make?*
- **Topic Explorer**: type a keyword (or leave blank for a fresh mix) and get ranked
  topic ideas with **volume, momentum/trend, difficulty, and search intent**.
- Sort & filter by volume, momentum, difficulty, intent.
- Open a topic to see its angle, related queries, and estimated momentum.
  *(Live Google Trends via `pytrends`; gracefully falls back to AI-estimated momentum
  when rate-limited.)*
- **Spawn content in one click** — a topic becomes a Text post, Image, Article, or Video.

### 🎨 Studio — *make the content*
- **AI composer**: image gallery on the left, editor on the right, one prompt bar that
  drives both.
  - ✍️ **Text mode** — generate captions/bodies with an LLM (OpenRouter).
  - 🖼️ **Image mode** — generate images (FAL), with style presets and a **saved-character
    reference** so your mascot stays consistent.
- **Kinds**: text · image · **article/blog** · short video.
- **Avatars** — reusable characters (portrait + voice) that give your content a memorable,
  recurring face.
- **Video** — short-form vertical videos *(pipeline being refactored — see [PLAN.md](PLAN.md))*.
- **Library** & **Calendar** — everything you've made, and when it's scheduled.

### 🏗️ Assets — *the properties you own*
- **Websites** — native multi-site (no WordPress). Each site is a row + a domain.
  - Themes: Minimal · Bold · Editorial · Warm · Tech.
  - Pages + a **static blog**; articles attach and publish to a site's blog.
  - Built-in **conversion blocks**: hero, stats, benefits, testimonial, **email capture**,
    FAQ, CTA.
  - Shared SEO layer; **static output deploys to a CDN** (Cloudflare Pages / Netlify).
- **Social Accounts** — real owned accounts used as publish targets.
- **Capture Pages** — standalone lead-capture landers with public URLs.
- **Email Lists** — segment leads into lists; captures route into the right list.

### 🌱 Grow — *keep leads warm*
- **Email Sequences** — nurture flows sent to your lists (via Resend).
- **Scheduler** & **Automations** — send and automate over time.

### 🛒 Products — *make money*
- **Offers** — the products you promote and sell, linkable from content and videos.

### 📊 Plus
- **Dashboard** — a Command Center with the **"one next action"**, live counters, and a
  funnel view (Videos → Leads → Clicks → Sales).
- **Analytics** — performance across the funnel.
- **Lead capture API** — the public opt-in endpoint (`/api/optin/`) that lets a static
  site on a CDN drop a lead straight back into the right workspace + list.

---

## 🔌 Integrations

| Purpose | Service | Notes |
|---|---|---|
| Text / LLM | **OpenRouter** | Scripts, captions, article bodies |
| Images | **FAL** (Ideogram / **nano-banana**) | Character-consistent generation |
| Voice | **ElevenLabs** → **FAL F5-TTS** | Voice cloning; migrating to F5-TTS (no membership) — see [PLAN.md](PLAN.md) |
| Speech-to-text | **FAL Whisper** | Transcribe voice memos / caption timing |
| Email | **Resend** | Sequences & broadcasts |
| Social publishing | **Upload-Post** | Push content to social accounts |
| Media storage | **Local `media/` ↔ Cloudflare R2** | Flip to R2 by setting `R2_*` env vars — no code change |
| Trends | **pytrends** | Topic momentum, with AI fallback |

---

## 🚀 Getting started

**Requirements:** Python 3.12+, PostgreSQL, and [ffmpeg](https://ffmpeg.org/) (for video).

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env          # then fill in the keys below

# 3. Set up the database
python manage.py migrate
python manage.py createsuperuser

# 4. Run it
python manage.py runserver
# → http://127.0.0.1:8000
```

### Environment variables

```ini
# Core
SECRET_KEY=...
DEBUG=true
ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=postgres://user:pass@host:5432/dbname

# AI / content
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=...
FAL_API_KEY=...

# Voice (migrating ElevenLabs → FAL F5-TTS)
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...

# Email + social
RESEND_API_KEY=...
RESEND_FROM_EMAIL=...
UPLOAD_POST_API_KEY=...
UPLOAD_POST_USER=...

# Media on Cloudflare R2 (optional — leave blank to use local media/)
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=
R2_PUBLIC_URL=
```

### Docker

```bash
docker build -t money-worker .
docker run --env-file .env -p 8000:8000 money-worker
```

---

## 🗂️ Project structure

```
money-worker/
├── apps/
│   ├── accounts/    # workspaces / tenancy
│   ├── dashboard/   # Command Center + analytics
│   ├── content/     # Studio: posts, AI composer (text + image)
│   ├── videos/      # Research, Topic Explorer, avatars, video pipeline
│   ├── sites/       # Websites: pages, static blog, opt-in API
│   ├── social/      # Social accounts (publish targets)
│   ├── leads/       # Leads, email lists, capture pages
│   ├── sequences/   # Email sequences, scheduler, automations
│   └── offers/      # Products
├── config/          # Django settings + root URLs
├── templates/       # UI (server-rendered)
├── docs/            # Per-phase design docs
├── PLAN.md          # Roadmap: UX simplification + video refactor
└── manage.py
```

---

## 🛠️ Tech stack

**Backend:** Django 5 · PostgreSQL (`psycopg`) · Gunicorn · WhiteNoise
**Storage:** django-storages + boto3 (S3-compatible Cloudflare R2)
**Frontend:** server-rendered templates (Archivo + IBM Plex Mono)
**AI/media:** OpenRouter · FAL · Whisper · Resend · Upload-Post · ffmpeg

---

## 🧭 Roadmap

Active work — see **[PLAN.md](PLAN.md)**:
- **UX simplification** — one composer for all content kinds, guided next-steps,
  one-click publish, de-duplicated surfaces.
- **Video refactor** — vertical shorts (≤60s) for TikTok/Reels/Shorts: script →
  voice-clone → caption/pause-synced nano-banana images → stickman-with-avatar-face →
  ffmpeg assembly → social.

Design history lives in [`docs/`](docs/).

---

<div align="center">
<sub>Built to turn ideas into content into leads into sales — automatically.</sub>
</div>
