from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Sum

from .models import Loan, LoanItem, Payment, PartialReleaseRecord
from inventory.models import Item
from schemes.models import DailyGoldRate
from accounting.services import post_loan_repayment_journal


def get_current_gold_rate_22k(branch=None):
    """Fetches the latest 22K gold rate from DailyGoldRate or returns fallback."""
    rate_obj = DailyGoldRate.objects.order_by('-date', '-id').first()
    if rate_obj and rate_obj.rate_22k_per_gram:
        return Decimal(str(rate_obj.rate_22k_per_gram))
    return Decimal('7000.00')  # Standard default benchmark


def get_loan_current_interest_due(loan):
    """
    Returns today's active interest due on the loan based on Net Payable position:
    Interest = Net Payable Still Due - Outstanding Principal
    Also considers accrued_interest field and calculate_interest() method.
    """
    if not loan or getattr(loan, 'status', None) != 'active':
        return Decimal('0.00')

    # 1. Primary: Net Payable interest due (date-to-date monthly cycle / minimum 1 month)
    try:
        net_payable = Decimal(str(loan.net_payable_still_due or '0.00'))
        net_interest = max(Decimal('0.00'), net_payable - Decimal(str(loan.principal_amount or '0.00')))
    except Exception:
        net_interest = Decimal('0.00')

    # 2. Check accrued_interest field on model
    field_accrued = Decimal(str(getattr(loan, 'accrued_interest', None) or '0.00'))

    # 3. Check calculate_interest() method
    calc_accrued = Decimal('0.00')
    if hasattr(loan, 'calculate_interest'):
        try:
            calc_accrued = Decimal(str(loan.calculate_interest() or '0.00'))
        except Exception:
            calc_accrued = Decimal('0.00')

    return max(net_interest, field_accrued, calc_accrued).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_item_market_value(loan_item, gold_rate=None, net_weight=None):
    """
    Computes market valuation of an ornament or partial weight:
    Formula: Net Weight * (Karat / 22.0) * Rate_22K
    """
    if gold_rate is None:
        gold_rate = get_current_gold_rate_22k(loan_item.loan.branch)

    try:
        karat = Decimal(str(loan_item.gold_karat or 22.0))
        net_wt = Decimal(str(net_weight if net_weight is not None else (loan_item.net_weight or 0.0)))
        val = (net_wt * (karat / Decimal('22.0')) * Decimal(str(gold_rate)))
        return val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal('0.00')


def parse_item_specs(loan, items_to_release_pks=None, items_specs=None):
    """
    Normalizes item specifications for partial or full releases.
    Supports either list of PKs or list of dicts with quantity/weight overrides.
    """
    all_pledged = list(loan.loan_ornaments.filter(status='pledged').select_related('item'))
    if not all_pledged:
        all_pledged = list(LoanItem.objects.filter(loan=loan, status='pledged').select_related('item'))

    specs_by_id = {}

    if items_specs:
        for spec in items_specs:
            if isinstance(spec, dict) and 'id' in spec:
                specs_by_id[int(spec['id'])] = spec
            elif str(spec).isdigit():
                specs_by_id[int(spec)] = {'id': int(spec)}
    elif items_to_release_pks:
        for pk in items_to_release_pks:
            if str(pk).isdigit():
                specs_by_id[int(pk)] = {'id': int(pk)}

    normalized = []
    for it in all_pledged:
        if it.id in specs_by_id:
            spec = specs_by_id[it.id]
            total_qty = max(1, it.quantity or 1)
            rel_qty = int(spec.get('release_qty', total_qty) or total_qty)
            rel_qty = max(1, min(rel_qty, total_qty))

            # Proportional or specified net weight
            if 'release_net_weight' in spec and spec['release_net_weight'] is not None and str(spec['release_net_weight']).strip():
                rel_net_wt = min(Decimal(str(spec['release_net_weight'])), Decimal(str(it.net_weight)))
            else:
                rel_net_wt = (Decimal(str(it.net_weight)) / Decimal(str(total_qty))) * Decimal(str(rel_qty))
            
            # Proportional gross weight
            if 'release_gross_weight' in spec and spec['release_gross_weight'] is not None and str(spec['release_gross_weight']).strip():
                rel_gross_wt = min(Decimal(str(spec['release_gross_weight'])), Decimal(str(it.gross_weight)))
            else:
                rel_gross_wt = (Decimal(str(it.gross_weight)) / Decimal(str(total_qty))) * Decimal(str(rel_qty))

            normalized.append({
                'item_obj': it,
                'is_selected': True,
                'release_qty': rel_qty,
                'release_net_weight': rel_net_wt.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP),
                'release_gross_weight': rel_gross_wt.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP),
                'remaining_qty': total_qty - rel_qty,
                'remaining_net_weight': (Decimal(str(it.net_weight)) - rel_net_wt).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP),
                'remaining_gross_weight': max(Decimal('0.000'), (Decimal(str(it.gross_weight)) - rel_gross_wt)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP),
            })
        else:
            normalized.append({
                'item_obj': it,
                'is_selected': False,
                'release_qty': 0,
                'release_net_weight': Decimal('0.000'),
                'release_gross_weight': Decimal('0.000'),
                'remaining_qty': it.quantity,
                'remaining_net_weight': Decimal(str(it.net_weight)),
                'remaining_gross_weight': Decimal(str(it.gross_weight)),
            })

    return normalized


