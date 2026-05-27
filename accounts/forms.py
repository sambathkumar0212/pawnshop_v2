from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from .models import CustomUser, Role, Customer, Organization
from django.contrib.auth.models import Group
from branches.models import Branch
from django.utils.text import slugify
import re

class UserFaceCreateForm(forms.ModelForm):
    """Form for creating a new user with face authentication"""
    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())
    face_image = forms.CharField(widget=forms.HiddenInput(), required=False)
    enable_face_auth = forms.BooleanField(
        initial=True, 
        required=False,
        label="Enable Face Authentication",
        help_text="Allow this user to login using facial recognition"
    )
    
    class Meta:
        model = CustomUser
        fields = [
            'username', 'password', 'confirm_password', 'first_name', 
            'last_name', 'email', 'phone', 'role', 'branch', 
            'enable_face_auth', 'face_image'
        ]
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        
        if password != confirm_password:
            self.add_error('confirm_password', "Passwords don't match")
        
        enable_face_auth = cleaned_data.get("enable_face_auth")
        face_image = cleaned_data.get("face_image")
        
        if enable_face_auth and not face_image:
            self.add_error('face_image', "Face image is required if face authentication is enabled")
            
        return cleaned_data

class UserUpdateForm(forms.ModelForm):
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        required=False,
        empty_label="Select a role"
    )
    
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone', 'role', 'branch', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Set initial role
            self.fields['role'].initial = self.instance.role
            # Set initial branch
            self.fields['branch'].initial = self.instance.branch

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Handle role assignment
            if self.cleaned_data.get('role'):
                user.role = self.cleaned_data['role']
                user.save()
                # Update user permissions based on role
                user.user_permissions.set(self.cleaned_data['role'].permissions.all())
        return user

class OrganizationSignupForm(forms.ModelForm):
    """Form for creating a new organization and initial admin user"""
    # Organization fields
    organization_name = forms.CharField(max_length=100, required=True)
    
    # User fields
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    password = forms.CharField(widget=forms.PasswordInput(), required=True)
    confirm_password = forms.CharField(widget=forms.PasswordInput(), required=True)
    
    # Contact information
    phone = forms.CharField(max_length=20, required=False)
    
    class Meta:
        model = Organization
        fields = ['organization_name', 'username', 'email', 'first_name', 
                 'last_name', 'password', 'confirm_password', 'phone']
        
    def clean_organization_name(self):
        """Validate organization name and create a slug"""
        name = self.cleaned_data.get('organization_name')
        
        # Check if organization with this name already exists
        if Organization.objects.filter(name=name).exists():
            raise forms.ValidationError("An organization with this name already exists.")
            
        # Create a slug from the name
        slug = slugify(name)
        
        # Ensure slug is unique
        if Organization.objects.filter(slug=slug).exists():
            raise forms.ValidationError("This organization name is too similar to an existing one.")
            
        return name
        
    def clean_username(self):
        """Validate username"""
        username = self.cleaned_data.get('username')
        
        # Check if username already exists
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
            
        return username
        
    def clean_email(self):
        """Validate email"""
        email = self.cleaned_data.get('email')
        
        # Check if email already exists
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
            
        return email
        
    def clean(self):
        """Validate passwords match"""
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords don't match")
            
        return cleaned_data
        
    def save(self, commit=True):
        """Prepares organization and admin user objects but does not save them if commit=False"""
        # Create the organization instance (not saved yet)
        organization = Organization(
            name=self.cleaned_data['organization_name'],
            slug=slugify(self.cleaned_data['organization_name']),
            contact_email=self.cleaned_data['email'],
            contact_phone=self.cleaned_data.get('phone', '')
        )
        
        # Create the user instance (not saved yet)
        user = CustomUser(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            phone=self.cleaned_data.get('phone', ''),
            is_organization_admin=True
        )
        user.set_password(self.cleaned_data['password'])
        
        # If commit is True, save the instances
        if commit:
            user.save()
            organization.owner = user
            organization.save()
            user.organization = organization
            user.save()
            return organization # Return the saved organization
        
        # If commit is False, return the unsaved instances
        return {'organization': organization, 'user': user}


class OrganizationUpdateForm(forms.ModelForm):
    """Form for updating organization details"""
    class Meta:
        model = Organization
        fields = ['name', 'contact_email', 'contact_phone']
        
        
