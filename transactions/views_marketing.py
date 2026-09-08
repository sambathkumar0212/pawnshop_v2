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
    add_single_lead,
    build_broadcast_queue,
    clear_all_marketing_leads,
    delete_or_reset_template,
    get_all_marketing_templates,
    get_segmented_audience,
    get_social_media_ad_copies,
    import_leads_from_csv,
    launch_pywhatkit_broadcast_async,
    render_campaign_message,
    save_or_overwrite_template,
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
        new_prospects_aud = get_segmented_audience('new_prospects', branch_id=selected_branch_id or None)

        kpis = {
            'total_customers': len(all_aud),
            'total_whatsapp_ready': sum(1 for c in all_aud if c['is_valid_whatsapp']),
            'active_borrowers_count': len(active_aud),
            'closed_prospects_count': len(closed_aud),
            'overdue_count': len(overdue_aud),
            'high_value_count': len(high_val_aud),
            'new_prospects_count': len(new_prospects_aud),
        }

        # Dynamic marketing templates (merged with database saved/custom templates)
        all_marketing_templates = get_all_marketing_templates()
        current_template = all_marketing_templates.get(template_key) or all_marketing_templates.get('festival_offer') or next(iter(all_marketing_templates.values()), {})

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
            'marketing_templates': all_marketing_templates,
            'current_template': current_template,
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
            send_mode = request.POST.get('send_mode', 'message_and_image')  # 'message_and_image', 'image_only', 'message_only'
            campaign_image_file = request.FILES.get('campaign_image')
            campaign_image_base64 = request.POST.get('campaign_image_base64', '').strip()

            saved_image_path = None
            try:
                import base64
                import os
                import time
                campaigns_dir = os.path.join(settings.BASE_DIR, 'media', 'campaigns')
                os.makedirs(campaigns_dir, exist_ok=True)

                if campaign_image_file:
                    ext = os.path.splitext(campaign_image_file.name)[1] or '.png'
                    filename = f"campaign_{int(time.time())}_{request.user.id}{ext}"
                    filepath = os.path.join(campaigns_dir, filename)
                    with open(filepath, 'wb+') as destination:
                        for chunk in campaign_image_file.chunks():
                            destination.write(chunk)
                    saved_image_path = filepath
                elif campaign_image_base64 and 'base64,' in campaign_image_base64:
                    _, encoded = campaign_image_base64.split('base64,', 1)
                    file_data = base64.b64decode(encoded)
                    filename = f"campaign_poster_{int(time.time())}_{request.user.id}.png"
                    filepath = os.path.join(campaigns_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(file_data)
                    saved_image_path = filepath
            except Exception as exc:
                logger.warning("Could not save campaign image attachment: %s", exc)

            started = launch_pywhatkit_broadcast_async(
                broadcast_queue,
                delay_seconds=delay_seconds,
                image_path=saved_image_path,
                send_mode=send_mode
            )
            if started:
                mode_desc = (
                    "Image Flyer + Message"
                    if (saved_image_path and send_mode != 'image_only')
                    else ("Image Flyer Only" if (saved_image_path and send_mode == 'image_only') else "Text Message")
                )
                messages.success(
                    request,
                    f"🚀 Automated PyWhatKit broadcast launched in background for {len(broadcast_queue)} contacts "
                    f"({mode_desc}, {delay_seconds}s safety interval). Keep WhatsApp Web ready on your browser!"
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


class SaveMarketingTemplateView(LoginRequiredMixin, View):
    """
    AJAX endpoint: Saves Gemini AI copy or custom message as a New Preset Template
    or Overwrites an existing preset template. Also supports resetting to defaults.
    """
    def post(self, request):
        try:
            import json
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode('utf-8'))
            else:
                data = request.POST.dict()

            action = data.get('action', 'save_as_new')  # 'save_as_new', 'overwrite_existing', 'reset_default'
            key = (data.get('template_key') or '').strip().lower().replace(' ', '_')
            title_en = data.get('title_en', '').strip()
            title_ta = data.get('title_ta', '').strip()
            category = data.get('category', 'Custom').strip() or 'Custom'
            badge = data.get('badge', 'AI Custom').strip() or 'AI Custom'
            body_text = data.get('message_body', '').strip()
            target_lang = data.get('lang', 'ta')

            if action == 'reset_default':
                if not key:
                    return JsonResponse({'status': 'error', 'message': 'Missing template key to reset.'}, status=400)
                delete_or_reset_template(key)
                return JsonResponse({
                    'status': 'success',
                    'message': f"Template '{key}' reset to original default successfully!",
                    'template_key': key,
                })

            if not body_text:
                return JsonResponse({'status': 'error', 'message': 'Message body cannot be empty.'}, status=400)

            # Check action mode
            if action == 'overwrite_existing':
                if not key:
                    return JsonResponse({'status': 'error', 'message': 'Please select an existing template to overwrite.'}, status=400)
                all_t = get_all_marketing_templates()
                existing = all_t.get(key, {})

                # If existing template had English & Tamil, update the appropriate language body
                if target_lang == 'en':
                    body_en = body_text
                    body_ta = data.get('body_ta', '') or existing.get('body_ta', body_text)
                    t_en = title_en or existing.get('title_en', 'Updated Template')
                    t_ta = title_ta or existing.get('title_ta', t_en)
                else:
                    body_ta = body_text
                    body_en = data.get('body_en', '') or existing.get('body_en', body_text)
                    t_ta = title_ta or existing.get('title_ta', 'புதுப்பிக்கப்பட்ட டெம்ப்ளேட்')
                    t_en = title_en or existing.get('title_en', t_ta)

                obj, created = save_or_overwrite_template(
                    key=key,
                    title_en=t_en,
                    title_ta=t_ta,
                    body_en=body_en,
                    body_ta=body_ta,
                    category=category or existing.get('category', 'Special'),
                    badge=badge or 'Updated',
                    is_custom=existing.get('is_custom', False),
                    user=request.user
                )
                msg = f"Preset template '{t_en or t_ta}' has been overwritten and saved successfully!"

            else:  # save_as_new
                import time
                import re
                base_slug = re.sub(r'[^a-zA-Z0-9_]', '', (title_en or 'custom_template').lower().replace(' ', '_'))
                new_key = f"custom_{base_slug}_{int(time.time()) % 10000}" if base_slug else f"custom_{int(time.time())}"

                t_en = title_en or 'Custom AI Campaign'
                t_ta = title_ta or (title_en or 'தனிப்பயன் பிரச்சாரம்')

                body_en = body_text if target_lang == 'en' else data.get('body_en', body_text)
                body_ta = body_text if target_lang == 'ta' else data.get('body_ta', body_text)

                obj, created = save_or_overwrite_template(
                    key=new_key,
                    title_en=t_en,
                    title_ta=t_ta,
                    body_en=body_en,
                    body_ta=body_ta,
                    category=category,
                    badge=badge,
                    is_custom=True,
                    user=request.user
                )
                key = new_key
                msg = f"✨ New campaign preset '{t_en or t_ta}' saved to your library successfully!"

            return JsonResponse({
                'status': 'success',
                'message': msg,
                'template_key': key,
                'is_new': (action == 'save_as_new'),
            })

        except Exception as exc:
            logger.exception("Error saving marketing template")
            return JsonResponse({'status': 'error', 'message': str(exc)}, status=500)


class ImportMarketingLeadsView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    """
    Handles importing external prospect leads via CSV, manual single entry,
    clearing lead lists, or downloading sample CSV template.
    """
    def post(self, request):
        action = request.POST.get('action', 'import_csv')
        branch_id = request.POST.get('branch', '')
        segment = request.POST.get('segment', 'new_prospects')
        template_key = request.POST.get('template', 'festival_offer')
        lang = request.POST.get('lang', 'ta')
        save_as_customer = (request.POST.get('save_as_customer') == 'on' or request.POST.get('save_as_customer') == 'true')

        if action == 'import_csv':
            csv_file = request.FILES.get('lead_csv_file')
            if not csv_file:
                messages.error(request, "Please choose a CSV file to upload.")
                return redirect(reverse('digital_marketing') + f"?segment={segment}&template={template_key}&lang={lang}&branch={branch_id}")

            try:
                imported, skipped, errors = import_leads_from_csv(
                    csv_file,
                    branch_id=branch_id or None,
                    user=request.user,
                    save_as_customer=save_as_customer
                )
                if imported > 0:
                    messages.success(request, f"✨ Successfully imported {imported} new prospect leads! Ready to broadcast.")
                if skipped > 0:
                    messages.warning(request, f"⚠️ Skipped {skipped} rows due to invalid/missing phone numbers.")
            except Exception as e:
                messages.error(request, f"Error importing CSV: {e}")

        elif action == 'manual_add':
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            city = request.POST.get('city', '').strip()
            notes = request.POST.get('notes', '').strip()

            if not name or not phone:
                messages.error(request, "Customer Name and Phone Number are required.")
                return redirect(reverse('digital_marketing') + f"?segment=new_prospects&template={template_key}&lang={lang}&branch={branch_id}")

            try:
                lead = add_single_lead(
                    name=name,
                    phone_raw=phone,
                    city=city,
                    notes=notes,
                    branch_id=branch_id or None,
                    user=request.user,
                    save_as_customer=save_as_customer
                )
                messages.success(request, f"✅ Added '{lead.name}' ({lead.phone}) to your New Prospects Broadcast Queue!")
            except Exception as e:
                messages.error(request, f"Could not add prospect lead: {e}")

        elif action == 'clear_leads':
            cleared = clear_all_marketing_leads(branch_id=branch_id or None)
            messages.info(request, f"Cleared {cleared} prospect leads from the list.")

        return redirect(reverse('digital_marketing') + f"?segment=new_prospects&template={template_key}&lang={lang}&branch={branch_id}")

    def get(self, request):
        action = request.GET.get('action', 'download_sample')
        if action == 'download_sample':
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = 'attachment; filename="sample_prospect_leads.csv"'
            writer = csv.writer(response)
            writer.writerow(['Name', 'Phone', 'City', 'Notes'])
            writer.writerow(['Harikrishnan', '9876543210', 'Theni', 'Interested in Gold Loan'])
            writer.writerow(['Murugan K', '9443322110', 'Madurai', 'Festival Mela Enquiry'])
            writer.writerow(['Saravanan R', '9123456780', 'Bodi', 'New Prospect Lead'])
            writer.writerow(['Priya S', '8877665544', 'Cumbum', '0.99% Promo Lead'])
            return response
        return redirect('digital_marketing')



