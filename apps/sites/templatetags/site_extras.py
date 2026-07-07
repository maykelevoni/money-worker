from django import template

from ..markdown_util import render_markdown

register = template.Library()


@register.filter
def markdownify(value):
    return render_markdown(value or "")
