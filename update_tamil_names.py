import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from accounts.models import Customer

# Find customers and update with Tamil names
customers = Customer.objects.all()[:3]  # Update first 3 customers
tamil_names = [
    ("சுதாகர்", "டமி"),
    ("இரவி", "குமார்"),
    ("அஞ்சली", "சிங்"),
]

for idx, customer in enumerate(customers):
    if idx < len(tamil_names):
        tamil_first, tamil_last = tamil_names[idx]
        customer.first_name_tamil = tamil_first
        customer.last_name_tamil = tamil_last
        customer.save()
        print(f"Updated: {customer.first_name} {customer.last_name} -> {customer.full_name_tamil}")

print("Done!")
