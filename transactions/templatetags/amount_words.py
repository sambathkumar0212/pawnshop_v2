from django import template
from num2words import num2words

register = template.Library()

@register.filter
def number_to_words(number):
    try:
        return num2words(number, lang='en_IN')
    except:
        return ''
