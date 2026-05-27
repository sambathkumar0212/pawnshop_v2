from django.core.management.base import BaseCommand
from django.utils import timezone
from schemes.models import Scheme
from datetime import timedelta
import decimal

class Command(BaseCommand):
    help = 'Creates a loan scheme with no interest if paid within 24 days'

    def handle(self, *args, **options):
        # Current date for start date
        today = timezone.now().date()
        # End date is exactly 6 months from today
        end_date = today + timedelta(days=180)
        
        # Additional conditions as they would be entered in the text box
        conditions_text = """No Interest Period Days: 24
Default Start Date: Current Date
Default End Date: 6 months from current date
Early Payment Discount: Yes"""

        # Convert text to JSON format
        conditions_dict = {}
        for line in conditions_text.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                
                # Try to convert value to appropriate type
                if value.replace('.', '', 1).isdigit():
                    # Convert to number if it's a number
                    if '.' in value:
                        conditions_dict[key] = float(value)
                    else:
                        conditions_dict[key] = int(value)
                elif value.lower() in ['yes', 'true']:
                    conditions_dict[key] = True
                elif value.lower() in ['no', 'false']:
                    conditions_dict[key] = False
                elif value == "Current Date":
                    conditions_dict[key] = today.isoformat()
                elif value == "6 months from current date":
                    conditions_dict[key] = end_date.isoformat()
                else:
                    conditions_dict[key] = value
        
        # Create the scheme
        scheme = Scheme.objects.create(
            name="24-Day No-Interest Loan Scheme",
            description="Special scheme with no interest if loan is repaid within 24 days. Default loan start date is current date, and default end date is 6 months from now.",
            interest_rate=decimal.Decimal('12.00'),  # Standard interest rate after 24 days
            loan_duration=180,  # Match the 6-month period mentioned in conditions
            minimum_amount=decimal.Decimal('1000.00'),
            maximum_amount=decimal.Decimal('100000.00'),
            additional_conditions=conditions_dict,
            start_date=today,
            end_date=end_date,
            status='active'
        )
        
        self.stdout.write(self.style.SUCCESS(
            f"Successfully created scheme: {scheme.name} (ID: {scheme.id})"
        ))
        self.stdout.write(
            f"- Start Date: {scheme.start_date}\n"
            f"- End Date: {scheme.end_date} (6 months from today)\n"
            f"- No Interest Period: 24 days\n"
            f"- Standard Interest Rate: {scheme.interest_rate}%\n"
            f"- Conditions stored as: {scheme.additional_conditions}"
        )