import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from accounts.models import Customer
from inventory.models import Item, ItemImage

def cleanup_customers():
    count = 0
    for customer in Customer.objects.all():
        if customer.profile_photo and not customer.profile_photo.strip():
            customer.profile_photo = ''
            customer.save()
            count += 1
    print(f"Cleaned up {count} customer profile photos.")

def cleanup_items():
    count = 0
    for item in Item.objects.all():
        # Remove all ItemImage objects with empty image fields
        empty_images = item.images.filter(image='')
        for img in empty_images:
            img.delete()
            count += 1
    print(f"Cleaned up {count} empty item images.")

def main():
    cleanup_customers()
    cleanup_items()
    print("Cleanup complete. Default photos will now be used where appropriate.")

if __name__ == '__main__':
    main() 