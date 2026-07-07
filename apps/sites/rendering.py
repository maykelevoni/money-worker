"""Shared context for rendering a Website's public pages.

The same templates power two modes:
- live: served on the site's own host (URLs like /, /about/, /blog/)
- preview: served in-app at /websites/<pk>/preview/... (no DNS needed)

Link URLs differ between the modes, so we precompute them here and hand the
templates ready-made URLs — the templates never hardcode a path.
"""
from django.urls import reverse

from apps.content.models import Post

from .themes import theme_for


def _live_links(site):
    return {
        "home": "/",
        "blog": "/blog/",
        "page": lambda slug: f"/{slug}/",
        "article": lambda slug: f"/blog/{slug}/",
    }


def _preview_links(site):
    pk = site.pk
    return {
        "home": reverse("sites:preview_home", args=[pk]),
        "blog": reverse("sites:preview_blog", args=[pk]),
        "page": lambda slug: reverse("sites:preview_page", args=[pk, slug]),
        "article": lambda slug: reverse("sites:preview_article", args=[pk, slug]),
    }


def published_articles(site):
    """Articles (content.Post kind=article) attached to this site's blog."""
    return (
        Post.objects.filter(
            website=site, kind=Post.Kind.ARTICLE, status=Post.Status.POSTED
        )
        .order_by("-created_at")
    )


def site_context(site, *, preview):
    links = _preview_links(site) if preview else _live_links(site)
    nav = []
    for p in site.pages.filter(status="published"):
        nav.append(
            {
                "title": p.title,
                "url": links["home"] if p.is_home else links["page"](p.slug),
                "is_home": p.is_home,
            }
        )
    return {
        "site": site,
        "nav": nav,
        "home_url": links["home"],
        "blog_url": links["blog"],
        "preview": preview,
        "links": links,
        "theme": theme_for(site),
    }
