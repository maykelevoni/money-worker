from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.content.models import Post
from apps.leads.models import EmailList

from . import public_views
from .models import MANDATORY_KINDS, Page, Section, Website


def _scaffold_sections(page, kinds):
    """Create default starter sections on a page, in order."""
    for i, kind in enumerate(kinds):
        Section.objects.create(
            workspace=page.workspace,
            page=page,
            kind=kind,
            order=i,
            data=Section.default_data(kind),
        )


# ==========================================================================
# Management (Assets → Websites)
# ==========================================================================
@login_required
def website_list(request):
    sites = Website.objects.for_workspace(request.workspace)
    return render(request, "sites/manage/list.html", {"sites": sites})


def _save_website(request, site):
    site.workspace = request.workspace
    site.name = request.POST.get("name", "").strip()
    site.subdomain = (
        request.POST.get("subdomain", "").strip() or slugify(site.name)
    )
    theme = request.POST.get("theme")
    if theme in Website.Theme.values:
        site.theme = theme
    if request.FILES.get("logo"):
        site.logo = request.FILES["logo"]
    if request.FILES.get("og_image"):
        site.og_image = request.FILES["og_image"]
    site.tagline = request.POST.get("tagline", "").strip()
    site.accent_color = request.POST.get("accent_color", "").strip() or "#ff7e2e"
    site.seo_title_suffix = request.POST.get("seo_title_suffix", "").strip()
    site.seo_description = request.POST.get("seo_description", "").strip()
    site.custom_domain = request.POST.get("custom_domain", "").strip() or None
    site.status = (
        Website.Status.PUBLISHED
        if request.POST.get("status") == "published"
        else Website.Status.DRAFT
    )
    if not site.name or not site.subdomain:
        messages.error(request, "A name and subdomain are required.")
        return None
    try:
        site.save()
    except IntegrityError:
        messages.error(request, f"Subdomain “{site.subdomain}” is taken — pick another.")
        return None
    return site


@login_required
def website_create(request):
    if request.method == "POST":
        site = _save_website(request, Website())
        if site is not None:
            # Every new site starts with a home page built from mandatory sections.
            home = Page.objects.create(
                workspace=request.workspace,
                website=site,
                title="Home",
                is_home=True,
                status="published",
            )
            _scaffold_sections(
                home,
                ["hero", "stats", "features", "testimonial", "optin", "faq", "cta"],
            )
            # Seed the hero from what we already know about the site.
            hero = home.sections.filter(kind="hero").first()
            if hero:
                hero.data["headline"] = site.name
                if site.tagline:
                    hero.data["subtext"] = site.tagline
                hero.save(update_fields=["data"])
            messages.success(request, f"Website “{site.name}” created.")
            return redirect("sites:edit", pk=site.pk)
    return render(request, "sites/manage/form.html",
                  {"site": None, "site_themes": Website.Theme.choices})


@login_required
def website_edit(request, pk):
    site = get_object_or_404(Website, pk=pk, workspace=request.workspace)
    if request.method == "POST":
        if _save_website(request, site) is not None:
            messages.success(request, "Website saved.")
            return redirect("sites:edit", pk=site.pk)
    articles = Post.objects.for_workspace(request.workspace).filter(
        kind=Post.Kind.ARTICLE
    )
    return render(request, "sites/manage/form.html", {
        "site": site,
        "pages": site.pages.all(),
        "articles": articles,
        "site_themes": Website.Theme.choices,
    })


@login_required
@require_POST
def publish_site(request, pk):
    site = get_object_or_404(Website, pk=pk, workspace=request.workspace)
    if not site.is_published:
        messages.error(request, "Mark the website Published (in settings) before publishing to the CDN.")
        return redirect("sites:edit", pk=pk)
    from django.utils import timezone

    from .deploy import deploy_site
    from .exporter import export_site

    try:
        build_dir, count = export_site(site)
        status = deploy_site(site, build_dir)
    except Exception as e:
        messages.error(request, f"Publish failed: {e}")
        return redirect("sites:edit", pk=pk)
    site.last_published_at = timezone.now()
    site.save(update_fields=["last_published_at"])
    messages.success(request, f"Exported {count} page(s). {status}")
    return redirect("sites:edit", pk=pk)


