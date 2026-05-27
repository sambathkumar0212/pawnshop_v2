from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def monthly_interest_rate(loan):
    """Display the monthly interest rate for a loan."""
    if hasattr(loan, 'monthly_interest'):
        return loan.monthly_interest['rate']
    return Decimal('0.00')

@register.filter
def monthly_interest_amount(loan):
    """Display the monthly interest amount for a loan."""
    if hasattr(loan, 'monthly_interest'):
        return loan.monthly_interest['amount']
    return Decimal('0.00')

@register.filter
def monthly_interest_per_thousand(loan):
    """Display the monthly interest per 1000 of principal."""
    if hasattr(loan, 'monthly_interest'):
        return loan.monthly_interest['per_thousand']
    return Decimal('0.00')

@register.simple_tag
def monthly_interest_info(loan):
    """Return a dict with all monthly interest information."""
    if hasattr(loan, 'monthly_interest'):
        return loan.monthly_interest
    return {
        'rate': Decimal('0.00'),
        'amount': Decimal('0.00'),
        'per_thousand': Decimal('0.00')
    }