from django.core.management.base import BaseCommand
from django.utils import timezone
from schemes.models import Scheme
from datetime import timedelta
import decimal

class Command(BaseCommand):
    help = 'Creates a special loan scheme with no interest for early payments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--branch',
            type=int,
            help='Branch ID to associate the scheme with (optional, global if not provided)'
        )

    def handle(self, *args, **options):
        branch_id = options.get('branch')
        branch = None
        
        if branch_id:
            try:
                from branches.models import Branch
                branch = Branch.objects.get(id=branch_id)
                self.stdout.write(f"Creating scheme for branch: {branch.name}")
            except Branch.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Branch with ID {branch_id} does not exist"))
                return
        else:
            self.stdout.write("Creating global scheme")
        
        # Current date for start date
        today = timezone.now().date()
        # End date is 6 months from today
        end_date = today + timedelta(days=180)
        
        # Additional conditions for no interest in first 24 days
        additional_conditions = {
            'no_interest_period_days': 24,
            'late_fee_percentage': 2.0,
            'processing_fee_percentage': 1.0,
            'early_payment_discount': True,
            'description': "Special scheme with no interest if paid within 24 days"
        }
        
        # Create the scheme
        scheme = Scheme.objects.create(
            name="24-Day Interest-Free Scheme",
            description="Special loan scheme with no interest if repaid within 24 days. After 24 days, standard interest applies.",
            interest_rate=decimal.Decimal('12.00'),  # Standard interest rate after 24 days
            loan_duration=90,  # Standard loan duration of 90 days
            minimum_amount=decimal.Decimal('1000.00'),
            maximum_amount=decimal.Decimal('100000.00'),
            additional_conditions=additional_conditions,
            start_date=today,
            end_date=end_date,
            status='active',
            branch=branch
        )
        
        self.stdout.write(self.style.SUCCESS(
            f"Successfully created special scheme: {scheme.name} (ID: {scheme.id})"
        ))
        self.stdout.write(
            f"- Start Date: {scheme.start_date}\n"
            f"- End Date: {scheme.end_date}\n"
            f"- No Interest Period: {additional_conditions['no_interest_period_days']} days\n"
            f"- Standard Interest Rate (after grace period): {scheme.interest_rate}%"
        )
        
        # Show how these conditions would look in the text format
        text_conditions = "\n".join([
            f"No Interest Period Days: {additional_conditions['no_interest_period_days']}",
            f"Late Fee Percentage: {additional_conditions['late_fee_percentage']}",
            f"Processing Fee Percentage: {additional_conditions['processing_fee_percentage']}",
            "Early Payment Discount: Yes"
        ])
        
        self.stdout.write("\nAdditional conditions as they would appear in the form:")
        self.stdout.write(text_conditions)