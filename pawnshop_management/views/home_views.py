from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.core.cache import cache
from datetime import timedelta

# Import models from different apps
from transactions.models import Loan, Sale
from inventory.models import Item
from accounts.models import Customer
from branches.models import Branch


def _build_dashboard_stats(user):
    """
    Compute all dashboard KPIs in the fewest possible DB queries.
    Results are cached per-user for 60 seconds so rapid page refreshes
    don't hammer the database.
    """
    today = timezone.now().date()

    # ------------------------------------------------------------------
    # Loan stats — 3 counts collapsed into a single annotated query
    # ------------------------------------------------------------------
    loan_qs = Loan.objects.all()
    if hasattr(user, 'organization') and user.organization:
        loan_qs = loan_qs.filter(branch__organization=user.organization)

    # One query with annotations instead of 3 separate .count() calls
    loan_agg = loan_qs.aggregate(
        active_total=Count('pk', filter=Q(status='active')),
        overdue_total=Count('pk', filter=Q(status='active', due_date__lt=today)),
        due_today_total=Count('pk', filter=Q(status='active', due_date=today)),
    )
    active_loans = loan_agg['active_total'] or 0
    overdue_loans = loan_agg['overdue_total'] or 0
    loans_due_today = loan_agg['due_today_total'] or 0

    # Recent loans — only 5 rows, lightweight
    recent_loans = list(
        loan_qs.select_related('customer', 'branch')
        .only('loan_number', 'status', 'principal_amount', 'issue_date',
              'customer__first_name', 'customer__last_name', 'branch__name')
        .order_by('-created_at')[:5]
    )

    # ------------------------------------------------------------------
    # Sales stats — today's revenue + recent 5 rows
    # ------------------------------------------------------------------
    sale_qs = Sale.objects.all()
    if hasattr(user, 'organization') and user.organization:
        sale_qs = sale_qs.filter(branch__organization=user.organization)

    total_sales = (
        sale_qs.filter(sale_date=today)
        .aggregate(s=Sum('total_amount'))['s'] or 0
    )
    recent_sales = list(
        sale_qs.select_related('customer', 'branch')
        .only('transaction_number', 'total_amount', 'sale_date',
              'customer__first_name', 'customer__last_name', 'branch__name')
        .order_by('-sale_date', '-created_at')[:5]
    )

    # ------------------------------------------------------------------
    # Inventory stats — 3 counts in one query
    # ------------------------------------------------------------------
    item_qs = Item.objects.all()
    if hasattr(user, 'organization') and user.organization:
        item_qs = item_qs.filter(branch__organization=user.organization)

    item_agg = item_qs.aggregate(
        total=Count('pk'),
        available=Count('pk', filter=Q(status='available')),
        pawned=Count('pk', filter=Q(status='pawned')),
    )
    total_items = item_agg['total'] or 0
    available_items = item_agg['available'] or 0
    pawned_items = item_agg['pawned'] or 0

    # ------------------------------------------------------------------
    # Customer stats — 2 counts in one query
    # ------------------------------------------------------------------
    customer_qs = Customer.objects.all()
    if hasattr(user, 'organization') and user.organization:
        customer_qs = customer_qs.filter(branch__organization=user.organization)

    customer_agg = customer_qs.aggregate(
        total=Count('pk'),
        new_today=Count('pk', filter=Q(created_at__date=today)),
    )
    customer_count = customer_agg['total'] or 0
    new_customers_today = customer_agg['new_today'] or 0

    # ------------------------------------------------------------------
    # Branch info
    # ------------------------------------------------------------------
    branch_qs = Branch.objects.all()
    if hasattr(user, 'organization') and user.organization:
        branch_qs = branch_qs.filter(organization=user.organization)
    branch_count = branch_qs.count()
    branches = list(branch_qs.only('name', 'city'))

    return {
        'active_loans': active_loans,
        'overdue_loans': overdue_loans,
        'loans_due_today': loans_due_today,
        'recent_loans': recent_loans,
        'total_sales': total_sales,
        'recent_sales': recent_sales,
        'total_items': total_items,
        'available_items': available_items,
        'pawned_items': pawned_items,
        'customer_count': customer_count,
        'new_customers_today': new_customers_today,
        'branch_count': branch_count,
        'branches': branches,
    }


@login_required
def home_page(request):
    """
    Main home page — dashboard KPIs cached per user for 60 seconds.
    Uses aggregated queries (not individual .count() calls) to minimise
    DB round-trips from the previous 10+ queries down to ~5.
    """
    cache_key = f'dashboard_stats_{request.user.pk}'
    context = cache.get(cache_key)

    if context is None:
        try:
            context = _build_dashboard_stats(request.user)
        except Exception:
            # Graceful degradation: show empty dashboard rather than 500
            context = {}
        # Cache for 60 seconds — recent enough for operational use
        cache.set(cache_key, context, 60)

    return render(request, 'home/home.html', context)