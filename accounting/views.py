from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q
from decimal import Decimal
import datetime

from branches.models import Branch, CashTill
from .models import AccountHead, JournalEntry, JournalItem, AccountCategory
from .forms import AccountHeadForm, BranchExpenseForm
from .services import ensure_default_chart_of_accounts, post_manual_expense_journal


class AccountingBaseMixin:
    """Helper to resolve active branch and branches list for accounting filters"""
    def get_selected_branch(self, request):
        branch_id = request.GET.get('branch_id')
        if branch_id:
            if branch_id == 'all':
                return None  # Consolidated all branches
            if str(branch_id).isdigit():
                return Branch.objects.filter(pk=int(branch_id), is_active=True).first()
            return None
        if getattr(request.user, 'branch', None):
            return request.user.branch
        return Branch.objects.filter(is_active=True).first()


class DayBookView(LoginRequiredMixin, AccountingBaseMixin, View):
    """
    Branch Day Book (Daily Financial Journal Log)
    Lists all financial debit & credit entries chronologically for a selected date.
    """
    template_name = 'accounting/day_book.html'

    def get(self, request):
        branch = self.get_selected_branch(request)
        all_branches = Branch.objects.filter(is_active=True)

        date_str = request.GET.get('date')
        if date_str:
            try:
                selected_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                selected_date = timezone.now().date()
        else:
            selected_date = timezone.now().date()

        ensure_default_chart_of_accounts(branch)

        entries_qs = JournalEntry.objects.filter(date=selected_date).prefetch_related('items__account', 'branch', 'created_by')
        if branch:
            entries_qs = entries_qs.filter(branch=branch)

        entries = list(entries_qs.order_by('created_at'))

        total_debit = Decimal('0.00')
        total_credit = Decimal('0.00')
        for e in entries:
            total_debit += e.total_debit
            total_credit += e.total_credit

        # Check corresponding Cash Till for this date & branch
        cash_till = None
        if branch:
            cash_till = CashTill.objects.filter(branch=branch, date=selected_date).first()

        context = {
            'branch': branch,
            'all_branches': all_branches,
            'selected_date': selected_date,
            'entries': entries,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'is_balanced': total_debit == total_credit,
            'cash_till': cash_till,
        }
        return render(request, self.template_name, context)


class CashBookView(LoginRequiredMixin, AccountingBaseMixin, View):
    """
    Cash & Bank Book Statement
    Detailed ledger of all Cash Drawer (1010) and Bank Account (1020) transactions with running balances.
    """
    template_name = 'accounting/cash_book.html'

    def get(self, request):
        branch = self.get_selected_branch(request)
        all_branches = Branch.objects.filter(is_active=True)

        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        account_code = request.GET.get('account_code', '1010')  # 1010 = Cash, 1020 = Bank

        today = timezone.now().date()
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else today.replace(day=1)
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else today

        ensure_default_chart_of_accounts(branch)

        account = AccountHead.objects.filter(code=account_code).first()
        
        # Calculate opening balance prior to start_date
        items_prior = JournalItem.objects.filter(account__code=account_code, entry__date__lt=start_date)
        if branch:
            items_prior = items_prior.filter(entry__branch=branch)
        
        prior_agg = items_prior.aggregate(
            dr=Sum('debit'),
            cr=Sum('credit')
        )
        prior_dr = prior_agg['dr'] or Decimal('0.00')
        prior_cr = prior_agg['cr'] or Decimal('0.00')
        opening_balance = prior_dr - prior_cr

        # Transactions in range
        items_range = JournalItem.objects.filter(
            account__code=account_code,
            entry__date__gte=start_date,
            entry__date__lte=end_date
        ).select_related('entry', 'entry__branch', 'entry__created_by').order_by('entry__date', 'entry__created_at')
        
        if branch:
            items_range = items_range.filter(entry__branch=branch)

        rows = []
        running_balance = opening_balance
        total_dr = Decimal('0.00')
        total_cr = Decimal('0.00')

        for item in items_range:
            running_balance += (item.debit - item.credit)
            total_dr += item.debit
            total_cr += item.credit
            rows.append({
                'item': item,
                'running_balance': running_balance
            })

        closing_balance = running_balance

        context = {
            'branch': branch,
            'all_branches': all_branches,
            'start_date': start_date,
            'end_date': end_date,
            'account_code': account_code,
            'account': account,
            'opening_balance': opening_balance,
            'rows': rows,
            'total_dr': total_dr,
            'total_cr': total_cr,
            'closing_balance': closing_balance,
        }
        return render(request, self.template_name, context)


