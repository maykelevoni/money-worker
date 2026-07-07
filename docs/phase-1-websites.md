# Phase 1 — Websites (native multi-site)

> Per-phase spec. **Review & approve before any code.**
> Parent plan: `PLAN.md` · Depends on: Phase 0 (tenancy) ✅ · Status: awaiting approval.

---

## 1. Goal

Make the **Websites** asset real: from this app, create and manage **many** SEO sites —
each with a small set of static pages and a blog — where a new site is *a database row +
a domain*, never a new installation. Public sites are eventually **static files on a CDN**
(locked decision), so hosting stays near-free at any number of sites.

**Success = Mayke can create a website, add pages + blog posts to it, see it live at its
own address, and it's indexable by Google — all without leaving the app or deploying code.**

---

## 2. The one important sequencing call

Full "static-generate → push to CDN → custom domains + SSL" is a big infra lift. Building
it all before a single site exists is risky and slow to show value. So I recommend
**splitting Phase 1 in two**, each independently useful:

- **1a — Sites are real, served by the app.** Build the models + editor + public rendering
  by hostname/subdomain, rendered by Django. You can create sites, write pages + blog
  posts, and view them live. SEO basics (meta, sitemap, clean URLs) included.
- **1b — Static export + CDN.** A command renders every site to static HTML and deploys it
  to the CDN; custom domains + SSL handled there. The **same templates** from 1a are the
  source, so nothing is rebuilt — 1b just changes *where* the HTML is served from.

This spec covers **1a in detail** and sketches **1b** (its own decisions come when we start it).

---

## 3. Data model (1a)

New app `apps.sites` (public name "Websites"). All models are `WorkspaceOwned`.

```
Website
  workspace       FK (WorkspaceOwned)
  name            CharField                     # "Sleep Tips"
  subdomain       SlugField unique              # sleeptips.<app-host>  (default address)
  custom_domain   CharField unique null         # sleeptips.co          (connected later)
  platform        CharField default="native"    # future-proof: native | wordpress | …
  tagline         CharField blank
  # branding
  logo            ImageField blank
  accent_color    CharField default="#ff7e2e"
  # SEO defaults (inherited by pages/posts that don't override)
  seo_title_suffix   CharField blank            # " · Sleep Tips"
  seo_description    TextField blank
  og_image        ImageField blank
  status          CharField  draft | published
  created_at / updated_at

Page                                            # static pages: home, about, landing
  website         FK Website
  workspace       FK (WorkspaceOwned, denormalised for scoping)
  title           CharField
  slug            SlugField                      # unique per website; "" = home
  body            TextField                      # rich content (see decision 2)
  meta_title      CharField blank                # overrides Website default
  meta_description TextField blank
  is_home         BooleanField default=False     # exactly one per site
  nav_order       PositiveIntegerField
  status          draft | published
```

**Blog** reuses the existing `content.Post` (`kind=article`) — no new post model. Add to it:
```
Post  (+ fields, only meaningful for articles)
  website         FK Website null                # which site's blog it belongs to
  slug            SlugField blank                # article URL
  meta_description TextField blank
```
This means your **Studio already feeds the blogs** — an article written in the workbench
just gets pointed at a Website.

---

## 4. Public rendering (1a — served by Django)

- **Resolve by host:** a middleware maps the incoming hostname → a `Website`
  (`custom_domain` match, else `<subdomain>.<app-host>`). Puts `request.site` on the request.
- **Routes on a matched site host:**
  - `/`               → the `is_home` Page
  - `/<page-slug>/`   → a static Page
  - `/blog/`          → list of published articles for that Website
  - `/blog/<slug>/`   → one article
  - `/sitemap.xml`    → generated from that site's published pages + posts
  - lead-capture form posts → existing capture endpoint, stamped to the site's workspace
- **The app itself** (dashboard, Studio, etc.) stays on the main app host, untouched.

SEO baked in from day one: server-rendered HTML, one `<h1>`, clean slugs, per-page
`<title>`/meta/canonical/OG, `sitemap.xml`, `robots.txt`.

## 5. Internal management (1a)

- **Assets → Websites** (flips the `soon` nav item to a real link): list of sites with
  status + address + page/post counts.
- **Website editor:** branding + SEO defaults; manage Pages (add/edit/reorder, pick home);
  attach blog posts.
- **Preview** each site in-app before publishing.

---

## 6. Phase 1b (sketch — separate go-ahead)

- Management command: render every published site to static HTML + assets + `sitemap.xml`.
- Deploy to a CDN (Cloudflare Pages / Netlify — **decision deferred to 1b**).
- Custom-domain onboarding: verification + automatic SSL via the CDN.
- Lead forms become a small serverless/endpoint post-back into the app.
- Incremental re-deploy on publish.

---

## 7. Acceptance checks (1a)

- Create a Website → it's reachable at its subdomain, isolated to its workspace.
- Add a home page + one more page + one blog post → all render with correct titles/meta.
- `sitemap.xml` lists exactly that site's published URLs; another workspace's site is
  never reachable or listed.
- A lead captured on the site is stamped with that site's workspace.
- `manage.py check` clean; driven live with `/verify` (Playwright).

---

## 8. Risks & watch-items

- **Host routing in dev:** testing multiple hostnames locally needs `/etc/hosts` entries or
  a wildcard dev domain. I'll document a simple local recipe.
- **Slug/home invariants:** exactly one `is_home` per site; unique slugs per site.
- **Don't leak the app on site hosts** (and vice-versa) — the host middleware must cleanly
  separate "app host" from "site host".
- **`Post.website` nullable** so existing/social posts (not blog articles) are unaffected.

---

## 9. Decisions I need from you before building

1. **Sub-phase split** — do **1a first** (sites real, served by the app), then **1b**
   (static + CDN) as a separate step? *(Recommended — value fast, de-risks the infra.)*
   Or insist on static+CDN as part of one big Phase 1?
2. **Blog / page content format** — how do you write a page/article body?
   **a)** Markdown, **b)** a rich WYSIWYG editor, or **c)** paste HTML (e.g. straight from
   your ChatGPT workbench). *(I lean Markdown: clean, SEO-safe, easy to generate with AI.)*
3. **Default site address before custom domains** — what's the app host that subdomains
   hang off (e.g. `*.moneyworker.io`)? Needed so a new site has an address on day one.
4. **CDN + generator** — deferred to 1b; no answer needed yet.
