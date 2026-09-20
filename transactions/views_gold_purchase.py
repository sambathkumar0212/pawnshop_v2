from decimal import Decimal, ROUND_HALF_UP
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from django.db.models import Sum, Q, Count
from django.conf import settings
import os
import re
import subprocess
import tempfile
import shutil

from accounts.mixins import RoleBranchAccessMixin
from accounts.models import Customer
from branches.models import Branch
from schemes.models import DailyGoldRate
from inventory.models import Item, Category
from accounting.services import post_gold_purchase_journal
from transactions.views import amount_to_english_words, number_to_tamil_words
from .models import GoldPurchase, GoldPurchaseItem, Payment

try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None


class GoldPurchaseListView(LoginRequiredMixin, RoleBranchAccessMixin, ListView):
    """
    List view for all Outright Used / Old Gold Purchase transactions.
    """
    model = GoldPurchase
    template_name = 'transactions/gold_purchase_list.html'
    context_object_name = 'purchases'
    paginate_by = 25

    def get_queryset(self):
        qs = GoldPurchase.objects.select_related('customer', 'branch', 'purchased_by').prefetch_related('items')
        
        # Enforce branch access
        user = self.request.user
        if not (user.is_superuser or getattr(user, 'is_organization_admin', False)):
            if user.branch:
                qs = qs.filter(branch=user.branch)
            elif hasattr(user, 'organization') and user.organization:
                qs = qs.filter(branch__organization=user.organization)

        # Filters
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(purchase_number__icontains=search) |
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search) |
                Q(customer__phone_number__icontains=search) |
                Q(reference_number__icontains=search)
            )

        branch_id = self.request.GET.get('branch')
        if branch_id:
            qs = qs.filter(branch_id=branch_id)

        pay_method = self.request.GET.get('payment_method')
        if pay_method:
            qs = qs.filter(payment_method=pay_method)

        date_from = self.request.GET.get('date_from')
        if date_from:
            qs = qs.filter(purchase_date__gte=date_from)

        date_to = self.request.GET.get('date_to')
        if date_to:
            qs = qs.filter(purchase_date__lte=date_to)

        return qs.order_by('-purchase_date', '-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_qs = self.get_queryset()

        totals = base_qs.aggregate(
            total_amount=Sum('net_payable_amount'),
            total_net_wt=Sum('total_net_weight'),
            total_gross_wt=Sum('total_gross_weight'),
            total_count=Count('id')
        )
        context['summary_total_amount'] = totals['total_amount'] or Decimal('0.00')
        context['summary_total_net_wt'] = totals['total_net_wt'] or Decimal('0.000')
        context['summary_total_gross_wt'] = totals['total_gross_wt'] or Decimal('0.000')
        context['summary_total_count'] = totals['total_count'] or 0

        # Today's stats
        today = timezone.now().date()
        today_totals = base_qs.filter(purchase_date=today).aggregate(
            today_amount=Sum('net_payable_amount'),
            today_count=Count('id')
        )
        context['today_amount'] = today_totals['today_amount'] or Decimal('0.00')
        context['today_count'] = today_totals['today_count'] or 0

        context['branches'] = Branch.objects.filter(is_active=True)
        context['selected_branch'] = self.request.GET.get('branch', '')
        context['selected_payment_method'] = self.request.GET.get('payment_method', '')
        context['search_query'] = self.request.GET.get('search', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        return context


class GoldPurchaseCreateView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    """
    Interactive Live Gold Buying Workflow with multi-item calculator,
    daily market rate integration, Section 269ST compliance, and auto inventory/accounting.
    """
    template_name = 'transactions/gold_purchase_form.html'

    def _get_form_context(self, request, extra=None):
        user = request.user
        branch = user.branch
        if not branch and hasattr(user, 'organization') and user.organization:
            branch = Branch.objects.filter(organization=user.organization, is_active=True).first()
        if not branch and user.is_superuser:
            branch = Branch.objects.filter(is_active=True).first()

        rate_obj = DailyGoldRate.objects.order_by('-date', '-id').first()
        rate_24k = Decimal(str(rate_obj.rate_24k_per_gram)) if rate_obj else Decimal('7200.00')
        rate_22k = Decimal(str(rate_obj.rate_22k_per_gram)) if rate_obj else Decimal('6600.00')
        rate_20k = Decimal(str(rate_obj.rate_20k_per_gram)) if rate_obj else Decimal('6000.00')
        rate_18k = Decimal(str(rate_obj.rate_18k_per_gram)) if rate_obj else Decimal('5400.00')
        rate_14k = (rate_24k * Decimal('0.585')).quantize(Decimal('1.00'))

        customers = Customer.objects.all().order_by('first_name', 'last_name')[:200]
        branches = Branch.objects.filter(is_active=True)

        context = {
            'branch': branch,
            'branches': branches,
            'customers': customers,
            'today_date': timezone.now().date(),
            'rate_24k': rate_24k,
            'rate_22k': rate_22k,
            'rate_20k': rate_20k,
            'rate_18k': rate_18k,
            'rate_14k': rate_14k,
            'rate_obj': rate_obj,
            'id_proof_choices': GoldPurchase.ID_PROOF_CHOICES,
            'payment_method_choices': GoldPurchase.PAYMENT_METHOD_CHOICES,
            'purity_choices': GoldPurchaseItem.PURITY_CHOICES,
        }
        if extra:
            context.update(extra)
        return context

    def get(self, request):
        return render(request, self.template_name, self._get_form_context(request))

    def post(self, request):
        user = request.user
        branch_id = request.POST.get('branch')
        if branch_id:
            branch = get_object_or_404(Branch, id=branch_id)
        else:
            branch = user.branch or Branch.objects.filter(is_active=True).first()

        customer_id = request.POST.get('customer', '').strip()
        customer_name = request.POST.get('customer_name', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        customer_address = request.POST.get('customer_address', '').strip()
        raw_purchase_date = request.POST.get('purchase_date')
        if raw_purchase_date:
            try:
                from datetime import datetime
                purchase_date = datetime.strptime(str(raw_purchase_date), '%Y-%m-%d').date()
            except Exception:
                purchase_date = timezone.now().date()
        else:
            purchase_date = timezone.now().date()
        payment_method = request.POST.get('payment_method', 'cash')
        reference_number = request.POST.get('reference_number', '').strip()
        id_proof_type = request.POST.get('id_proof_type', 'aadhaar')
        id_proof_number = request.POST.get('id_proof_number', '').strip()
        notes = request.POST.get('notes', '').strip()
        items_json = request.POST.get('items_json', '[]')
        other_deductions_raw = request.POST.get('other_deductions', '0.00') or '0.00'
        customer_photo = request.POST.get('customer_photo', '').strip()
        kyc_document_file = request.FILES.get('kyc_document')
        kyc_document_data = request.POST.get('kyc_document_data', '').strip()
        item_photos = request.POST.get('item_photos', '[]').strip()

        # State payload for preserving on error
        submitted_state = {
            'submitted_customer_id': int(customer_id) if customer_id and customer_id.isdigit() else '',
            'submitted_customer_name': customer_name,
            'submitted_customer_phone': customer_phone,
            'submitted_customer_address': customer_address,
            'submitted_branch_id': int(branch_id) if branch_id and str(branch_id).isdigit() else (branch.id if branch else ''),
            'submitted_purchase_date': purchase_date,
            'submitted_payment_method': payment_method,
            'submitted_reference_number': reference_number,
            'submitted_id_proof_type': id_proof_type,
            'submitted_id_proof_number': id_proof_number,
            'submitted_notes': notes,
            'submitted_other_deductions': other_deductions_raw,
            'submitted_items_json': items_json,
            'submitted_customer_photo': customer_photo,
            'submitted_kyc_data': kyc_document_data,
            'submitted_item_photos': item_photos,
        }

        # Resolve or auto-create Customer
        customer = None
        if customer_id and customer_id.isdigit():
            customer = Customer.objects.filter(id=int(customer_id)).first()

        if not customer and customer_phone:
            customer = Customer.objects.filter(branch=branch, phone=customer_phone).first() or Customer.objects.filter(phone=customer_phone).first()

        if not customer and customer_name:
            # Split into first and last name
            name_parts = customer_name.strip().split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            # Map ID Proof Type
            mapped_id_type = 'aadhar_card' if id_proof_type == 'aadhaar' else ('pan_card' if id_proof_type == 'pan' else id_proof_type)

            customer = Customer.objects.create(
                first_name=first_name,
                last_name=last_name or '.',
                phone=customer_phone or '0000000000',
                address=customer_address,
                branch=branch,
                id_type=mapped_id_type,
                id_number=id_proof_number or '',
                profile_photo=customer_photo if customer_photo else None,
                created_by=request.user if hasattr(Customer, 'created_by') else None
            )
        elif customer and customer_address and not customer.address:
            customer.address = customer_address
            customer.save(update_fields=['address'])

        if not customer:
            messages.error(request, 'Please enter a valid Customer Name.')
            return render(request, self.template_name, self._get_form_context(request, submitted_state))

        # Parse JSON items payload
        try:
            items_data = json.loads(items_json)
        except Exception:
            items_data = []

        if not items_data:
            messages.error(request, 'Please add at least one gold item to purchase.')
            return render(request, self.template_name, self._get_form_context(request, submitted_state))

        # Calculate totals
        total_gross = Decimal('0.000')
        total_stone = Decimal('0.000')
        total_net = Decimal('0.000')
        total_payable_wt = Decimal('0.000')
        total_fine_wt = Decimal('0.000')
        subtotal_val = Decimal('0.00')

        parsed_items = []
        for raw in items_data:
            name = (raw.get('item_name') or 'Gold Ornament').strip()
            karat = raw.get('purity_karat', '22K')
            purity_pct = Decimal(str(raw.get('purity_percentage', '91.60')))
            gross = Decimal(str(raw.get('gross_weight', '0.000')))
            stone = Decimal(str(raw.get('stone_weight', '0.000')))
            net = max(Decimal('0.000'), gross - stone)
            loss_pct = Decimal(str(raw.get('melting_loss_percentage', '0.00')))
            payable_wt = (net * (Decimal('100.00') - loss_pct) / Decimal('100.00')).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            rate = Decimal(str(raw.get('rate_per_gram', '0.00')))
            val = (payable_wt * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            fine_wt = (payable_wt * purity_pct / Decimal('100.00')).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

            total_gross += gross
            total_stone += stone
            total_net += net
            total_payable_wt += payable_wt
            total_fine_wt += fine_wt
            subtotal_val += val

            parsed_items.append({
                'name': name,
                'karat': karat,
                'purity_pct': purity_pct,
                'gross': gross,
                'stone': stone,
                'net': net,
                'loss_pct': loss_pct,
                'payable_wt': payable_wt,
                'rate': rate,
                'val': val,
            })

        other_deductions = Decimal(str(other_deductions_raw))
        net_payable = max(Decimal('0.00'), subtotal_val - other_deductions)

        # Section 269ST Cash Compliance check
        if payment_method.lower() == 'cash':
            same_day_cash = Payment.objects.filter(
                loan__customer=customer,
                payment_date=purchase_date,
                payment_method__iexact='cash'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            same_day_purchases = GoldPurchase.objects.filter(
                customer=customer,
                purchase_date=purchase_date,
                payment_method__iexact='cash'
            ).aggregate(total=Sum('net_payable_amount'))['total'] or Decimal('0.00')

            total_customer_cash_today = same_day_cash + same_day_purchases + net_payable
            if total_customer_cash_today >= Decimal('200000.00'):
                max_cash_left = max(Decimal('0.00'), Decimal('199999.00') - (same_day_cash + same_day_purchases))
                messages.error(
                    request,
                    f"Section 269ST Violation: Total daily cash transactions with customer {customer.full_name} cannot reach or exceed ₹2,00,000. "
                    f"Maximum cash remaining for today is ₹{max_cash_left:,.2f}. Please select Bank Transfer, UPI, or Cheque."
                )
                return render(request, self.template_name, self._get_form_context(request, submitted_state))

        try:
            with transaction.atomic():
                purchase_no = GoldPurchase.generate_purchase_number(branch)
                gold_purchase = GoldPurchase.objects.create(
                    purchase_number=purchase_no,
                    branch=branch,
                    customer=customer,
                    purchase_date=purchase_date,
                    total_gross_weight=total_gross,
                    total_stone_weight=total_stone,
                    total_net_weight=total_net,
                    total_payable_weight=total_payable_wt,
                    total_fine_gold_weight=total_fine_wt,
                    subtotal_amount=subtotal_val,
                    melting_deduction_amount=Decimal('0.00'),
                    other_deductions=other_deductions,
                    net_payable_amount=net_payable,
                    payment_method=payment_method,
                    reference_number=reference_number,
                    id_proof_type=id_proof_type,
                    id_proof_number=id_proof_number,
                    customer_photo=customer_photo or None,
                    kyc_document=kyc_document_file,
                    kyc_document_data=kyc_document_data or None,
                    item_photos=item_photos if item_photos != '[]' else None,
                    status='completed',
                    notes=notes,
                    purchased_by=user
                )

                # Sync customer profile photo and KYC image if not already set
                if customer_photo and not customer.profile_photo:
                    customer.profile_photo = customer_photo
                    customer.save(update_fields=['profile_photo'])
                if kyc_document_file and not customer.id_image:
                    customer.id_image = kyc_document_file
                    customer.save(update_fields=['id_image'])

                # Get or create a default category for purchased gold
                gold_category, _ = Category.objects.get_or_create(
                    name="Purchased Gold Ornaments",
                    defaults={'description': 'Outright purchased used gold jewelry & scrap'}
                )

                # Create items and stock in inventory
                for it in parsed_items:
                    # Create inventory item
                    item_code = f"BUY-{gold_purchase.id}-{parsed_items.index(it)+1:02d}"
                    inv_item = Item.objects.create(
                        item_id=item_code,
                        name=f"{it['name']} ({it['karat']} - {it['gross']}g)",
                        description=f"Purchased from {customer.full_name} under #{purchase_no}. Net wt: {it['net']}g, Purity: {it['karat']}.",
                        category=gold_category,
                        branch=branch,
                        condition='good',
                        purchase_price=it['val'],
                        appraised_value=it['val'],
                        sale_price=it['val'],
                        selling_price=it['val'],
                        status='available',
                        created_by=user
                    )

                    GoldPurchaseItem.objects.create(
                        purchase=gold_purchase,
                        item_name=it['name'],
                        purity_karat=it['karat'],
                        purity_percentage=it['purity_pct'],
                        gross_weight=it['gross'],
                        stone_weight=it['stone'],
                        net_weight=it['net'],
                        melting_loss_percentage=it['loss_pct'],
                        payable_net_weight=it['payable_wt'],
                        rate_per_gram=it['rate'],
                        item_total_value=it['val'],
                        inventory_item=inv_item
                    )

                # Post Double-Entry Accounting Journal
                try:
                    post_gold_purchase_journal(gold_purchase, user=user)
                except Exception as ex:
                    # Log error but don't fail transaction
                    print(f"Warning: Journal entry for Gold Purchase #{purchase_no} failed: {ex}")

            messages.success(request, f"Gold Purchase #{purchase_no} recorded successfully! Total paid: Rs. {net_payable:,.2f}")
            return redirect('gold_purchase_detail', pk=gold_purchase.pk)

        except Exception as e:
            messages.error(request, f"Error saving gold purchase: {str(e)}")
            return redirect('gold_purchase_create')


class GoldPurchaseDetailView(LoginRequiredMixin, RoleBranchAccessMixin, DetailView):
    """
    Detail view for a Gold Purchase transaction.
    """
    model = GoldPurchase
    template_name = 'transactions/gold_purchase_detail.html'
    context_object_name = 'purchase'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        purchase = self.object
        context['items'] = purchase.items.select_related('inventory_item').all()
        context['amount_in_words'] = amount_to_english_words(purchase.net_payable_amount)
        context['amount_in_words_tamil'] = number_to_tamil_words(purchase.net_payable_amount)

        item_photos = []
        if purchase.item_photos:
            try:
                item_photos = json.loads(purchase.item_photos)
            except Exception:
                item_photos = []
        context['item_photos_list'] = item_photos
        return context


class GoldPurchaseDeleteView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    """
    Deletes or voids a Used Gold Purchase voucher, reverting associated inventory items and journal entries.
    """
    def get(self, request, pk):
        purchase = get_object_or_404(GoldPurchase, pk=pk)
        return render(request, 'transactions/gold_purchase_confirm_delete.html', {
            'purchase': purchase,
            'next_url': request.GET.get('next', '')
        })

    def post(self, request, pk):
        purchase = get_object_or_404(GoldPurchase, pk=pk)
        purchase_no = purchase.purchase_number
        cust_id = purchase.customer.id if purchase.customer else None
        next_destination = request.POST.get('next', request.GET.get('next', ''))

        with transaction.atomic():
            # 1. Delete associated inventory items created during purchase
            for itm in purchase.items.all():
                if itm.inventory_item:
                    try:
                        itm.inventory_item.delete()
                    except Exception:
                        pass
            try:
                Item.objects.filter(item_id__startswith=f"BUY-{purchase.id}-").delete()
            except Exception:
                pass

            # 2. Delete associated double-entry journal entries
            try:
                from accounting.models import JournalEntry
                JournalEntry.objects.filter(reference_id=f"BUY-{purchase.id}").delete()
            except Exception:
                pass

            # 3. Delete GoldPurchase record (cascades to GoldPurchaseItem)
            purchase.delete()

        messages.success(request, f"Used Gold Purchase #{purchase_no} has been deleted successfully.")
        
        if next_destination == 'customer' and cust_id:
            return redirect('customer_detail', pk=cust_id)
        return redirect('gold_purchase_list')


class GoldPurchaseReceiptPDFView(LoginRequiredMixin, View):
    """
    Generates printable PDF receipt / Purchase Voucher for a Gold Purchase transaction.
    """
    def get(self, request, pk):
        purchase = get_object_or_404(GoldPurchase, pk=pk)
        branch = purchase.branch

        from transactions.views import get_branch_bill_details, get_branch_bill_header_phones
        bill_details = get_branch_bill_details(branch)

        amount_in_words = amount_to_english_words(purchase.net_payable_amount)
        amount_in_words_tamil = number_to_tamil_words(purchase.net_payable_amount)

        customer_name_display = ""
        if purchase.customer:
            customer_name_display = f"{purchase.customer.first_name or ''} {purchase.customer.last_name or ''}".strip()
            if not customer_name_display and hasattr(purchase.customer, 'full_name'):
                customer_name_display = str(purchase.customer.full_name or '')

        # Prepare Customer Photo
        customer_photo = None
        raw_cust_photo = purchase.customer_photo or (purchase.customer.profile_photo if purchase.customer else None)
        if raw_cust_photo:
            if raw_cust_photo.startswith('data:image/'):
                customer_photo = raw_cust_photo.split(',')[1]
            else:
                customer_photo = raw_cust_photo

        # Prepare KYC Document Photo
        kyc_document_photo = None
        raw_kyc = purchase.kyc_document_data
        if not raw_kyc and purchase.kyc_document:
            try:
                import base64
                with open(purchase.kyc_document.path, 'rb') as img_f:
                    raw_kyc = base64.b64encode(img_f.read()).decode('utf-8')
            except Exception:
                raw_kyc = None
        if not raw_kyc and purchase.customer and purchase.customer.id_image:
            try:
                import base64
                with open(purchase.customer.id_image.path, 'rb') as img_f:
                    raw_kyc = base64.b64encode(img_f.read()).decode('utf-8')
            except Exception:
                raw_kyc = None

        if raw_kyc:
            if raw_kyc.startswith('data:image/'):
                kyc_document_photo = raw_kyc.split(',')[1]
            else:
                kyc_document_photo = raw_kyc

        # Prepare Item Photos
        item_photos = []
        if purchase.item_photos:
            try:
                raw_items = json.loads(purchase.item_photos)
                for itm in raw_items:
                    if itm.startswith('data:image/'):
                        item_photos.append(itm.split(',')[1])
                    else:
                        item_photos.append(itm)
            except Exception:
                item_photos = []

        # Prepare item list with Tamil translations
        PAYMENT_METHOD_TAMIL = {
            'cash': 'ரொக்கம் (Cash)',
            'bank_transfer': 'வங்கி பரிமாற்றம் (Bank Transfer)',
            'upi': 'யுபிஐ / டிஜிட்டல் (UPI / GPay / PhonePe)',
            'cheque': 'காசோலை (Cheque)',
        }
        payment_method_display_tamil = PAYMENT_METHOD_TAMIL.get(purchase.payment_method, purchase.get_payment_method_display())

        def _get_ornament_tamil(name):
            if not name:
                return ''
            ln = name.lower()
            if 'chain' in ln and 'dollar' in ln:
                return 'டாலர் சங்கிலி'
            elif 'chain' in ln:
                return 'தங்க சங்கிலி'
            elif 'ring' in ln or 'mothiram' in ln:
                return 'மோதிரம்'
            elif 'bangle' in ln or 'valai' in ln:
                return 'வளையல்'
            elif 'necklace' in ln or 'malai' in ln or 'haram' in ln:
                return 'நெக்லஸ் / மாலை'
            elif 'earring' in ln or 'jimikki' in ln:
                return 'ஜிமிக்கி / கம்மல்'
            elif 'stud' in ln or 'thodu' in ln:
                return 'தோடு'
            elif 'thali' in ln or 'mangalsutra' in ln or 'kodi' in ln:
                return 'தாலி / மாங்கல்யம்'
            elif 'coin' in ln or 'kasoo' in ln:
                return 'தங்கக் காசு'
            elif 'bracelet' in ln or 'kappu' in ln:
                return 'பிரேஸ்லெட் / காப்பு'
            elif 'anklet' in ln or 'kolusu' in ln:
                return 'கொலுசு'
            elif 'toe' in ln or 'metti' in ln:
                return 'மெட்டி'
            elif 'scrap' in ln or 'melt' in ln or 'bit' in ln or 'bar' in ln:
                return 'உருக்கு / பழைய தங்கம்'
            return ''

        items_list = list(purchase.items.all())
        for it in items_list:
            it.tamil_name = _get_ornament_tamil(it.item_name)

        context = {
            'purchase': purchase,
            'purchase_date_display': purchase.purchase_date.strftime('%d-%b-%Y') if purchase.purchase_date else '',
            'items': items_list,
            'payment_method_display_tamil': payment_method_display_tamil,
            'customer_name_display': customer_name_display,
            'customer_photo': customer_photo,
            'kyc_document_photo': kyc_document_photo,
            'item_photos': item_photos,
            'amount_in_words': amount_in_words,
            'amount_in_words_tamil': amount_in_words_tamil,
            'branch_phone_display': get_branch_bill_header_phones(branch),
            'branch_address_display': bill_details.get('address', ''),
            'bill_shop_name': bill_details.get('shop_name', ''),
            'bill_address_display': bill_details.get('address', ''),
            'bill_phone_display': bill_details.get('phone', ''),
            'bill_email_display': bill_details.get('email', ''),
            'bill_logo_url': bill_details.get('logo_url', ''),
            'date_today': timezone.now(),
            'date_today_display': timezone.now().strftime('%d-%b-%Y %H:%M:%S'),
            'tamil_font_file_uri': f"file:///{str((settings.BASE_DIR / 'static' / 'fonts' / 'NotoSansTamil-Regular.ttf')).replace(os.sep, '/')}",
        }

        template = get_template('transactions/gold_purchase_receipt_pdf.html')
        html = template.render(context)

        # Construct filename: <Customer_Name>_<Voucher_Number>.pdf
        raw_cust_name = customer_name_display or (purchase.customer.full_name if purchase.customer else "") or "Customer"
        clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw_cust_name.strip()).strip('_')
        clean_name = re.sub(r'_+', '_', clean_name)
        clean_voucher = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(purchase.purchase_number).strip()).strip('_')
        
        pdf_filename = f"{clean_name}_{clean_voucher}.pdf" if clean_name else f"gold_purchase_voucher_{clean_voucher}.pdf"
        disposition = request.GET.get('disposition', 'attachment')

        # 1. Primary PDF Engine: Headless Chromium (Chrome/Edge) for pixel-perfect Tamil OpenType script shaping
        browser = self._find_browser_executable()
        if browser:
            tmp_dir = tempfile.mkdtemp(prefix='gp_pdf_')
            html_path = os.path.join(tmp_dir, 'gold_purchase_receipt.html')
            pdf_path = os.path.join(tmp_dir, 'gold_purchase_receipt.pdf')
            profile_dir = os.path.join(tmp_dir, 'profile')
            os.makedirs(profile_dir, exist_ok=True)
            try:
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html)

                cmd = [
                    browser,
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    f"--user-data-dir={profile_dir}",
                    "--allow-file-access-from-files",
                    "--disable-web-security",
                    "--print-to-pdf-no-header",
                    f"--print-to-pdf={pdf_path}",
                    f"file:///{html_path.replace(os.sep, '/')}",
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0 and os.path.exists(pdf_path):
                    with open(pdf_path, 'rb') as f:
                        pdf_bytes = f.read()
                    if pdf_bytes:
                        response = HttpResponse(pdf_bytes, content_type='application/pdf')
                        response['Content-Disposition'] = f'{disposition}; filename="{pdf_filename}"'
                        return response
            except Exception as e:
                print(f"Browser PDF generation failed for Gold Purchase, falling back to xhtml2pdf: {e}")
            finally:
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                except Exception:
                    pass

        # 2. Secondary Fallback: xhtml2pdf
        if pisa:
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'{disposition}; filename="{pdf_filename}"'

            try:
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                from xhtml2pdf.default import DEFAULT_FONT
                tamil_font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'NotoSansTamil-Regular.ttf')
                if os.path.exists(tamil_font_path):
                    pdfmetrics.registerFont(TTFont('NotoSansTamil', tamil_font_path))
                    DEFAULT_FONT['notosanstamil'] = 'NotoSansTamil'
                    DEFAULT_FONT['notosans-tamil'] = 'NotoSansTamil'
                    DEFAULT_FONT['tamil'] = 'NotoSansTamil'
            except Exception:
                pass

            def link_callback(uri, rel):
                if uri.startswith(settings.MEDIA_URL):
                    path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
                elif uri.startswith(settings.STATIC_URL):
                    path = os.path.join(settings.STATIC_ROOT or (settings.BASE_DIR / 'static'), uri.replace(settings.STATIC_URL, ""))
                else:
                    path = uri
                return path

            pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
            if not pisa_status.err:
                return response

        # 3. Final Fallback to HTML
        return HttpResponse(html)

    def _find_browser_executable(self):
        """Find an installed Chromium-based browser executable (Chrome or Edge)."""
        candidates = [
            shutil.which('chrome'),
            shutil.which('msedge'),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate
        return None
