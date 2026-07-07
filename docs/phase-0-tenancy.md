# Phase 0 — Tenancy Foundation

> Per-phase spec (format for all future phases).
> Parent plan: `PLAN.md` · **Status: ✅ IMPLEMENTED 2026-07-07** — verified live (workspace
> chip renders; `claude-preview` workspace sees none of Mayke's data; a product created
> via the UI as claude was stamped to claude-preview and stayed invisible to Mayke's).

---

## 1. Goal

Give every important row an **owner** (a Workspace), so the app is ready to become a
product without a rewrite. Build it now while the tables are nearly empty; retrofitting
this later is the single most painful migration there is.

**Success = the app works exactly as it does today for Mayke, but every query is silently
scoped to a Workspace, and a second Workspace would see none of the first's data.**

---

## 2. Scope

**In:**
- A `Workspace` model (the tenant) + a `Membership` linking `User` ↔ `Workspace`.
- A `tenant` (Workspace) FK on every owned model.
- Automatic per-request tenant resolution + query isolation.
- Migration that backfills all existing rows to Mayke's Workspace.

**Explicitly OUT (later phases / not yet):**
- Public signup, billing, plans, invites, roles beyond owner.
- Custom domains / per-tenant public routing (that's Phase 1).
- Any UI beyond a read-only workspace name in the top bar.

---

## 3. Data model

Default Django `auth.User` stays. Add one small app, `apps.accounts`:

```
Workspace
  name            CharField                 # "Mayke's Workspace"
  slug            SlugField  unique         # internal id, e.g. "mayke"
  created_at      DateTimeField

Membership
  user            FK auth.User
  workspace       FK Workspace
  role            CharField  default="owner"   # owner | member (future)
  is_default      BooleanField default=False   # which workspace opens on login
  unique_together (user, workspace)
```

**Owned models get a `workspace` FK** (`on_delete=CASCADE`, `related_name="+"`):

| App | Models getting `workspace` |
|-----|----------------------------|
| content | `Post` |
| leads | `CapturePage`, `Lead` |
| offers | `Offer` |
| sequences | `SequenceStep`, `SentEmail`, `AutomationRun` |
| videos | `Video`, `Avatar`, `TopicIdea` |

`SentEmail`/`AutomationRun` carry `workspace` directly (not derived through FKs) so every
query filters on one indexed column — simpler and leak-proof.

---

## 4. Tenant resolution (per request)

1. Middleware reads the logged-in user → their **active workspace** (from session, else
   their `is_default` Membership).
2. Stores it on `request.workspace`.
3. Views/managers use `request.workspace` to scope reads and to stamp writes.

**Public capture pages** (`/p/<slug>/`, no login) are the exception: the visitor isn't
authenticated, so the workspace is resolved **from the `CapturePage` row itself**, and a
`Lead` created there inherits `page.workspace`.

---

## 5. Query isolation strategy

A small `TenantManager` + base model so scoping is the default, not a thing to remember:

```python
class TenantQuerySet(models.QuerySet):
    def for_workspace(self, ws):
        return self.filter(workspace=ws)
```

- List/detail views call `.for_workspace(request.workspace)`.
- Creates set `workspace=request.workspace`.
- Admin (superuser) still sees everything, with a workspace column + filter.

> Note: we scope **explicitly at the view layer** rather than via hidden global state.
> It's a little more typing but avoids the classic "forgot to set the tenant in a
> background job / management command" leak. The engine (`sequences/engine.py`) and any
> cron command loop **per workspace** explicitly.

---

## 6. Migration & backfill

Tiny dataset today (2 Posts, 1 Avatar, 5 TopicIdeas, everything else 0), so this is safe:

1. Create `Workspace(name="Mayke's Workspace", slug="mayke")`.
2. Create `Membership(user=mayke, workspace=…, role=owner, is_default=True)` for each
   existing user (2 users → both attached; decide if `claude` preview user shares it).
3. Data migration: set `workspace` on every existing row to Mayke's Workspace.
4. Only then flip the FKs to `null=False`.

Reversible; nothing deleted.

---

## 7. Acceptance checks (how we'll verify)

- `manage.py check` and `makemigrations --check` clean; migrations apply.
- Every existing screen (Dashboard, Studio, Assets, Grow, Products, Analytics) renders
  unchanged for Mayke, with the same data.
- Create a **throwaway second Workspace + user**, log in as them → they see **zero** of
  Mayke's posts/avatars/ideas. Log back in as Mayke → everything still there.
- Submit a public capture page → the resulting Lead is stamped with that page's workspace.
- Top bar shows the active workspace name (the switcher UI from the mockup; single option
  for now).
- Driven live via `/verify` (Playwright), not just tests.

---

## 8. Risks & things to watch

- **Leak risk** = a query that forgets to scope. Mitigation: explicit `.for_workspace()`
  at views + a checklist pass over every list view before we call it done.
- **Background jobs** (email engine, scheduler) must loop per workspace — easy to miss.
- **Public slug collisions**: today `CapturePage.slug` is globally unique. Two customers
  can't both have `/p/freebie/`. Fine for now (see decision 3).

---

## 9. Decisions — LOCKED (2026-07-07)

1. **UI name for a tenant** → **"Workspace"**.
2. **User ↔ Workspace** → **multiple**, via `Membership` (build it now).
3. **Public page slugs** → **globally unique for now**; revisit at Phase 1 (custom domains).
4. **`claude` preview user** → **its own throwaway workspace** (doubles as the isolation
   test in the acceptance checks).

Spec is settled. Implement against it on Mayke's "build" / "go".
