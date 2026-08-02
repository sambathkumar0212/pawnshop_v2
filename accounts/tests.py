from django.test import TransactionTestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone
from datetime import timedelta
from accounts.models import Organization, OrganizationVerificationToken

User = get_user_model()

class SubscriptionTests(TransactionTestCase):
    def setUp(self):
        # Create a user first so we can assign ownership to the Organization
        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword",
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )
        
        # Create an organization
        self.org = Organization.objects.create(
            name="Test Org",
            slug="test-org",
            owner=self.user,
            plan="free",
            max_branches=1,
            max_users=3
        )
        
        # Associate user with the organization
        self.user.organization = self.org
        self.user.save()
        
        self.client = Client()
        
    def test_subscription_plans_view_authenticated(self):
        self.client.login(username="testuser", password="testpassword")
        response = self.client.get(reverse('subscription_plans'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('plans', response.context)
        self.assertIn('usage_stats', response.context)
        
    def test_subscription_plans_view_unauthenticated(self):
        response = self.client.get(reverse('subscription_plans'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login
        
    def test_upgrade_plan_get(self):
        self.client.login(username="testuser", password="testpassword")
        response = self.client.get(reverse('subscription_upgrade', kwargs={'plan': 'professional'}))
        self.assertEqual(response.status_code, 302)
        
        # Verify limits updated
        self.org.refresh_from_db()
        self.assertEqual(self.org.plan, 'professional')
        self.assertEqual(self.org.max_branches, 10)
        self.assertEqual(self.org.max_users, 30)
        self.assertTrue(self.org.enable_biometrics)


class EmailVerificationTests(TransactionTestCase):
    def setUp(self):
        self.client = Client()

    def test_signup_creates_pending_org_and_sends_email(self):
        # Clear outbox
        mail.outbox = []
        
        # Post to signup
        signup_data = {
            'organization_name': 'New SaaS Shop',
            'username': 'saasadmin',
            'email': 'saasadmin@example.com',
            'first_name': 'SaaS',
            'last_name': 'Admin',
            'password': 'strongpassword123',
            'confirm_password': 'strongpassword123',
            'phone': '1234567890'
        }
        
        response = self.client.post(reverse('organization_signup'), signup_data)
        
        # Verify redirect to check-email
        self.assertEqual(response.status_code, 302)
        self.assertIn('/check-email/', response.url)
        self.assertIn('email=saasadmin@example.com', response.url)
        
        # Verify organization is pending
        org = Organization.objects.get(name='New SaaS Shop')
        self.assertEqual(org.status, 'pending')
        
        # Verify token was created
        token_obj = OrganizationVerificationToken.objects.filter(organization=org).first()
        self.assertIsNotNone(token_obj)
        self.assertFalse(token_obj.is_expired())
        
        # Verify email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['saasadmin@example.com'])
        self.assertIn(token_obj.token, mail.outbox[0].body)

    def test_verify_email_endpoint_success(self):
        # Setup organization and token
        user = User.objects.create_user(username="owner", password="pwd", email="owner@ex.com")
        org = Organization.objects.create(name="Verify Org", slug="verify-org", owner=user, status='pending', contact_email="owner@ex.com")
        token_obj = OrganizationVerificationToken.objects.create(
            organization=org,
            token="valid_token_123",
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        # Hit Verify GET endpoint to render page
        response = self.client.get(reverse('verify_email') + "?token=valid_token_123")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/verify_email_landing.html')
        
        # Hit AJAX verification endpoint
        ajax_response = self.client.get(reverse('verify_email') + "?token=valid_token_123&ajax=1")
        self.assertEqual(ajax_response.status_code, 200)
        data = ajax_response.json()
        self.assertTrue(data['success'])
        
        # Verify org status changed to active
        org.refresh_from_db()
        self.assertEqual(org.status, 'active')
        
        # Verify token deleted
        self.assertFalse(OrganizationVerificationToken.objects.filter(token="valid_token_123").exists())

    def test_verify_email_expired_token(self):
        user = User.objects.create_user(username="owner2", password="pwd", email="owner2@ex.com")
        org = Organization.objects.create(name="Verify Org 2", slug="verify-org-2", owner=user, status='pending', contact_email="owner2@ex.com")
        token_obj = OrganizationVerificationToken.objects.create(
            organization=org,
            token="expired_token_123",
            expires_at=timezone.now() - timedelta(hours=1)  # Already expired
        )
        
        ajax_response = self.client.get(reverse('verify_email') + "?token=expired_token_123&ajax=1")
        self.assertEqual(ajax_response.status_code, 400)
        data = ajax_response.json()
        self.assertFalse(data['success'])
        self.assertIn("expired", data['message'])
        
        # Verify org is still pending
        org.refresh_from_db()
        self.assertEqual(org.status, 'pending')

    def test_verify_email_invalid_token(self):
        ajax_response = self.client.get(reverse('verify_email') + "?token=fake_token&ajax=1")
        self.assertEqual(ajax_response.status_code, 400)
        data = ajax_response.json()
        self.assertFalse(data['success'])
        self.assertIn("Invalid", data['message'])

    def test_resend_verification_email(self):
        user = User.objects.create_user(username="owner3", password="pwd", email="owner3@ex.com", is_organization_admin=True)
        org = Organization.objects.create(name="Verify Org 3", slug="verify-org-3", owner=user, status='pending', contact_email="owner3@ex.com")
        user.organization = org
        user.save()
        
        mail.outbox = []
        
        # Resend email
        res = self.client.post(reverse('resend_verification_email'), {'email': 'owner3@ex.com'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        
        # Verify email sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['owner3@ex.com'])
        
        # Verify new token created
        self.assertTrue(OrganizationVerificationToken.objects.filter(organization=org).exists())
