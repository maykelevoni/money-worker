# Money Worker — Product Plan

> One app to run a content business: research a topic → make content → publish to
> sites you own → capture leads → nurture → sell. Multi-tenant from day one so it can
> become a product for others without a rewrite.
>
> When Mayke says "follow this / follow the plan", execute the workstreams below in order.
> **Do not build ahead of Mayke's go-ahead.**

---

## 1. Vision

- **Research** — discover *what* to create about; front of the funnel.
- **Studio** — the content hub: text, image, article, **short video** — from one composer.
- **Assets** — the properties you own & grow: websites, social accounts, email lists.
- **Grow** — nurture captured leads (sequences, scheduler, automations).
- **Products** — the offers you sell.

Flow, left to right: **Research → Studio → Assets → Grow → Products.**
Goal: a *money content-creation machine* that carries you through the flow instead of
making you assemble it by hand.

---

## 2. Locked decisions (don't re-litigate without Mayke)

1. **Multi-tenant from day one.** Every important row is owned by a workspace/tenant.
   Built for Mayke as a single tenant, but the ownership stamp exists so the pivot to a
   paid product is not a rewrite.
2. **Websites = native multi-site, NOT WordPress.** One app serves many sites; a new
   site = a `Website` row + a domain. Public sites are static-generated and deploy to a
   CDN (Cloudflare Pages / Netlify): near-zero hosting, top SEO. SEO layer (sitemaps,
   meta, schema, RSS) built once; every site inherits it.
3. **Two conceptual halves:** a dynamic multi-tenant Django *control tower* (research,
   create, schedule, publish, capture) and *public static websites* on a CDN whose only
   dynamic piece is the lead-capture opt-in endpoint (already live).
4. **Media storage is abstracted (local ↔ R2).** `STORAGES` in `config/settings.py`
   uses local `media/` in dev and switches to Cloudflare R2 (S3-compatible, durable
   public URLs, free egress) when the `R2_*` env vars are set — **no code change**.
   All generated assets MUST go through Django's storage API so this switch works
   (see Workstream B; today `voice.py` writes to disk directly and must be fixed).

---

## 3. Status — DONE (Phases 0–6)

- **Tenancy foundation** — workspace ownership on all models.
- **Websites** — `Website` + `Page`, themes (Minimal/Bold/Editorial/Warm/Tech), SEO
  fields, static blog, preview. Articles attach & publish to a site's blog.
- **Social Accounts** — real owned accounts as publish targets.
- **Email Lists** — leads segmented into lists; captures/sequences route to lists.
- **Research → any content** — a `TopicIdea` spawns any `Post` kind.
- **AI Studio (New Post)** — image gallery + prompt bar (text via OpenRouter, image via
  FAL) + editor, all in one draft.

**Verified end-to-end (2026-07-09, via Playwright):** Research → idea → text → image →
attach to website → publish → live conversion site → public opt-in → lead in list. ✅

**Bug fixes applied (uncommitted):**
- `apps/content/views.py` — articles/videos no longer lose their `kind` when they gain
  a hero image (previously demoted to `image`, breaking blog attach).
- `apps/sites/views.py` — article slug trimmed to the `varchar(50)` column on a hyphen
  boundary (previously a long title threw `DataError` on attach).
- **Open:** widen `Post.slug` via migration (~160) for full SEO slugs? — Mayke's call.

---

## 4. Workstream A — UX simplification (make it feel like fewer processes)

The core loop is powerful but scattered across 4 nav menus with manual handoffs, so the
user has to *assemble* the flow. Fixes, highest-leverage first:

1. **One composer, many kinds.** Merge "New Post" (Studio) and "Video Factory" into a
   single builder with a kind switch: **text / image / article / short video**. Removes
   the "which builder?" question and is the natural home for the new video pipeline.
