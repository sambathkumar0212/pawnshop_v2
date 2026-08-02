from django.contrib.auth import get_user_model
from django.db import transaction
from .models import Role, UserActivity

User = get_user_model()

def assign_role_to_user(user, role_name, request=None):
    """
    Assign a role to a user and set up appropriate permissions
    
    Args:
        user: CustomUser instance
        role_name: String name of the role to assign
        request: Optional HTTP request object for activity logging
    """
    with transaction.atomic():
        try:
            role = Role.objects.get(name=role_name)
            
            # Assign role
            user.role = role
            user.save()
            
            # Log the activity if request is provided
            if request:
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='role_assigned',
                    description=f'Assigned role {role.name} to user {user.username}',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
            return True, f"Successfully assigned role {role.name} to {user.username}"
            
        except Role.DoesNotExist:
            return False, f"Role '{role_name}' does not exist"
        except Exception as e:
            return False, f"Error assigning role: {str(e)}"

def get_user_permissions_by_app(user):
    """
    Get all permissions for a user, grouped by app
    
    Args:
        user: CustomUser instance
        
    Returns:
        dict: Permissions grouped by app label
    """
    if not user.is_active:
        return {}
        
    # Get all permissions from the user's role and direct permissions
    all_perms = set()
    if user.role:
        all_perms.update(user.role.permissions.all())
    all_perms.update(user.user_permissions.all())
    
    # Group by app
    from itertools import groupby
    from operator import attrgetter
    
    sorted_perms = sorted(all_perms, key=lambda p: p.content_type.app_label)
    return {
        app: list(perms)
        for app, perms in groupby(sorted_perms, key=lambda p: p.content_type.app_label)
    }

def check_user_permission(user, permission_codename):
    """
    Check if a user has a specific permission
    
    Args:
        user: CustomUser instance
        permission_codename: String codename of the permission to check
        
    Returns:
        bool: True if user has the permission, False otherwise
    """
    if not user.is_active:
        return False
    
    # Superusers have all permissions
    if user.is_superuser:
        return True
        
    # Check role permissions
    if user.role and user.role.has_permission(permission_codename):
        return True
        
    # Check direct user permissions
    return user.user_permissions.filter(codename=permission_codename).exists()

def modify_role_permissions(role, add_permissions=None, remove_permissions=None):
    """
    Modify permissions for a role and update all users with that role
    
    Args:
        role: Role instance
        add_permissions: List of permission codenames to add
        remove_permissions: List of permission codenames to remove
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        if add_permissions:
            role.add_permissions(*add_permissions)
            
        if remove_permissions:
            role.remove_permissions(*remove_permissions)
            
        # Update permissions for all users with this role
        for user in role.users.all():
            user.user_permissions.set(role.permissions.all())
            
        return True, "Successfully modified role permissions"
    except Exception as e:
        return False, f"Error modifying permissions: {str(e)}"


def send_organization_verification_email(organization, request=None):
    """
    Generate a secure verification token and send a verification email to the organization.
    """
    import uuid
    from datetime import timedelta
    from django.utils import timezone
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings
    from django.urls import reverse
    from .models import OrganizationVerificationToken
    
    # 1. Generate secure unique token
    token_str = uuid.uuid4().hex
    expires_at = timezone.now() + timedelta(hours=24)
    
    # 2. Save token to db (delete any existing verification tokens for this organization first)
    OrganizationVerificationToken.objects.filter(organization=organization).delete()
    verification_token = OrganizationVerificationToken.objects.create(
        organization=organization,
        token=token_str,
        expires_at=expires_at
    )
    
    # 3. Construct URL
    if request:
        base_url = request.build_absolute_uri('/')[:-1] # Remove trailing slash
    else:
        base_url = getattr(settings, 'SITE_URL', 'https://myapp.com').rstrip('/')
    
    verify_url = f"{base_url}{reverse('verify_email')}?token={token_str}"
    
    # 4. Construct clean professional email body using template
    subject = "Verify Your Organization Registration - Pawnshop Management System"
    
    context = {
        'organization': organization,
        'verify_url': verify_url,
        'owner_name': f"{organization.owner.first_name} {organization.owner.last_name}",
    }
    
    html_message = render_to_string('accounts/emails/verification_email.html', context)
    plain_message = (
        f"Hello {context['owner_name']},\n\n"
        f"Thank you for registering {organization.name} on the Pawnshop Management System. "
        f"Please verify your email by clicking the link below:\n\n"
        f"{verify_url}\n\n"
        f"This link is valid for 24 hours.\n\n"
        f"Best regards,\nThe Pawnshop Team"
    )
    
    # 5. Send email
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@myapp.com')
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=from_email,
        recipient_list=[organization.contact_email],
        html_message=html_message,
        fail_silently=False,
    )
    
    return verification_token