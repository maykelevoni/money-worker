"""Render a published Website to static HTML files.

Reuses the live public renderers (via RequestFactory) so the exported files are
byte-identical to what the app serves / previews. The one change: opt-in forms
are rewired to POST cross-origin to the control tower's /api/optin/ endpoint,
since a static site can't run Django.
"""
import json
import shutil
from pathlib import Path

from django.conf import settings
from django.test import RequestFactory

from . import public_views
from .rendering import published_articles


def _optin_script(api_base, key):
    """A tiny inline script that submits opt-in forms to the JSON API."""
    return (
        "<script>(function(){var API=%s,KEY=%s;"
        "document.querySelectorAll('form.optin-form[action=\"/optin/\"]').forEach(function(f){"
        "f.addEventListener('submit',function(e){e.preventDefault();"
        "var g=function(n){var el=f.querySelector('input[name='+n+']');return el?el.value:'';};"
        "var email=g('email'),lm=g('lead_magnet'),sm=g('success_message')||\"You're in!\";"
        "var btn=f.querySelector('button');if(btn)btn.disabled=true;"
        "fetch(API+'/api/optin/',{method:'POST',"
        "headers:{'Content-Type':'application/x-www-form-urlencoded'},"
        "body:'site_key='+encodeURIComponent(KEY)+'&email='+encodeURIComponent(email)+'&lead_magnet='+encodeURIComponent(lm)})"
        ".then(function(){f.parentNode.innerHTML='<div class=\"optin-done\">'+sm+'</div>';})"
        ".catch(function(){if(btn)btn.disabled=false;alert('Something went wrong, please try again.');});"
        "});});})();</script>"
    ) % (json.dumps(api_base), json.dumps(key))


def _inject(html, script):
    if "</body>" in html:
        return html.replace("</body>", script + "</body>", 1)
    return html + script


def export_site(site):
    """Write the whole site to BUILD_ROOT/<subdomain>/. Returns (dir, page_count)."""
    rf = RequestFactory()

    def req(path):
        r = rf.get(path)
        r.site = site
        r.urlconf = settings.SITE_URLCONF
        return r

    out = Path(settings.BUILD_ROOT) / site.subdomain
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    script = _optin_script(settings.APP_BASE_URL, site.public_key)
    count = 0

    def write_html(rel, resp):
        nonlocal count
        html = _inject(resp.content.decode("utf-8"), script)
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")
        count += 1

    write_html("index.html", public_views.render_home(req("/"), site, preview=False))
    for page in site.pages.filter(status="published"):
        if page.is_home:
            continue
        write_html(
            f"{page.slug}/index.html",
            public_views.render_page(req(page.path), site, page.slug, preview=False),
        )
    write_html("blog/index.html", public_views.render_blog(req("/blog/"), site, preview=False))
    for a in published_articles(site):
        write_html(
            f"blog/{a.slug}/index.html",
            public_views.render_article(req(f"/blog/{a.slug}/"), site, a.slug, preview=False),
        )

    (out / "sitemap.xml").write_text(
        public_views.sitemap(req("/sitemap.xml")).content.decode("utf-8"), encoding="utf-8"
    )
    (out / "robots.txt").write_text(
        public_views.robots(req("/robots.txt")).content.decode("utf-8"), encoding="utf-8"
    )
    return out, count
