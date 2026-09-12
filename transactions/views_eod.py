import csv
from datetime import datetime
from decimal import Decimal
from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Sum, Count, Q

from .models import Loan, InterestAccrualLog, EODBatchExecutionLog, IRACAlertLog
from branches.models import Branch
from .services_eod import run_daily_eod_batch
from .services_irac import (
    get_delinquency_watchlist,
    render_irac_alert_message,
    build_irac_alert_url,
    log_irac_alert,
    IRAC_ALERT_TEMPLATES
)
from .services_whatsapp_automator import (
    is_whatsapp_paired,
    pair_whatsapp_interactive,
    get_whatsapp_qr_image_base64,
    send_batch_irac_alerts_automated,
    send_whatsapp_message_headless
)


class EODConsoleView(LoginRequiredMixin, View):
    """
    End-of-Day (EOD) Operations Console for Interest Accrual & RBI IRAC NPA Tagging.
    Provides execution triggers, delinquency watchlist, risk alerts, and audit history.
    """
    template_name = 'transactions/eod_console.html'

    def get(self, request):
        user = request.user
        branch_id = request.GET.get('branch_id')
        bucket_filter = request.GET.get('bucket', 'ALL_OVERDUE')
        search_query = request.GET.get('q', '').strip()
        lang = request.GET.get('lang', 'ta' if str(getattr(request, 'LANGUAGE_CODE', '')).startswith('ta') else 'en')
        use_tamil = (lang == 'ta')
        selected_branch = None

        loans_qs = Loan.objects.filter(status='active')
        if branch_id and branch_id.isdigit():
            loans_qs = loans_qs.filter(branch_id=int(branch_id))
            selected_branch = Branch.objects.filter(pk=int(branch_id)).first()
        elif user.branch and not user.is_superuser:
            loans_qs = loans_qs.filter(branch=user.branch)
            selected_branch = user.branch
            branch_id = str(user.branch.id)

        # Portfolio metrics
        total_active_loans = loans_qs.count()
        total_principal = loans_qs.aggregate(total=Sum('principal_amount'))['total'] or Decimal('0.00')
        total_accrued = loans_qs.aggregate(total=Sum('accrued_interest'))['total'] or Decimal('0.00')

        # IRAC distribution
        standard_count = loans_qs.filter(irac_status='STANDARD').count()
        sma0_count = loans_qs.filter(irac_status='SMA_0').count()
        sma1_count = loans_qs.filter(irac_status='SMA_1').count()
        sma2_count = loans_qs.filter(irac_status='SMA_2').count()
        npa_count = loans_qs.filter(irac_status__in=['NPA_SUBSTANDARD', 'NPA_DOUBTFUL', 'NPA_LOSS']).count()

        # Fetch Delinquency Watchlist & Calculated Stats
        watchlist, delinquency_stats = get_delinquency_watchlist(
            branch_id=branch_id,
            bucket_filter=bucket_filter,
            search_query=search_query,
            use_tamil=use_tamil
        )

        # Recent EOD runs
        eod_runs = EODBatchExecutionLog.objects.select_related('branch', 'executed_by', 'gl_journal_entry').all().order_by('-started_at')[:15]

        # Recent IRAC Alert Logs
        recent_alert_logs = IRACAlertLog.objects.select_related('loan', 'customer', 'sent_by').all().order_by('-created_at')[:20]

        all_branches = Branch.objects.filter(is_active=True)

        context = {
            'total_active_loans': total_active_loans,
            'total_principal': total_principal,
            'total_accrued': total_accrued,
            'standard_count': standard_count,
            'sma0_count': sma0_count,
            'sma1_count': sma1_count,
            'sma2_count': sma2_count,
            'npa_count': npa_count,
            'eod_runs': eod_runs,
            'watchlist': watchlist,
            'delinquency_stats': delinquency_stats,
            'recent_alert_logs': recent_alert_logs,
            'all_branches': all_branches,
            'selected_branch': selected_branch,
            'selected_branch_id': branch_id or '',
            'bucket_filter': bucket_filter,
            'search_query': search_query,
            'lang': lang,
            'use_tamil': use_tamil,
            'whatsapp_paired': is_whatsapp_paired(),
            'today': timezone.now().date(),
        }
        return render(request, self.template_name, context)


class EODRunBatchActionView(LoginRequiredMixin, View):
    """
    Action endpoint to trigger manual or scheduled EOD batch execution.
    """
    def post(self, request):
        date_str = request.POST.get('execution_date')
        branch_id = request.POST.get('branch_id')

        if date_str:
            try:
                exec_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")
                return redirect('eod_console')
        else:
            exec_date = timezone.now().date()

        branch = None
        if branch_id and branch_id.isdigit():
            branch = Branch.objects.filter(pk=int(branch_id)).first()

        try:
            exec_log = run_daily_eod_batch(
                date=exec_date,
                branch=branch,
                user=request.user,
                post_gl=True
            )
            messages.success(
                request,
                f"EOD Batch for {exec_date.strftime('%d-%b-%Y')} completed successfully! "
                f"Processed {exec_log.total_loans_processed} loans | "
                f"Daily Interest Accrued: ₹{exec_log.total_daily_interest_accrued:,.2f} | "
                f"NPA Tagged: {exec_log.npa_count} loans."
            )
        except Exception as e:
            messages.error(request, f"EOD Batch failed: {e}")

        return redirect('eod_console')


