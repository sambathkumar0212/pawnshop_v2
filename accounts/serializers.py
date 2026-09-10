from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate, get_user_model
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, Role, Organization
from branches.models import Branch

User = get_user_model()


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for user roles"""
    class Meta:
        model = Role
        fields = ['id', 'name', 'role_type', 'category', 'description']


class BranchBasicSerializer(serializers.ModelSerializer):
    """Lightweight serializer for user's assigned branch"""
    class Meta:
        model = Branch
        fields = ['id', 'name', 'phone', 'address', 'city', 'state', 'is_active']


class OrganizationBasicSerializer(serializers.ModelSerializer):
    """Lightweight serializer for tenant organization"""
    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug', 'plan', 'status']


class UserProfileSerializer(serializers.ModelSerializer):
    """Detailed user profile serializer for authenticated sessions"""
    role = RoleSerializer(read_only=True)
    branch = BranchBasicSerializer(read_only=True)
    organization = OrganizationBasicSerializer(read_only=True)
    permissions = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'phone',
            'role',
            'branch',
            'organization',
            'is_active',
            'is_staff',
            'is_superuser',
            'is_organization_admin',
            'is_pawnshop_admin',
            'is_branch_manager',
            'is_regional_manager',
            'permissions',
            'date_joined',
            'last_login',
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    def get_permissions(self, obj):
        """Return list of string permission codenames for client-side capability checking"""
        if obj.is_superuser:
            return ['all_permissions']
        return list(obj.get_all_permissions())


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT login serializer that:
    1. Supports login with either username or email.
    2. Embeds useful claims into the JWT token payload.
    3. Returns full user profile & permissions alongside tokens.
    """
    def validate(self, attrs):
        username_or_email = attrs.get(self.username_field)
        password = attrs.get('password')

        user = authenticate(
            request=self.context.get('request'),
            username=username_or_email,
            password=password
        )

        if not user:
            raise serializers.ValidationError(
                {'detail': _('No active account found with the given credentials.')}
            )

        if not user.is_active:
            raise serializers.ValidationError(
                {'detail': _('This account is inactive. Please contact your administrator.')}
            )

        # Generate tokens
        refresh = self.get_token(user)

        # Custom claims embedded in token payload
        refresh['username'] = user.username
        refresh['email'] = user.email
        refresh['role'] = user.role.name if user.role else 'Staff'
        refresh['branch_id'] = user.branch.id if user.branch else None
        refresh['branch_name'] = user.branch.name if user.branch else None
        refresh['org_id'] = user.organization.id if user.organization else None

        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserProfileSerializer(user).data,
        }
        return data


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for users updating their own profile details"""
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'phone', 'email']

    def validate_email(self, value):
        user = self.context['request'].user
        if User.objects.filter(email__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError(_('A user with this email already exists.'))
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change endpoint"""
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=6)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(_('Incorrect old password.'))
        return value


class CustomerSerializer(serializers.ModelSerializer):
    """Serializer for customer management on mobile app"""
    full_name = serializers.CharField(read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True, default='')

    class Meta:
        from accounts.models import Customer
        model = Customer
        fields = [
            'id',
            'first_name',
            'last_name',
            'full_name',
            'email',
            'phone',
            'branch',
            'branch_name',
            'address',
            'city',
            'state',
            'zip_code',
            'id_type',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
