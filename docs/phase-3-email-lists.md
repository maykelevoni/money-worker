# Phase 3 — Email list segmentation

> Per-phase spec. **Review & approve before any code.**
> Parent plan: `PLAN.md` · Depends on: Phase 0 (tenancy) ✅
> **Status: BUILT & verified live 2026-07-07** — EmailList + Lead M2M, default "All
> subscribers" backfill, capture sources (capture page + site opt-in + /api/optin/) join a
> target list, engine sends a step when global OR the lead is on the step's list. UI: Email
> Lists page (chips/filter/create + per-lead add/remove), list pickers on capture page,
> opt-in section, and sequence step. Verified: targeted opt-in → right list; list-targeted
> step reaches only that list.

---

## 1. Goal

Turn the single flat `Lead` table into **named, segmentable lists**, so leads from different
sites / lead-magnets are grouped and can be nurtured differently. Makes **Assets → Email Lists**
a real segmentation surface (not just "all leads").

**Success = a lead captured on Site A lands on the "Site A" list; you can see, filter and
nurture each list on its own.**

---

## 2. Today's reality

- One flat `Lead` table per workspace (email, stage, lead_magnet, source_page/source_video).
- Capture sources (capture pages + site opt-in sections) create leads with a free-text
  `lead_magnet` but **no list**.
- Nurture is **one global sequence per workspace** — every non-converted lead gets the same
  emails. No way to send different sequences to different audiences.

---

## 3. Data model

```
EmailList (WorkspaceOwned)
  name          CharField        # "Sleep Tips subscribers"
  description   CharField blank
  is_active     bool

Lead
  + lists       M2M → EmailList  # a lead can be on several lists
```

**Auto-join at capture:** add an optional `email_list` target to the capture sources so new
leads join the right list automatically:
- `CapturePage.email_list` (FK, optional)
- opt-in `Section` data gets a `list_id` (optional)
- `/api/optin/` + the capture views stamp the resulting Lead onto that list

Existing leads: a data migration puts them all on a default **"All subscribers"** list so
nothing is orphaned.

---

## 4. Sequences — the key fork

Right now a `SequenceStep` targets *everyone* in the workspace. To nurture lists differently:

- **A — list-target the steps (recommended, light).** Add optional `SequenceStep.email_list`
  (FK, `null` = everyone). The engine sends a step to a lead when the step is global **or**
  the lead is on the step's list. No big refactor; back-compatible (existing steps = global).
- **B — full Sequence objects.** Introduce a `Sequence` model (a named drip) that owns its
  steps and targets a list. Cleaner long-term, bigger change to the engine + UI.
- **C — leave sequences global this phase.** Just build lists + membership + filtering now;
  per-list nurture comes later.

Recommendation: **A** — real per-list nurture with minimal disruption.

---

## 5. UI

- **Assets → Email Lists**: the lists with per-list counts; create/rename/deactivate; open a
  list to see its leads.
- **Leads view**: filter by list; add/remove/move leads between lists; bulk select.
- **Capture page + opt-in editors**: pick which list new leads join.
- **Sequences** (if 4A): each step can optionally be scoped to a list.

---

## 6. Scope

**In:** EmailList model + Lead M2M, capture-source targeting, backfill to a default list,
Lists UI + Leads filtering, (per decision) list-targeted sequence steps.

**Out (later):** import/export CSV, list-level analytics, double opt-in, unsubscribe-per-list,
tags on top of lists.

---

## 7. Decisions — LOCKED (2026-07-07)

1. **Segmentation primitive** → **named Lists** (Lead M2M to EmailList).
2. **Sequence targeting** → **A: list-target the steps** (optional `SequenceStep.email_list`,
   blank = everyone; back-compatible).

## 8. Acceptance checks
- Create two lists; point Site A's opt-in at list A, a capture page at list B.
- A lead from each lands on the right list; the Leads view filters correctly.
- (If 4A) a step scoped to list A only sends to list-A leads; a global step still sends to all.
- Another workspace never sees these lists or leads.
