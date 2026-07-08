# Phase 6 — New Post → AI Studio (gallery + prompt + iterative editing)

> Per-phase spec. Built iteratively with Mayke on 2026-07-07.
> **Status: BUILT & verified live** — generate, iterative edit, gallery modal all working.

---

## 1. Goal

The old New Post workbench had an unclear "✨ Ask AI" button and a single-image canvas.
Turn it into an **AI Studio**: an image **gallery** on the left, the **content** editor on the
right, and one **Prompt** bar driving both — with nano-banana-style **iterative image editing**
(generate → "make the background purple" edits *that* image). Fold **Image Studio** in.

---

## 2. Locked decisions (Mayke)

1. **Layout** — split workspace: left = image **gallery** (thumbnails) + Prompt bar; right =
   content (title + caption/body) + format/accounts/schedule/publish. Not a chat thread.
2. **Gallery** — every generation/upload becomes a tile; **click a tile → modal** with the big
   image + actions (Use for post · Edit this · Download · Delete). One tile is the selected
   (publishing) image, mirrored into `Post.media`.
3. **Prompt bar** — labelled **"Prompt"** (not "Ask AI"), with a **🖼 Image / ✍️ Text** toggle so
   it's never unclear what the box does. Image → generate or edit; Text → write the caption.
4. **Multiple reference images** — 📎 attach one or more of your own images; "Edit this" feeds a
   gallery image back. Both go to a multi-image model.
5. **Image model** — text-to-image stays **ideogram/v2** (with style); editing/multi-ref uses
   **`fal-ai/nano-banana/edit`** (`image_urls[]`, up to 14, data-URI encoded). Env overrides:
   `FAL_IMAGE_MODEL`, `FAL_EDIT_MODEL`.
6. **UI constraints** — all file pickers are **styled** buttons that open via an explicit JS
   `.click()` on a hidden input (label-wrapping was unreliable); **no `alert()`/`confirm()`** —
   inline status, toasts, and a two-click delete confirm instead.
7. **Image Studio is folded in** — nav + tab entries removed; `/content/image/` redirects to the
   New Post studio. The in-creator Library/Calendar tabs were removed too (felt out of place).
8. **No Format widget** — the post kind is **derived**, not chosen: a selected image → image
   post, otherwise text. (The old Text/Image/Everything selector was redundant.)
9. **Saved avatars as references** — an image-mode character picker lists the workspace's
   `Avatar`s; picking one feeds its image into the edit references so the character stays
   consistent across scenes (verified: Duck Hacker → same duck on a beach).

---

## 3. Data model

`content.PostImage` (new): `post` FK → images, `image`, `prompt`, `is_selected`, `created_at`.
Exactly one is selected; `_select_image()` mirrors it into `Post.media` (same stored object, no
re-upload) so the publish flow is unchanged.

---

## 4. Endpoints (content)

- `compose_ai` (POST) — `mode=text` writes the caption; `mode=image` generates (ideogram) or,
  when `edit_from`/`refs` are present, edits via nano-banana. Returns the new tile JSON.
- `gallery_upload` (POST) — ＋ tile; stores uploaded image(s) as PostImage(s).
- `image_select` / `image_delete` (POST) — select the publishing image / remove a tile
  (reselects another if the selected one is deleted).

---

## 5. Verified live 2026-07-07
- Generate "neon duck hacker" → tile appears, auto-selected, format → Image. ✓
- Click tile → modal with big image + styled Use/Edit/Download/Delete. ✓
- "Edit this" → "make the background purple" → nano-banana edited THAT image; gallery now holds
  both versions, edited one selected. ✓
- ＋ upload tile and 📎 Refs are styled (no raw "Choose File"); status is inline; no alerts. ✓

## 6. Out (later)
- Persisted chat history; drag-reorder gallery; per-image aspect ratio; caption that reads the
  selected image; removing now-dead `_route_intent`/`_IMAGE_WORDS` helpers.
