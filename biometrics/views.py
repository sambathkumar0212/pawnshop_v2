from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Avg
from .models import BiometricSetting, FaceEnrollment, CustomerFaceEnrollment, FaceAuthLog
from branches.models import Branch
from django.contrib.auth import get_user_model

User = get_user_model()

# Placeholder views for biometrics functionality
class UserFaceEnrollmentView(LoginRequiredMixin, TemplateView):
    template_name = 'biometrics/user_face_enrollment.html'


class UserFaceCaptureView(LoginRequiredMixin, View):
    def post(self, request):
        # This would implement the face capture logic
        return JsonResponse({'status': 'success'})


class UserFaceVerificationView(LoginRequiredMixin, View):
    def post(self, request):
        # This would implement face verification logic
        return JsonResponse({'status': 'success', 'verified': True})


class CustomerFaceEnrollmentView(LoginRequiredMixin, TemplateView):
    template_name = 'biometrics/customer_face_enrollment.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer_id'] = self.kwargs.get('customer_id')
        return context


class CustomerFaceCaptureView(LoginRequiredMixin, View):
    def post(self, request, customer_id):
        # This would implement the customer face capture logic
        return JsonResponse({'status': 'success'})


class CustomerFaceVerificationView(LoginRequiredMixin, View):
    def post(self, request, customer_id):
        # This would implement customer face verification logic
        return JsonResponse({'status': 'success', 'verified': True})


class FaceLoginView(View):
    def get(self, request):
        return render(request, 'biometrics/face_login.html')
    
    def post(self, request):
        # This would implement face login logic
        return JsonResponse({'status': 'success'})


class CustomerIdentificationView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'biometrics/customer_identify.html')
    
    def post(self, request):
        # This would implement customer identification logic
        return JsonResponse({'status': 'success'})


class BiometricSettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'biometrics/biometric_settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get global settings (using first branch as default if exists)
        context['settings'] = BiometricSetting.objects.first()
        
        # Get all branches with their biometric settings
        branches = Branch.objects.all()
        
        # Ensure each branch has associated biometric settings
        for branch in branches:
            # Create biometric settings for branch if they don't exist
            BiometricSetting.objects.get_or_create(
                branch=branch,
                defaults={
                    'min_confidence': 0.6,
                    'max_attempts': 3,
                    'lockout_duration': timezone.timedelta(minutes=30),
                    'require_liveness': True,
                    'allow_customer_enrollment': True,
                    'face_recognition_enabled': False,
                    'fingerprint_enabled': False,
                    'face_recognition_required_for_staff': False,
                    'face_recognition_required_for_customers': False,
                }
            )
        
        # Now fetch all branches again with their settings properly prefetched
        context['branches'] = Branch.objects.prefetch_related('biometric_settings').all()

        # Calculate enrollment statistics
        total_staff = User.objects.filter(is_staff=True).count()
        staff_enrolled = FaceEnrollment.objects.filter(user__is_staff=True, is_active=True).count()
        total_customers = User.objects.filter(is_staff=False).count()
        customers_enrolled = CustomerFaceEnrollment.objects.filter(is_active=True).count()

        context.update({
            'total_staff': total_staff,
            'staff_enrolled': staff_enrolled,
            'total_customers': total_customers,
            'customers_enrolled': customers_enrolled,
            'staff_enrolled_percentage': (staff_enrolled / total_staff * 100) if total_staff > 0 else 0,
            'customers_enrolled_percentage': (customers_enrolled / total_customers * 100) if total_customers > 0 else 0,
        })

        return context

    def post(self, request, *args, **kwargs):
        try:
            # Get or create global settings
            settings = BiometricSetting.objects.first()
            if not settings:
                # Create settings for the first branch if no settings exist
                first_branch = Branch.objects.first()
                if not first_branch:
                    messages.error(request, "No branches exist in the system. Please create a branch first.")
                    return redirect('biometric_settings')
                settings = BiometricSetting(branch=first_branch)

            # Update settings from form data
            settings.face_recognition_enabled = request.POST.get('face_recognition_enabled') == 'on'
            settings.face_recognition_required_for_staff = request.POST.get('face_recognition_required_for_staff') == 'on'
            settings.face_recognition_required_for_customers = request.POST.get('face_recognition_required_for_customers') == 'on'
            settings.fingerprint_enabled = request.POST.get('fingerprint_enabled') == 'on'
            
            # Handle threshold value
            threshold = request.POST.get('face_recognition_threshold')
            if threshold:
                settings.face_recognition_threshold = float(threshold)

            settings.updated_by = request.user
            settings.save()

            messages.success(request, "Biometric settings updated successfully.")
        except Exception as e:
            messages.error(request, f"Error updating settings: {str(e)}")

        return redirect('biometric_settings')


class BranchBiometricSettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'biometrics/branch_biometric_settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        branch_id = self.kwargs.get('branch_id')
        
        try:
            branch = Branch.objects.get(id=branch_id)
            context['branch'] = branch
            
            # Get or initialize branch-specific biometric settings
            branch_settings, created = BiometricSetting.objects.get_or_create(
                branch=branch,
                defaults={
                    'min_confidence': 0.6,
                    'max_attempts': 3,
                    'lockout_duration': timezone.timedelta(minutes=30),
                    'require_liveness': True,
                    'allow_customer_enrollment': True,
                    'face_recognition_enabled': True,
                    'fingerprint_enabled': False,
                    'face_recognition_required_for_staff': False,
                    'face_recognition_required_for_customers': False,
                }
            )
            
            context['branch_settings'] = branch_settings
            if created:
                messages.info(self.request, f"Initial biometric settings created for {branch.name}.")
                
        except Branch.DoesNotExist:
            messages.error(self.request, f"Branch with ID {branch_id} not found.")
            context['branch'] = None
            context['branch_settings'] = None
            
        return context
    
    def post(self, request, *args, **kwargs):
        branch_id = self.kwargs.get('branch_id')
        
        try:
            branch = Branch.objects.get(id=branch_id)
            
            # Get or create branch settings
            branch_settings, created = BiometricSetting.objects.get_or_create(branch=branch)
            
            # Update settings from form data
            branch_settings.face_recognition_enabled = request.POST.get('face_recognition_enabled') == 'on'
            branch_settings.face_recognition_required_for_staff = request.POST.get('face_recognition_required_for_staff') == 'on'
            branch_settings.face_recognition_required_for_customers = request.POST.get('face_recognition_required_for_customers') == 'on'
            branch_settings.fingerprint_enabled = request.POST.get('fingerprint_enabled') == 'on'
            branch_settings.require_liveness = request.POST.get('require_liveness') == 'on'
            branch_settings.allow_customer_enrollment = request.POST.get('allow_customer_enrollment') == 'on'
            
            # Handle numeric values
            if min_confidence := request.POST.get('min_confidence'):
                branch_settings.min_confidence = float(min_confidence)
            
            if max_attempts := request.POST.get('max_attempts'):
                branch_settings.max_attempts = int(max_attempts)
            
            if lockout_minutes := request.POST.get('lockout_duration_minutes'):
                branch_settings.lockout_duration = timezone.timedelta(minutes=int(lockout_minutes))
            
            # Save who updated the settings
            branch_settings.updated_by = request.user
            branch_settings.save()
            
            messages.success(request, f"Biometric settings for {branch.name} updated successfully.")
            
        except Branch.DoesNotExist:
            messages.error(request, f"Branch with ID {branch_id} not found.")
        except Exception as e:
            messages.error(request, f"Error updating branch settings: {str(e)}")
        
        return redirect('branch_biometric_settings', branch_id=branch_id)

class BiometricLogListView(LoginRequiredMixin, ListView):
    template_name = 'biometrics/biometric_logs.html'
    context_object_name = 'logs'
    paginate_by = 20  # Show 20 logs per page
    
    def get_queryset(self):
        queryset = FaceAuthLog.objects.all().order_by('-timestamp')
        
        # Apply filters based on GET parameters
        if date_from := self.request.GET.get('date_from'):
            queryset = queryset.filter(timestamp__gte=date_from)
            
        if date_to := self.request.GET.get('date_to'):
            queryset = queryset.filter(timestamp__lte=date_to)
            
        if success := self.request.GET.get('success'):
            queryset = queryset.filter(success=(success == 'true'))
            
        if user_type := self.request.GET.get('type'):
            if user_type == 'staff':
                queryset = queryset.exclude(user__isnull=True)
            elif user_type == 'customer':
                queryset = queryset.exclude(customer__isnull=True)
                
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all logs for calculating statistics (regardless of pagination)
        all_logs = self.get_queryset()
        total_logs = all_logs.count()
        successful_logs = all_logs.filter(success=True).count()
        
        # Calculate statistics for dashboard cards
        context['total_logs'] = total_logs
        context['success_rate'] = round((successful_logs / total_logs) * 100) if total_logs > 0 else 0
        
        # Recent failures (in the last 24 hours)
        one_day_ago = timezone.now() - timezone.timedelta(days=1)
        context['recent_failures'] = all_logs.filter(
            success=False, 
            timestamp__gte=one_day_ago
        ).count()
        
        # Average confidence score (only for successful authentications)
        avg_confidence = all_logs.filter(
            success=True, 
            confidence__isnull=False
        ).aggregate(Avg('confidence'))['confidence__avg']
        
        context['avg_confidence'] = avg_confidence if avg_confidence else 0
        
        return context
        
    def render_to_response(self, context, **response_kwargs):
        # Check if CSV export is requested
        if self.request.GET.get('export') == 'csv':
            return self.export_csv(context['logs'])
        return super().render_to_response(context, **response_kwargs)
        
    def export_csv(self, logs):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="biometric_logs.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Timestamp', 'User Type', 'User/Customer', 'Success', 
            'Confidence', 'IP Address', 'Device Info'
        ])
        
        for log in logs:
            # Determine user type and name
            if log.user:
                user_type = 'Staff'
                name = log.user.get_full_name() or log.user.username
            elif log.customer:
                user_type = 'Customer'
                name = log.customer.get_full_name()
            else:
                user_type = 'Unknown'
                name = 'Unknown'
                
            writer.writerow([
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                user_type,
                name,
                'Success' if log.success else 'Failed',
                f"{log.confidence:.2f}" if log.confidence else 'N/A',
                log.ip_address or 'N/A',
                log.device_info or 'N/A',
            ])
            
        return response
