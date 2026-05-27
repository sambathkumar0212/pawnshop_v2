from django import template
from decimal import Decimal
from datetime import timedelta
import re
from num2words import num2words
import json

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        value = Decimal(str(value))
        arg = Decimal(str(arg))
        return value * arg
    except (ValueError, TypeError):
        return 0

@register.filter
def date_add_days(value, days):
    """Add a number of days to a date"""
    try:
        days = int(days)
        return value + timedelta(days=days)
    except (ValueError, TypeError):
        return value

@register.filter
def calculate_total_items(item_name):
    """
    Calculate the total number of items from an item name string
    Format: "ring-6, chain-1" would return 7
    """
    if not item_name:
        return 0
    
    total_count = 0
    # Split by commas to handle multiple items
    items = [item.strip() for item in item_name.split(',') if item.strip()]
    
    for item in items:
        # Find patterns like "item-3" or "item - 5"
        match = re.search(r'(\w+)\s*-\s*(\d+)', item)
        if match:
            try:
                count = int(match.group(2))
                total_count += count
            except ValueError:
                pass
    
    return total_count

@register.filter
def number_to_words(value):
    """Convert a number to words in Indian format"""
    try:
        # Convert to float and format to handle decimals properly
        amount = float(value)
        return num2words(amount, lang='en_IN').title()
    except (ValueError, TypeError):
        return ''

@register.filter
def is_base64(value):
    """Check if a string is a base64 image data URL or contains base64 data"""
    if not value:
        return False
    
    # If it's a string
    if isinstance(value, str):
        # Direct base64 image check
        if value.startswith('data:image/'):
            return True
            
        # Check if it's a JSON string containing base64 data
        try:
            if value.startswith('[') and value.endswith(']'):
                data = json.loads(value)
                if isinstance(data, list) and any(isinstance(item, str) and item.startswith('data:image/') for item in data):
                    return True
        except (json.JSONDecodeError, TypeError):
            pass
            
        # If it's a URL path, return False
        if value.startswith('/media/') or value.startswith('http'):
            return False
    
    return False

@register.filter
def is_empty_photo_list(value):
    """Check if a value represents an empty photo list (either '[]' string or actual empty list)"""
    if value is None:
        return True
        
    if isinstance(value, str):
        # Check if it's a string that just contains '[]'
        if value.strip() == '[]':
            return True
            
        # Try to decode as JSON to see if it's an empty list
        try:
            data = json.loads(value)
            return isinstance(data, list) and len(data) == 0
        except (json.JSONDecodeError, TypeError):
            pass
            
    # Check if it's an actual Python empty list
    if isinstance(value, list) and len(value) == 0:
        return True
        
    return False

@register.filter
def subtract(value, arg):
    """Subtract the argument from the value"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0

# Try/Except template tags for error handling
@register.tag(name="try")
def do_try(parser, token):
    """
    Wrap content in a try/except block for graceful error handling in templates.
    
    Usage:
    {% try %}
        <!-- code that might raise an error -->
    {% except %}
        <!-- fallback content -->
    {% endtry %}
    """
    bits = list(token.split_contents())
    if len(bits) != 1:
        raise template.TemplateSyntaxError("'try' tag takes no arguments")
    
    # Parse content until endtry, with except as a divider
    try_nodelist = parser.parse(('except',))
    token = parser.next_token()
    
    except_nodelist = parser.parse(('endtry',))
    parser.delete_first_token()
    
    return TryExceptNode(try_nodelist, except_nodelist)

class TryExceptNode(template.Node):
    def __init__(self, try_nodelist, except_nodelist):
        self.try_nodelist = try_nodelist
        self.except_nodelist = except_nodelist
        
    def render(self, context):
        try:
            return self.try_nodelist.render(context)
        except Exception:
            return self.except_nodelist.render(context)