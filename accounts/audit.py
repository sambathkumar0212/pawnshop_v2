"""
Audit trail logging utilities for tracking all admin actions
"""
from django.utils import timezone
from .models import AuditTrail, PasswordChangeHistory


def log_audit_trail(admin_user, change_type, model_name, object_id, object_str, 
                    field_name=None, old_value=None, new_value=None, 
                    target_user=None, ip_address=None, user_agent=None, 
                    description=None):
    """
    Log an action to the audit trail
    
    Args:
        admin_user: CustomUser object who made the change
        change_type: Type of change (create, update, delete, password_change, etc.)
        model_name: Name of the model changed
        object_id: ID of the changed object
        object_str: String representation of the changed object
        field_name: Name of the field changed (for updates)
        old_value: Previous value (for updates)
        new_value: New value (for updates)
        target_user: CustomUser object that was affected (for staff changes)
        ip_address: IP address from where change was made
        user_agent: Browser/User Agent information
        description: Detailed description of the change
    """
    if not admin_user or not admin_user.is_pawnshop_admin:
        return None
    
    audit_entry = AuditTrail.objects.create(
        admin_user=admin_user,
        change_type=change_type,
        model_name=model_name,
        object_id=object_id,
        object_str=str(object_str),
        field_name=field_name or '',
        old_value=str(old_value) if old_value is not None else '',
        new_value=str(new_value) if new_value is not None else '',
        target_user=target_user,
        ip_address=ip_address,
        user_agent=user_agent or '',
        description=description or '',
        timestamp=timezone.now()
    )
    
    return audit_entry


def log_password_change(user, changed_by_admin, change_type='admin_reset', 
                        ip_address=None, description=None):
    """
    Log a password change for a staff member
    
    Args:
        user: CustomUser object whose password was changed
        changed_by_admin: CustomUser object (admin) who changed the password
        change_type: Type of password change
        ip_address: IP address from where change was made
        description: Additional description
    """
    if not changed_by_admin or not changed_by_admin.is_pawnshop_admin:
        return None
    
    password_change = PasswordChangeHistory.objects.create(
        user=user,
        changed_by_admin=changed_by_admin,
        change_type=change_type,
        ip_address=ip_address,
        description=description or f"Password changed by {changed_by_admin.get_full_name()}",
        timestamp=timezone.now()
    )
    
    # Also log to audit trail
    log_audit_trail(
        admin_user=changed_by_admin,
        change_type='password_change',
        model_name='CustomUser',
        object_id=user.id,
        object_str=str(user),
        target_user=user,
        ip_address=ip_address,
        description=f"Password reset for {user.get_full_name()} ({user.username})"
    )
    
    return password_change


def get_request_info(request):
    """
    Extract IP address and user agent from request
    
    Args:
        request: Django request object
    
    Returns:
        dict with ip_address and user_agent
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    return {
        'ip_address': ip,
        'user_agent': user_agent
    }


def log_staff_creation(admin_user, staff_user, request=None, description=None):
    """Log staff account creation"""
    request_info = get_request_info(request) if request else {}
    
    return log_audit_trail(
        admin_user=admin_user,
        change_type='create',
        model_name='CustomUser',
        object_id=staff_user.id,
        object_str=str(staff_user),
        target_user=staff_user,
        description=description or f"Created staff account for {staff_user.get_full_name()}",
        ip_address=request_info.get('ip_address'),
        user_agent=request_info.get('user_agent')
    )


def log_staff_update(admin_user, staff_user, changes_dict, request=None):
    """
    Log staff account updates with field-level tracking
    
    Args:
        admin_user: Admin user making the change
        staff_user: Staff user being updated
        changes_dict: Dict of field changes {field_name: (old_value, new_value)}
        request: Optional Django request
    """
    request_info = get_request_info(request) if request else {}
    
    for field_name, (old_value, new_value) in changes_dict.items():
        log_audit_trail(
            admin_user=admin_user,
            change_type='update',
            model_name='CustomUser',
            object_id=staff_user.id,
            object_str=str(staff_user),
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            target_user=staff_user,
            ip_address=request_info.get('ip_address'),
            user_agent=request_info.get('user_agent'),
            description=f"Updated {field_name} for {staff_user.get_full_name()}"
        )


def log_staff_deletion(admin_user, staff_user, reason=None, request=None):
    """Log staff account deletion"""
    from .models import StaffDeletion
    
    request_info = get_request_info(request) if request else {}
    
    # Create staff deletion record
    deletion_record = StaffDeletion.objects.create(
        staff_user=staff_user,
        deleted_by_admin=admin_user,
        username=staff_user.username,
        email=staff_user.email,
        first_name=staff_user.first_name,
        last_name=staff_user.last_name,
        role_name=staff_user.role.name if staff_user.role else 'No Role',
        reason_for_deletion=reason or '',
        ip_address=request_info.get('ip_address')
    )
    
    # Also log to audit trail
    log_audit_trail(
        admin_user=admin_user,
        change_type='delete',
        model_name='CustomUser',
        object_id=staff_user.id,
        object_str=str(staff_user),
        target_user=staff_user,
        ip_address=request_info.get('ip_address'),
        user_agent=request_info.get('user_agent'),
        description=f"Deleted staff account: {staff_user.get_full_name()} ({staff_user.username}). Reason: {reason or 'Not provided'}"
    )
    
    return deletion_record


def log_permission_change(admin_user, staff_user, old_permissions, new_permissions, request=None):
    """Log permission/role changes for staff"""
    request_info = get_request_info(request) if request else {}
    
    return log_audit_trail(
        admin_user=admin_user,
        change_type='permission_change',
        model_name='CustomUser',
        object_id=staff_user.id,
        object_str=str(staff_user),
        target_user=staff_user,
        old_value=str(old_permissions),
        new_value=str(new_permissions),
        ip_address=request_info.get('ip_address'),
        user_agent=request_info.get('user_agent'),
        description=f"Changed permissions for {staff_user.get_full_name()}"
    )


def log_login(user, request=None):
    """Log user login"""
    request_info = get_request_info(request) if request else {}
    
    if user.is_pawnshop_admin:
        log_audit_trail(
            admin_user=user,
            change_type='login',
            model_name='CustomUser',
            object_id=user.id,
            object_str=str(user),
            ip_address=request_info.get('ip_address'),
            user_agent=request_info.get('user_agent'),
            description=f"{user.get_full_name()} logged in"
        )


def log_logout(user, request=None):
    """Log user logout"""
    request_info = get_request_info(request) if request else {}
    
    if user.is_pawnshop_admin:
        log_audit_trail(
            admin_user=user,
            change_type='logout',
            model_name='CustomUser',
            object_id=user.id,
            object_str=str(user),
            ip_address=request_info.get('ip_address'),
            user_agent=request_info.get('user_agent'),
            description=f"{user.get_full_name()} logged out"
        )
