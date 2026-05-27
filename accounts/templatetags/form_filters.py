from django import template

register = template.Library()

@register.filter
def add_class(field, css_class):
    """Add CSS class to a form field"""
    if hasattr(field, 'as_widget'):
        return field.as_widget(attrs={'class': css_class})
    return field

@register.filter
def get_field(form, field_name):
    """Get a field from a form by name"""
    try:
        return form[field_name]
    except (KeyError, TypeError):
        return None

@register.filter
def getattribute(obj, attr_name):
    """Get an attribute of an object dynamically by name"""
    try:
        return getattr(obj, attr_name)
    except (AttributeError, TypeError):
        return None
