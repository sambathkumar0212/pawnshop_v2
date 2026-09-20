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
from transactions.services_whatsapp_automator import (
    is_whatsapp_paired,
    get_whatsapp_session_info,
)
from transactions.services_marketing import (
    MARKETING_TEMPLATES,
    add_single_lead,
    build_broadcast_queue,
    clear_all_marketing_leads,
    delete_marketing_group,
    delete_or_reset_template,
    get_all_marketing_groups,
    get_all_marketing_templates,
    get_broadcast_status,
    get_campaign_analytics,
    get_segmented_audience,
    get_social_media_ad_copies,
    import_leads_from_csv,
    launch_pywhatkit_broadcast_async,
    log_campaign_broadcast,
    pause_automated_broadcast,
    render_campaign_message,
    resume_automated_broadcast,
    resume_remaining_broadcast,
    save_or_overwrite_template,
    stop_automated_broadcast,
)

logger = logging.getLogger(__name__)


class DigitalMarketingDashboardView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    """
    Main Digital Marketing & Campaign Studio Dashboard.
    Handles audience segmentation, Contact Groups, template selection, message editing,
    live queue building, and social media copy generation.
    """
    template_name = 'transactions/digital_marketing.html'

    def get(self, request):
        user_branch = getattr(request.user, 'branch', None)
        selected_branch_id = request.GET.get('branch', '')
        if not selected_branch_id and user_branch and not request.user.is_superuser:
            selected_branch_id = str(user_branch.id)

        segment = request.GET.get('segment', 'all')
        selected_group_id = request.GET.get('group', '')
        if not selected_group_id and segment.startswith('group_'):
            try:
                selected_group_id = segment.replace('group_', '')
            except Exception:
                selected_group_id = ''

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

        # Fetch Marketing Groups
        groups = get_all_marketing_groups(branch_id=selected_branch_id or None)
        active_group = None
        if selected_group_id:
            for g in groups:
                if str(g.id) == str(selected_group_id):
                    active_group = g
                    break

        # Fetch Segment Counts for KPIs
        all_aud = get_segmented_audience('all', branch_id=selected_branch_id or None)
        active_aud = get_segmented_audience('active_borrowers', branch_id=selected_branch_id or None)
        closed_aud = get_segmented_audience('closed_loans', branch_id=selected_branch_id or None)
        overdue_aud = get_segmented_audience('overdue', branch_id=selected_branch_id or None)
        high_val_aud = get_segmented_audience('high_value', branch_id=selected_branch_id or None)
        new_prospects_aud = get_segmented_audience('new_prospects', branch_id=selected_branch_id or None)
        birthday_aud = get_segmented_audience('birthday', branch_id=selected_branch_id or None)
        anniversary_aud = get_segmented_audience('anniversary', branch_id=selected_branch_id or None)

        kpis = {
            'total_customers': len(all_aud),
            'total_whatsapp_ready': sum(1 for c in all_aud if c['is_valid_whatsapp']),
            'active_borrowers_count': len(active_aud),
            'closed_prospects_count': len(closed_aud),
            'overdue_count': len(overdue_aud),
            'high_value_count': len(high_val_aud),
            'new_prospects_count': len(new_prospects_aud),
            'birthday_count': len(birthday_aud),
            'anniversary_count': len(anniversary_aud),
            'groups_count': len(groups),
        }

        # Dynamic marketing templates (merged with database saved/custom templates)
        all_marketing_templates = get_all_marketing_templates()
        current_template = all_marketing_templates.get(template_key) or all_marketing_templates.get('festival_offer') or next(iter(all_marketing_templates.values()), {})

        # Targeted Audience according to current segment selection or group
        target_audience = get_segmented_audience(
            segment_type=segment,
            branch_id=selected_branch_id or None,
            group_id=selected_group_id or None
        )
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

        # Fetch Campaign Broadcast Analytics & History
        campaign_analytics = get_campaign_analytics(branch_id=selected_branch_id or None, limit=50)

        # Raw template body with dynamic variables for editor textarea
        raw_template_body = current_template.get('body_ta' if use_tamil else 'body_en', '')

        context = {
            'segment': segment,
            'selected_group_id': selected_group_id,
            'selected_group': selected_group_id,
            'selected_group_obj': active_group,
            'active_group': active_group,
            'groups': groups,
            'template_key': template_key,
            'lang': lang,
            'use_tamil': use_tamil,
            'selected_branch_id': selected_branch_id,
            'branches': branches,
            'kpis': kpis,
            'campaign_analytics': campaign_analytics,
            'marketing_templates': all_marketing_templates,
            'current_template': current_template,
            'raw_template_body': raw_template_body,
            'broadcast_queue': broadcast_queue,
            'total_queue_count': len(broadcast_queue),
            'valid_whatsapp_count': sum(1 for item in broadcast_queue if item.get('is_valid_whatsapp')),
            'invalid_whatsapp_count': sum(1 for item in broadcast_queue if not item.get('is_valid_whatsapp')),
            'sample_preview_text': sample_preview_text,
            'social_copies': social_copies,
            'schemes': schemes,
            'current_gold_rate': current_gold_rate,
            'is_whatsapp_paired': is_whatsapp_paired(),
            'whatsapp_session': get_whatsapp_session_info(),
            'organization_name': getattr(settings, 'ORGANIZATION_NAME', 'First Money Gold'),
        }
        return render(request, self.template_name, context)


