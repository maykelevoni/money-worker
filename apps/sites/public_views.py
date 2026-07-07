"""Public rendering for a Website. Mode-agnostic core renderers are reused by
both the live (host-based) entry points here and the in-app preview in views.py.
"""
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string

from .markdown_util import render_markdown
from .rendering import published_articles, site_context


# --------------------------------------------------------------------------
# Core renderers — take an explicit `site` + `preview` flag.
# --------------------------------------------------------------------------
def render_home(request, site, *, preview):
    page = site.pages.filter(is_home=True, status="published").first()
    if page is None:
        page = site.pages.filter(status="published").order_by("nav_order").first()
    ctx = site_context(site, preview=preview)
    ctx["page"] = page
    ctx["sections"] = page.sections.all() if page else []
    ctx["body_html"] = render_markdown(page.body) if page else ""
    ctx["meta_title"] = site.title_for(page.title) if page else site.name
    ctx["meta_description"] = (
        page.meta_description if page and page.meta_description else site.seo_description
    )
    return render(request, "sites/public/page.html", ctx)


def render_page(request, site, slug, *, preview):
    page = get_object_or_404(site.pages.filter(status="published"), slug=slug)
    ctx = site_context(site, preview=preview)
    ctx["page"] = page
    ctx["sections"] = page.sections.all()
    ctx["body_html"] = render_markdown(page.body)
    ctx["meta_title"] = site.title_for(page.meta_title or page.title)
    ctx["meta_description"] = page.meta_description or site.seo_description
    return render(request, "sites/public/page.html", ctx)


def render_blog(request, site, *, preview):
    ctx = site_context(site, preview=preview)
    article_url = ctx["links"]["article"]
    ctx["articles"] = [
        {
            "title": a.title,
            "excerpt": a.meta_description or (a.body[:160] if a.body else ""),
            "url": article_url(a.slug),
            "date": a.created_at,
            "image": a.media_src,
        }
        for a in published_articles(site)
    ]
    ctx["meta_title"] = site.title_for("Blog")
    ctx["meta_description"] = site.seo_description
    return render(request, "sites/public/blog_list.html", ctx)


def render_article(request, site, slug, *, preview):
    article = get_object_or_404(published_articles(site), slug=slug)
    ctx = site_context(site, preview=preview)
    article_url = ctx["links"]["article"]
    ctx["article"] = article
    ctx["body_html"] = render_markdown(article.body)
    ctx["meta_title"] = site.title_for(article.title)
    ctx["meta_description"] = article.meta_description or site.seo_description
    ctx["related"] = [
        {"title": a.title, "url": article_url(a.slug), "image": a.media_src}
        for a in published_articles(site).exclude(pk=article.pk)[:3]
    ]
    return render(request, "sites/public/blog_detail.html", ctx)


# --------------------------------------------------------------------------
# Live entry points — served on the site's own host (request.site set by middleware).
# --------------------------------------------------------------------------
def live_home(request):
    return render_home(request, request.site, preview=False)


def live_page(request, slug):
    return render_page(request, request.site, slug, preview=False)


def live_blog(request):
    return render_blog(request, request.site, preview=False)


def live_article(request, slug):
    return render_article(request, request.site, slug, preview=False)


def sitemap(request):
    site = request.site
    base = site.public_url.rstrip("/")
    urls = [base + p.path for p in site.pages.filter(status="published")]
    urls.append(base + "/blog/")
    urls += [base + f"/blog/{a.slug}/" for a in published_articles(site)]
    xml = render_to_string("sites/public/sitemap.xml", {"urls": urls})
    return HttpResponse(xml, content_type="application/xml")


def robots(request):
    site = request.site
    base = site.public_url.rstrip("/")
    body = f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"
    return HttpResponse(body, content_type="text/plain")


def optin(request):
    """Public email capture on a site → a Lead in that site's workspace."""
    site = request.site
    if request.method != "POST":
        return redirect("/")
    email = request.POST.get("email", "").strip().lower()
    if not email:
        return redirect("/")

    from apps.leads.models import Lead

    lead, created = Lead.objects.get_or_create(
        workspace=site.workspace,
        email=email,
        defaults={
            "lead_magnet": request.POST.get("lead_magnet", ""),
            "stage": Lead.Stage.NEW,
        },
    )
    if created:
        try:
            from apps.sequences.engine import process_due_emails

            process_due_emails(lead, log=False)
        except Exception:
            pass

    ctx = site_context(site, preview=False)
    ctx["success_message"] = (
        request.POST.get("success_message") or "You're in! Check your inbox."
    )
    ctx["meta_title"] = site.title_for("Thanks")
    return render(request, "sites/public/thanks.html", ctx)
