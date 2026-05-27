import os
import django
import base64
from datetime import date

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from accounts.models import Customer
from transactions.models import Loan, LoanItem

# Sample base64 photos (small placeholder images)
SAMPLE_PERSON_PHOTO = """
iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6
JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMA
AAsTAAALEwEAmpwYAAAAB3RJTUUH5gQaDyoKQAHnpAAAA+1JREFUaN7tmm1IVEEUht+Z3VxXs7TdVikR
IlMhkEgogxDCQrGPBCMsP37RD21D/RH0L/xRUJFA/QiMwC9E0NAfJUVEaYmGJWUUUUFFJZG2rru3H+ru
uO7u3L1z72p04ID7dWbmnPec887ZO8A0pmlM07j+2DFy5I+4/r9YSYa7MX4QCSRsKTR0Fbgd6olObJyX
hEJX+gbPsQ15E+iEo02rpf6MgR9gOFU5Ksv4ISDBqaYMPcQIn51zQcr4pZBAx8xkZcxZmxA3BNrryPb1
syWgdNdVXwxzNr+W6wvNmUKNAZdnCJHRqKAEsOQk7HoWi8S1Bs6Fc2Gl6IfDSFWl8bPv84LInywiKoYN
OImHCTMDXCus2ITOPGmfmjNkIbRMiTwLnkIfJ/xJx9OESkDZFNJbIPpOIfdggxLnPbdWNnQV4EY6AyDP
kXf2gwlZdtwbhRG+sVJrYDDcxEn+uWhCFi751Jzb67iapgbrppCaIQw4Pzc7ya9k2HwLtVAXmnzCN3rK
tBIIf4j9FB5aSIi0sJIVIvAQS8jcBe9qBX+qDpn47Nxs5HtvuVYzrd9ByDmkqd5lu+XLGDJw430Gl/Pr
vTfSfgm7+gYR97x1ED88UyL280r7Nsf3vePRpFBroMH7ky6F3K5mjHSJ/2n0h3HbH03MsE+MdL5cStHV
BfLQBcGJezoH53Pi4N1/14UkfnEFz7RcoXp37qiWqA402CT/XV8/BNb5qVSubK9IxhsOAlHO5ykJSF6o
MpHAThZjkBDARO/XkRnQMsIXeCnfeNU0YRbid/oG5ji2Uw5CI524/x4x7i4p441DgOHTnTdciRxaSHCY
yzEQiSC10Ymlg1ay8Un3UydIcEEo5zN8QWPyfcM19aGeZRXja+O3FTGBLiXD52aCZw1oeAAAAAA=
"""

SAMPLE_GOLD_PHOTO = """
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
UVORK5CYII=
"""

def add_photos_to_customers():
    """Add sample photos to all customers"""
    customers = Customer.objects.all()
    for customer in customers:
        customer.profile_photo = f"data:image/jpeg;base64,{SAMPLE_PERSON_PHOTO}"
        customer.save()
    print(f"Added photos to {len(customers)} customers")

def add_photos_to_loans():
    """Add sample photos to all loans and their items"""
    loans = Loan.objects.all()
    for loan in loans:
        # Add customer face capture
        loan.customer_face_capture = f"data:image/jpeg;base64,{SAMPLE_PERSON_PHOTO}"
        
        # Add item photos
        loan.item_photos = [f"data:image/jpeg;base64,{SAMPLE_GOLD_PHOTO}"]
        loan.save()
    print(f"Added photos to {len(loans)} loans")

def main():
    print("Adding sample photos...")
    add_photos_to_customers()
    add_photos_to_loans()
    print("Sample photos added successfully!")

if __name__ == '__main__':
    main() 