2. **Guided next step.** After every action, surface the next action ("→ Publish to a
   site", "→ Add to an email list"), the way the dashboard's "one next action" already
   does. Make that pattern the spine of every screen.
3. **One-click publish.** Collapse attach → publish article → publish site into a single
   "Publish" that does all three.
4. **De-duplicate surfaces:**
   - Research appears twice (top-nav + a Video Factory sub-tab) → keep one.
   - Capture Pages vs the website's built-in email block → fold together / relabel
     standalone landers clearly.
   - Email Lists (under Assets) sit apart from Email Sequences (under Grow) → group
     lists + sequences together.
5. **Naming cleanup (low priority):** legacy `factory/` URLs & tabs vs the "Studio"
   language — rename later; cosmetic.

**Keep:** the dashboard "👉 one next action" + funnel visualization — the right pattern;
extend it everywhere.

---

## 5. Workstream B — Video refactor (vertical shorts)

**Scrap** the Kling talking-avatar renderer (`talking.py`). **Keep & extend** script gen,
STT, images, uploadpost. **Swap** the voice provider.

### Target
Vertical **1080×1920**, **≤60s**, for TikTok / Instagram Reels / YouTube Shorts.

### Pipeline
1. **Script** — `openrouter` (exists); tune prompt for a ≤60s hook-driven short.
2. **Voice clone** — swap `voice.py` from ElevenLabs → **FAL F5-TTS** (reuses `FAL_API_KEY`,
   no membership, cross-lingual). Store one reference clip of Mayke's voice. Route output
   through the storage API (fixes the direct-disk-write issue).
3. **Audio** — render the voiceover from the clone.
4. **Captions + timing** — extend `stt.py` (FAL Whisper) to return **word/segment
   timestamps**; detect **pauses** (gaps > ~0.4s) → segment boundaries.
5. **Images per segment** — point image gen to **nano-banana** (already on FAL,
   referenced in `images.py`); one image per caption/segment, using the avatar as a
   character reference for consistency.
6. **Avatar** — composite a **stick-man body with the selected avatar's face/head** as
   the recurring, friendly, memorable character.
7. **Assemble** — new **ffmpeg** step (ffmpeg is installed): slides switch at segment
   times + audio track + burned-in captions + avatar overlay → vertical MP4.
8. **Publish** — wire the short into the existing `uploadpost` social publish.

### New data model
A **`Segment` / `Slide`** table per video: `caption_text`, `start`, `end`, `image`,
`order` — the backbone that makes images change on the pauses.

### Decisions needed from Mayke (each changes the build)
1. **Image cadence** — one image per sentence / per pause / fixed ~4s? (more images =
   more dynamic but more nano-banana cost).
2. **Stickman + avatar-head** — how produced? (a) one reusable animated corner element,
   (b) generated per video, (c) avatar head only as a small persistent brand mark.
   *Fuzziest piece — needs Mayke's taste.*
3. **On-screen captions** — burned-in TikTok-style (word highlight) / plain / none?
4. **Music/SFX** — background track or silent?
5. **Voice reference** — Mayke records ~30–60s clean audio for the F5-TTS clone.

### Build order (when Mayke says go)
V1 voice clone → V2 timed captions → V3 nano-banana images → **V4 ffmpeg assembly**
(skip the fancy avatar first — prove a watchable synced-slides short) → V5 stickman /
avatar overlay → V6 polish (captions / music). Reaching a watchable short at **V4**
de-risks everything before investing in avatar art.

### Storage impact
Working/temp files (frames, scratch audio) → local temp during assembly. **Final
outputs** (voice clip, segment images, MP4) → storage API, so they get durable public
URLs (needed for social upload + the CDN blog) and move to R2 automatically when enabled.

---

## 6. Open decisions (need Mayke before the relevant work)

- **Static generator + CDN** for public sites: Cloudflare Pages vs Netlify vs other.
- **Custom-domain onboarding UX**: how a customer connects a domain.
- **Scope:** stop at Mayke's own use, or push toward the product surface (signup,
  billing) once the video + UX work lands.
- **`Post.slug` widening** migration (see §3).
- The five **video decisions** in §5.

---

## 7. Housekeeping

- Media assets live under `media/` (local) or R2 when configured. Root must stay free of
  stray screenshots/exports.
- A preview superuser `claude` may hold a temporary password for Playwright previews —
  clear it when no longer needed.