class ExecuteBroadcastActionView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    """
    POST-only action to launch automated background Playwright broadcast or download audience CSV.
    """
    def post(self, request):
        is_ajax = (request.headers.get('x-requested-with') == 'XMLHttpRequest' or 
                   request.content_type == 'application/json')

        action = request.POST.get('action', 'pywhatkit_broadcast')
        segment = request.POST.get('segment', 'all')
        group_id = request.POST.get('group', '')
        if not group_id and segment.startswith('group_'):
            try:
                group_id = segment.replace('group_', '')
            except Exception:
                group_id = ''

        template_key = request.POST.get('template', 'festival_offer')
        lang = request.POST.get('lang', 'ta')
        branch_id = request.POST.get('branch', '')
        custom_message = request.POST.get('custom_message', '').strip() or None
        delay_seconds = int(request.POST.get('delay_seconds', 5))

        use_tamil = (lang == 'ta')
        target_audience = get_segmented_audience(
            segment_type=segment,
            branch_id=branch_id or None,
            group_id=group_id or None
        )
        broadcast_queue = build_broadcast_queue(
            target_audience,
            template_key=template_key,
            use_tamil=use_tamil,
            custom_body=custom_message
        )

        # Check if user selected specific contacts in the UI table
        selected_phones_raw = request.POST.get('selected_phones', '').strip()
        selected_contacts_json = request.POST.get('selected_contacts_json', '').strip()
        
        target_phones = set()
        target_customer_ids = set()
        target_lead_ids = set()

        if selected_phones_raw:
            target_phones.update(p.strip() for p in selected_phones_raw.split(',') if p.strip())

        if selected_contacts_json:
            try:
                import json
                contacts_list = json.loads(selected_contacts_json)
                if isinstance(contacts_list, list):
                    for c in contacts_list:
                        if isinstance(c, dict):
                            if c.get('phone'):
                                target_phones.add(str(c.get('phone')).strip())
                            if c.get('customer_id'):
                                target_customer_ids.add(str(c.get('customer_id')).strip())
                            if c.get('lead_id'):
                                target_lead_ids.add(str(c.get('lead_id')).strip())
                        elif isinstance(c, str):
                            target_phones.add(c.strip())
            except Exception as e:
                logger.warning(f"Error parsing selected_contacts_json: {e}")

        def normalize_phone_match(phone_str):
            if not phone_str:
                return ''
            digits = ''.join(c for c in str(phone_str) if c.isdigit())
            return digits[-10:] if len(digits) >= 10 else digits

        if target_phones or target_customer_ids or target_lead_ids:
            normalized_target_phones = {normalize_phone_match(p) for p in target_phones if normalize_phone_match(p)}
            filtered_queue = []
            for item in broadcast_queue:
                c_id = str(item.get('customer_id') or '').strip()
                l_id = str(item.get('lead_id') or '').strip()
                p_norm = normalize_phone_match(item.get('phone', ''))

                if target_customer_ids and c_id and c_id in target_customer_ids:
                    filtered_queue.append(item)
                elif target_lead_ids and l_id and l_id in target_lead_ids:
                    filtered_queue.append(item)
                elif normalized_target_phones and p_norm and p_norm in normalized_target_phones:
                    filtered_queue.append(item)

            if filtered_queue:
                broadcast_queue = filtered_queue

        # Filter out invalid / non-WhatsApp numbers automatically for broadcast execution
        if action in ('pywhatkit_broadcast', 'automated_blast', 'headless_broadcast'):
            broadcast_queue = [item for item in broadcast_queue if item.get('is_valid_whatsapp', True)]

        redirect_url = reverse('digital_marketing') + f"?segment={segment}&template={template_key}&lang={lang}&branch={branch_id}"
        if group_id:
            redirect_url += f"&group={group_id}"

        if not broadcast_queue:
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': 'No valid WhatsApp contacts found for the selection.'}, status=400)
            messages.warning(request, "No valid WhatsApp contacts found for the selection.")
            return redirect(redirect_url)

        if action == 'export_csv':
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="whatsapp_broadcast_{segment}_{template_key}.csv"'
            writer = csv.writer(response)
            writer.writerow(['Customer ID', 'Name', 'Phone Number', 'Group', 'City', 'Branch', 'WhatsApp Direct URL', 'Personalized Message'])
            for row in broadcast_queue:
                writer.writerow([
                    row['customer_id'],
                    row['name'],
                    row['phone'],
                    row.get('group_name', ''),
                    row['city'],
                    row['branch_name'],
                    row['whatsapp_url'],
                    row['message']
                ])
            return response

        elif action in ('pywhatkit_broadcast', 'automated_blast', 'headless_broadcast'):
            # Verify WhatsApp session is paired
            if not is_whatsapp_paired():
                err_msg = "WhatsApp Web session is not paired! Please pair your WhatsApp session from 24/7 Autopilot or Loans page before launching an automated campaign."
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': err_msg, 'unpaired': True}, status=400)
                messages.error(request, err_msg)
                return redirect(redirect_url)

            send_mode = request.POST.get('send_mode', 'message_and_image')  # 'message_and_image', 'image_only', 'message_only'
            campaign_image_file = request.FILES.get('campaign_image')
            campaign_image_base64 = request.POST.get('campaign_image_base64', '').strip()

            saved_image_path = None
            if send_mode != 'message_only':
                try:
                    import base64
                    import os
                    import time
                    from io import BytesIO
                    from PIL import Image

                    campaigns_dir = os.path.join(settings.BASE_DIR, 'media', 'campaigns')
                    os.makedirs(campaigns_dir, exist_ok=True)

                    if campaign_image_file:
                        filename = f"campaign_flyer_{int(time.time())}_{request.user.id}.png"
                        filepath = os.path.abspath(os.path.join(campaigns_dir, filename))
                        
                        try:
                            img = Image.open(campaign_image_file)
                            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                                img = img.convert('RGBA')
                            else:
                                img = img.convert('RGB')
                            img.save(filepath, format='PNG')
                            saved_image_path = filepath
                        except Exception:
                            campaign_image_file.seek(0)
                            with open(filepath, 'wb+') as destination:
                                for chunk in campaign_image_file.chunks():
                                    destination.write(chunk)
                            saved_image_path = filepath

                    elif campaign_image_base64:
                        if 'base64,' in campaign_image_base64:
                            _, encoded = campaign_image_base64.split('base64,', 1)
                        else:
                            encoded = campaign_image_base64

                        file_data = base64.b64decode(encoded)
                        filename = f"campaign_flyer_{int(time.time())}_{request.user.id}.png"
                        filepath = os.path.abspath(os.path.join(campaigns_dir, filename))

                        try:
                            img = Image.open(BytesIO(file_data))
                            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                                img = img.convert('RGBA')
                            else:
                                img = img.convert('RGB')
                            img.save(filepath, format='PNG')
                            saved_image_path = filepath
                        except Exception:
                            with open(filepath, 'wb') as f:
                                f.write(file_data)
                            saved_image_path = filepath

                    if saved_image_path and os.path.exists(saved_image_path) and os.path.getsize(saved_image_path) > 0:
                        logger.info("Campaign flyer image saved successfully: %s (%d bytes)", saved_image_path, os.path.getsize(saved_image_path))
                    else:
                        saved_image_path = None

                except Exception as exc:
                    logger.warning("Could not process campaign image attachment: %s", exc)

            started = launch_pywhatkit_broadcast_async(
                broadcast_queue,
                delay_seconds=delay_seconds,
                image_path=saved_image_path,
                send_mode=send_mode,
                user=request.user
            )
            if started:
                mode_desc = (
                    "Image Flyer + Message"
                    if (saved_image_path and send_mode != 'image_only')
                    else ("Image Flyer Only" if (saved_image_path and send_mode == 'image_only') else "Personalized Text Message")
                )
                success_msg = (
                    f"🚀 Automated WhatsApp Campaign launched in background for {len(broadcast_queue)} contacts "
                    f"({mode_desc}, {delay_seconds}s safe interval). Delivery is running automatically in background!"
                )
                if is_ajax:
                    return JsonResponse({
                        'status': 'success',
                        'message': success_msg,
                        'total': len(broadcast_queue),
                        'delay_seconds': delay_seconds
                    })
                messages.success(request, success_msg)
            else:
                fail_msg = "Failed to initiate automated background broadcast."
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': fail_msg}, status=500)
                messages.error(request, fail_msg)

        return redirect(redirect_url)


