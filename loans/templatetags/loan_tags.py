from django import template

register = template.Library()

# ...existing filters...

@register.filter
def percentage(part, whole):
    """Calculate what percentage the part is of the whole"""
    try:
        if whole == 0:
            return 0
        return min(100, int((float(part) / float(whole)) * 100))
    except (ValueError, ZeroDivisionError):
        return 0