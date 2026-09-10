from rest_framework import serializers
from decimal import Decimal
from django.db import models
from django.utils import timezone
from .models import Loan, Payment, LoanItem, DisbursementTransaction
from inventory.models import Item, Category
from accounts.models import Customer
from branches.models import Branch
from schemes.models import Scheme
from accounts.serializers import CustomerSerializer, BranchBasicSerializer


class LoanItemSerializer(serializers.ModelSerializer):
    """Serializer for pledged ornaments in a loan"""
    item_name = serializers.CharField(source='item.name', read_only=True)
    category_name = serializers.CharField(source='item.category.name', read_only=True, default='')
    item_valuation = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = LoanItem
        fields = [
            'id',
            'item_id',
            'item_name',
            'category_name',
            'quantity',
            'gold_karat',
            'gross_weight',
            'net_weight',
            'stone_weight',
            'market_price_22k',
            'status',
            'item_valuation',
        ]


class LoanItemInputSerializer(serializers.Serializer):
    """Input serializer for ornaments when creating a loan via mobile app"""
    name = serializers.CharField(max_length=255, default="Gold Ornament")
    category_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(default=1, min_value=1)
    gold_karat = serializers.DecimalField(max_digits=4, decimal_places=2, default=Decimal('22.00'))
    gross_weight = serializers.DecimalField(max_digits=7, decimal_places=3)
    net_weight = serializers.DecimalField(max_digits=7, decimal_places=3)
    stone_weight = serializers.DecimalField(max_digits=7, decimal_places=3, required=False, default=Decimal('0.000'))
    market_price_22k = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=Decimal('6000.00'))


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for loan repayments"""
    received_by_name = serializers.CharField(source='received_by.get_full_name', read_only=True, default='')
    loan_number = serializers.CharField(source='loan.loan_number', read_only=True)
    customer_name = serializers.CharField(source='loan.customer.full_name', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id',
            'loan',
            'loan_number',
            'customer_name',
            'amount',
            'payment_date',
            'payment_method',
            'reference_number',
            'received_by',
            'received_by_name',
            'notes',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'received_by']


class PaymentCreateSerializer(serializers.Serializer):
    """Serializer for submitting a new repayment from mobile"""
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('1.00'))
    payment_date = serializers.DateField(required=False)
    payment_method = serializers.ChoiceField(choices=Payment.PAYMENT_METHOD_CHOICES, default='cash')
    reference_number = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class LoanListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for loan listing & search on mobile"""
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    total_gross_weight = serializers.SerializerMethodField()
    total_net_weight = serializers.SerializerMethodField()
    items_count = serializers.SerializerMethodField()
    remaining_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Loan
        fields = [
            'id',
            'loan_number',
            'customer',
            'customer_name',
            'customer_phone',
            'branch',
            'branch_name',
            'principal_amount',
            'interest_rate',
            'issue_date',
            'due_date',
            'status',
            'is_overdue',
            'remaining_balance',
            'total_gross_weight',
            'total_net_weight',
            'items_count',
            'created_at',
        ]

    def get_total_gross_weight(self, obj):
        agg = obj.loanitem_set.aggregate(total=models.Sum('gross_weight'))['total']
        return str(agg or '0.000')

    def get_total_net_weight(self, obj):
        agg = obj.loanitem_set.aggregate(total=models.Sum('net_weight'))['total']
        return str(agg or '0.000')

    def get_items_count(self, obj):
        return obj.loanitem_set.count()


class LoanDetailSerializer(serializers.ModelSerializer):
    """Detailed loan serializer with calculation metrics & ornament list"""
    customer = CustomerSerializer(read_only=True)
    branch = BranchBasicSerializer(read_only=True)
    loan_items = LoanItemSerializer(source='loanitem_set', many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    total_paid = serializers.DecimalField(source='amount_paid', max_digits=12, decimal_places=2, read_only=True)
    remaining_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    current_interest_due = serializers.SerializerMethodField()
    item_photos_list = serializers.ListField(source='item_photo_list', read_only=True)

    class Meta:
        model = Loan
        fields = [
            'id',
            'loan_number',
            'customer',
            'branch',
            'scheme',
            'principal_amount',
            'interest_rate',
            'processing_fee',
            'is_processing_fee_paid',
            'is_first_month_interest_paid',
            'issue_date',
            'due_date',
            'grace_period_end',
            'status',
            'is_overdue',
            'days_since_issue',
            'days_remaining',
            'total_paid',
            'current_interest_due',
            'remaining_balance',
            'loan_items',
            'payments',
            'item_photos_list',
            'created_at',
            'updated_at',
        ]

    def get_current_interest_due(self, obj):
        try:
            from transactions.services_partial_release import get_loan_current_interest_due
            return str(get_loan_current_interest_due(obj))
        except Exception:
            return '0.00'


class LoanCreateSerializer(serializers.Serializer):
    """Serializer for creating a new pledge/loan from mobile app"""
    # Customer
    customer_id = serializers.IntegerField(required=False, allow_null=True)
    customer_first_name = serializers.CharField(max_length=100, required=False)
    customer_last_name = serializers.CharField(max_length=100, required=False, default='')
    customer_phone = serializers.CharField(max_length=20, required=False)
    customer_address = serializers.CharField(required=False, allow_blank=True, default='')

    # Branch & Scheme
    branch_id = serializers.IntegerField(required=False, allow_null=True)
    scheme_id = serializers.IntegerField(required=False, allow_null=True)

    # Financials
    principal_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('100.00'))
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    duration_months = serializers.IntegerField(default=12, min_value=1, max_value=36)
    issue_date = serializers.DateField(required=False)
    processing_fee = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, default=Decimal('0.00'))
    is_processing_fee_paid = serializers.BooleanField(default=False)
    is_first_month_interest_paid = serializers.BooleanField(default=False)
    disbursement_payment_mode = serializers.ChoiceField(
        choices=['CASH', 'BANK_TRANSFER', 'UPI', 'CHEQUE'],
        default='CASH'
    )

    # Ornaments & Photos
    items = LoanItemInputSerializer(many=True)
    item_photos = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    customer_face_capture = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')