class MarketingBroadcastStatusView(LoginRequiredMixin, View):
    """
    AJAX endpoint: Returns real-time execution progress of background WhatsApp broadcasts.
    """
    def get(self, request):
        status_data = get_broadcast_status()
        status_data['is_whatsapp_paired'] = is_whatsapp_paired()
        status_data['whatsapp_session'] = get_whatsapp_session_info()
        return JsonResponse(status_data)


class MarketingBroadcastControlView(LoginRequiredMixin, View):
    """
    AJAX endpoint: Pauses, Resumes, or Stops the active automated WhatsApp background campaign.
    """
    def post(self, request):
        try:
            import json
            data = {}
            if request.body:
                try:
                    data = json.loads(request.body.decode('utf-8'))
                except Exception:
                    data = request.POST.dict()
            else:
                data = request.POST.dict()

            action = str(data.get('action', '')).lower().strip()
            if action == 'pause':
                success = pause_automated_broadcast()
                msg = "Campaign paused." if success else "Campaign is not currently running."
            elif action == 'resume':
                success = resume_automated_broadcast()
                msg = "Campaign resumed." if success else "Campaign is not currently running or paused."
            elif action == 'resume_remaining':
                success, msg = resume_remaining_broadcast(user=request.user)
            elif action == 'stop':
                success = stop_automated_broadcast()
                msg = "Campaign stopped successfully." if success else "No active campaign to stop."
            else:
                return JsonResponse({'status': 'error', 'message': f"Invalid control action '{action}'."}, status=400)

            current_status = get_broadcast_status()
            current_status['is_whatsapp_paired'] = is_whatsapp_paired()
            current_status['whatsapp_session'] = get_whatsapp_session_info()
            return JsonResponse({
                'status': 'success',
                'action': action,
                'message': msg,
                'broadcast_status': current_status
            })
        except Exception as e:
            logger.exception("Error in MarketingBroadcastControlView")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


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
            data = {}
            if request.body:
                try:
                    data = json.loads(request.body.decode('utf-8'))
                except Exception:
                    data = request.POST.dict()
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
    Handles importing external prospect leads into Contact Groups via CSV,
    manual single entry, group management, clearing lists, or downloading sample CSV.
    """
    def post(self, request):
        action = request.POST.get('action', 'import_csv')
        branch_id = request.POST.get('branch', '')
        segment = request.POST.get('segment', 'new_prospects')
        template_key = request.POST.get('template', 'festival_offer')
        lang = request.POST.get('lang', 'ta')
        save_as_customer = (request.POST.get('save_as_customer') == 'on' or request.POST.get('save_as_customer') == 'true')

        group_option = request.POST.get('group_option', '').strip()  # 'new', 'existing', 'unassigned'
        existing_group_id = request.POST.get('existing_group_id', '').strip()
        new_group_name = request.POST.get('new_group_name', '').strip()
        group_description = request.POST.get('group_description', '').strip()
        group_fallback = request.POST.get('group', request.GET.get('group', '')).strip()

        target_group_id = None
        target_group_name = None

        if group_option == 'existing':
            if existing_group_id:
                try:
                    target_group_id = int(existing_group_id)
                except (ValueError, TypeError):
                    target_group_id = None
            elif group_fallback:
                try:
                    target_group_id = int(group_fallback)
                except (ValueError, TypeError):
                    target_group_id = None
            elif segment.startswith('group_'):
                try:
                    target_group_id = int(segment.replace('group_', ''))
                except (ValueError, TypeError):
                    target_group_id = None
        elif group_option == 'new':
            if new_group_name:
                target_group_name = new_group_name
            elif existing_group_id:
                try:
                    target_group_id = int(existing_group_id)
                except (ValueError, TypeError):
                    target_group_id = None
            elif group_fallback:
                try:
                    target_group_id = int(group_fallback)
                except (ValueError, TypeError):
                    target_group_id = None
            elif segment.startswith('group_'):
                try:
                    target_group_id = int(segment.replace('group_', ''))
                except (ValueError, TypeError):
                    target_group_id = None
        elif group_option == 'unassigned':
            target_group_id = None
            target_group_name = None
        else:
            # Fallback when group_option radio was not explicitly set
            if existing_group_id:
                try:
                    target_group_id = int(existing_group_id)
                except (ValueError, TypeError):
                    pass
            elif group_fallback:
                try:
                    target_group_id = int(group_fallback)
                except (ValueError, TypeError):
                    pass
            elif segment.startswith('group_'):
                try:
                    target_group_id = int(segment.replace('group_', ''))
                except (ValueError, TypeError):
                    pass
            elif new_group_name:
                target_group_name = new_group_name

        if action == 'import_csv':
            csv_file = request.FILES.get('lead_csv_file')
            if not csv_file:
                messages.error(request, "Please choose a CSV file to upload.")
                return redirect(reverse('digital_marketing') + f"?segment={segment}&template={template_key}&lang={lang}&branch={branch_id}")

            try:
                imported, skipped, errors, group = import_leads_from_csv(
                    csv_file,
                    branch_id=branch_id or None,
                    user=request.user,
                    save_as_customer=save_as_customer,
                    group_id=target_group_id,
                    new_group_name=target_group_name,
                    group_description=group_description
                )
                if group:
                    total_in_grp = group.leads.count()
                    group_tag = f" into Group '{group.name}' (Total: {total_in_grp} contacts)"
                else:
                    group_tag = ""

                if imported > 0:
                    messages.success(request, f"✨ Successfully added {imported} contacts{group_tag}! Ready to broadcast.")
                if skipped > 0:
                    messages.warning(request, f"⚠️ Skipped {skipped} rows due to invalid/missing phone numbers.")

                target_seg = f"group_{group.id}" if group else "new_prospects"
                group_param = f"&group={group.id}" if group else ""
                return redirect(reverse('digital_marketing') + f"?segment={target_seg}{group_param}&template={template_key}&lang={lang}&branch={branch_id}")
            except Exception as e:
                messages.error(request, f"Error importing CSV: {e}")

        elif action == 'manual_add':
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            city = request.POST.get('city', '').strip()
            notes = request.POST.get('notes', '').strip()

            if not name or not phone:
                messages.error(request, "Customer Name and Phone Number are required.")
                return redirect(reverse('digital_marketing') + f"?segment={segment}&template={template_key}&lang={lang}&branch={branch_id}")

            try:
                lead, group = add_single_lead(
                    name=name,
                    phone_raw=phone,
                    city=city,
                    notes=notes,
                    branch_id=branch_id or None,
                    user=request.user,
                    save_as_customer=save_as_customer,
                    group_id=target_group_id,
                    new_group_name=target_group_name,
                    group_description=group_description
                )
                if group:
                    total_in_grp = group.leads.count()
                    group_tag = f" to Group '{group.name}' (Total: {total_in_grp} contacts)"
                else:
                    group_tag = ""

                messages.success(request, f"✅ Added '{lead.name}' ({lead.phone}){group_tag} to your Broadcast Queue!")
                target_seg = f"group_{group.id}" if group else "new_prospects"
                group_param = f"&group={group.id}" if group else ""
                return redirect(reverse('digital_marketing') + f"?segment={target_seg}{group_param}&template={template_key}&lang={lang}&branch={branch_id}")
            except Exception as e:
                messages.error(request, f"Could not add contact: {e}")

        elif action == 'delete_lead':
            lead_id = request.POST.get('lead_id')
            grp_id = request.POST.get('group_id')
            if lead_id:
                try:
                    from transactions.models import MarketingLead
                    lead = MarketingLead.objects.get(id=lead_id)
                    lead_name = lead.name
                    if not grp_id and lead.group_id:
                        grp_id = str(lead.group_id)
                    lead.delete()
                    messages.success(request, f"🗑️ Removed contact '{lead_name}' from the group.")
                except Exception as e:
                    messages.error(request, f"Could not remove contact: {e}")
            target_seg = f"group_{grp_id}" if grp_id else "new_prospects"
            group_param = f"&group={grp_id}" if grp_id else ""
            return redirect(reverse('digital_marketing') + f"?segment={target_seg}{group_param}&template={template_key}&lang={lang}&branch={branch_id}")

        elif action == 'delete_group':
            del_group_id = request.POST.get('delete_group_id')
            if del_group_id:
                success, g_name = delete_marketing_group(del_group_id, delete_leads=True)
                if success:
                    messages.success(request, f"🗑️ Deleted Contact Group '{g_name}' and its contacts.")
                else:
                    messages.error(request, f"Could not delete group: {g_name}")
            return redirect(reverse('digital_marketing') + f"?segment=all&template={template_key}&lang={lang}&branch={branch_id}")

        elif action == 'clear_leads':
            group_filter_id = request.POST.get('clear_group_id') or None
            cleared = clear_all_marketing_leads(branch_id=branch_id or None, group_id=group_filter_id)
            messages.info(request, f"Cleared {cleared} contacts from the list.")

        return redirect(reverse('digital_marketing') + f"?segment=new_prospects&template={template_key}&lang={lang}&branch={branch_id}")

    def get(self, request):
        action = request.GET.get('action', 'download_sample')
        if action == 'download_sample':
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = 'attachment; filename="sample_prospect_contacts.csv"'
            writer = csv.writer(response)
            writer.writerow(['Name', 'Phone', 'City', 'Notes'])
            writer.writerow(['Harikrishnan', '9876543210', 'Theni', 'Interested in Gold Loan'])
            writer.writerow(['Murugan K', '9443322110', 'Madurai', 'Festival Mela Enquiry'])
            writer.writerow(['Saravanan R', '9123456780', 'Bodi', 'VIP Prospect'])
            writer.writerow(['Priya S', '8877665544', 'Cumbum', '0.99% Promo Lead'])
            return response
        return redirect('digital_marketing')


class GroupContactsAPIView(LoginRequiredMixin, View):
    """
    AJAX endpoint: Returns all contacts in a specified MarketingGroup.
    """
    def get(self, request):
        group_id = request.GET.get('group_id')
        if not group_id:
            return JsonResponse({'status': 'error', 'message': 'Missing group_id parameter.'}, status=400)

        try:
            from transactions.models import MarketingGroup, MarketingLead
            from transactions.services_marketing import get_known_non_whatsapp_phones, get_phone_whatsapp_status, normalize_phone_number
            group = MarketingGroup.objects.get(id=group_id)
            leads = MarketingLead.objects.filter(group=group).order_by('-created_at')

            known_non_wa = get_known_non_whatsapp_phones()
            contacts = []
            for lead in leads:
                raw_phone = lead.phone or ''
                norm_phone = lead.norm_phone or normalize_phone_number(raw_phone)
                is_valid, status_msg, status_code = get_phone_whatsapp_status(raw_phone, norm_phone, known_non_wa)
                contacts.append({
                    'id': lead.id,
                    'name': lead.name or 'Valued Customer',
                    'phone': raw_phone,
                    'norm_phone': norm_phone,
                    'is_valid_whatsapp': is_valid,
                    'whatsapp_status_msg': status_msg,
                    'whatsapp_status_code': status_code,
                    'city': lead.city or '',
                    'notes': lead.notes or '',
                    'source': lead.source,
                    'created_at': lead.created_at.strftime('%d %b %Y, %I:%M %p') if lead.created_at else '',
                })

            return JsonResponse({
                'status': 'success',
                'group': {
                    'id': group.id,
                    'name': group.name,
                    'description': group.description or '',
                    'contact_count': len(contacts),
                    'created_at': group.created_at.strftime('%d %b %Y') if group.created_at else '',
                },
                'contacts': contacts,
            })
        except MarketingGroup.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Group not found.'}, status=404)
        except Exception as e:
            logger.exception("Error in GroupContactsAPIView")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


class ResetWhatsAppStatusAPIView(LoginRequiredMixin, View):
    """
    API endpoint to clear/reset non-WhatsApp flags for a specific contact or all contacts.
    Allows manual recheck/re-verification before sending broadcast messages.
    """
    def post(self, request, *args, **kwargs):
        try:
            import json
            data = {}
            if request.body:
                try:
                    data = json.loads(request.body.decode('utf-8'))
                except Exception:
                    data = request.POST.dict()
            else:
                data = request.POST.dict()

            phone = str(data.get('phone', '')).strip()
            clear_all = data.get('clear_all') in [True, 'true', '1', 1]

            from transactions.services_marketing import clear_non_whatsapp_flag, get_known_non_whatsapp_phones, get_phone_whatsapp_status, normalize_phone_number
            res = clear_non_whatsapp_flag(phone=phone, clear_all=clear_all)

            known_non_wa = get_known_non_whatsapp_phones()
            norm_phone = normalize_phone_number(phone) if phone else ''
            is_valid, status_msg, status_code = get_phone_whatsapp_status(phone, norm_phone, known_non_wa) if phone else (True, 'WhatsApp Ready', 'valid')

            return JsonResponse({
                'status': 'success',
                'cleared_count': res.get('cleared_count', 0),
                'phone': phone,
                'norm_phone': norm_phone,
                'is_valid_whatsapp': is_valid,
                'whatsapp_status_msg': status_msg,
                'whatsapp_status_code': status_code,
                'message': f"All WhatsApp verification flags cleared ({res.get('cleared_count', 0)} records reset)." if clear_all else f"WhatsApp status for {phone} has been reset to Ready."
            })
        except Exception as e:
            logger.exception("Error in ResetWhatsAppStatusAPIView")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



class LogBroadcastAPIView(LoginRequiredMixin, View):
    """
    AJAX endpoint: Records an individual or batch WhatsApp Web broadcast click / delivery
    into the audit log and marks the contact as contacted.
    """
    def post(self, request):
        import json
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode('utf-8'))
            else:
                data = request.POST

            template_key = data.get('template_key', '')
            campaign_name = data.get('campaign_name', 'Broadcast')
            recipient_name = data.get('recipient_name', 'Valued Customer')
            recipient_phone = data.get('recipient_phone', '')
            recipient_type = data.get('recipient_type', 'customer')
            group_id = data.get('group_id') or None
            branch_id = data.get('branch_id') or None
            channel = data.get('channel', 'whatsapp_web')
            status = data.get('status', 'sent')
            message_snippet = data.get('message_snippet', '')

            log_entry = log_campaign_broadcast(
                template_key=template_key,
                campaign_name=campaign_name,
                recipient_name=recipient_name,
                recipient_phone=recipient_phone,
                recipient_type=recipient_type,
                group_id=group_id,
                branch_id=branch_id,
                channel=channel,
                status=status,
                message_snippet=message_snippet,
                user=request.user
            )

            return JsonResponse({
                'status': 'success',
                'log_id': log_entry.id,
                'recipient': recipient_name,
                'sent_at': log_entry.created_at.strftime('%d %b %Y, %I:%M %p')
            })
        except Exception as exc:
            logger.warning("Error logging campaign broadcast: %s", exc)
            return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)


class ExportCampaignLogsView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    """
    Exports full campaign broadcast history logs to a CSV report.
    """
    def get(self, request):
        branch_id = request.GET.get('branch', '')
        channel = request.GET.get('channel', '')
        group_id = request.GET.get('group', '')

        from transactions.models import MarketingCampaignLog
        qs = MarketingCampaignLog.objects.all().select_related('group', 'branch', 'sent_by').order_by('-created_at')

        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        if channel:
            qs = qs.filter(channel=channel)
        if group_id:
            qs = qs.filter(group_id=group_id)

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="marketing_campaign_broadcast_history.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Log ID', 'Timestamp', 'Campaign / Template', 'Recipient Name',
            'Phone', 'Type', 'Group', 'Branch', 'Channel', 'Status', 'Sent By', 'Message Snippet'
        ])

        for log in qs:
            writer.writerow([
                log.id,
                log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                log.campaign_name or log.template_key,
                log.recipient_name,
                log.recipient_phone,
                log.recipient_type,
                log.group.name if log.group else 'N/A',
                log.branch.name if log.branch else 'All Branches',
                log.get_channel_display(),
                log.get_status_display(),
                log.sent_by.username if log.sent_by else 'System',
                (log.message_snippet or '').replace('\n', ' ')[:250]
            ])

        return response





