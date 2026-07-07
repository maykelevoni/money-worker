# Phase 2 — Social Accounts

> Per-phase spec. **Review & approve before any code.**
> Parent plan: `PLAN.md` · Depends on: Phase 0 (tenancy) ✅
> **Status: BUILT & verified live 2026-07-07** — apps.social + SocialAccount, management UI
> (Assets → Social Accounts, nav real), publishing rewired (Video share + Post compose/detail
> target chosen accounts, grouped by Upload-Post profile). Verified: 3 accounts incl. 2 on
> Instagram, workspace-isolated; workbench shows account chips filtered by format. Real
> Upload-Post posting not exercised (needs paid API + file).

---

## 1. Goal

Turn the loose publishing "channels" (bare strings like `["youtube","tiktok"]`) into **real,
owned Social Accounts** — so you know *which* account a post goes to, can hold **several
accounts per platform**, and it's all scoped per workspace. Makes the **Assets → Social
Accounts** nav real.

**Success = you register your accounts once, then when publishing a video/post you pick
*which accounts* (not just which platforms), and it goes to exactly those.**

---

## 2. Today's reality (grounds the design)

- Publishing (videos + content Posts) goes through **Upload-Post**, which takes a single
  global `UPLOAD_POST_USER` profile + a `platforms` list (`youtube|tiktok|instagram`).
- So today: **one profile, one account per platform, not workspace-scoped.** No way to run
  multiple accounts or know where content actually went.

Upload-Post's model: a **profile** (their "user") has one connected account per platform.
Multiple accounts per platform ⇒ multiple profiles.

---

## 3. Data model

```
SocialAccount (WorkspaceOwned)
  workspace     FK
  platform      youtube | tiktok | instagram   (extensible)
  handle        CharField        # @sleeptips
  display_name  CharField blank
  up_profile    CharField        # the Upload-Post profile this account lives under
  status        connected | disconnected | error
  is_active     bool
  created_at
```

Publishing target changes from platform strings → **links to SocialAccounts**:
- `Post.channels` (JSON of platform strings) → resolved against the workspace's accounts;
  add `Post.accounts` (M2M or JSON of account ids) as the real target.
- `Video` sharing likewise selects accounts, not raw platforms.

(Existing `channels` data stays readable during migration; we map it to accounts.)

---

## 4. Connecting an account

Options (this is the main decision):

- **A — via Upload-Post profiles (recommended).** Create/point to an Upload-Post profile per
  account; use Upload-Post's **hosted connect link** so you authorize the real platform
  (OAuth handled by them). We store `up_profile` + connection status. Leverages the layer you
  already pay for; no platform app-reviews for us.
- **B — direct OAuth per platform.** We build YouTube/TikTok/Instagram OAuth ourselves. Full
  control, but each needs app registration + review; heavy and slow.
- **C — manual record only.** Just store handles; keep the single global profile for actual
  posting. Lightest, but not true multi-account (no real per-account publishing).

Recommendation: **A** — it's the natural fit with the existing Upload-Post pipeline.

---

## 5. Publishing rewrite

- The publish UI (Video share + Post compose/publish) shows the workspace's **connected
  accounts grouped by platform** as the pick list, instead of raw platform checkboxes.
- On publish, selected accounts → resolve to `(up_profile, platform)` and call Upload-Post
  per profile. Per-account results tracked (extends existing `share_results`).
- `KIND_CHANNELS` still limits which platforms a content kind can go to.

---

## 6. Scope

**In:** SocialAccount model + management UI (Assets → Social Accounts), connect flow (A),
rewire Video + Post publishing to target accounts, migrate existing `channels` → accounts.

**Out (later):** analytics per account, scheduling per account, platforms beyond the current
three, team permissions per account.

---

## 7. Decisions — LOCKED (2026-07-07)

1. **Connect method** → **Upload-Post profiles** (leverage the existing pipeline).
2. **Multiple accounts per platform per workspace** → **yes, from the start**.
3. **Scope** → **model + full publishing rewire** (Video + Post target chosen accounts).

Build note: an account references its Upload-Post **profile name** (`up_profile`); you create/
connect profiles in Upload-Post and we publish per profile. Auto-creating profiles + generating
the hosted connect link via their API is a follow-up if their plan/endpoints support it.

## 8. Dependency to confirm
- Does your **Upload-Post plan allow multiple profiles**? (Needed for >1 account per platform.)
  If not, we start one-profile-per-workspace and revisit.

## 9. Acceptance checks
- Register two accounts (incl. two on one platform) → both listed, workspace-scoped.
- Publish a post to a chosen subset → only those accounts receive it; results tracked.
- Another workspace never sees or can target these accounts.
