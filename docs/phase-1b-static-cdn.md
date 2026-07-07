# Phase 1b — Static export → CDN + custom domains

> Per-phase spec. **Review & approve before any code.**
> Parent plan: `PLAN.md` · Depends on: Phase 1a ✅ (+ theme/capture layer ✅) · Status: awaiting approval.

---

## 1. Goal

Take the sites the app already renders and **publish them as static files on a CDN**, each
on its **own custom domain with SSL** — so hosting is near-free and scales to many sites
without the app serving public traffic. The app becomes the *control tower*; the CDN serves
the public.

**Success = click "Publish" on a website → it goes live at its real domain as static HTML,
and an opt-in on that static site still creates a Lead back in the app.**

---

## 2. Scope

**In:**
- A **static exporter**: render every published page/blog/sitemap/robots to HTML files + copy
  media, for one site.
- A **deployer**: push that build to the CDN.
- **Custom-domain onboarding**: connect a domain, verify, auto-SSL (via the CDN).
- **Lead capture on static sites** (the key wrinkle — see §4).
- A **Publish** action + status in the Websites UI.

**Out (later):** incremental partial builds, preview deploys per draft, multi-region tuning,
Blog v2 (editor/categories/RSS/search — tracked separately).

---

## 3. Architecture

```
 CONTROL TOWER (this app, dynamic)        CDN (static hosting)
 ┌───────────────────────────┐           ┌────────────────────────┐
 │ render site → HTML files   │  deploy   │ site1.com  (static)    │
 │ (reuses the SAME templates)│ ────────► │ site2.com  (static)    │
 │ + media                    │           │ …                      │
 └───────────────────────────┘           └───────────┬────────────┘
        ▲  lead POST (JSON, CORS)                     │ opt-in form
        └─────────────────────────────────────────────┘
```

The exporter reuses the existing `public_views` renderers — so **what you preview is exactly
what ships**. Only the *delivery* changes (files on a CDN instead of Django responses).

---

## 4. The one hard part: lead capture on a static site

A static site can't run Django, so the opt-in form can't POST to a local view. Options:

- **A — Post back to the app's API (recommended).** The static form does a `fetch()` to
  `https://app.<host>/api/optin/` with `{site_id, email, lead_magnet}`. The app validates,
  creates the Lead in that site's workspace, returns JSON; the page shows a thank-you inline.
  Needs CORS for the site domains + a token/site-key (no CSRF cookie cross-origin). One
  endpoint, works for every site.
- **B — CDN serverless function / native forms** (e.g. Cloudflare Functions, Netlify Forms).
  Less code but ties us to one CDN's form product and still has to forward to the app.
- **C — Third-party form service.** Fastest, but the lead lives outside the app first.

Recommendation: **A** — one small JSON API on the control tower, CDN-agnostic, keeps leads
first-class in the app immediately.

---

## 5. Components to build

1. `export_site(site)` — renders `/`, each page, `/blog/`, each article, `sitemap.xml`,
   `robots.txt` to a build dir; rewrites the opt-in form to the JSON API; copies media.
2. `deploy_site(site)` — push build dir to the CDN via its API/CLI.
3. `POST /api/optin/` — CORS-enabled JSON endpoint creating a Lead (replaces the form-post
   path for static sites; the in-app preview keeps using the current view).
4. Custom-domain model fields already exist (`custom_domain`); add verification status +
   the CDN's connection steps.
5. Websites UI: **Publish** button, last-published time, live-URL link, domain status.

---

## 6. Decisions — LOCKED (2026-07-07)

1. **CDN / host** → **Cloudflare Pages** (needs a Cloudflare account + API token from Mayke).
2. **Lead-capture mechanism** → **Post back to the app API** (JSON `/api/optin/` + CORS + per-site key).
3. **Deploy trigger** → **Manual Publish button**.
4. **Base domain** → still needed from Mayke (production `SITE_HOST`, e.g. `moneyworker.io`).

## 6b. Build status (2026-07-07)

**Local pieces BUILT & verified** (no accounts needed):
- Static **exporter** (`apps/sites/exporter.py`) — renders home/pages/blog/sitemap/robots to
  `builds/<subdomain>/`, reusing the live renderers; rewrites opt-in forms to call the API.
- **`/api/optin/`** (`apps/sites/api_views.py`) — CORS + csrf-exempt; `public_key` → Lead in the
  site's workspace + sequences. Verified: valid key → lead created, bad key → 403.
- **Publish** button + `last_published_at`; `deploy_site()` stub (`deploy.py`) skips until creds.
- `Website.public_key` (auto) + `APP_BASE_URL` / `BUILD_ROOT` settings.

**Remaining (needs Mayke's accounts):** real Cloudflare Pages push in `deploy.py`, custom-domain
attach + SSL, production `SITE_HOST` + `APP_BASE_URL` + `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`
for real domains.

## 7. What you'll need to provide
- A CDN account + API token (for the deployer).
- A base domain (and, per site, the custom domains you'll point at the CDN).

## 8. Acceptance checks
- Publish a site → static build appears on the CDN, reachable at its domain over HTTPS.
- Pages, blog, sitemap.xml, robots.txt all correct and identical to the in-app preview.
- Submit the opt-in on the *static* site → a Lead appears in the right workspace.
- A second site stays fully isolated (own domain, own content).
