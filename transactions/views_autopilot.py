"""
Views for the 24/7 Autopilot Automation Console, Configuration Management,
and On-Demand Pillar Triggers.
"""

import csv
import json
import logging
from decimal import Decimal
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone

from transactions.models import AutopilotConfig, AutopilotLog
from transactions.services_autopilot import (
    get_or_create_autopilot_config,
    get_management_stakeholders,
    run_autopilot_cycle,
    run_pillar_2_whatsapp_collections,
    run_pillar_3_ltv_surveillance,
    run_pillar_4_retention_marketing,
    run_pillar_5_owner_digest,
    start_autopilot_daemon,
)
from transactions.services_whatsapp_automator import is_whatsapp_paired

logger = logging.getLogger(__name__)


class AutopilotConsoleView(LoginRequiredMixin, View):
    """
    Renders the Autopilot Control Console with real-time status indicators,
    per-pillar toggles, live performance metrics, and activity logs.
    """
    def get(self, request):
        config = get_or_create_autopilot_config()
        
        # Ensure daemon is initiated if autopilot is active
        if config.is_enabled:
            start_autopilot_daemon()

        recent_logs = AutopilotLog.objects.all().order_by('-created_at')[:30]
        
        # Aggregated stats for today
        today = timezone.localtime().date()
        today_logs = AutopilotLog.objects.filter(created_at__date=today)
        total_actions_today = today_logs.count()
        total_wa_sent_today = sum(l.success_count for l in today_logs if l.pillar in ('pillar_2', 'pillar_4', 'pillar_5'))

        # Fetch management & branch manager stakeholders and check for missing contact info
        stakeholder_data = get_management_stakeholders()

        context = {
            'config': config,
            'recent_logs': recent_logs,
            'today_actions_count': total_actions_today,
            'today_wa_sent_count': total_wa_sent_today,
            'is_wa_paired': is_whatsapp_paired(),
            'stakeholder_data': stakeholder_data,
        }
        return render(request, 'transactions/autopilot_console.html', context)


class AutopilotSaveConfigView(LoginRequiredMixin, View):
    """
    AJAX / POST endpoint: Updates Autopilot switches, thresholds, and execution schedules.
    """
    def post(self, request):
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode('utf-8'))
            else:
                data = request.POST

            config = get_or_create_autopilot_config()

            # Master Switch
            if 'is_enabled' in data:
                config.is_enabled = str(data.get('is_enabled')).lower() in ('true', '1', 'on')

            # Pillar 2
            if 'enable_due_date_reminders' in data:
                config.enable_due_date_reminders = str(data.get('enable_due_date_reminders')).lower() in ('true', '1', 'on')
            if 'due_reminder_days' in data:
                config.due_reminder_days = str(data.get('due_reminder_days', '7,3,1')).strip()
            if 'enable_monthly_interest_reminders' in data:
                config.enable_monthly_interest_reminders = str(data.get('enable_monthly_interest_reminders')).lower() in ('true', '1', 'on')
            if 'enable_irac_delinquency_alerts' in data:
                config.enable_irac_delinquency_alerts = str(data.get('enable_irac_delinquency_alerts')).lower() in ('true', '1', 'on')
            if 'enable_expiry_auction_notices' in data:
                config.enable_expiry_auction_notices = str(data.get('enable_expiry_auction_notices')).lower() in ('true', '1', 'on')
            if 'whatsapp_dispatch_time' in data and data.get('whatsapp_dispatch_time'):
                config.whatsapp_dispatch_time = data.get('whatsapp_dispatch_time')
            if 'dispatch_channel' in data:
                config.dispatch_channel = data.get('dispatch_channel', 'headless_automated')

            # Pillar 3
            if 'enable_ltv_surveillance' in data:
                config.enable_ltv_surveillance = str(data.get('enable_ltv_surveillance')).lower() in ('true', '1', 'on')
            if 'ltv_warning_threshold' in data:
                config.ltv_warning_threshold = Decimal(str(data.get('ltv_warning_threshold', '75.00')))
            if 'ltv_critical_threshold' in data:
                config.ltv_critical_threshold = Decimal(str(data.get('ltv_critical_threshold', '85.00')))
            if 'ltv_check_time' in data and data.get('ltv_check_time'):
                config.ltv_check_time = data.get('ltv_check_time')

            # Pillar 4
            if 'enable_repledge_retention' in data:
                config.enable_repledge_retention = str(data.get('enable_repledge_retention')).lower() in ('true', '1', 'on')
            if 'repledge_cooldown_days' in data:
                config.repledge_cooldown_days = int(data.get('repledge_cooldown_days', 30))
            if 'marketing_dispatch_time' in data and data.get('marketing_dispatch_time'):
                config.marketing_dispatch_time = data.get('marketing_dispatch_time')

            # Pillar 5
            if 'enable_owner_digest' in data:
                config.enable_owner_digest = str(data.get('enable_owner_digest')).lower() in ('true', '1', 'on')
            if 'owner_phone' in data:
                config.owner_phone = str(data.get('owner_phone', '')).strip()
            if 'owner_email' in data:
                config.owner_email = str(data.get('owner_email', '')).strip()
            if 'digest_time' in data and data.get('digest_time'):
                config.digest_time = data.get('digest_time')

            # Safety Guardrails
            if 'safe_window_start' in data and data.get('safe_window_start'):
                config.safe_window_start = data.get('safe_window_start')
            if 'safe_window_end' in data and data.get('safe_window_end'):
                config.safe_window_end = data.get('safe_window_end')
            if 'min_days_between_reminders' in data:
                config.min_days_between_reminders = int(data.get('min_days_between_reminders', 5))

            config.save()

            if config.is_enabled:
                start_autopilot_daemon()

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({
                    'status': 'success',
                    'message': 'Autopilot Configuration saved successfully!',
                    'is_enabled': config.is_enabled
                })

            messages.success(request, "Autopilot configuration updated successfully.")
            return redirect('autopilot_console')

        except Exception as exc:
            logger.exception("Error saving Autopilot config: %s", exc)
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
            messages.error(request, f"Could not save configuration: {exc}")
            return redirect('autopilot_console')


