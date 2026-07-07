import markdown as _md
from django.utils.safestring import mark_safe

_EXTENSIONS = ["extra", "sane_lists", "smarty"]


def render_markdown(text: str) -> str:
    """Render Markdown body → safe HTML for a public page/article."""
    if not text:
        return ""
    return mark_safe(_md.markdown(text, extensions=_EXTENSIONS, output_format="html"))
