from django import template

register = template.Library()


@register.filter
def split_lines(value):
    return [line.strip() for line in (value or "").splitlines() if line.strip()]
