from rest_framework import serializers
from decimal import Decimal


class RecentLoanSerializer(serializers.Serializer):
    """Lightweight serializer for recent loans on mobile dashboard"""
    id = serializers.IntegerField()
    loan_number = serializers.CharField()
    customer_name = serializers.CharField()
    customer_phone = serializers.CharField()
    principal_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    status = serializers.CharField()
    issue_date = serializers.DateField()
    branch_name = serializers.CharField()


class RecentPaymentSerializer(serializers.Serializer):
    """Lightweight serializer for recent payments on mobile dashboard"""
    id = serializers.IntegerField()
    loan_number = serializers.CharField()
    customer_name = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method = serializers.CharField()
    payment_date = serializers.DateField()
    reference_number = serializers.CharField(allow_blank=True, allow_null=True)


class DashboardKPISerializer(serializers.Serializer):
    """Financial & Operational KPI summary metrics"""
    # Daily Activities
    today_disbursed_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    today_disbursed_count = serializers.IntegerField()
    today_collection_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    today_collection_count = serializers.IntegerField()
    today_cash_collected = serializers.DecimalField(max_digits=14, decimal_places=2)
    today_digital_collected = serializers.DecimalField(max_digits=14, decimal_places=2)
    today_net_cash_flow = serializers.DecimalField(max_digits=14, decimal_places=2)

    # Portfolio Health
    active_loans_count = serializers.IntegerField()
    active_loans_principal = serializers.DecimalField(max_digits=14, decimal_places=2)
    overdue_loans_count = serializers.IntegerField()
    loans_due_today_count = serializers.IntegerField()

    # Gold In Custody
    total_pledged_gross_weight_grams = serializers.DecimalField(max_digits=12, decimal_places=3)
    total_pledged_net_weight_grams = serializers.DecimalField(max_digits=12, decimal_places=3)
    total_active_pledge_items = serializers.IntegerField()

    # Customers & Inventory
    total_customers_count = serializers.IntegerField()
    new_customers_today = serializers.IntegerField()
    total_inventory_items = serializers.IntegerField()


class DashboardSummaryResponseSerializer(serializers.Serializer):
    """Main response structure for /api/v1/dashboard/summary/"""
    date = serializers.DateField()
    branch_filter = serializers.DictField(allow_null=True)
    kpis = DashboardKPISerializer()
    recent_loans = RecentLoanSerializer(many=True)
    recent_payments = RecentPaymentSerializer(many=True)
