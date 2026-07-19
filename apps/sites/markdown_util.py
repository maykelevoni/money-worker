"""Render Markdown → HTML for public pages/articles.

python-markdown passes raw HTML through untouched, so a body containing
`<script>` would execute on the public site (stored XSS). We sanitize the
rendered HTML before trusting it. `nh3` (a fast, well-audited HTML sanitizer)
is the real defense; if it isn't installed we fall back to a conservative
regex scrub so a fresh checkout is never left wide open.
"""
import re

import markdown as _md
from django.utils.safestring import mark_safe

_EXTENSIONS = ["extra", "sane_lists", "smarty"]

try:  # preferred: a proper allow-list sanitizer
    import nh3

    def _sanitize(html: str) -> str:
        return nh3.clean(html)
except ImportError:  # fallback: strip the obviously dangerous bits
    _DANGEROUS_TAGS = re.compile(
        r"<\s*(script|style|iframe|object|embed|link|meta|base|form)\b[^>]*>.*?"
        r"<\s*/\s*\1\s*>",
        re.IGNORECASE | re.DOTALL,
    )
    _SELF_CLOSING = re.compile(
        r"<\s*(script|style|iframe|object|embed|link|meta|base)\b[^>]*/?>",
        re.IGNORECASE,
    )
    _ON_ATTR = re.compile(
        r"""\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""", re.IGNORECASE
    )
    _JS_URI = re.compile(
        r"""(href|src)\s*=\s*("javascript:[^"]*"|'javascript:[^']*')""",
        re.IGNORECASE,
    )

    def _sanitize(html: str) -> str:
        html = _DANGEROUS_TAGS.sub("", html)
        html = _SELF_CLOSING.sub("", html)
        html = _ON_ATTR.sub("", html)
        html = _JS_URI.sub(r'\1="#"', html)
        return html


def render_markdown(text: str) -> str:
    """Render Markdown body → sanitized, safe HTML for a public page/article."""
    if not text:
        return ""
    html = _md.markdown(text, extensions=_EXTENSIONS, output_format="html")
    return mark_safe(_sanitize(html))
