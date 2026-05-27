"""Utility module for handling default photos across the project"""

from urllib.parse import quote
from .category_photos import CATEGORY_PHOTOS

def get_default_person_photo():
    """Returns a stable, lightweight SVG avatar as data URI."""
    svg = """
    <svg xmlns='http://www.w3.org/2000/svg' width='240' height='240' viewBox='0 0 240 240'>
      <rect width='240' height='240' fill='#f1f3f5'/>
      <circle cx='120' cy='92' r='44' fill='#adb5bd'/>
      <path d='M40 214c0-44 36-74 80-74s80 30 80 74' fill='#adb5bd'/>
    </svg>
    """.strip()
    return f"data:image/svg+xml;utf8,{quote(svg)}"

def get_default_item_photo(category=None):
    """Returns the default item photo based on category"""
    if not category:
        return f"data:image/jpeg;base64,{CATEGORY_PHOTOS['jewelry']}"  # Default to jewelry
        
    # Convert category name to snake_case for matching
    category_key = category.name.lower().replace(' ', '_')
    
    # Get the appropriate photo or default to jewelry
    photo_base64 = CATEGORY_PHOTOS.get(category_key, CATEGORY_PHOTOS['jewelry'])
    return f"data:image/jpeg;base64,{photo_base64}"

def get_category_specific_photo(category_name):
    """Returns a category-specific photo by name"""
    category_key = category_name.lower().replace(' ', '_')
    photo_base64 = CATEGORY_PHOTOS.get(category_key, CATEGORY_PHOTOS['jewelry'])
    return f"data:image/jpeg;base64,{photo_base64}" 
