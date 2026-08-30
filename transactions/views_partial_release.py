import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.core.exceptions import ValidationError

from .models import Loan, LoanItem, PartialReleaseRecord
from .services_partial_release import (
    evaluate_partial_release,
    execute_partial_release,
    get_current_gold_rate_22k,
    calculate_item_market_value,
    get_loan_current_interest_due
)


class LoanPartialReleaseView(LoginRequiredMixin, View):
    """
    View for Partial Ornament Release workflow:
    - Select specific items or partial quantities/weights to release
    - Live statutory 75% LTV verification & shortfall calculation
    - Part-payment collection & customer acknowledgment
    """
    template_name = 'transactions/loan_partial_release.html'

    def get(self, request, loan_number):
        loan = get_object_or_404(Loan, loan_number=loan_number)
        gold_rate = get_current_gold_rate_22k(loan.branch)
        pledged_items = loan.loan_ornaments.filter(status='pledged').select_related('item')
        if not pledged_items:
            pledged_items = LoanItem.objects.filter(loan=loan, status='pledged').select_related('item')

        # Check for AJAX simulation request
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('simulate') == '1':
            selected_ids = request.GET.getlist('item_ids[]') or request.GET.getlist('item_ids')
            principal_payment_str = request.GET.get('principal_payment', None)
            principal_payment = Decimal(principal_payment_str) if principal_payment_str not in [None, ''] else None
            
            # Parse individual item specs if provided
            items_specs = []
            for item_id_str in selected_ids:
                if not str(item_id_str).isdigit():
                    continue
                item_id = int(item_id_str)
                qty_str = request.GET.get(f'release_qty_{item_id}', '')
                net_wt_str = request.GET.get(f'release_net_wt_{item_id}', '')
                spec = {'id': item_id}
                if qty_str and qty_str.isdigit():
                    spec['release_qty'] = int(qty_str)
                if net_wt_str:
                    try:
                        spec['release_net_weight'] = Decimal(net_wt_str)
                    except Exception:
                        pass
                items_specs.append(spec)

            eval_res = evaluate_partial_release(
                loan=loan,
                items_to_release_pks=selected_ids if not items_specs else None,
                items_specs=items_specs if items_specs else None,
                principal_repayment=principal_payment if principal_payment is not None else Decimal('0.00'),
                gold_rate=gold_rate
            )

            # If user hasn't explicitly entered a principal repayment, evaluate with auto_principal_payment
            if principal_payment is None or principal_payment == Decimal('0.00'):
                auto_eval = evaluate_partial_release(
                    loan=loan,
                    items_to_release_pks=selected_ids if not items_specs else None,
                    items_specs=items_specs if items_specs else None,
                    principal_repayment=eval_res['auto_principal_payment'],
                    gold_rate=gold_rate
                )
                new_ltv_to_report = float(auto_eval['new_ltv'])
                is_eligible_to_report = auto_eval['is_eligible']
                new_principal_to_report = float(auto_eval['new_outstanding_principal'])
            else:
                new_ltv_to_report = float(eval_res['new_ltv'])
                is_eligible_to_report = eval_res['is_eligible']
                new_principal_to_report = float(eval_res['new_outstanding_principal'])

            return JsonResponse({
                'is_eligible': is_eligible_to_report,
                'current_outstanding_principal': float(eval_res['current_outstanding_principal']),
                'principal_repayment': float(eval_res['principal_repayment']),
                'new_outstanding_principal': new_principal_to_report,
                'total_collateral_value': float(eval_res['total_collateral_value']),
                'released_collateral_value': float(eval_res['released_collateral_value']),
                'remaining_collateral_value': float(eval_res['remaining_collateral_value']),
                'current_ltv': float(eval_res['current_ltv']),
                'new_ltv': new_ltv_to_report,
                'max_allowed_principal': float(eval_res['max_allowed_principal']),
                'min_principal_required': float(eval_res['min_principal_required']),
                'shortfall': float(eval_res['shortfall']),
                'auto_principal_payment': float(eval_res['auto_principal_payment']),
                'auto_interest_payment': float(eval_res['auto_interest_payment']),
                'total_release_value': float(eval_res['total_release_value']),
                'total_accrued_interest': float(eval_res['total_accrued_interest']),
                'released_count': eval_res['released_count'],
                'retained_count': eval_res['retained_count'],
            })

        items_with_val = []
        for it in pledged_items:
            qty = max(1, it.quantity or 1)
            full_val = calculate_item_market_value(it, gold_rate)
            unit_net_wt = (Decimal(str(it.net_weight)) / Decimal(str(qty))).quantize(Decimal('0.001'))
            unit_gross_wt = (Decimal(str(it.gross_weight)) / Decimal(str(qty))).quantize(Decimal('0.001'))
            unit_val = (full_val / Decimal(str(qty))).quantize(Decimal('0.01'))
            
            items_with_val.append({
                'obj': it,
                'total_quantity': qty,
                'unit_net_weight': unit_net_wt,
                'unit_gross_weight': unit_gross_wt,
                'unit_valuation': unit_val,
                'current_valuation': full_val,
                'qty_range': list(range(1, qty + 1))
            })

        total_pledged_val = sum(x['current_valuation'] for x in items_with_val)
        existing_ltv = ((loan.principal_amount / total_pledged_val) * Decimal('100')).quantize(Decimal('0.01')) if total_pledged_val > 0 else Decimal('0.00')

        total_accrued = get_loan_current_interest_due(loan)
        total_net_payable = (loan.principal_amount + total_accrued).quantize(Decimal('0.01'))

        for item_dict in items_with_val:
            u_val = item_dict['unit_valuation']
            item_p = (loan.principal_amount * (u_val / total_pledged_val)).quantize(Decimal('0.01')) if total_pledged_val > 0 else Decimal('0.00')
            item_i = (total_accrued * (u_val / total_pledged_val)).quantize(Decimal('0.01')) if total_pledged_val > 0 else Decimal('0.00')
            item_dict['unit_release_principal'] = item_p
            item_dict['unit_release_interest'] = item_i
            item_dict['unit_release_value'] = item_p + item_i

        target_ltv = max(existing_ltv - Decimal('2.00'), Decimal('0.00')).quantize(Decimal('0.01'))

        context = {
            'loan': loan,
            'gold_rate': gold_rate,
            'items_with_val': items_with_val,
            'total_pledged_val': total_pledged_val,
            'existing_ltv': existing_ltv,
            'target_ltv': target_ltv,
            'total_accrued': total_accrued,
            'total_net_payable': total_net_payable,
        }
        return render(request, self.template_name, context)

    def post(self, request, loan_number):
        loan = get_object_or_404(Loan, loan_number=loan_number)
        item_ids = request.POST.getlist('item_ids')
        principal_paid = Decimal(request.POST.get('principal_paid', '0.00') or '0.00')
        interest_paid = Decimal(request.POST.get('interest_paid', '0.00') or '0.00')
        payment_method = request.POST.get('payment_method', 'cash')
        reference_number = request.POST.get('reference_number', '').strip()
        witness_name = request.POST.get('witness_name', '').strip()
        signature_data = request.POST.get('customer_signature_data', '').strip()
        notes = request.POST.get('notes', '').strip()

        if not item_ids:
            messages.error(request, "Please select at least one ornament to release.")
            return redirect('loan_partial_release', loan_number=loan.loan_number)

        # Build items_specs with quantity and weights
        items_specs = []
        for item_id_str in item_ids:
            if not str(item_id_str).isdigit():
                continue
            item_id = int(item_id_str)
            qty_str = request.POST.get(f'release_qty_{item_id}', '')
            net_wt_str = request.POST.get(f'release_net_wt_{item_id}', '')
            gross_wt_str = request.POST.get(f'release_gross_wt_{item_id}', '')

            spec = {'id': item_id}
            if qty_str and qty_str.isdigit():
                spec['release_qty'] = int(qty_str)
            if net_wt_str:
                try:
                    spec['release_net_weight'] = Decimal(net_wt_str)
                except Exception:
                    pass
            if gross_wt_str:
                try:
                    spec['release_gross_weight'] = Decimal(gross_wt_str)
                except Exception:
                    pass
            items_specs.append(spec)

        try:
            record = execute_partial_release(
                loan=loan,
                items_specs=items_specs,
                principal_paid=principal_paid,
                interest_paid=interest_paid,
                payment_method=payment_method,
                reference_number=reference_number,
                user=request.user,
                signature_data=signature_data,
                witness_name=witness_name,
                notes=notes
            )
            messages.success(
                request,
                f"Partial Ornament Release #{record.release_number} completed successfully! "
                f"Released {record.released_items.count()} items. New LTV is safe at {record.new_ltv_percentage}%."
            )
            return redirect('loan_partial_release_voucher', loan_number=loan.loan_number, release_id=record.id)
        except ValidationError as ve:
            messages.error(request, str(ve.message if hasattr(ve, 'message') else ve))
            return redirect('loan_partial_release', loan_number=loan.loan_number)
        except Exception as e:
            messages.error(request, f"Failed to execute partial release: {e}")
            return redirect('loan_partial_release', loan_number=loan.loan_number)


class LoanPartialReleaseVoucherView(LoginRequiredMixin, View):
    """
    Printable and formal legal Partial Ornament Release Voucher.
    """
    template_name = 'transactions/loan_partial_release_voucher.html'

    def get(self, request, loan_number, release_id):
        loan = get_object_or_404(Loan, loan_number=loan_number)
        record = get_object_or_404(PartialReleaseRecord, pk=release_id, loan=loan)
        
        released_items = record.released_items.all()
        retained_items = loan.loan_ornaments.filter(status='pledged')
        if not retained_items:
            retained_items = LoanItem.objects.filter(loan=loan, status='pledged')

        context = {
            'loan': loan,
            'record': record,
            'released_items': released_items,
            'retained_items': retained_items,
        }
        return render(request, self.template_name, context)