class TrialBalanceView(LoginRequiredMixin, AccountingBaseMixin, View):
    """
    Trial Balance Report
    Double-entry balancing statement showing net debit & credit balances across all GL accounts.
    Supports single branch or consolidated 100+ branches rollup.
    """
    template_name = 'accounting/trial_balance.html'

    def get(self, request):
        branch = self.get_selected_branch(request)
        all_branches = Branch.objects.filter(is_active=True)

        as_of_str = request.GET.get('as_of_date')
        if as_of_str:
            try:
                as_of_date = datetime.datetime.strptime(as_of_str, '%Y-%m-%d').date()
            except ValueError:
                as_of_date = timezone.now().date()
        else:
            as_of_date = timezone.now().date()

        ensure_default_chart_of_accounts(branch)

        accounts = AccountHead.objects.filter(is_active=True).order_by('code')
        report_rows = []
        grand_total_debit = Decimal('0.00')
        grand_total_credit = Decimal('0.00')

        for acc in accounts:
            items = JournalItem.objects.filter(account=acc, entry__date__lte=as_of_date)
            if branch:
                items = items.filter(entry__branch=branch)

            agg = items.aggregate(
                total_dr=Sum('debit'),
                total_cr=Sum('credit')
            )
            dr = agg['total_dr'] or Decimal('0.00')
            cr = agg['total_cr'] or Decimal('0.00')

            net_dr = Decimal('0.00')
            net_cr = Decimal('0.00')

            if acc.is_debit_nature:
                balance = dr - cr
                if balance > 0:
                    net_dr = balance
                elif balance < 0:
                    net_cr = abs(balance)
            else:
                balance = cr - dr
                if balance > 0:
                    net_cr = balance
                elif balance < 0:
                    net_dr = abs(balance)

            if dr > 0 or cr > 0:
                report_rows.append({
                    'account': acc,
                    'total_dr': dr,
                    'total_cr': cr,
                    'net_dr': net_dr,
                    'net_cr': net_cr
                })
                grand_total_debit += net_dr
                grand_total_credit += net_cr

        context = {
            'branch': branch,
            'all_branches': all_branches,
            'as_of_date': as_of_date,
            'report_rows': report_rows,
            'grand_total_debit': grand_total_debit,
            'grand_total_credit': grand_total_credit,
            'is_balanced': grand_total_debit == grand_total_credit,
        }
        return render(request, self.template_name, context)


class ProfitAndLossView(LoginRequiredMixin, AccountingBaseMixin, View):
    """
    Profit and Loss (Income Statement)
    Revenue (Interest, Fees) - Expenses (Rent, Salary, Vault, Office) = Net Operating Profit.
    """
    template_name = 'accounting/profit_and_loss.html'

    def get(self, request):
        branch = self.get_selected_branch(request)
        all_branches = Branch.objects.filter(is_active=True)

        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')

        today = timezone.now().date()
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else today.replace(month=1, day=1)
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else today

        ensure_default_chart_of_accounts(branch)

        # Income Accounts
        income_accounts = AccountHead.objects.filter(category=AccountCategory.INCOME, is_active=True)
        income_rows = []
        total_income = Decimal('0.00')

        for acc in income_accounts:
            bal = acc.get_balance(start_date=start_date, end_date=end_date, branch=branch)
            if bal > 0:
                income_rows.append({'account': acc, 'amount': bal})
                total_income += bal

        # Expense Accounts
        expense_accounts = AccountHead.objects.filter(category=AccountCategory.EXPENSE, is_active=True)
        expense_rows = []
        total_expenses = Decimal('0.00')

        for acc in expense_accounts:
            bal = acc.get_balance(start_date=start_date, end_date=end_date, branch=branch)
            if bal > 0:
                expense_rows.append({'account': acc, 'amount': bal})
                total_expenses += bal

        net_profit = total_income - total_expenses

        context = {
            'branch': branch,
            'all_branches': all_branches,
            'start_date': start_date,
            'end_date': end_date,
            'income_rows': income_rows,
            'total_income': total_income,
            'expense_rows': expense_rows,
            'total_expenses': total_expenses,
            'net_profit': net_profit,
        }
        return render(request, self.template_name, context)


