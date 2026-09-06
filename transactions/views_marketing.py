"""
transactions/views_marketing.py
Views for the Digital Marketing, Campaign Studio, and WhatsApp Broadcast Hub.
"""

import csv
import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from accounts.mixins import RoleBranchAccessMixin
from branches.models import Branch
from schemes.models import DailyGoldRate, Scheme
from transactions.services_marketing import (
    MARKETING_TEMPLATES,
    build_broadcast_queue,
    get_segmented_audience,
    get_social_media_ad_copies,
    launch_pywhatkit_broadcast_async,
    render_campaign_message,
)

logger = logging.getLogger(__name__)


class DigitalMarketingDashboardView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    """
    Main Digital Marketing & Campaign Studio Dashboard.
    Handles audience segmentation, template selection, message editing,
    live queue building, and social media copy generation.
    """
    template_name = 'transactions/digital_marketing.html'

    def get(self, request):
        user_branch = getattr(request.user, 'branch', None)
        selected_branch_id = request.GET.get('branch', '')
        if not selected_branch_id and user_branch and not request.user.is_superuser:
            selected_branch_id = str(user_branch.id)

        segment = request.GET.get('segment', 'all')
        template_key = request.GET.get('template', 'festival_offer')
        lang = request.GET.get('lang', 'ta' if str(getattr(request, 'LANGUAGE_CODE', '')).startswith('ta') else 'en')
        use_tamil = (lang == 'ta')

        # Branches list for filtering (filtered by role access)
        branches = self.get_branch_queryset(Branch.objects.filter(is_active=True)) if hasattr(self, 'get_branch_queryset') else Branch.objects.filter(is_active=True)

        # Get latest gold rate
        try:
            latest_gold_rate_obj = DailyGoldRate.objects.order_by('-date', '-created_at').first()
            current_gold_rate = latest_gold_rate_obj.rate_22k if latest_gold_rate_obj else Decimal('6850.00')
        except Exception:
            current_gold_rate = Decimal('6850.00')

        # Fetch Segment Counts for KPIs
        all_aud = get_segmented_audience('all', branch_id=selected_branch_id or None)
        active_aud = get_segmented_audience('active_borrowers', branch_id=selected_branch_id or None)
        closed_aud = get_segmented_audience('closed_loans', branch_id=selected_branch_id or None)
        overdue_aud = get_segmented_audience('overdue', branch_id=selected_branch_id or None)
        high_val_aud = get_segmented_audience('high_value', branch_id=selected_branch_id or None)

        kpis = {
            'total_customers': len(all_aud),
            'total_whatsapp_ready': sum(1 for c in all_aud if c['is_valid_whatsapp']),
            'active_borrowers_count': len(active_aud),
            'closed_prospects_count': len(closed_aud),
            'overdue_count': len(overdue_aud),
            'high_value_count': len(high_val_aud),
        }

        # Targeted Audience according to current segment selection
        target_audience = get_segmented_audience(segment, branch_id=selected_branch_id or None)
        broadcast_queue = build_broadcast_queue(
            target_audience,
            template_key=template_key,
            use_tamil=use_tamil,
            gold_rate=current_gold_rate
        )

        # Sample preview message using first contact or placeholder
        sample_cust = broadcast_queue[0] if broadcast_queue else {
            'name': 'John Doe' if not use_tamil else 'ஹரிஹரன்',
            'branch_name': getattr(user_branch, 'name', 'Main Branch'),
            'branch_phone': getattr(user_branch, 'phone', '9876543210'),
            'city': 'Theni',
        }
        sample_preview_text = render_campaign_message(
            template_key,
            sample_cust,
            use_tamil=use_tamil,
            gold_rate=current_gold_rate
        )

        # Social Media ad copy
        social_copies = get_social_media_ad_copies(
            organization_name=getattr(settings, 'ORGANIZATION_NAME', 'First Money Gold'),
            phone=getattr(user_branch, 'phone', '') or getattr(settings, 'COMPANY_PHONE', 'Customer Care'),
            gold_rate=current_gold_rate
        )

        # Active Loan Schemes for promo banner
        try:
            schemes = Scheme.objects.filter(status='active')[:6]
        except Exception:
            schemes = Scheme.objects.all()[:6]

        context = {
            'segment': segment,
            'template_key': template_key,
            'lang': lang,
            'use_tamil': use_tamil,
            'selected_branch_id': selected_branch_id,
            'branches': branches,
            'kpis': kpis,
            'marketing_templates': MARKETING_TEMPLATES,
            'current_template': MARKETING_TEMPLATES.get(template_key, MARKETING_TEMPLATES['festival_offer']),
            'broadcast_queue': broadcast_queue,
            'total_queue_count': len(broadcast_queue),
            'sample_preview_text': sample_preview_text,
            'social_copies': social_copies,
            'schemes': schemes,
            'current_gold_rate': current_gold_rate,
            'organization_name': getattr(settings, 'ORGANIZATION_NAME', 'First Money Gold'),
        }
        return render(request, self.template_name, context)


