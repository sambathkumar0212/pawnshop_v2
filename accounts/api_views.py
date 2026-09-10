from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import update_session_auth_hash
from drf_spectacular.utils import extend_schema
from .serializers import (
    CustomTokenObtainPairSerializer,
    UserProfileSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
)


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    POST /api/v1/auth/login/
    Login with username or email + password. Returns JWT access & refresh tokens
    plus complete user profile and branch/role info.
    """
    serializer_class = CustomTokenObtainPairSerializer


class CurrentUserView(APIView):
    """
    GET /api/v1/auth/me/
    Retrieve the profile of the currently authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Get Current User Profile",
        responses={200: UserProfileSerializer},
        tags=["Authentication"]
    )
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UpdateProfileView(APIView):
    """
    PATCH /api/v1/auth/update-profile/
    Update the authenticated user's first name, last name, phone, or email.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Update User Profile",
        request=UserUpdateSerializer,
        responses={200: UserProfileSerializer},
        tags=["Authentication"]
    )
    def patch(self, request):
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Profile updated successfully.',
                'user': UserProfileSerializer(request.user).data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """
    POST /api/v1/auth/change-password/
    Change password for the authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Change User Password",
        request=ChangePasswordSerializer,
        responses={200: dict},
        tags=["Authentication"]
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            update_session_auth_hash(request, user)
            return Response({'message': 'Password changed successfully.'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
