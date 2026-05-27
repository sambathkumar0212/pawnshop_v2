from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import timedelta

# Import models from different apps
from transactions.models import Loan, Sale
from inventory.models import Item
from accounts.models import CustomUser
from branches.models import Branch

@login_required
def home_page(request):
    """
    Main home page view that displays links to all modules in the system
    and provides key statistics and quick access to common functions.
    """
    today = timezone.now().date()
    
    # Get statistics for the dashboard
    context = {}
    
    # Loan statistics
    try:
        active_loans = Loan.objects.filter(status='active').count()
        overdue_loans = Loan.objects.filter(status='active', due_date__lt=today).count()
        loans_due_today = Loan.objects.filter(status='active', due_date=today).count()
        recent_loans = Loan.objects.all().order_by('-created_at')[:5]
        
        context.update({
            'active_loans': active_loans,
            'overdue_loans': overdue_loans,
            'loans_due_today': loans_due_today,
            'recent_loans': recent_loans,
        })
    except Exception:
        # Handle case where Loan model might not be accessible
        pass
    
    # Sales statistics
    try:
        total_sales = Sale.objects.filter(sale_date=today).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        recent_sales = Sale.objects.all().order_by('-sale_date', '-created_at')[:5]
        
        context.update({
            'total_sales': total_sales,
            'recent_sales': recent_sales,
        })
    except Exception:
        # Handle case where Sale model might not be accessible
        pass
    
    # Inventory statistics
    try:
        total_items = Item.objects.count()
        available_items = Item.objects.filter(status='available').count()
        pawned_items = Item.objects.filter(status='pawned').count()
        
        context.update({
            'total_items': total_items,
            'available_items': available_items,
            'pawned_items': pawned_items,
        })
    except Exception:
        # Handle case where Item model might not be accessible
        pass
    
    # Customer statistics
    try:
        # Assuming there's a Customer model linked to CustomUser
        customer_count = CustomUser.objects.filter(is_customer=True).count()
        new_customers_today = CustomUser.objects.filter(
            is_customer=True, 
            date_joined__date=today
        ).count()
        
        context.update({
            'customer_count': customer_count,
            'new_customers_today': new_customers_today,
        })
    except Exception:
        # Handle case where CustomUser model might not be accessible
        pass
    
    # Branch information
    try:
        branch_count = Branch.objects.count()
        branches = Branch.objects.all()
        
        context.update({
            'branch_count': branch_count,
            'branches': branches,
        })
    except Exception:
        # Handle case where Branch model might not be accessible
        pass
    
    return render(request, 'home/home.html', context)