# Phase 4 — Research → any content

> Per-phase spec. **Review & approve before any code.**
> Parent plan: `PLAN.md` · Depends on: Phase 0 (tenancy) ✅, content.Post (exists) ✅
> **Status: BUILT 2026-07-07** — decisions locked (D1-A kind picker, D2-A reusable + badge).
> `Post.source_idea` + `Video.source_idea` FKs; research card has a Text/Image/Article picker
> (spawns a pre-seeded Post → workbench) alongside the existing Video button; ideas stay in
> research after picking, showing a "✓ used: N posts · M videos" badge + Archive; the workbench
> shows "From research: <headline>".

---

## 1. Goal

Make **Research** the true front-of-funnel for the whole Studio. Today a `TopicIdea`
can only become a **Video**. Let one idea spawn **any** content kind — text post, image,
article/blog, or video — so research feeds every Studio format, not just the video factory.

**Success = from a researched idea I can, in one click, start a text post / image / article /
video that opens pre-seeded from that idea, and I can see which idea a piece of content came
from.**

---

## 2. Today's reality

- `videos.TopicIdea` (headline / why_viral / angle / `selected` bool) is created by the
  research step in **Studio → (Video Factory) → Research**.
- Its only exit is `pick_idea` → `Video.objects.create(...)` + `generate_talking_points`,
  then `idea.selected = True` (which drops it from the research list forever).
- `content.Post` already models every kind (`text`/`image`/`video`/`article`) and already
  carries a `source_video` FK for provenance. It has **no** link to a `TopicIdea`.
- The Studio compose page (`content.compose`) already routes a chosen "format" → `Post.kind`
  and can AI-seed a draft (`compose_ai`).

So the pipes on both ends exist. Phase 4 connects them.

---

## 3. Data model

```
Post (content)
  + source_idea   FK → videos.TopicIdea  (null, SET_NULL)   # provenance, mirrors source_video

TopicIdea (videos)
  (unchanged fields; see decision D2 on whether picking still "consumes" the idea)
```

No new top-level model — a `TopicIdea` simply gains a second exit (into `Post`) alongside its
existing exit (into `Video`).

---

## 4. The two real forks

### D1 — Where does the "make content from idea" choice live?

- **A — one picker on the research card (recommended).** The current single
  "Create video →" button becomes a small kind picker: **Text · Image · Article · Video**.
  Video keeps the existing pipeline; the other three create a `Post` of that kind
  (`source_idea` set, title/body pre-seeded from headline+angle) and land on the Studio
  compose page. One surface, matches how `pick_idea` already works.
  - *Risk:* the research card gets slightly busier.
- **B — keep Video button, add a separate "Send to Studio →".** Video button unchanged;
  a second control creates a `Post` (defaulting to text) and opens compose, where the kind is
  chosen. Simpler card, but the kind decision moves off research and Video stays a
  special-case sibling instead of "just another kind".

### D2 — Does picking an idea still consume it?

Today `pick` sets `selected=True` and the idea vanishes. If an idea can now spawn several
pieces (a text post *and* a video), auto-consuming on first pick blocks reuse.

- **A — stop consuming; keep ideas in the list (recommended).** Picking creates the content
  and leaves the idea available; show a "used → 2 posts, 1 video" badge instead. Lets one
  strong idea feed multiple formats. Add an explicit archive/delete to clear it.
  - *Risk:* research list grows; needs an "archive" affordance (delete already exists).
- **B — keep current behavior (pick consumes).** First pick hides the idea. Simplest, but a
  good idea can only ever become one piece — which undercuts the whole "feed every format"
  goal.

---

## 5. UI

- **Research card:** per D1 — a kind picker (A) or a second "Send to Studio" control (B).
- **Content library / post detail:** show the source idea ("From research: <headline>") the
  same way a repurposed post shows its source video.
- **AI seeding:** for a non-video kind, pre-fill the `Post` title from the idea headline and
  the body from the angle (reuse existing `compose_ai` seed path where it fits).

---

## 6. Scope

**In:** `Post.source_idea` FK; a research-card path that spawns any `Post` kind; pre-seed
title/body from the idea; source-idea provenance shown on the post; (per D2) idea reuse.

**Out (later):** bulk "spawn a whole content set from one idea", research-driven scheduling,
per-kind AI templates, moving `TopicIdea` out of the `videos` app into a `research` app.

---

## 7. Decisions — LOCKED (2026-07-07)

1. **D1 — where the choice lives** → **A: kind picker on the research card**
   (Text · Image · Article buttons spawn a Post; Video keeps its pipeline).
2. **D2 — idea consumption** → **A: reusable** — picking no longer consumes the idea; it stays
   in research with a "✓ used" badge and an explicit Archive to clear it.

## 8. Acceptance checks
- From one idea, spawn a text post and (separately) a video; both open pre-seeded.
- The text post shows "From research: <headline>"; the video still works as before.
- (If D2-A) the idea remains in research with a "used" badge and can be archived.
- Another workspace never sees these ideas or the content spawned from them.
