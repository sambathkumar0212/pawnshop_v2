import json
from django import template
from django.utils.safestring import mark_safe
try:
    from transactions.views import process_item_photos_for_display, get_first_item_photo, get_item_photos_count
except Exception:
    def process_item_photos_for_display(item_photos):
        return item_photos

    def get_first_item_photo(item_photos):
        return ''

    def get_item_photos_count(item_photos):
        return 0

register = template.Library()

@register.filter
def status_color(status):
    """Return the appropriate Bootstrap color class for a loan status"""
    colors = {
        'active': 'success',
        'repaid': 'info',
        'defaulted': 'danger',
        'extended': 'warning',
        'foreclosed': 'secondary',
    }
    return colors.get(status, 'secondary')

@register.filter
def first_item_photo(item_photos):
    """Return the first item photo from the item_photos JSON data using centralized logic"""
    return get_first_item_photo(item_photos)

@register.filter
def item_photos_count(item_photos):
    """Return the count of item photos using centralized logic"""
    return get_item_photos_count(item_photos)

@register.filter
def process_item_photos(item_photos):
    """Process item photos for display using centralized logic"""
    return process_item_photos_for_display(item_photos)

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        from decimal import Decimal
        value = Decimal(str(value))
        arg = Decimal(str(arg))
        return value * arg
    except (ValueError, TypeError):
        return 0

@register.filter
def subtract(value, arg):
    """Subtract arg from value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def add(value, arg):
    """Add the arg to the value."""
    try:
        return value + arg
    except (ValueError, TypeError):
        return value

@register.filter
def add_days(date, days):
    """Add days to a date"""
    from datetime import timedelta
    try:
        return date + timedelta(days=int(days))
    except (ValueError, TypeError):
        return date

@register.filter
def split(value, arg):
    """Split the value by the delimiter."""
    return value.split(arg)

@register.filter
def calculate_total_items(item_name):
    """Calculate total items from item name like 'ring-6, chain-1' -> 7"""
    if not item_name:
        return 0
    
    total = 0
    import re
    # Pattern to match formats like "ring-6" or "earrings-2"
    pattern = r'(\w+)-(\d+)'
    matches = re.findall(pattern, str(item_name))
    
    for item_type, count in matches:
        try:
            total += int(count)
        except ValueError:
            continue
    
    return total

@register.filter
def is_base64(value):
    """Check if a value is a base64 image"""
    return isinstance(value, str) and value.startswith('data:image/')

@register.filter
def is_empty_photo_list(item_photos):
    """Check if item_photos is empty or contains no valid photos"""
    if not item_photos:
        return True
    
    if isinstance(item_photos, str):
        if item_photos in ['[]', '', 'null']:
            return True
        try:
            photos = json.loads(item_photos)
            return not photos or len(photos) == 0
        except:
            return True
    
    if isinstance(item_photos, list):
        return len(item_photos) == 0
    
    return True

@register.filter
def replace_underscore(value):
    """Replace underscores with spaces"""
    return str(value).replace('_', ' ')

@register.filter
def due_date_color(loan):
    """Return color class based on due date status:
    - Green: 30+ days until due date
    - Orange/Warning: Less than 30 days until due date
    - Red/Danger: In grace period (due_date passed, grace_period_end not passed)
    - Dark Red: Grace period expired
    """
    from django.utils import timezone
    from datetime import timedelta
    
    if not hasattr(loan, 'due_date') or not loan.due_date:
        return 'secondary'
    
    today = timezone.now().date()
    days_until_due = (loan.due_date - today).days
    
    # Check grace period
    if hasattr(loan, 'grace_period_end') and loan.grace_period_end:
        if today > loan.grace_period_end:
            # Grace period expired
            return 'danger'
        elif today > loan.due_date:
            # In grace period
            return 'warning'
    
    # Days until due date
    if days_until_due >= 30:
        return 'success'  # Green - safe
    elif days_until_due > 0:
        return 'warning'  # Orange/Yellow - approaching
    elif days_until_due == 0:
        return 'warning'  # Today is due date
    else:
        # Overdue
        return 'danger'

@register.filter
def due_date_bg_color(loan):
    """Return background color styling for due date cell"""
    color_class = due_date_color(loan)
    color_map = {
        'success': '#d4edda',  # Light green
        'warning': '#fff3cd',  # Light yellow
        'danger': '#f8d7da',   # Light red
        'secondary': '#e2e3e5',  # Light gray
    }
    color = color_map.get(color_class, '#fff')
    return f'background-color: {color};'
