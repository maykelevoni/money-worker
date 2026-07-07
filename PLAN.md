# Money Worker — Product Plan

> Reorganize the app around three pillars, and build it **multi-tenant from day one**
> so it can become a product for other people without a rewrite.
> When Mayke says "follow this / follow the plan", execute the phases below in order.

---

## 1. Vision

One place to run a content business:

- **Assets** — the properties you own & grow: websites, social media accounts, email lists.
- **Studio (Create)** — the central content hub: blog, social, image, video — text, image, or both.
- **Research** — discover *what* to create about; it feeds the Studio.

Flow, left to right: **Research → Studio → Assets → Grow (nurture) → Products (money).**

---

## 2. Locked decisions

These are decided. Don't re-litigate without Mayke.

1. **Multi-tenant from day one.** Every important row is owned by a `Tenant` (an
   Account/Workspace). Build for Mayke now as a single tenant, but the ownership
   stamp exists from the first model so the pivot to a paid product is *not* a rewrite.
   - Each model (`Website`, `Post`, `Lead`, `SocialAccount`, `Offer`, sequences…)
     gets a `tenant` FK.
   - Every query filters by the logged-in tenant. No customer ever sees another's data.

2. **Websites = native multi-site, NOT WordPress.** Rejected WordPress because a
   portfolio of sites means one heavy installation *per site*. Instead:
   - **One app serves many websites.** A new site = a `Website` row + a domain pointed
     at the app. Zero new installations.
   - **Public sites are static-generated and deployed to a CDN** (e.g. Cloudflare
     Pages / Netlify): near-zero hosting cost, top SEO, fast, and custom domains + SSL
     are handled by the CDN, not by us. A static site is the lightest possible website.
   - Build the SEO layer (sitemaps, meta, schema, RSS) **once** — every current and
     future site inherits it automatically.
   - Model `Website` with a `platform` field so a future dynamic/hybrid option can be
     added without a rewrite.

3. **The app splits in two conceptually:**
   - **Control tower** (dynamic, multi-tenant Django): research, create, schedule,
     publish to social, capture leads. This is the product.
     lead-capture form submissions flow back into the app.
   - **Public websites** (static output pushed to a CDN). The only dynamic piece a
     static site needs is the lead-capture endpoint, which already exists.

---

## 3. Information architecture (navigation) — DONE

Nav reorganized in `templates/base.html` to match the pillars:

**Dashboard · Research · Studio ▾ · Assets ▾ · Grow ▾ · Products · Analytics · ⚙**

- **Research** — top level (start of the flow). Currently `/factory/research/`.
- **Studio ▾** — New Post · Image Studio · Video Factory · Avatars · Library · Calendar.
- **Assets ▾** — Websites `soon` · Social Accounts `soon` · Capture Pages · Email Lists.
- **Grow ▾** — Email Sequences · Scheduler · Automations.
- **Products**, **Analytics** — top level.
- **⚙ (settings, top-right)** — Admin panel link moved here (out of main nav). Future
  home for *Connections* (CDN key, social auth, R2, WordPress-if-ever).

`soon` items (Websites, Social Accounts) are greyed, non-clickable placeholders that
show the roadmap without dead links.

---

## 4. Build phases (ordered)

Each phase is shippable on its own. Do them top-down.

### Phase 0 — Tenancy foundation
- Add `Tenant` (Account/Workspace) model + link the current user(s) to a tenant.
- Add `tenant` FK to existing models (`Post`, `Lead`, `CapturePage`, `Offer`,
  `SequenceStep`, `Video`, `Avatar`, `TopicIdea`).
- Add a query layer / manager that auto-filters by the current tenant.
- Backfill: assign all existing rows to Mayke's tenant.
- **Why first:** cheap now (tables ~empty), painful later. Everything else assumes it.

### Phase 1 — Assets: Websites (static multi-site)
- `Website` model: tenant, domain, name, branding, SEO defaults, `platform`, `is_active`.
- `Page` model: static pages per site (home, about, money/landing).
- Reuse `content.Post` (`kind=article`) linked to a `Website` for blog posts.
- Static generation + CDN deploy pipeline; custom-domain connection flow.
- Shared SEO layer: per-site `sitemap.xml`, meta/schema, RSS — built once.
- Makes the "Websites" nav item real.

### Phase 2 — Assets: Social Accounts
- `SocialAccount` model: tenant, platform, handle, connection/auth status.
- Replace loose `Post.channels` strings with links to real owned accounts.
- Makes the "Social Accounts" nav item real.

### Phase 3 — Assets: Email Lists (segmentation)
- Turn the one flat `Lead` table into real, segmentable lists (a `List`/tag layer).
- Map capture pages → lists.

### Phase 4 — Research → any content
- Let a `TopicIdea` spawn any `Post` kind (text/image/article), not only a Video.
- Wire Research as the true front-of-funnel for the whole Studio.

### Phase 5 — Blog publishing polish
- `kind=article` posts publish to their `Website`'s static blog cleanly
  (the view already says "Articles publish to the blog" — this makes it true).

---

## 5. Open decisions (need Mayke before the relevant phase)

- **Static generator + CDN choice** (Phase 1): Cloudflare Pages vs Netlify vs other.
- **Custom-domain onboarding UX** (Phase 1): how a customer connects their domain.
- **Scope of first build:** stop at Mayke's own use, or push toward the product surface
  (signup, billing) once Phases 0–2 are solid.

---

## 6. Housekeeping notes

- A preview superuser `claude` was given a temporary password for Playwright previews.
  Clear it when no longer needed.