class SendIRACAlertActionView(LoginRequiredMixin, View):
    """
    Action to log and trigger IRAC Risk Alert dispatch (single or batch).
    """
    def post(self, request):
        import json
        is_ajax = (request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json')
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode('utf-8'))
            else:
                data = request.POST

            loan_id = data.get('loan_id')
            bucket = data.get('bucket', 'SMA_0')
            channel = data.get('channel', 'whatsapp_web')
            message_text = data.get('message', '')

            loan = Loan.objects.select_related('customer', 'branch').get(id=loan_id)
            log_entry = log_irac_alert(
                loan=loan,
                bucket=bucket,
                channel=channel,
                status='sent',
                message_text=message_text,
                user=request.user
            )

            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'log_id': log_entry.id,
                    'loan_number': loan.loan_number,
                    'sent_at': log_entry.created_at.strftime('%d-%b-%Y %I:%M %p')
                })
            else:
                messages.success(request, f"✅ Logged {bucket} Risk Alert for Loan #{loan.loan_number} ({loan.customer}).")
                return redirect('eod_console')
        except Exception as exc:
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
            else:
                messages.error(request, f"Could not log alert: {exc}")
                return redirect('eod_console')


class ExportIRACWatchlistCSVView(LoginRequiredMixin, View):
    """
    Exports regulatory RBI IRAC Delinquency & Provisioning Watchlist to CSV.
    """
    def get(self, request):
        branch_id = request.GET.get('branch_id')
        bucket_filter = request.GET.get('bucket', 'ALL_OVERDUE')
        search_query = request.GET.get('q', '').strip()

        watchlist, stats = get_delinquency_watchlist(
            branch_id=branch_id,
            bucket_filter=bucket_filter,
            search_query=search_query,
            use_tamil=False
        )

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="rbi_irac_delinquency_watchlist_{timezone.now().strftime("%Y%m%d")}.csv"'
        writer = csv.writer(response)

        # Header Row
        writer.writerow([
            'Loan Number', 'Customer Name', 'Customer Phone', 'Branch',
            'Principal Outstanding (Rs)', 'Accrued Interest (Rs)', 'Total Overdue (Rs)',
            'Issue Date', 'Due Date', 'Overdue Days', 'IRAC Status Tag',
            'Provisioning %', 'Statutory Provision Amount (Rs)', 'Risk Category'
        ])

        for item in watchlist:
            writer.writerow([
                item['loan_number'],
                item['customer_name'],
                item['customer_phone'],
                item['branch_name'],
                f"{item['principal_amount']:.2f}",
                f"{item['accrued_interest']:.2f}",
                f"{item['total_due']:.2f}",
                item['issue_date'].strftime('%Y-%m-%d') if item['issue_date'] else '',
                item['due_date'].strftime('%Y-%m-%d') if item['due_date'] else '',
                item['overdue_days'],
                item['irac_status'],
                f"{item['provisioning_percentage']:.2f}%",
                f"{item['provisioning_amount']:.2f}",
                item['alert_bucket']
            ])

        return response


class PairWhatsAppSessionView(LoginRequiredMixin, View):
    """
    Triggers an interactive browser window to scan WhatsApp Web QR code once.
    """
    def post(self, request):
        try:
            res = pair_whatsapp_interactive(timeout_seconds=90)
            return JsonResponse(res)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class GetWhatsAppQRView(LoginRequiredMixin, View):
    """
    Returns the live Base64 QR code image or session authentication status.
    """
    def get(self, request):
        try:
            res = get_whatsapp_qr_image_base64()
            return JsonResponse(res)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


class AutoDispatchIRACAlertsView(LoginRequiredMixin, View):
    """
    AJAX endpoint to run 100% headless background WhatsApp message dispatch.
    Zero manual clicking required.
    """
    def post(self, request):
        if not is_whatsapp_paired():
            return JsonResponse({
                'status': 'unpaired',
                'message': 'WhatsApp session is not paired yet. Please scan the QR code first.'
            }, status=400)

        import json
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            payload = request.POST

        loan_ids = payload.get('loan_ids', [])
        bucket_filter = payload.get('bucket', 'ALL_OVERDUE')
        branch_id = payload.get('branch_id')
        lang = payload.get('lang', 'ta')

        if loan_ids:
            loans = list(Loan.objects.filter(pk__in=loan_ids).select_related('customer', 'branch', 'scheme'))
        else:
            watchlist, _ = get_delinquency_watchlist(
                branch_id=branch_id if branch_id and str(branch_id).isdigit() else None,
                bucket_filter=bucket_filter or 'ALL_OVERDUE',
                use_tamil=(lang == 'ta')
            )
            loans = [item['loan'] for item in watchlist]

        if not loans:
            return JsonResponse({'status': 'empty', 'message': 'No delinquent loan accounts found for the current filter.'})

        # Run automated batch dispatch
        res = send_batch_irac_alerts_automated(
            loans=loans,
            user=request.user,
            lang=lang,
            delay_between_seconds=3,
            headless=True
        )

        status_flag = 'success' if not res.get('error') else 'error'
        return JsonResponse({
            'status': status_flag,
            'sent': res.get('sent', 0),
            'failed': res.get('failed', 0),
            'total': res.get('total', len(loans)),
            'details': res.get('details', []),
            'message': res.get('error') or f"{res.get('sent', 0)} sent successfully"
        })


