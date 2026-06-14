import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','pawnshop_management.settings')
import django
django.setup()

from accounts.models import CustomUser
from accounts.forms import UserFaceCreateForm

username = 'validation_test_user'
if not CustomUser.objects.filter(username=username).exists():
    CustomUser.objects.create_user(username=username, email='valtest@example.com', password='TempPass123!')
    print('Created test user:', username)
else:
    print('Test user exists:', username)

form_data = {
    'username': username,
    'password': 'AnotherPass123!',
    'confirm_password': 'AnotherPass123!',
    'first_name': 'Val',
    'last_name': 'Test',
    'email': 'valtest@example.com',
    'phone': '9999999999',
    'enable_face_auth': False,
    'face_image': ''
}
form = UserFaceCreateForm(form_data)
print('Form valid?', form.is_valid())
print('Errors:', form.errors.as_json())
