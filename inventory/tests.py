from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from accounts.models import CustomUser, Organization, Customer
from branches.models import Branch
from transactions.models import Loan
from schemes.models import Scheme
from inventory.models import VaultPouch, VaultAuditLog, Category, Item


class VaultCustodyTests(TestCase):
    def setUp(self):
        # Setup Organization, Branch, and Users
        self.owner = CustomUser.objects.create_user(
            username="org_owner",
            password="testpassword123",
            email="owner@firstmoneygold.com"
        )
        self.org = Organization.objects.create(
            name="First Money Gold",
            slug="first-money-gold",
            owner=self.owner,
            contact_email="owner@firstmoneygold.com",
            status="active"
        )
        self.branch = Branch.objects.create(
            name="Main Branch",
            address="100 Gold St",
            city="Chennai",
            state="TN",
            zip_code="600001",
            phone="9876543210",
            organization=self.org
        )
        
        self.maker_user = CustomUser.objects.create_user(
            username="maker_appraiser",
            password="testpassword123",
            organization=self.org,
            branch=self.branch
        )
        self.checker_user = CustomUser.objects.create_user(
            username="checker_manager",
            password="testpassword123",
            organization=self.org,
            branch=self.branch
        )

        self.customer = Customer.objects.create(
            first_name="Murugan",
            last_name="K",
            phone="9876543211",
            address="12 Temple Rd",
            branch=self.branch
        )

        self.scheme = Scheme.objects.create(
            name="Standard Gold Scheme",
            description="Standard pawn gold loan scheme",
            interest_rate=Decimal("12.00"),
            loan_duration=364,
            minimum_amount=Decimal("1000.00"),
            maximum_amount=Decimal("1000000.00"),
            start_date=timezone.now().date(),
            status="active"
        )

        # Create active loan
        self.loan = Loan.objects.create(
            loan_number="LN-2026-001",
            customer=self.customer,
            branch=self.branch,
            scheme=self.scheme,
            principal_amount=Decimal("50000"),
            distribution_amount=Decimal("50000"),
            interest_rate=Decimal("12.00"),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            status="active"
        )

        # Create security pouch
        self.pouch = VaultPouch.objects.create(
            pouch_number="PCH-001",
            loan=self.loan,
            branch=self.branch,
            safe_locker_number="Safe-01 / Locker-A1",
            shelf_rack_number="Rack-01 / Tray-B",
            seal_barcode="SEAL-998811",
            gross_weight=Decimal("18.500"),
            net_weight=Decimal("15.200"),
            item_count=2,
            custodian_maker=self.maker_user,
            status="pending_inward"
        )

        self.client = Client()
        self.client.login(username="checker_manager", password="testpassword123")

    def test_pouch_creation_and_location_display(self):
        """Test model creation and helper methods"""
        self.assertEqual(self.pouch.pouch_number, "PCH-001")
        self.assertEqual(self.pouch.status, "pending_inward")
        self.assertIn("Safe-01 / Locker-A1", self.pouch.location_display)
        self.assertIn("Rack-01 / Tray-B", self.pouch.location_display)

    def test_dual_custody_inward_verification(self):
        """Test Checker (Manager) signing off to vault the pouch"""
        url = reverse('verify_vault_inward', kwargs={'pk': self.pouch.pk})
        response = self.client.post(url, {'remarks': 'Security seal checked and verified'})
        self.assertRedirects(response, reverse('vault_explorer'))

        self.pouch.refresh_from_db()
        self.assertEqual(self.pouch.status, 'vaulted')
        self.assertEqual(self.pouch.custodian_checker, self.checker_user)
        self.assertIsNotNone(self.pouch.inward_verified_at)

        # Verify audit log generated
        audit = VaultAuditLog.objects.filter(pouch=self.pouch, action='inward_verified').first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.verified_by, self.checker_user)

    def test_release_guard_blocks_on_active_loan(self):
        """Test security rule: release is strictly blocked on an active loan"""
        self.pouch.status = 'vaulted'
        self.pouch.save()

        url = reverse('release_vault_pouch', kwargs={'pk': self.pouch.pk})
        response = self.client.post(url, {'release_notes': 'Attempting early release'})
        
        self.assertRedirects(response, reverse('vault_explorer'))
        self.pouch.refresh_from_db()
        # Status MUST remain vaulted
        self.assertEqual(self.pouch.status, 'vaulted')

    def test_release_guard_allows_on_repaid_loan(self):
        """Test security rule: release succeeds when loan status is repaid"""
        self.loan.status = 'repaid'
        self.loan.save()

        self.pouch.status = 'vaulted'
        self.pouch.save()

        url = reverse('release_vault_pouch', kwargs={'pk': self.pouch.pk})
        response = self.client.post(url, {'release_notes': 'Customer cleared loan and collected ornaments'})
        
        self.assertRedirects(response, reverse('vault_explorer'))
        self.pouch.refresh_from_db()
        self.assertEqual(self.pouch.status, 'released')
        self.assertIsNotNone(self.pouch.released_at)
        self.assertEqual(self.pouch.released_by, self.checker_user)

    def test_vault_explorer_view(self):
        """Test Vault Explorer listing and KPI calculations"""
        url = reverse('vault_explorer')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PCH-001")
        self.assertContains(response, "Safe-01 / Locker-A1")
        self.assertEqual(response.context['total_pouches'], 1)

    def test_vault_pouch_label_view(self):
        """Test printable pouch barcode label rendering"""
        url = reverse('vault_pouch_label', kwargs={'pk': self.pouch.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PCH-001")
        self.assertContains(response, "SEAL-998811")
        self.assertContains(response, "15.2")
