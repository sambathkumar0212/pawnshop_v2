from django import template

register = template.Library()

@register.filter(name='split')
def split_filter(value, arg):
    """Split a string by the given delimiter"""
    return value.split(arg)

@register.filter(name='replace')
def replace_filter(value, arg):
    """Replace characters in a string with a space"""
    return value.replace(arg, " ")

@register.filter(name='calculate_late_period')
def calculate_late_period(scheme):
    """Calculate the late period duration for a scheme"""
    if scheme.expiry_period and scheme.early_period_months and scheme.standard_period_months:
        late_period = scheme.expiry_period - (scheme.early_period_months + scheme.standard_period_months)
        return max(0, late_period)  # Ensure it's not negative
    return 0