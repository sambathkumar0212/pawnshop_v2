from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Template filter to get an item from a dictionary using a dynamic key.
    Usage: {{ my_dict|get_item:key_variable }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def get_nested_item(dictionary, key_path):
    """
    Template filter to get a nested item from a dictionary using dot notation.
    Usage: {{ my_dict|get_nested_item:"key1.key2" }}
    """
    if dictionary is None:
        return None
    
    keys = key_path.split('.')
    value = dictionary
    
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
        if value is None:
            return None
    
    return value