@login_required
@require_POST
def website_delete(request, pk):
    site = get_object_or_404(Website, pk=pk, workspace=request.workspace)
    name = site.name
    site.delete()
    messages.success(request, f"Deleted “{name}”.")
    return redirect("sites:list")


# ---- Pages ----
def _save_page(request, page):
    page.workspace = request.workspace
    page.title = request.POST.get("title", "").strip()
    page.body = request.POST.get("body", "")
    page.meta_title = request.POST.get("meta_title", "").strip()
    page.meta_description = request.POST.get("meta_description", "").strip()
    page.is_home = bool(request.POST.get("is_home"))
    page.slug = request.POST.get("slug", "").strip()
    page.nav_order = int(request.POST.get("nav_order") or 0)
    page.status = (
        "published" if request.POST.get("status") == "published" else "draft"
    )
    if not page.title:
        messages.error(request, "The page needs a title.")
        return None
    try:
        page.save()
    except IntegrityError:
        messages.error(request, f"Slug “{page.slug}” is already used on this site.")
        return None
    # One home page per site.
    if page.is_home:
        page.website.pages.exclude(pk=page.pk).filter(is_home=True).update(
            is_home=False
        )
    return page


@login_required
def page_create(request, website_pk):
    site = get_object_or_404(Website, pk=website_pk, workspace=request.workspace)
    page = Page(website=site)
    if request.method == "POST":
        if _save_page(request, page) is not None:
            _scaffold_sections(page, ["text"])
            messages.success(request, "Page created — now build its sections.")
            return redirect("sites:page_edit", pk=page.pk)
    return render(request, "sites/manage/page_form.html", {"site": site, "page": None})


@login_required
def page_edit(request, pk):
    page = get_object_or_404(Page, pk=pk, workspace=request.workspace)
    if request.method == "POST":
        if _save_page(request, page) is not None:
            messages.success(request, "Page saved.")
            return redirect("sites:page_edit", pk=page.pk)
    return render(
        request,
        "sites/manage/page_form.html",
        {
            "site": page.website,
            "page": page,
            "sections": page.sections.all(),
            "section_kinds": Section.Kind.choices,
            "lists": EmailList.objects.for_workspace(request.workspace),
        },
    )


@login_required
@require_POST
def page_delete(request, pk):
    page = get_object_or_404(Page, pk=pk, workspace=request.workspace)
    site_pk = page.website_id
    page.delete()
    messages.success(request, "Page deleted.")
    return redirect("sites:edit", pk=site_pk)


# ---- Blog articles (content.Post kind=article) ----
@login_required
@require_POST
def article_attach(request, website_pk):
    site = get_object_or_404(Website, pk=website_pk, workspace=request.workspace)
    article = get_object_or_404(
        Post, pk=request.POST.get("article"), workspace=request.workspace,
        kind=Post.Kind.ARTICLE,
    )
    article.website = site
    if not article.slug:
        article.slug = slugify(article.title or f"post-{article.pk}")
    article.save(update_fields=["website", "slug"])
    messages.success(request, f"Attached “{article.title}” to the blog.")
    return redirect("sites:edit", pk=site.pk)


@login_required
@require_POST
def article_toggle(request, pk):
    article = get_object_or_404(
        Post, pk=pk, workspace=request.workspace, kind=Post.Kind.ARTICLE
    )
    if article.status == Post.Status.POSTED:
        article.status = Post.Status.DRAFT
    else:
        article.status = Post.Status.POSTED
        if not article.slug:
            article.slug = slugify(article.title or f"post-{article.pk}")
    article.save(update_fields=["status", "slug"])
    messages.success(request, "Article publish state updated.")
    return redirect("sites:edit", pk=article.website_id)