class OrganizationBranchForm(forms.ModelForm):
    """Form for adding/editing a branch within an organization"""
    class Meta:
        model = Branch
        fields = ['name', 'address', 'city', 'state', 'zip_code', 'phone', 'email',
                 'manager', 'is_active', 'opening_time', 'closing_time']
        
    def __init__(self, organization, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter manager choices to users from this organization
        self.fields['manager'].queryset = CustomUser.objects.filter(
            organization=organization,
            role__role_type__in=['branch_manager', 'regional_manager']
        )

class CustomerForm(forms.ModelForm):
    """Form for creating and updating customers"""
    
    class Meta:
        model = Customer
        fields = [
            'first_name', 'first_name_tamil', 'last_name', 'last_name_tamil',
            'email', 'phone', 'branch',
            'address', 'address_tamil', 'city', 'city_tamil', 'state', 'state_tamil',
            'zip_code', 'id_type', 'id_number', 'id_image',
            'notes', 'notes_tamil'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'address_tamil': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'notes_tamil': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Make branch field required
        self.fields['branch'].required = True
        self.fields['branch'].empty_label = "Select a branch"
        
        # Filter branches based on user's organization and permissions
        if self.user:
            if hasattr(self.user, 'organization') and self.user.organization:
                # Filter branches by organization
                branches_query = Branch.objects.filter(organization=self.user.organization)
                
                # Further filter by branch if user is not a regional manager or superuser
                if not self.user.is_superuser and self.user.branch:
                    if not (hasattr(self.user, 'role') and self.user.role and 
                            self.user.role.name.lower() == 'regional manager'):
                        # Regular users can only create customers for their own branch
                        branches_query = branches_query.filter(id=self.user.branch.id)
                        # Pre-select user's branch
                        self.fields['branch'].initial = self.user.branch
                        
                self.fields['branch'].queryset = branches_query.filter(is_active=True)
            else:
                # Show all active branches for superusers or users without organization
                self.fields['branch'].queryset = Branch.objects.filter(is_active=True)
                
            # If user has a branch and can only create customers for their branch, hide the field
            if (not self.user.is_superuser and self.user.branch and 
                not (hasattr(self.user, 'role') and self.user.role and 
                     self.user.role.name.lower() in ['regional manager', 'area manager'])):
                self.fields['branch'].widget = forms.HiddenInput()
        else:
            # Default to all active branches if no user context
            self.fields['branch'].queryset = Branch.objects.filter(is_active=True)
    
    def clean_branch(self):
        """Validate that branch is provided"""
        branch = self.cleaned_data.get('branch')
        if not branch:
            raise forms.ValidationError('Each customer must be assigned to a branch.')
        return branch
    
    def clean_phone(self):
        """Validate phone number"""
        phone = self.cleaned_data.get('phone')
        if phone:
            # Keep only digits and store as 10-digit number.
            phone_digits = re.sub(r'[^\d]', '', phone)
            if len(phone_digits) < 10:
                raise forms.ValidationError('Phone number must be at least 10 digits.')
            # Use last 10 digits (handles prefixes like +91, brackets, dashes).
            phone_digits = phone_digits[-10:]
            if len(phone_digits) != 10:
                raise forms.ValidationError('Phone number must be exactly 10 digits.')
            return phone_digits
        return phone
    
    def clean_email(self):
        """Validate email if provided"""
        email = self.cleaned_data.get('email')
        if email:
            # Check if email already exists for another customer
            if self.instance and self.instance.pk:
                # Updating existing customer
                if Customer.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
                    raise forms.ValidationError('This email is already registered to another customer.')
            else:
                # Creating new customer
                if Customer.objects.filter(email=email).exists():
                    raise forms.ValidationError('This email is already registered to another customer.')
        return email
    
    def save(self, commit=True):
        """Save customer with proper branch assignment"""
        customer = super().save(commit=False)
        
        # Ensure branch is set
        if not customer.branch:
            if self.user and self.user.branch:
                customer.branch = self.user.branch
            else:
                raise forms.ValidationError('Customer must be assigned to a branch.')
        
        # Set created_by if this is a new customer
        if not customer.pk and self.user:
            customer.created_by = self.user
            
        if commit:
            customer.save()
        return customer
