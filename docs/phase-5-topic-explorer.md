# Phase 5 — Research revamp: Topic Explorer

> Per-phase spec. **Review & approve before any code.**
> Parent plan: `PLAN.md` · Depends on: Phase 0 (tenancy) ✅, Phase 4 (idea → any content) ✅
> **Status: BUILT & verified live 2026-07-07** — decisions locked below. Research is now a
> data-first topic explorer (Ubersuggest / Google-Trends flavour) instead of a video-idea list.

---

## 1. Goal

Research was too video-focused: it spat out short-form *video* ideas with no data. Turn it into
a **Topic Explorer** — type a seed (or leave it blank), get a list of content topics each with
estimated **search data** (volume, SEO difficulty, intent) and a **momentum** read, a
plain-English **description** so you understand the topic, then create any format from it.

**Success = I explore a topic, scan the numbers to filter, open one to understand it (with a
real Google Trends line), and spawn text/image/article/video from it.**

---

## 2. Locked decisions (from Mayke)

1. **Purpose = both** — surface **viral/rising** *and* **stable/evergreen** topics (not SEO-only,
   not trends-only). Volume/difficulty serve the evergreen/article side; Google Trends serves the
   momentum side.
2. **Data sources = AI-estimated + Google Trends.**
   - Volume / difficulty / intent / momentum estimate + the description come from the existing
     **OpenRouter** LLM (gpt-4o-mini), **with `:online` dropped** — Google Trends supplies the
     real signal, so the LLM only estimates + describes. Keeps a full search ≈ **$0.002**
     (~$2 / 1,000 searches). Google Trends (pytrends) is **free**.
   - Real **Google Trends** (interest-over-time sparkline + rising queries) is fetched **on the
     topic detail page only**, for one term — never for the whole list — so we don't trip its
     rate limit. Best-effort: any failure degrades to the AI estimate.
3. **One combined list**, not split into viral/stable sections. Each row shows the numbers so you
   filter/scan without opening anything.
4. **Replaces** the old trending-video-ideas generator entirely.

---

## 3. Data model

`videos.TopicIdea` gains research fields (headline = the topic phrase):
```
seed          Char     # the term this came from (blank = open)
description   Text     # "what this is"
search_volume Int null # est. monthly searches
difficulty    Int null # est. SEO difficulty 0-100
intent        Char     # how-to | ideas | question | commercial | news
trend_dir     Char     # up | flat | down
trend_pct     Int null # est. YoY interest change
related       JSON     # related / rising queries
```
Provenance FKs from Phase 4 (`Post.source_idea`, `Video.source_idea`) are unchanged.

---

## 4. Flow

- **Explore** (`research_run`) → `research.explore_topics(seed, niche)` → 1 LLM call → saves ~10
  `TopicIdea` rows with data (mix of rising + evergreen).
- **List** (`research_page`) → all non-archived topics in one sortable/filterable table
  (sort: volume / momentum / easiest / newest; filter: min volume, max difficulty, trend, intent).
- **Detail** (`topic_detail`) → metrics + real Google Trends (`trends.interest`, graceful) +
  description + angle + related queries + the Phase-4 create buttons (Text/Image/Article/Video)
  + Archive / Delete.

---

## 5. Scope

**In:** TopicIdea data fields; LLM explorer (no `:online`); combined sortable/filterable list;
topic detail page; Google Trends enrichment on detail (pytrends, best-effort); reuse Phase-4
spawn/pick; `pytrends` added to requirements.

**Out (later):** paid SEO API (real absolute volume/CPC), trend charts on the list itself,
saved searches, per-topic scheduling, moving `TopicIdea` into its own `research` app.

---

## 6. Acceptance checks — all verified live 2026-07-07
- Seed "faceless youtube" → 9 topics with volume/trend/difficulty/intent + descriptions. ✓
- Sort/filter bar present and wired. ✓
- Topic detail shows metrics, **real Google Trends** (+344% sparkline), description, angle. ✓
- "Article" from a topic opens a pre-seeded post ("From research: …", caption from the angle). ✓
- Google Trends failure degrades to AI estimate (try/except returns None). ✓
- Another workspace never sees these topics.