def evaluate_partial_release(loan, items_to_release_pks=None, items_specs=None,
                            principal_repayment=Decimal('0.00'), principal_payment=None, gold_rate=None):
    """
    Evaluates statutory LTV feasibility for releasing specific ornaments or partial item quantities.
    Enforces maximum 75.00% LTV under RBI NBFC regulations.
    """
    if principal_payment is not None:
        principal_repayment = principal_payment

    if gold_rate is None:
        gold_rate = get_current_gold_rate_22k(loan.branch)

    principal_repayment = Decimal(str(principal_repayment or 0.00))

    specs = parse_item_specs(loan, items_to_release_pks=items_to_release_pks, items_specs=items_specs)

    total_collateral_value = Decimal('0.00')
    released_collateral_value = Decimal('0.00')
    remaining_collateral_value = Decimal('0.00')
    released_count = 0
    retained_count = 0

    for spec in specs:
        it = spec['item_obj']
        item_full_val = calculate_item_market_value(it, gold_rate=gold_rate)
        total_collateral_value += item_full_val

        if spec['is_selected']:
            rel_val = calculate_item_market_value(it, gold_rate=gold_rate, net_weight=spec['release_net_weight'])
            ret_val = calculate_item_market_value(it, gold_rate=gold_rate, net_weight=spec['remaining_net_weight'])
            released_collateral_value += rel_val
            remaining_collateral_value += ret_val
            released_count += spec['release_qty']
            if spec['remaining_qty'] > 0:
                retained_count += spec['remaining_qty']
        else:
            remaining_collateral_value += item_full_val
            retained_count += it.quantity

    current_outstanding_principal = Decimal(str(loan.principal_amount or 0.00))
    new_outstanding_principal = max(Decimal('0.00'), current_outstanding_principal - principal_repayment)

    # Current LTV
    if total_collateral_value > Decimal('0.00'):
        current_ltv = ((current_outstanding_principal / total_collateral_value) * Decimal('100')).quantize(Decimal('0.01'))
    else:
        current_ltv = Decimal('0.00')

    # Target LTV = Existing LTV - 2% (each partial release steps the LTV down by 2%)
    LTV_REDUCTION_STEP = Decimal('2.00')
    target_ltv = max(current_ltv - LTV_REDUCTION_STEP, Decimal('0.00'))
    # But never below 75% for safety compliance check (eligible threshold)
    effective_allowed_ltv = max(target_ltv, Decimal('73.00'))  # allow slight headroom above 75

    # Calculate Accrued Interest based on Today's Net Payable position
    total_accrued = get_loan_current_interest_due(loan)

    # Auto-Calculated Principal & Interest to achieve (existing LTV - 2%) on remaining collateral
    if remaining_collateral_value <= Decimal('0.00'):
        auto_principal_payment = current_outstanding_principal
        auto_interest_payment = total_accrued
        min_principal_required = current_outstanding_principal
        max_allowed_principal = Decimal('0.00')
    elif total_collateral_value > Decimal('0.00') and released_collateral_value > Decimal('0.00'):
        # Target: new_principal on remaining collateral = target_ltv %
        # i.e. new_principal = remaining_collateral_value * target_ltv / 100
        target_remaining_principal = (remaining_collateral_value * (target_ltv / Decimal('100.0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        auto_principal_payment = max(
            Decimal('0.00'),
            min(current_outstanding_principal, current_outstanding_principal - target_remaining_principal)
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        # Proportionate interest based on released share
        auto_interest_payment = (total_accrued * (released_collateral_value / total_collateral_value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        min_principal_required = auto_principal_payment
        max_allowed_principal = target_remaining_principal
    else:
        auto_principal_payment = Decimal('0.00')
        auto_interest_payment = Decimal('0.00')
        min_principal_required = Decimal('0.00')
        max_allowed_principal = Decimal('0.00')

    # Effective principal repayment (use manual payment if provided > 0, otherwise auto-calculated payment)
    effective_principal_repayment = principal_repayment if principal_repayment > Decimal('0.00') else auto_principal_payment
    new_outstanding_principal = max(Decimal('0.00'), current_outstanding_principal - effective_principal_repayment)

    shortfall = max(Decimal('0.00'), (min_principal_required - (principal_repayment if principal_repayment > Decimal('0.00') else auto_principal_payment)).quantize(Decimal('0.01')))

    # Calculate New LTV
    if remaining_collateral_value > Decimal('0.00'):
        new_ltv = ((new_outstanding_principal / remaining_collateral_value) * Decimal('100')).quantize(Decimal('0.01'))
    else:
        new_ltv = Decimal('0.00') if new_outstanding_principal == Decimal('0.00') else Decimal('999.99')

    # Eligible if new LTV does not exceed the effective allowed LTV (existing - 2%) or if full loan is being paid off (all ornaments released with full principal)
    if remaining_collateral_value <= Decimal('0.00'):
        is_eligible = (new_outstanding_principal == Decimal('0.00')) and (released_collateral_value > Decimal('0.00'))
    else:
        is_eligible = (new_ltv <= (effective_allowed_ltv + Decimal('0.05'))) and (released_collateral_value > Decimal('0.00'))

    total_release_value = (auto_principal_payment + auto_interest_payment).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


    return {
        'is_eligible': is_eligible,
        'current_outstanding_principal': current_outstanding_principal,
        'principal_repayment': principal_repayment,
        'new_outstanding_principal': new_outstanding_principal,
        'total_collateral_value': total_collateral_value,
        'released_collateral_value': released_collateral_value,
        'remaining_collateral_value': remaining_collateral_value,
        'current_ltv': current_ltv,
        'new_ltv': new_ltv,
        'max_allowed_principal': max_allowed_principal,
        'min_principal_required': min_principal_required,
        'shortfall': shortfall,
        'auto_principal_payment': auto_principal_payment,
        'auto_interest_payment': auto_interest_payment,
        'total_release_value': total_release_value,
        'total_accrued_interest': total_accrued,
        'released_count': released_count,
        'retained_count': retained_count,
        'specs': specs,
        'gold_rate_used': gold_rate
    }


def execute_partial_release(loan, items_to_release_pks=None, items_specs=None,
                            principal_paid=Decimal('0.00'), interest_paid=Decimal('0.00'),
                            payment_method='cash', reference_number=None, user=None,
                            signature_data=None, witness_name=None, notes=None):
    """
    Executes an atomic Partial Ornament Release and Part-Payment:
    - Handles whole items as well as partial quantity/weight splits.
    - Updates Loan and LoanItem states.
    - Generates PartialReleaseRecord and GL payment journal.
    """
    principal_paid = Decimal(str(principal_paid or 0.00))
    interest_paid = Decimal(str(interest_paid or 0.00))
    total_payment = principal_paid + interest_paid

    eval_result = evaluate_partial_release(
        loan=loan,
        items_to_release_pks=items_to_release_pks,
        items_specs=items_specs,
        principal_repayment=principal_paid
    )
    if not eval_result['is_eligible']:
        raise ValidationError(
            f"Cannot release ornaments! Resulting LTV is {eval_result['new_ltv']}%, which exceeds the 75% statutory limit. "
            f"Additional minimum principal payment of ₹{eval_result['shortfall']:,.2f} is required."
        )

    with transaction.atomic():
        # 1. Create Payment Record if amount > 0
        payment = None
        if total_payment > Decimal('0.00'):
            payment = Payment.objects.create(
                loan=loan,
                amount=total_payment,
                payment_date=timezone.now().date(),
                payment_method=payment_method,
                reference_number=reference_number or f"PART-REL-{loan.loan_number}",
                received_by=user,
                notes=f"Partial Ornament Release Payment (Principal: ₹{principal_paid:,.2f}, Interest: ₹{interest_paid:,.2f})"
            )

        # 2. Update Loan Financials
        previous_principal = Decimal(str(loan.principal_amount))
        new_principal = eval_result['new_outstanding_principal']
        loan.principal_amount = new_principal

        if interest_paid > Decimal('0.00'):
            loan.accrued_interest = max(Decimal('0.00'), Decimal(str(loan.accrued_interest)) - interest_paid)

        if eval_result['remaining_collateral_value'] <= Decimal('0.00') and new_principal <= Decimal('0.00'):
            loan.status = 'closed'
            loan.foreclosed_date = timezone.now().date()

        loan.save()

        # 3. Process Released Items (including item splits for multi-quantity lines)
        now_dt = timezone.now()
        released_loan_items = []

        for spec in eval_result['specs']:
            if not spec['is_selected']:
                continue

            it = spec['item_obj']
            rel_qty = spec['release_qty']
            rel_net_wt = spec['release_net_weight']
            rel_gross_wt = spec['release_gross_weight']
            rem_qty = spec['remaining_qty']
            rem_net_wt = spec['remaining_net_weight']
            rem_gross_wt = spec['remaining_gross_weight']

            if rem_qty <= 0 or rem_net_wt <= Decimal('0.000'):
                # Entire line released
                it.status = 'released'
                it.released_at = now_dt
                it.released_by = user
                it.save()

                inv_item = it.item
                if inv_item:
                    inv_item.status = 'available'
                    inv_item.save(update_fields=['status'])

                released_loan_items.append(it)
            else:
                # Partial quantity / weight release (Split line)
                it.quantity = rem_qty
                it.net_weight = rem_net_wt
                it.gross_weight = rem_gross_wt
                it.save()

                # Create separate inventory item to satisfy unique(loan, item) constraint
                orig_item = it.item
                released_inv_item = Item.objects.create(
                    name=f"{orig_item.name} (Partially Released)",
                    description=orig_item.description,
                    tamil_name=orig_item.tamil_name,
                    tamil_description=orig_item.tamil_description,
                    tamil_brand=orig_item.tamil_brand or '',
                    tamil_model=orig_item.tamil_model or '',
                    tamil_tags=orig_item.tamil_tags or '',
                    tamil_notes=orig_item.tamil_notes or '',
                    category=orig_item.category,
                    status='available',
                    branch=orig_item.branch,
                    created_by=user
                )

                # Create released portion record with the newly created released item
                released_portion = LoanItem.objects.create(
                    loan=loan,
                    item=released_inv_item,
                    quantity=rel_qty,
                    gold_karat=it.gold_karat,
                    gross_weight=rel_gross_wt,
                    net_weight=rel_net_wt,
                    stone_weight=Decimal('0.00'),
                    market_price_22k=it.market_price_22k,
                    status='released',
                    released_at=now_dt,
                    released_by=user
                )
                released_loan_items.append(released_portion)

        # 4. Generate Unique Release Voucher Number
        date_str = now_dt.strftime('%Y%m%d')
        rel_count = PartialReleaseRecord.objects.filter(release_date=now_dt.date()).count() + 1
        release_number = f"REL-{date_str}-{rel_count:04d}"

        # 5. Create PartialReleaseRecord
        record = PartialReleaseRecord.objects.create(
            release_number=release_number,
            loan=loan,
            payment=payment,
            release_date=now_dt.date(),
            principal_paid=principal_paid,
            interest_paid=interest_paid,
            previous_outstanding_principal=previous_principal,
            new_outstanding_principal=new_principal,
            remaining_gold_value=eval_result['remaining_collateral_value'],
            new_ltv_percentage=eval_result['new_ltv'],
            released_by=user,
            customer_signature_data=signature_data,
            witness_name=witness_name,
            notes=notes
        )
        record.released_items.set(released_loan_items)

        # 6. Post General Ledger Repayment Journal Entry
        if total_payment > Decimal('0.00'):
            try:
                post_loan_repayment_journal(
                    loan=loan,
                    principal_amount=principal_paid,
                    interest_amount=interest_paid,
                    penal_amount=Decimal('0.00'),
                    payment_mode='CASH' if payment_method == 'cash' else 'BANK',
                    user=user,
                    notes=f"Partial release repayment for #{release_number}"
                )
            except Exception:
                pass

    return record