class BalanceSheetView(LoginRequiredMixin, AccountingBaseMixin, View):
    """
    Balance Sheet Statement
    Total Assets == Total Liabilities + Total Equity (including Net Operating Profit).
    """
    template_name = 'accounting/balance_sheet.html'

    def get(self, request):
        branch = self.get_selected_branch(request)
        all_branches = Branch.objects.filter(is_active=True)

        as_of_str = request.GET.get('as_of_date')
        if as_of_str:
            try:
                as_of_date = datetime.datetime.strptime(as_of_str, '%Y-%m-%d').date()
            except ValueError:
                as_of_date = timezone.now().date()
        else:
            as_of_date = timezone.now().date()

        ensure_default_chart_of_accounts(branch)

        # 1. Assets
        asset_accounts = AccountHead.objects.filter(category=AccountCategory.ASSET, is_active=True)
        asset_rows = []
        total_assets = Decimal('0.00')
        for acc in asset_accounts:
            bal = acc.get_balance(end_date=as_of_date, branch=branch)
            if bal != 0:
                asset_rows.append({'account': acc, 'amount': bal})
                total_assets += bal

        # 2. Liabilities
        liability_accounts = AccountHead.objects.filter(category=AccountCategory.LIABILITY, is_active=True)
        liability_rows = []
        total_liabilities = Decimal('0.00')
        for acc in liability_accounts:
            bal = acc.get_balance(end_date=as_of_date, branch=branch)
            if bal != 0:
                liability_rows.append({'account': acc, 'amount': bal})
                total_liabilities += bal

        # 3. Equity
        equity_accounts = AccountHead.objects.filter(category=AccountCategory.EQUITY, is_active=True)
        equity_rows = []
        total_equity = Decimal('0.00')
        for acc in equity_accounts:
            bal = acc.get_balance(end_date=as_of_date, branch=branch)
            if bal != 0:
                equity_rows.append({'account': acc, 'amount': bal})
                total_equity += bal

        # 4. Current Period Net Operating Profit/Loss
        income_accs = AccountHead.objects.filter(category=AccountCategory.INCOME, is_active=True)
        total_inc = sum(acc.get_balance(end_date=as_of_date, branch=branch) for acc in income_accs)
        expense_accs = AccountHead.objects.filter(category=AccountCategory.EXPENSE, is_active=True)
        total_exp = sum(acc.get_balance(end_date=as_of_date, branch=branch) for acc in expense_accs)
        current_period_profit = total_inc - total_exp

        total_liabilities_and_equity = total_liabilities + total_equity + current_period_profit

        context = {
            'branch': branch,
            'all_branches': all_branches,
            'as_of_date': as_of_date,
            'asset_rows': asset_rows,
            'total_assets': total_assets,
            'liability_rows': liability_rows,
            'total_liabilities': total_liabilities,
            'equity_rows': equity_rows,
            'total_equity': total_equity,
            'current_period_profit': current_period_profit,
            'total_liabilities_and_equity': total_liabilities_and_equity,
            'is_balanced': total_assets == total_liabilities_and_equity,
        }
        return render(request, self.template_name, context)


class ChartOfAccountsListView(LoginRequiredMixin, ListView):
    """Hierarchical list of Chart of Accounts"""
    model = AccountHead
    template_name = 'accounting/chart_of_accounts.html'
    context_object_name = 'accounts'

    def get_queryset(self):
        ensure_default_chart_of_accounts()
        return AccountHead.objects.all().order_by('code')


class RecordExpenseView(LoginRequiredMixin, AccountingBaseMixin, View):
    """Quick voucher form to record operational expenses"""
    template_name = 'accounting/expense_form.html'

    def get(self, request):
        branch = self.get_selected_branch(request)
        ensure_default_chart_of_accounts(branch)
        form = BranchExpenseForm()
        return render(request, self.template_name, {'form': form, 'branch': branch})

    def post(self, request):
        branch = self.get_selected_branch(request)
        ensure_default_chart_of_accounts(branch)
        form = BranchExpenseForm(request.POST)
        if form.is_valid():
            post_manual_expense_journal(
                branch=branch,
                expense_head=form.cleaned_data['expense_head'],
                amount=form.cleaned_data['amount'],
                payment_mode=form.cleaned_data['payment_mode'],
                narration=form.cleaned_data['narration'],
                user=request.user
            )
            messages.success(request, f"Expense voucher of ₹{form.cleaned_data['amount']:,.2f} for {form.cleaned_data['expense_head'].name} recorded successfully.")
            return redirect('accounting_day_book')
        return render(request, self.template_name, {'form': form, 'branch': branch})


class JournalEntryDetailView(LoginRequiredMixin, DetailView):
    """View details of a specific Journal Voucher"""
    model = JournalEntry
    template_name = 'accounting/journal_entry_detail.html'
    context_object_name = 'entry'
