from datetime import datetime
from decimal import Decimal
from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q

from .models import Loan, InterestAccrualLog, EODBatchExecutionLog
from branches.models import Branch
from .services_eod import run_daily_eod_batch


class EODConsoleView(LoginRequiredMixin, View):
    """
    End-of-Day (EOD) Operations Console for Interest Accrual & RBI IRAC NPA Tagging.
    Provides execution triggers, asset health metrics, and audit history.
    """
    template_name = 'transactions/eod_console.html'

    def get(self, request):
        user = request.user
        branch_id = request.GET.get('branch_id')
        selected_branch = None

        loans_qs = Loan.objects.filter(status='active')
        if branch_id and branch_id.isdigit():
            loans_qs = loans_qs.filter(branch_id=int(branch_id))
            selected_branch = Branch.objects.filter(pk=int(branch_id)).first()
        elif user.branch and not user.is_superuser:
            loans_qs = loans_qs.filter(branch=user.branch)
            selected_branch = user.branch

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

        # Recent EOD runs
        eod_runs = EODBatchExecutionLog.objects.select_related('branch', 'executed_by', 'gl_journal_entry').all().order_by('-started_at')[:20]

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
            'all_branches': all_branches,
            'selected_branch': selected_branch,
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
