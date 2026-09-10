from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.utils import timezone
from django.db.models import Sum, Count, Q
from decimal import Decimal
import datetime
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from transactions.models import Loan, Payment, LoanItem, DisbursementTransaction
from accounts.models import Customer
from branches.models import Branch
from inventory.models import Item
from .serializers import DashboardSummaryResponseSerializer


class DashboardSummaryAPIView(APIView):
    """
    GET /api/v1/dashboard/summary/
    
    Query parameters:
    - branch_id (int, optional): Filter by specific branch ID.
    - date (str, optional): Target date in YYYY-MM-DD format (defaults to today).
    
    Returns comprehensive KPIs:
    - Daily collections (cash vs digital) & disbursements
    - Active loan portfolio & overdue metrics
    - Total gold weight in locker custody
    - Recent loans & payments
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Get Dashboard KPI Summary",
        description="Returns daily collections, active portfolio stats, cash flow, and gold inventory in custody.",
        responses={200: DashboardSummaryResponseSerializer},
        parameters=[
            OpenApiParameter(name='branch_id', description='Filter by Branch ID', required=False, type=OpenApiTypes.INT),
            OpenApiParameter(name='date', description='Target date in YYYY-MM-DD format (defaults to today)', required=False, type=OpenApiTypes.STR),
        ],
        tags=["Dashboard & Analytics"]
    )
    def get(self, request):
        user = request.user

        # 1. Determine Target Date
        date_param = request.query_params.get('date')
        if date_param:
            try:
                target_date = datetime.date.fromisoformat(date_param)
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Expected YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            target_date = timezone.now().date()

        # 2. Branch Scoping & Filtering
        branch_id_param = request.query_params.get('branch_id')
        selected_branch = None
        branch_filter_info = None

        if branch_id_param:
            try:
                branch_obj = Branch.objects.get(pk=int(branch_id_param), is_active=True)
                # Check user access to this branch
                if user.is_superuser:
                    selected_branch = branch_obj
                elif hasattr(user, 'organization') and user.organization and branch_obj.organization_id == user.organization_id:
                    selected_branch = branch_obj
                elif user.branch_id == branch_obj.id:
                    selected_branch = branch_obj
                elif user.is_regional_manager and branch_obj in user.managed_branches:
                    selected_branch = branch_obj
                else:
                    return Response(
                        {'error': 'You do not have permission to access data for this branch.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except (Branch.DoesNotExist, ValueError):
                return Response(
                    {'error': f'Branch with ID {branch_id_param} not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif not user.is_superuser and not user.is_regional_manager and user.branch:
            # Standard staff default to their assigned branch
            selected_branch = user.branch

        if selected_branch:
            branch_filter_info = {
                'id': selected_branch.id,
                'name': selected_branch.name,
            }

        # 3. Base QuerySets with Tenant & Branch isolation
        loan_qs = Loan.objects.all()
        payment_qs = Payment.objects.all()
        loan_item_qs = LoanItem.objects.all()
        customer_qs = Customer.objects.all()
        item_qs = Item.objects.all()

        if hasattr(user, 'organization') and user.organization:
            loan_qs = loan_qs.filter(branch__organization=user.organization)
            payment_qs = payment_qs.filter(loan__branch__organization=user.organization)
            loan_item_qs = loan_item_qs.filter(loan__branch__organization=user.organization)
            customer_qs = customer_qs.filter(branch__organization=user.organization)
            item_qs = item_qs.filter(branch__organization=user.organization)

        if selected_branch:
            loan_qs = loan_qs.filter(branch=selected_branch)
            payment_qs = payment_qs.filter(loan__branch=selected_branch)
            loan_item_qs = loan_item_qs.filter(loan__branch=selected_branch)
            customer_qs = customer_qs.filter(branch=selected_branch)
            item_qs = item_qs.filter(branch=selected_branch)

        # 4. Compute Daily Disbursement KPIs
        today_loans = loan_qs.filter(issue_date=target_date)
        today_disbursed_agg = today_loans.aggregate(
            total_disbursed=Sum('principal_amount'),
            count=Count('pk')
        )
        today_disbursed_amount = today_disbursed_agg['total_disbursed'] or Decimal('0.00')
        today_disbursed_count = today_disbursed_agg['count'] or 0

        # 5. Compute Daily Payment Collections
        today_payments = payment_qs.filter(payment_date=target_date)
        payment_agg = today_payments.aggregate(
            total=Sum('amount'),
            count=Count('pk'),
            cash_total=Sum('amount', filter=Q(payment_method__iexact='cash')),
            digital_total=Sum('amount', filter=~Q(payment_method__iexact='cash'))
        )
        today_collection_amount = payment_agg['total'] or Decimal('0.00')
        today_collection_count = payment_agg['count'] or 0
        today_cash_collected = payment_agg['cash_total'] or Decimal('0.00')
        today_digital_collected = payment_agg['digital_total'] or Decimal('0.00')

        # Compute net cash flow (Cash collected - Cash disbursed)
        # Check cash disbursements
        cash_disbursed_agg = DisbursementTransaction.objects.filter(
            loan__in=today_loans,
            payment_mode='CASH'
        ).aggregate(total=Sum('amount'))
        today_cash_disbursed = cash_disbursed_agg['total'] or Decimal('0.00')
        today_net_cash_flow = today_cash_collected - today_cash_disbursed

        # 6. Compute Portfolio Health
        portfolio_agg = loan_qs.aggregate(
            active_count=Count('pk', filter=Q(status='active')),
            active_principal=Sum('principal_amount', filter=Q(status='active')),
            overdue_count=Count('pk', filter=Q(status='active', due_date__lt=target_date)),
            due_today_count=Count('pk', filter=Q(status='active', due_date=target_date)),
        )
        active_loans_count = portfolio_agg['active_count'] or 0
        active_loans_principal = portfolio_agg['active_principal'] or Decimal('0.00')
        overdue_loans_count = portfolio_agg['overdue_count'] or 0
        loans_due_today_count = portfolio_agg['due_today_count'] or 0

        # 7. Compute Gold in Custody (from active pledged LoanItems)
        active_items_agg = loan_item_qs.filter(
            loan__status='active',
            status='pledged'
        ).aggregate(
            gross_weight=Sum('gross_weight'),
            net_weight=Sum('net_weight'),
            items_count=Count('pk')
        )
        total_pledged_gross_weight = active_items_agg['gross_weight'] or Decimal('0.000')
        total_pledged_net_weight = active_items_agg['net_weight'] or Decimal('0.000')
        total_active_pledge_items = active_items_agg['items_count'] or 0

        # 8. Customer and Inventory Counts
        customer_agg = customer_qs.aggregate(
            total=Count('pk'),
            new_today=Count('pk', filter=Q(created_at__date=target_date))
        )
        total_customers_count = customer_agg['total'] or 0
        new_customers_today = customer_agg['new_today'] or 0
        total_inventory_items = item_qs.count()

        # 9. Recent 5 Loans
        recent_loans_raw = loan_qs.select_related('customer', 'branch').order_by('-created_at')[:5]
        recent_loans = [
            {
                'id': l.id,
                'loan_number': l.loan_number,
                'customer_name': l.customer.full_name if l.customer else 'Unknown',
                'customer_phone': l.customer.phone if hasattr(l.customer, 'phone') else '',
                'principal_amount': l.principal_amount,
                'status': l.status,
                'issue_date': l.issue_date,
                'branch_name': l.branch.name if l.branch else '',
            }
            for l in recent_loans_raw
        ]

        # 10. Recent 5 Payments
        recent_payments_raw = payment_qs.select_related('loan__customer').order_by('-payment_date', '-created_at')[:5]
        recent_payments = [
            {
                'id': p.id,
                'loan_number': p.loan.loan_number if p.loan else '',
                'customer_name': p.loan.customer.full_name if p.loan and p.loan.customer else 'Unknown',
                'amount': p.amount,
                'payment_method': p.payment_method,
                'payment_date': p.payment_date,
                'reference_number': p.reference_number or '',
            }
            for p in recent_payments_raw
        ]

        # 11. Compile Full Response Payload
        response_data = {
            'date': target_date,
            'branch_filter': branch_filter_info,
            'kpis': {
                'today_disbursed_amount': today_disbursed_amount,
                'today_disbursed_count': today_disbursed_count,
                'today_collection_amount': today_collection_amount,
                'today_collection_count': today_collection_count,
                'today_cash_collected': today_cash_collected,
                'today_digital_collected': today_digital_collected,
                'today_net_cash_flow': today_net_cash_flow,
                'active_loans_count': active_loans_count,
                'active_loans_principal': active_loans_principal,
                'overdue_loans_count': overdue_loans_count,
                'loans_due_today_count': loans_due_today_count,
                'total_pledged_gross_weight_grams': total_pledged_gross_weight,
                'total_pledged_net_weight_grams': total_pledged_net_weight,
                'total_active_pledge_items': total_active_pledge_items,
                'total_customers_count': total_customers_count,
                'new_customers_today': new_customers_today,
                'total_inventory_items': total_inventory_items,
            },
            'recent_loans': recent_loans,
            'recent_payments': recent_payments,
        }

        serializer = DashboardSummaryResponseSerializer(response_data)
        return Response(serializer.data, status=status.HTTP_200_OK)