class AutopilotTriggerActionView(LoginRequiredMixin, View):
    """
    AJAX endpoint: Allows on-demand instant triggering of specific pillars or dry-runs.
    """
    def post(self, request):
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode('utf-8'))
            else:
                data = request.POST

            pillar = data.get('pillar', 'all')
            is_dry_run = str(data.get('dry_run', 'false')).lower() in ('true', '1')

            config = get_or_create_autopilot_config()
            result = {}

            if pillar == 'pillar_2':
                result = run_pillar_2_whatsapp_collections(config=config, dry_run=is_dry_run, forced=True)
            elif pillar == 'pillar_3':
                result = run_pillar_3_ltv_surveillance(config=config, dry_run=is_dry_run, forced=True)
            elif pillar == 'pillar_3_single_margin_call':
                loan_id = data.get('loan_id')
                from transactions.models import Loan, LoanWhatsAppLog
                from transactions.services_whatsapp_automator import send_whatsapp_message_headless, is_whatsapp_paired
                from transactions.services_whatsapp import normalize_phone_number

                loan = Loan.objects.get(id=loan_id)
                cust = loan.customer
                raw_phone = getattr(cust, 'phone', '') or ''
                norm_phone = normalize_phone_number(raw_phone)
                msg = data.get('message', '')

                if not norm_phone:
                    return JsonResponse({'status': 'error', 'message': f'Customer {cust} has no valid phone number.'})

                if not is_whatsapp_paired():
                    return JsonResponse({'status': 'error', 'message': 'WhatsApp session is not paired. Please pair WhatsApp Web from Digital Marketing/Loans page first.'})

                res = send_whatsapp_message_headless(phone=norm_phone, message=msg, headless=True)
                status_str = 'sent' if res.get('success') else 'failed'

                LoanWhatsAppLog.objects.create(
                    loan=loan,
                    customer=cust,
                    recipient_phone=norm_phone,
                    notification_type='margin_call',
                    status=status_str,
                    message_content=msg,
                    channel='automated_browser',
                    sent_by=request.user
                )

                if res.get('success'):
                    return JsonResponse({'status': 'success', 'message': f'Margin Call WhatsApp alert sent to {cust} (+{norm_phone})!'})
                else:
                    return JsonResponse({'status': 'error', 'message': res.get('message', 'Failed to dispatch WhatsApp message.')})

            elif pillar == 'pillar_4':
                custom_tpl = data.get('custom_template') or data.get('message_template')
                sel_loans = data.get('selected_loan_ids')
                result = run_pillar_4_retention_marketing(
                    config=config,
                    dry_run=is_dry_run,
                    forced=True,
                    user=request.user,
                    custom_template=custom_tpl,
                    selected_loan_ids=sel_loans
                )
            elif pillar == 'pillar_4_single_promo':
                from transactions.models import LoanWhatsAppLog, MarketingCampaignLog, Loan
                from transactions.services_whatsapp import normalize_phone_number
                from transactions.services_whatsapp_automator import send_whatsapp_message_headless, is_whatsapp_paired

                loan_id = data.get('loan_id')
                loan = Loan.objects.filter(id=loan_id).select_related('customer').first() if loan_id else None
                cust = loan.customer if loan else None
                raw_phone = data.get('phone') or (cust.phone if cust else '')
                norm_phone = normalize_phone_number(raw_phone)
                msg = data.get('message', '')

                if not norm_phone:
                    return JsonResponse({'status': 'error', 'message': 'Customer has no valid phone number.'})

                if not is_whatsapp_paired():
                    return JsonResponse({'status': 'error', 'message': 'WhatsApp session is not paired. Please pair WhatsApp Web from Digital Marketing/Loans page first.'})

                res = send_whatsapp_message_headless(phone=norm_phone, message=msg, headless=True)
                status_str = 'sent' if res.get('success') else 'failed'
                cust_name = getattr(cust, 'first_name', '') if cust else (data.get('name') or 'Customer')

                try:
                    MarketingCampaignLog.objects.create(
                        template_key='repledge_retention',
                        campaign_name='Autopilot Re-Pledge Retention (Manual 1-Click)',
                        recipient_name=cust_name,
                        recipient_phone=norm_phone,
                        recipient_type='customer',
                        channel='whatsapp_blast',
                        status=status_str,
                        message_snippet=msg[:300],
                        sent_by=request.user
                    )
                    if loan:
                        LoanWhatsAppLog.objects.create(
                            loan=loan,
                            customer=cust,
                            recipient_phone=norm_phone,
                            notification_type='marketing_broadcast',
                            status=status_str,
                            message_content=msg,
                            channel='automated_browser',
                            sent_by=request.user
                        )
                except Exception as log_ex:
                    logger.warning("Could not log single retention promo: %s", log_ex)

                if res.get('success'):
                    return JsonResponse({'status': 'success', 'message': f'Re-Pledge Promo WhatsApp sent to {cust_name} (+{norm_phone})!'})
                else:
                    return JsonResponse({'status': 'error', 'message': res.get('message', res.get('error', 'Failed to dispatch WhatsApp promo.'))})
            elif pillar == 'pillar_5':
                result = run_pillar_5_owner_digest(config=config, dry_run=is_dry_run, forced=True)
            else:
                # Run full cycle
                result = run_autopilot_cycle(forced=True)

            return JsonResponse({
                'status': 'success',
                'pillar': pillar,
                'dry_run': is_dry_run,
                'result': result
            })

        except Exception as exc:
            logger.exception("Error executing on-demand Autopilot trigger: %s", exc)
            return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)


class AutopilotLogsExportView(LoginRequiredMixin, View):
    """
    Exports full Autopilot activity and execution audit trail to CSV.
    """
    def get(self, request):
        logs = AutopilotLog.objects.all().order_by('-created_at')

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="autopilot_activity_logs_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
        writer = csv.writer(response)

        writer.writerow([
            'Timestamp', 'Pillar', 'Action Name', 'Status',
            'Target Count', 'Success Count', 'Failed Count', 'Summary', 'Error Details', 'Executed By'
        ])

        for l in logs:
            writer.writerow([
                l.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                l.get_pillar_display(),
                l.action_name,
                l.status.upper(),
                l.target_count,
                l.success_count,
                l.failed_count,
                l.summary,
                l.error_details,
                l.executed_by
            ])

        return response
