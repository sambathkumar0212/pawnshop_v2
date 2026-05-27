import os
import uuid
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib import messages
from django.shortcuts import redirect
import re
from django.utils.text import slugify

def item_photo_path(instance, filename):
    """Generate a unique file path for loan item photos"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('inventory_images', f'loan_{instance.loan_number}', filename)

def loan_document_path(instance, filename):
    """Generate a file path for loan documents using customer name and item name"""
    # Get file extension
    ext = filename.split('.')[-1].lower()
    
    # Get customer name (clean it for filename)
    customer_name = ""
    if instance.customer:
        customer_name = f"{instance.customer.first_name}_{instance.customer.last_name}"
        customer_name = slugify(customer_name).replace('-', '_')
    
    # Get item names from loan items
    item_names = []
    if instance.pk:  # Only if loan exists (for updates)
        loan_items = instance.loanitem_set.all()
        for loan_item in loan_items:
            if loan_item.item and loan_item.item.name:
                item_name = slugify(loan_item.item.name).replace('-', '_')
                item_names.append(item_name)
    
    # If no items found or for new loans, use a default
    if not item_names:
        item_names = ['item']
    
    # Combine item names (limit to first 3 items to avoid very long filenames)
    items_part = '_'.join(item_names[:3])
    
    # Create filename: CustomerName_ItemNames_LoanNumber.ext
    if customer_name and items_part:
        filename_base = f"{customer_name}_{items_part}"
    elif customer_name:
        filename_base = f"{customer_name}_loan"
    else:
        filename_base = "loan_document"
    
    # Add loan number if available
    if instance.loan_number:
        loan_number = re.sub(r'[^a-zA-Z0-9_-]', '_', instance.loan_number)
        filename_base = f"{filename_base}_{loan_number}"
    
    # Limit filename length to avoid filesystem issues
    if len(filename_base) > 200:
        filename_base = filename_base[:200]
    
    # Final filename
    final_filename = f"{filename_base}.{ext}"
    
    # Return path: loan_documents/YYYY/MM/filename
    from django.utils import timezone
    now = timezone.now()
    return os.path.join('loan_documents', str(now.year), f"{now.month:02d}", final_filename)

class ManagerPermissionMixin(UserPassesTestMixin):
    """
    Permission mixin that restricts access to managers, regional managers, and admin users only.
    Regular employees will be redirected with an error message.
    """
    permission_denied_message = "Only branch managers, regional managers, and administrators can edit loans."
    
    def test_func(self):
        """Check if user has manager-level permissions."""
        # Allow superuser access
        if self.request.user.is_superuser:
            return True
        
        # Check if the user has a role
        if not hasattr(self.request.user, 'role') or not self.request.user.role:
            return False
        
        # Check if role name indicates manager-level permissions
        role_name = self.request.user.role.name.lower()
        return any(title in role_name for title in ['manager', 'admin', 'director', 'supervisor', 'head'])
    
    def handle_no_permission(self):
        """Show an error message and redirect when permission is denied."""
        messages.error(self.request, self.permission_denied_message)
        return redirect('loan_detail', loan_number=self.kwargs.get('loan_number'))