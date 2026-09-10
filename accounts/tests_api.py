from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from branches.models import Branch

User = get_user_model()


class AuthAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.branch = Branch.objects.create(
            name="Main Head Branch",
            phone="9876543210",
            address="123 Gold Street",
            city="Chennai",
            state="Tamil Nadu",
            zip_code="600001",
            is_active=True
        )
        self.user = User.objects.create_user(
            username="testmanager",
            email="manager@pawnshop.com",
            password="securePassword123!",
            first_name="Test",
            last_name="Manager",
            phone="9988776655",
            branch=self.branch,
            is_active=True
        )

    def test_login_with_username_success(self):
        response = self.client.post('/api/v1/auth/login/', {
            'username': 'testmanager',
            'password': 'securePassword123!'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['username'], 'testmanager')
        self.assertEqual(response.data['user']['email'], 'manager@pawnshop.com')
        self.assertEqual(response.data['user']['branch']['name'], 'Main Head Branch')

    def test_login_with_email_success(self):
        response = self.client.post('/api/v1/auth/login/', {
            'username': 'manager@pawnshop.com',
            'password': 'securePassword123!'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertEqual(response.data['user']['username'], 'testmanager')

    def test_login_invalid_password(self):
        response = self.client.post('/api/v1/auth/login/', {
            'username': 'testmanager',
            'password': 'wrongPassword'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_current_user_me_endpoint(self):
        # Obtain access token
        login_res = self.client.post('/api/v1/auth/login/', {
            'username': 'testmanager',
            'password': 'securePassword123!'
        }, format='json')
        token = login_res.data['access']

        # Call /api/v1/auth/me/ with Bearer token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testmanager')
        self.assertEqual(response.data['full_name'], 'Test Manager')

    def test_token_refresh(self):
        login_res = self.client.post('/api/v1/auth/login/', {
            'username': 'testmanager',
            'password': 'securePassword123!'
        }, format='json')
        refresh_token = login_res.data['refresh']

        response = self.client.post('/api/v1/auth/refresh/', {
            'refresh': refresh_token
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_update_profile(self):
        login_res = self.client.post('/api/v1/auth/login/', {
            'username': 'testmanager',
            'password': 'securePassword123!'
        }, format='json')
        token = login_res.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.patch('/api/v1/auth/update-profile/', {
            'first_name': 'UpdatedFirst',
            'phone': '9111122222'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'UpdatedFirst')
        self.assertEqual(self.user.phone, '9111122222')

    def test_unauthenticated_access_denied(self):
        self.client.credentials()  # Clear auth
        response = self.client.get('/api/v1/auth/me/')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
