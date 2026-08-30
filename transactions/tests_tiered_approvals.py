from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal

from accounts.models import CustomUser, Customer, Role, Region
from branches.models import Branch, Zone, RegionalOffice, BranchCluster
from schemes.models import Scheme
from transactions.models import Loan, DisbursementTransaction


class TieredMakerCheckerApprovalTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Setup Organizational Hierarchy
        self.zone_south = Zone.objects.create(name="South Zone", code="SZ")
        self.ro_salem = RegionalOffice.objects.create(name="Salem Regional Office", code="RO-SLM", zone=self.zone_south)
        self.ro_cbe = RegionalOffice.objects.create(name="Coimbatore Regional Office", code="RO-CBE", zone=self.zone_south)
        self.cluster_salem = BranchCluster.objects.create(name="Salem City Cluster", code="CL-SLM", region=self.ro_salem)

        self.region_salem = Region.objects.create(name="Salem Region")
        self.region_cbe = Region.objects.create(name="Coimbatore Region")

        self.branch_salem = Branch.objects.create(
            name="Salem Main Branch",
            address="100 Main Road",
            city="Salem",
            state="Tamil Nadu",
            zip_code="636001",
            phone="9876543210",
            zone=self.zone_south,
            regional_office=self.ro_salem,
            cluster=self.cluster_salem,
            region=self.region_salem
        )
        self.branch_cbe = Branch.objects.create(
            name="Coimbatore Main Branch",
            address="200 Cross Cut Road",
            city="Coimbatore",
            state="Tamil Nadu",
            zip_code="641012",
            phone="9876543211",
            zone=self.zone_south,
            regional_office=self.ro_cbe,
            region=self.region_cbe
        )

        # 2. Roles & Users
        self.role_appraiser, _ = Role.objects.get_or_create(name="Appraiser", role_type="appraiser")
        self.role_bm, _ = Role.objects.get_or_create(name="Branch Manager", role_type="branch_manager")
        self.role_ro, _ = Role.objects.get_or_create(name="Regional Manager", role_type="regional_manager")
        self.role_ho, _ = Role.objects.get_or_create(name="Finance Manager", role_type="finance_manager")

        self.appraiser = CustomUser.objects.create_user(
            username="appraiser_ravi",
            email="ravi@fmg.com",
            password="Password123!",
            role=self.role_appraiser,
            branch=self.branch_salem
        )
        self.bm = CustomUser.objects.create_user(
            username="bm_kumar",
            email="kumar@fmg.com",
            password="Password123!",
            role=self.role_bm,
            branch=self.branch_salem
        )
        self.branch_salem.manager = self.bm
        self.branch_salem.save()

        self.ro = CustomUser.objects.create_user(
            username="ro_selvan",
            email="selvan@fmg.com",
            password="Password123!",
            role=self.role_ro,
            branch=self.branch_salem
        )
        self.ro.regions.add(self.region_salem)
        self.ro_salem.regional_manager = self.ro
        self.ro_salem.save()

        self.ho_user = CustomUser.objects.create_user(
            username="ho_credit",
            email="ho@fmg.com",
            password="Password123!",
            role=self.role_ho,
            branch=self.branch_salem
        )

        self.customer = Customer.objects.create(
            first_name="Arun",
            last_name="Pandian",
            phone="9876500001",
            id_type="aadhar_card",
            id_number="987654321011",
            branch=self.branch_salem
        )

        self.scheme = Scheme.objects.create(
            name="12M Gold Loan",
            interest_rate=Decimal('12.00'),
            loan_duration=364,
            minimum_amount=Decimal('1000.00'),
            maximum_amount=Decimal('5000000.00'),
            start_date=timezone.now().date(),
            status='active',
            branch=self.branch_salem
        )

    def test_01_tier1_approval_workflow_and_disbursal_lock(self):
        """
        1. Tier 1 Test (Loan <= ₹2,00,000):
        - Initiated by Appraiser (Maker)
        - Requires Branch Manager (Checker)
        - Disbursal blocked while pending_approval
        - Disbursal succeeds and transitions to active once approved
        """
        loan = Loan.objects.create(
            loan_number="LN-T1-001",
            customer=self.customer,
            branch=self.branch_salem,
            scheme=self.scheme,
            principal_amount=Decimal('150000'),
            processing_fee=1500,
            distribution_amount=Decimal('148500'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            status='pending_approval',
            approval_tier=1,
            maker=self.appraiser
        )

        self.assertEqual(loan.approval_tier, 1)
        self.assertFalse(loan.is_approved_for_disbursal)

        # Disbursal attempt should raise ValidationError
        disb = DisbursementTransaction(
            loan=loan,
            payment_mode='BANK_TRANSFER',
            amount=Decimal('148500.00'),
            account_number='1234567890',
            ifsc_code='HDFC0001234',
            disbursed_by=self.bm
        )
        with self.assertRaises(ValidationError):
            disb.clean()

        # BM approves
        self.assertTrue(loan.can_user_approve(self.bm))
        status = loan.approve(self.bm, "Appraisal and gold purity verified.")
        self.assertEqual(status, 'approved')
        self.assertTrue(loan.is_approved_for_disbursal)
        self.assertEqual(loan.checker_bm, self.bm)

        # Now disbursal succeeds
        disb.clean()
        disb.save()
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'active')

    def test_02_tier2_escalation_workflow(self):
        """
        2. Tier 2 Test (₹2,00,001 to ₹10,00,000):
        - Principal: ₹5,00,000
        - Requires BM -> then RO approval
        """
        loan = Loan.objects.create(
            loan_number="LN-T2-002",
            customer=self.customer,
            branch=self.branch_salem,
            scheme=self.scheme,
            principal_amount=Decimal('500000'),
            processing_fee=5000,
            distribution_amount=Decimal('495000'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            status='pending_approval',
            approval_tier=2,
            maker=self.appraiser
        )

        self.assertEqual(loan.determine_approval_tier(), 2)

        # Step 1: BM approves
        self.assertTrue(loan.can_user_approve(self.bm))
        status_bm = loan.approve(self.bm, "BM verified.")
        self.assertEqual(status_bm, 'pending_approval')
        self.assertFalse(loan.is_approved_for_disbursal)
        self.assertIsNotNone(loan.checker_bm)

        # Step 2: RO approves
        self.assertTrue(loan.can_user_approve(self.ro))
        status_ro = loan.approve(self.ro, "RO approved.")
        self.assertEqual(status_ro, 'approved')
        self.assertTrue(loan.is_approved_for_disbursal)
        self.assertEqual(loan.checker_ro, self.ro)

    def test_03_tier3_head_office_signoff(self):
        """
        3. Tier 3 Test (Principal > ₹10,00,000):
        - Principal: ₹15,00,000
        - Requires BM -> RO -> HO Credit Committee sign-off
        """
        loan = Loan.objects.create(
            loan_number="LN-T3-003",
            customer=self.customer,
            branch=self.branch_salem,
            scheme=self.scheme,
            principal_amount=Decimal('1500000'),
            processing_fee=15000,
            distribution_amount=Decimal('1485000'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            status='pending_approval',
            approval_tier=3,
            maker=self.appraiser
        )

        # Step 1: BM
        loan.approve(self.bm)
        self.assertFalse(loan.is_approved_for_disbursal)

        # Step 2: RO
        loan.approve(self.ro)
        self.assertFalse(loan.is_approved_for_disbursal)

        # Step 3: HO
        self.assertTrue(loan.can_user_approve(self.ho_user))
        status_ho = loan.approve(self.ho_user, "Credit Committee unanimous sign-off.")
        self.assertEqual(status_ho, 'approved')
        self.assertTrue(loan.is_approved_for_disbursal)
        self.assertEqual(loan.checker_ho, self.ho_user)

    def test_04_rejection_and_reappraisal_lifecycle(self):
        """4. Verify Rejection with reason and Request Re-appraisal mechanics."""
        loan = Loan.objects.create(
            loan_number="LN-REJ-004",
            customer=self.customer,
            branch=self.branch_salem,
            scheme=self.scheme,
            principal_amount=Decimal('250000'),
            processing_fee=2500,
            distribution_amount=Decimal('247500'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            status='pending_approval',
            approval_tier=2,
            maker=self.appraiser
        )

        # Re-appraisal flow
        loan.request_reappraisal(self.bm, "Stone weight deduction inadequate. Please re-weigh with jeweler.")
        self.assertEqual(loan.reappraisal_notes, "Stone weight deduction inadequate. Please re-weigh with jeweler.")
        self.assertEqual(loan.status, 'pending_approval')

        # Rejection flow
        loan.reject(self.bm, "Hallmark fake; gold purity only 14K instead of claimed 22K.")
        self.assertEqual(loan.status, 'rejected')
        self.assertEqual(loan.rejection_reason, "Hallmark fake; gold purity only 14K instead of claimed 22K.")
        self.assertFalse(loan.is_approved_for_disbursal)

    def test_05_approval_queue_views_and_actions(self):
        """5. Approval queue dashboard view and POST action endpoints."""
        loan = Loan.objects.create(
            loan_number="LN-VIEW-005",
            customer=self.customer,
            branch=self.branch_salem,
            scheme=self.scheme,
            principal_amount=Decimal('100000'),
            processing_fee=1000,
            distribution_amount=Decimal('99000'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            status='pending_approval',
            approval_tier=1,
            maker=self.appraiser
        )

        self.client.login(username="bm_kumar", password="Password123!")

        # 1. Queue Dashboard View
        queue_url = reverse('loan_approval_queue')
        resp = self.client.get(queue_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'LN-VIEW-005')
        self.assertContains(resp, 'Tier 1')

        # 2. Approve via POST action
        approve_url = reverse('loan_approval_approve', kwargs={'pk': loan.pk})
        resp_app = self.client.post(approve_url, {'approval_notes': 'Looks good!'}, follow=True)
        self.assertEqual(resp_app.status_code, 200)
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'approved')