class ExecuteBroadcastActionView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    """
    POST-only action to launch automated background PyWhatKit broadcast or download audience CSV.
    """
    def post(self, request):
        action = request.POST.get('action', 'pywhatkit_broadcast')
        segment = request.POST.get('segment', 'all')
        template_key = request.POST.get('template', 'festival_offer')
        lang = request.POST.get('lang', 'ta')
        branch_id = request.POST.get('branch', '')
        custom_message = request.POST.get('custom_message', '').strip() or None
        delay_seconds = int(request.POST.get('delay_seconds', 20))

        use_tamil = (lang == 'ta')
        target_audience = get_segmented_audience(segment, branch_id=branch_id or None)
        broadcast_queue = build_broadcast_queue(
            target_audience,
            template_key=template_key,
            use_tamil=use_tamil,
            custom_body=custom_message
        )

        if not broadcast_queue:
            messages.warning(request, "No valid WhatsApp contacts found in the selected audience segment.")
            return redirect(reverse('digital_marketing') + f"?segment={segment}&template={template_key}&lang={lang}")

        if action == 'export_csv':
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="whatsapp_broadcast_{segment}_{template_key}.csv"'
            writer = csv.writer(response)
            writer.writerow(['Customer ID', 'Name', 'Phone Number', 'City', 'Branch', 'WhatsApp Direct URL', 'Personalized Message'])
            for row in broadcast_queue:
                writer.writerow([
                    row['customer_id'],
                    row['name'],
                    row['phone'],
                    row['city'],
                    row['branch_name'],
                    row['whatsapp_url'],
                    row['message']
                ])
            return response

        elif action == 'pywhatkit_broadcast':
            started = launch_pywhatkit_broadcast_async(broadcast_queue, delay_seconds=delay_seconds)
            if started:
                messages.success(
                    request,
                    f"🚀 Automated PyWhatKit broadcast launched in background for {len(broadcast_queue)} contacts "
                    f"(with {delay_seconds}s safety interval per contact). Keep WhatsApp Web ready on your browser!"
                )
            else:
                messages.error(request, "Failed to initiate PyWhatKit background broadcast.")

        return redirect(reverse('digital_marketing') + f"?segment={segment}&template={template_key}&lang={lang}&branch={branch_id}")


class GenerateAICampaignView(LoginRequiredMixin, View):
    """
    AJAX endpoint: Generates AI-powered campaign copies using Google Gemini Free Tier.
    Returns WhatsApp copy, SMS text, social media caption, and key highlights.
    """
    def post(self, request):
        try:
            import json
            if request.content_type == 'application/json':
                body_data = json.loads(request.body.decode('utf-8'))
            else:
                body_data = request.POST.dict()

            from transactions.services_gemini import generate_campaign_content

            custom_key = body_data.get('custom_api_key', '').strip()
            params = {
                'offer_type': body_data.get('offer_type', 'festival_offer'),
                'festival_name': body_data.get('festival_name', ''),
                'language': body_data.get('language', 'ta'),
                'tone': body_data.get('tone', 'festive'),
                'interest_rate': body_data.get('interest_rate', '0.99%'),
                'gold_rate': body_data.get('gold_rate', '₹6,850/g'),
                'bonus_offer': body_data.get('bonus_offer', ''),
                'custom_instructions': body_data.get('custom_instructions', ''),
                'organization_name': getattr(settings, 'ORGANIZATION_NAME', 'First Money Gold'),
            }

            result = generate_campaign_content(params, custom_api_key=custom_key)
            return JsonResponse({'status': 'success', 'data': result})

        except Exception as e:
            logger.exception("Error in GenerateAICampaignView")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

