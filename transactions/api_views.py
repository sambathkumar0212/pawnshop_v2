from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Sum
from decimal import Decimal
import datetime
import uuid
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import Loan, Payment, LoanItem, DisbursementTransaction
from inventory.models import Item, Category
from accounts.models import Customer
from branches.models import Branch
from schemes.models import Scheme
from .serializers import (
    LoanListSerializer,
    LoanDetailSerializer,
    LoanCreateSerializer,
    PaymentSerializer,
    PaymentCreateSerializer,
)


class LoanListAPIView(APIView):
    """
    GET /api/v1/loans/
    
    Query Parameters:
    - search (str): Searches loan number, customer full name, or phone number.
    - status (str): Filter by status ('active', 'repaid', 'overdue', 'defaulted').
    - branch_id (int): Filter by branch.
    - is_overdue (bool): If 'true', filters only overdue active loans.
    - page & page_size: Pagination controls.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="List & Search Loans",
        description="List and filter loans by status, customer name, phone number, or branch with pagination.",
        responses={200: LoanListSerializer(many=True)},
        parameters=[
            OpenApiParameter(name='search', description='Search by loan number, customer name, or phone', required=False, type=OpenApiTypes.STR),
            OpenApiParameter(name='status', description='Filter by loan status (active, repaid, overdue)', required=False, type=OpenApiTypes.STR),
            OpenApiParameter(name='branch_id', description='Filter by Branch ID', required=False, type=OpenApiTypes.INT),
            OpenApiParameter(name='page', description='Page number', required=False, type=OpenApiTypes.INT),
            OpenApiParameter(name='page_size', description='Items per page', required=False, type=OpenApiTypes.INT),
        ],
        tags=["Loans & Pledges"]
    )
    def get(self, request):
        user = request.user
        queryset = Loan.objects.select_related('customer', 'branch').prefetch_related('loanitem_set').order_by('-created_at')

        # Multi-tenant isolation
        if hasattr(user, 'organization') and user.organization:
            queryset = queryset.filter(branch__organization=user.organization)
        elif not user.is_superuser and not user.is_regional_manager and user.branch:
            queryset = queryset.filter(branch=user.branch)

        # Filter by branch query param if allowed
        branch_id = request.query_params.get('branch_id')
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)

        # Search query (loan_number, customer name, customer phone)
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(loan_number__icontains=search) |
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search) |
                Q(customer__phone__icontains=search)
            )

        # Status filter
        status_filter = request.query_params.get('status', '').strip().lower()
        if status_filter == 'overdue':
            queryset = queryset.filter(status='active', due_date__lt=timezone.now().date())
        elif status_filter:
            queryset = queryset.filter(status=status_filter)

        # Direct overdue flag
        is_overdue = request.query_params.get('is_overdue')
        if is_overdue and is_overdue.lower() in ('true', '1'):
            queryset = queryset.filter(status='active', due_date__lt=timezone.now().date())

        # Simple pagination
        try:
            page = max(1, int(request.query_params.get('page', 1)))
            page_size = min(100, max(1, int(request.query_params.get('page_size', 20))))
        except ValueError:
            page, page_size = 1, 20

        total_count = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        results = queryset[start:end]

        serializer = LoanListSerializer(results, many=True)
        return Response({
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size if total_count > 0 else 1,
            'results': serializer.data,
        }, status=status.HTTP_200_OK)


class LoanDetailAPIView(APIView):
    """
    GET /api/v1/loans/<loan_identifier>/
    Retrieves full details for a loan by ID or loan number.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, loan_identifier, user):
        queryset = Loan.objects.select_related('customer', 'branch', 'scheme').prefetch_related('loanitem_set__item', 'payments')
        if hasattr(user, 'organization') and user.organization:
            queryset = queryset.filter(branch__organization=user.organization)
        elif not user.is_superuser and not user.is_regional_manager and user.branch:
            queryset = queryset.filter(branch=user.branch)

        if loan_identifier.isdigit():
            return queryset.filter(Q(id=int(loan_identifier)) | Q(loan_number=loan_identifier)).first()
        return queryset.filter(loan_number=loan_identifier).first()

    @extend_schema(
        summary="Get Loan Details",
        description="Retrieve complete loan details, customer info, pledged ornaments, interest calculations, and payment history.",
        responses={200: LoanDetailSerializer},
        tags=["Loans & Pledges"]
    )
    def get(self, request, loan_identifier):
        loan = self.get_object(loan_identifier, request.user)
        if not loan:
            return Response({'error': f'Loan "{loan_identifier}" not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = LoanDetailSerializer(loan)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LoanCreateAPIView(APIView):
    """
    POST /api/v1/loans/create/
    Creates a new pledge/loan with attached gold items and photos from mobile app.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Create New Loan / Pledge",
        description="Create a loan with pledged gold ornaments, item weights, camera photos, and disbursement records.",
        request=LoanCreateSerializer,
        responses={201: LoanDetailSerializer},
        tags=["Loans & Pledges"]
    )
    @transaction.atomic
    def post(self, request):
        serializer = LoanCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user = request.user

        # 1. Determine Branch
        branch = None
        if data.get('branch_id'):
            branch = Branch.objects.filter(pk=data['branch_id'], is_active=True).first()
        elif user.branch:
            branch = user.branch
        elif user.is_superuser:
            branch = Branch.objects.filter(is_active=True).first()

        if not branch:
            return Response({'error': 'A valid active branch must be specified.'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Determine / Create Customer
        customer = None
        if data.get('customer_id'):
            customer = Customer.objects.filter(pk=data['customer_id']).first()
        elif data.get('customer_phone'):
            phone = data['customer_phone'].strip()
            customer = Customer.objects.filter(phone=phone).first()
            if not customer:
                customer = Customer.objects.create(
                    first_name=data.get('customer_first_name', 'Customer'),
                    last_name=data.get('customer_last_name', ''),
                    phone=phone,
                    address=data.get('customer_address', ''),
                    branch=branch
                )

        if not customer:
            return Response({'error': 'Customer details or valid customer_id required.'}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Determine Scheme & Interest Rate
        scheme = None
        if data.get('scheme_id'):
            scheme = Scheme.objects.filter(pk=data['scheme_id'], is_active=True).first()

        interest_rate = data.get('interest_rate')
        if interest_rate is None:
            if scheme and scheme.interest_rate:
                interest_rate = Decimal(str(scheme.interest_rate))
            else:
                interest_rate = Decimal('18.00')

        # 4. Compute Issue & Due Dates
        issue_date = data.get('issue_date') or timezone.now().date()
        duration_months = data.get('duration_months', 12)
        due_date = issue_date + datetime.timedelta(days=duration_months * 30)
        grace_period_end = due_date + datetime.timedelta(days=7)

        # 5. Create Loan Record
        loan = Loan(
            customer=customer,
            branch=branch,
            scheme=scheme,
            principal_amount=data['principal_amount'],
            interest_rate=interest_rate,
            processing_fee=data.get('processing_fee', Decimal('0.00')),
            is_processing_fee_paid=data.get('is_processing_fee_paid', False),
            is_first_month_interest_paid=data.get('is_first_month_interest_paid', False),
            issue_date=issue_date,
            due_date=due_date,
            grace_period_end=grace_period_end,
            status='active',
            item_photos=data.get('item_photos', []),
            customer_face_capture=data.get('customer_face_capture', ''),
            maker=user,
        )
        loan.save()

        # 6. Create Items & LoanItems for each pledged ornament
        default_cat = Category.objects.filter(name='Mixed Items').first()
        if not default_cat:
            default_cat = Category.objects.create(name='Mixed Items', slug='mixed-items')

        for item_data in data['items']:
            cat = None
            if item_data.get('category_id'):
                cat = Category.objects.filter(pk=item_data['category_id']).first()
            if not cat:
                cat = default_cat

            inv_item = Item.objects.create(
                item_id=f"ITM-{uuid.uuid4().hex[:8].upper()}",
                name=item_data.get('name', 'Gold Ornament'),
                description=f"Pledged in Loan {loan.loan_number}",
                category=cat,
                branch=branch,
                status='pawned',
                appraised_value=item_data['gross_weight'] * Decimal('5000.00'),
                created_by=user
            )

            LoanItem.objects.create(
                loan=loan,
                item=inv_item,
                quantity=item_data.get('quantity', 1),
                gold_karat=item_data.get('gold_karat', Decimal('22.00')),
                gross_weight=item_data['gross_weight'],
                net_weight=item_data['net_weight'],
                stone_weight=item_data.get('stone_weight', Decimal('0.000')),
                market_price_22k=item_data.get('market_price_22k', Decimal('6000.00')),
                status='pledged'
            )

        # 7. Record Disbursement Transaction
        payment_mode = data.get('disbursement_payment_mode', 'CASH')
        DisbursementTransaction.objects.create(
            loan=loan,
            amount=loan.principal_amount,
            payment_mode=payment_mode,
            disbursed_by=user,
            notes=f"Disbursed via Mobile App ({payment_mode})"
        )

        detail_serializer = LoanDetailSerializer(loan)
        return Response({
            'message': 'Loan created successfully.',
            'loan': detail_serializer.data,
        }, status=status.HTTP_201_CREATED)


class LoanPaymentAPIView(APIView):
    """
    POST /api/v1/loans/<loan_identifier>/repay/
    Records an interest / principal repayment against a loan.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Record Loan Repayment",
        description="Records a payment (Cash, UPI, Bank Transfer) towards a loan and validates Section 269ST limits.",
        request=PaymentCreateSerializer,
        responses={201: PaymentSerializer},
        tags=["Repayments & Cash"]
    )
    @transaction.atomic
    def post(self, request, loan_identifier):
        user = request.user
        queryset = Loan.objects.select_related('customer', 'branch')
        if hasattr(user, 'organization') and user.organization:
            queryset = queryset.filter(branch__organization=user.organization)
        elif not user.is_superuser and not user.is_regional_manager and user.branch:
            queryset = queryset.filter(branch=user.branch)

        if loan_identifier.isdigit():
            loan = queryset.filter(Q(id=int(loan_identifier)) | Q(loan_number=loan_identifier)).first()
        else:
            loan = queryset.filter(loan_number=loan_identifier).first()

        if not loan:
            return Response({'error': f'Loan "{loan_identifier}" not found.'}, status=status.HTTP_404_NOT_FOUND)

        if loan.status not in ['active', 'overdue']:
            return Response(
                {'error': f'Cannot record payment. Loan status is "{loan.get_status_display()}".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = PaymentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        p_data = serializer.validated_data
        amount = p_data['amount']
        payment_date = p_data.get('payment_date') or timezone.now().date()
        payment_method = p_data.get('payment_method', 'cash')

        # Section 269ST Compliance: Daily cash repayment ceiling of ₹1,99,999 per customer
        if str(payment_method).lower() == 'cash':
            same_day_cash = Payment.objects.filter(
                loan__customer=loan.customer,
                payment_date=payment_date,
                payment_method__iexact='cash'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            if same_day_cash + amount >= Decimal('200000.00'):
                max_allowed = max(Decimal('0.00'), Decimal('199999.00') - same_day_cash)
                return Response({
                    'error': (
                        f"Section 269ST Violation: Total daily cash repayments from a customer cannot reach or exceed ₹2,00,000. "
                        f"Today's existing cash repayments for {loan.customer.full_name}: ₹{same_day_cash:,.2f}. "
                        f"Maximum cash remaining for today: ₹{max_allowed:,.2f}. Please select UPI or Bank Transfer."
                    )
                }, status=status.HTTP_400_BAD_REQUEST)

        # Create payment
        payment = Payment.objects.create(
            loan=loan,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            reference_number=p_data.get('reference_number', ''),
            received_by=user,
            notes=p_data.get('notes', '')
        )

        # Check if loan is fully paid
        loan.refresh_from_db()
        if loan.remaining_balance <= Decimal('0.00'):
            loan.status = 'repaid'
            loan.save(update_fields=['status'])

        return Response({
            'message': f'Payment of ₹{amount:,.2f} recorded successfully.',
            'payment': PaymentSerializer(payment).data,
            'loan_remaining_balance': str(loan.remaining_balance),
            'loan_status': loan.status,
        }, status=status.HTTP_201_CREATED)


class PaymentListAPIView(APIView):
    """
    GET /api/v1/payments/
    Lists payments with date, branch, and customer filters.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="List Repayments",
        description="Retrieve payment transactions with filtering by loan number, date, or branch.",
        responses={200: PaymentSerializer(many=True)},
        parameters=[
            OpenApiParameter(name='loan_number', description='Filter by Loan Number', required=False, type=OpenApiTypes.STR),
            OpenApiParameter(name='date', description='Filter by Date (YYYY-MM-DD)', required=False, type=OpenApiTypes.STR),
            OpenApiParameter(name='page', description='Page number', required=False, type=OpenApiTypes.INT),
            OpenApiParameter(name='page_size', description='Items per page', required=False, type=OpenApiTypes.INT),
        ],
        tags=["Repayments & Cash"]
    )
    def get(self, request):
        user = request.user
        queryset = Payment.objects.select_related('loan__customer', 'loan__branch', 'received_by').order_by('-payment_date', '-created_at')

        if hasattr(user, 'organization') and user.organization:
            queryset = queryset.filter(loan__branch__organization=user.organization)
        elif not user.is_superuser and not user.is_regional_manager and user.branch:
            queryset = queryset.filter(loan__branch=user.branch)

        # Filter by loan
        loan_number = request.query_params.get('loan_number')
        if loan_number:
            queryset = queryset.filter(loan__loan_number=loan_number)

        # Filter by date
        date_param = request.query_params.get('date')
        if date_param:
            try:
                target_date = datetime.date.fromisoformat(date_param)
                queryset = queryset.filter(payment_date=target_date)
            except ValueError:
                pass

        # Pagination
        try:
            page = max(1, int(request.query_params.get('page', 1)))
            page_size = min(100, max(1, int(request.query_params.get('page_size', 20))))
        except ValueError:
            page, page_size = 1, 20

        total_count = queryset.count()
        start = (page - 1) * page_size
        results = queryset[start:start + page_size]

        serializer = PaymentSerializer(results, many=True)
        return Response({
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'results': serializer.data
        }, status=status.HTTP_200_OK)
