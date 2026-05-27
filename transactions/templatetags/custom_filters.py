from django import template
import re
from decimal import Decimal
import json

register = template.Library()


@register.filter(name='mobile_digits')
def mobile_digits(value):
    """Return only the last 10 digits from a phone-like value."""
    if value is None:
        return ''
    digits = re.sub(r'\D', '', str(value))
    if len(digits) >= 10:
        return digits[-10:]
    return digits


@register.filter(name='mobile_format')
def mobile_format(value):
    """Format phone as '85758 69850' (5+5) using last 10 digits."""
    digits = mobile_digits(value)
    if len(digits) == 10:
        return f"{digits[:5]} {digits[5:]}"
    return digits

@register.filter(name='percentage')
def percentage(part, whole):
    """Calculate what percentage the part is of the whole"""
    try:
        if not whole:
            return 0
        return float(part) / float(whole) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter(name='subtract')
def subtract(value, arg):
    """Subtract the arg from the value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter(name='remaining_balance')
def remaining_balance(total_payable, amount_paid):
    """Calculate remaining balance, ensuring it's never negative (0 for fully paid loans)"""
    try:
        balance = float(total_payable) - float(amount_paid)
        return max(0, balance)  # Ensure it's never negative
    except (ValueError, TypeError):
        return 0

@register.filter(name='replace_underscore')
def replace_underscore(value):
    """Replace underscores with spaces and capitalize each word"""
    if not value:
        return ""
    try:
        return value.replace('_', ' ')
    except (ValueError, TypeError, AttributeError):
        return value

@register.filter(name='get_first_photo')
def get_first_photo(item_photos):
    """Extract the first photo URL from JSON string of photos"""
    if not item_photos:
        return ""
    
    try:
        # If it's a string, try to parse as JSON
        if isinstance(item_photos, str):
            if item_photos.startswith('data:image/'):
                # It's already a direct base64 image
                return item_photos
            
            # Try to parse JSON
            photos = json.loads(item_photos)
            
            # If we got a list and it contains items
            if isinstance(photos, list) and photos:
                return photos[0]
            
            return ""
        
        # If it's already a list
        elif isinstance(item_photos, list) and item_photos:
            return item_photos[0]
        
        return ""
    except (json.JSONDecodeError, TypeError, IndexError):
        # If there's any error, return empty string
        return ""