# ==========================================================================
# Sections (the page builder)
# ==========================================================================
def _parse_section(kind, POST):
    if kind == "hero":
        return {
            "headline": POST.get("headline", "").strip(),
            "subtext": POST.get("subtext", "").strip(),
            "button_text": POST.get("button_text", "").strip(),
            "button_url": POST.get("button_url", "").strip(),
        }
    if kind == "cta":
        return {
            "headline": POST.get("headline", "").strip(),
            "button_text": POST.get("button_text", "").strip(),
            "button_url": POST.get("button_url", "").strip(),
        }
    if kind == "text":
        return {"body": POST.get("body", "")}
    if kind == "optin":
        return {
            "headline": POST.get("headline", "").strip(),
            "subtext": POST.get("subtext", "").strip(),
            "lead_magnet": POST.get("lead_magnet", "").strip(),
            "button_text": POST.get("button_text", "").strip(),
            "success_message": POST.get("success_message", "").strip(),
            "list_id": POST.get("list_id", "").strip(),
        }
    if kind == "testimonial":
        return {
            "quote": POST.get("quote", "").strip(),
            "author": POST.get("author", "").strip(),
            "role": POST.get("role", "").strip(),
        }
    if kind == "image":
        return {"caption": POST.get("caption", "").strip()}
    if kind == "stats":
        items = []
        for i in range(1, 5):
            v = POST.get(f"s{i}_value", "").strip()
            l = POST.get(f"s{i}_label", "").strip()
            if v or l:
                items.append({"value": v, "label": l})
        return {"items": items}
    if kind == "features":
        items = []
        for i in range(1, 4):
            t = POST.get(f"f{i}_title", "").strip()
            b = POST.get(f"f{i}_body", "").strip()
            if t or b:
                items.append({"title": t, "body": b})
        return {"items": items}
    if kind == "faq":
        items = []
        for i in range(1, 6):
            q = POST.get(f"q{i}", "").strip()
            a = POST.get(f"a{i}", "").strip()
            if q or a:
                items.append({"q": q, "a": a})
        return {"items": items}
    return {}


@login_required
@require_POST
def section_add(request, page_pk):
    page = get_object_or_404(Page, pk=page_pk, workspace=request.workspace)
    kind = request.POST.get("kind")
    if kind not in Section.Kind.values:
        messages.error(request, "Unknown section type.")
        return redirect("sites:page_edit", pk=page.pk)
    order = (page.sections.count())
    Section.objects.create(
        workspace=request.workspace, page=page, kind=kind, order=order,
        data=Section.default_data(kind),
    )
    messages.success(request, f"Added a {kind} section.")
    return redirect("sites:page_edit", pk=page.pk)


@login_required
@require_POST
def section_edit(request, pk):
    section = get_object_or_404(Section, pk=pk, workspace=request.workspace)
    section.data = _parse_section(section.kind, request.POST)
    if request.FILES.get("image"):
        section.image = request.FILES["image"]
    if request.POST.get("remove_image"):
        section.image = ""
    section.save()
    messages.success(request, "Section saved.")
    return redirect("sites:page_edit", pk=section.page_id)


@login_required
@require_POST
def section_move(request, pk, direction):
    section = get_object_or_404(Section, pk=pk, workspace=request.workspace)
    siblings = list(section.page.sections.all())
    idx = next((i for i, s in enumerate(siblings) if s.pk == section.pk), None)
    swap = idx - 1 if direction == "up" else idx + 1
    if idx is not None and 0 <= swap < len(siblings):
        other = siblings[swap]
        section.order, other.order = other.order, section.order
        section.save(update_fields=["order"])
        other.save(update_fields=["order"])
    return redirect("sites:page_edit", pk=section.page_id)


@login_required
@require_POST
def section_delete(request, pk):
    section = get_object_or_404(Section, pk=pk, workspace=request.workspace)
    page = section.page
    # Keep at least one Hero and one CTA on the home page.
    if (
        page.is_home
        and section.is_mandatory
        and page.sections.filter(kind=section.kind).count() <= 1
    ):
        messages.error(
            request, f"The home page needs a {section.get_kind_display()} — can't delete the last one."
        )
        return redirect("sites:page_edit", pk=page.pk)
    section.delete()
    messages.success(request, "Section removed.")
    return redirect("sites:page_edit", pk=page.pk)


# ==========================================================================
# In-app preview (no DNS needed) — workspace-scoped.
# ==========================================================================
def _own_site(request, pk):
    return get_object_or_404(Website, pk=pk, workspace=request.workspace)


@login_required
def preview_home(request, pk):
    return public_views.render_home(request, _own_site(request, pk), preview=True)


@login_required
def preview_page(request, pk, slug):
    return public_views.render_page(request, _own_site(request, pk), slug, preview=True)


@login_required
def preview_blog(request, pk):
    return public_views.render_blog(request, _own_site(request, pk), preview=True)


@login_required
def preview_article(request, pk, slug):
    return public_views.render_article(
        request, _own_site(request, pk), slug, preview=True
    )
