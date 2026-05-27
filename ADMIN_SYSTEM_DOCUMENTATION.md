# Admin-Only Access System with Audit Trail

## Overview / பொதுவான விளக்கம்

A complete admin-controlled user management system has been implemented for the pawnshop application. Only the admin can create staff accounts, manage passwords, and delete staff. All changes are tracked with complete audit trails showing who changed what, when, and where.

### முக்கிய அம்சங்கள் (Key Features):

## 1. Admin-Only Login
- **Admin Access**: Special `is_pawnshop_admin` flag on CustomUser model
- **Staff Access**: Regular staff login without admin privileges
- **Separate Control**: Only admins have access to staff management dashboard

## 2. Staff Account Management
### Create Staff Account (Admin Only)
- Path: `/accounts/admin/staff/add/`
- Admin creates new staff account with username, email, name, phone, role, branch
- System auto-generates temporary secure password
- Admin shown password to share securely with staff member
- Creation logged to audit trail

### Update Staff Account (Admin Only)
- Path: `/accounts/admin/staff/<id>/edit/`
- Admin can update: email, name, phone, role, branch, active status
- All changes tracked field-by-field
- Logged with who, what, and when

### Delete Staff Account (Admin Only)
- Path: `/accounts/admin/staff/<id>/delete/`
- Admin can permanently delete staff accounts
- Reason for deletion recorded
- Deletion logged with admin info, date, time, IP address
- Deleted staff info archived in StaffDeletion model

## 3. Password Management
### Staff Password Reset
- **Change Request**: Staff cannot change their own password
- **Forgot Password**: Staff submits request via `/accounts/password-reset/`
- **Admin Action**: Only admin can reset staff password
- **New Password**: Admin generates new temporary password via `/accounts/admin/staff/<id>/reset-password/`
- **Logging**: All password changes tracked in PasswordChangeHistory model

### Admin Password Change
- **Self-Service**: Only admin can change their own password
- **Access**: `/accounts/password-change/`
- **Restriction**: Staff members blocked with error message

## 4. Audit Trail & Change Tracking

### Audit Trail Model (AuditTrail)
Fields tracked:
- `admin_user`: Who made the change
- `change_type`: Create, Update, Delete, Password Change, Login, Logout, Permission Change
- `model_name`: Which model was changed (e.g., CustomUser)
- `object_id`: ID of the object
- `object_str`: String representation of the object
- `field_name`: Specific field changed (for updates)
- `old_value`: Previous value
- `new_value`: New value
- `timestamp`: When it happened (auto-added)
- `ip_address`: Where request came from
- `user_agent`: Browser/device info
- `target_user`: Which staff member was affected
- `description`: Detailed description

### Password Change History (PasswordChangeHistory)
- `user`: Staff member whose password changed
- `changed_by_admin`: Admin who made the change
- `change_type`: admin_reset, forgot_password, user_change
- `timestamp`: When changed
- `ip_address`: From where
- `description`: Why/how

### Staff Deletion History (StaffDeletion)
- `username`: Deleted staff username
- `email`: Staff email
- `first_name`, `last_name`: Staff name
- `role_name`: What role they had
- `reason_for_deletion`: Why deleted
- `deleted_by_admin`: Which admin deleted
- `deletion_timestamp`: When deleted
- `ip_address`: From where

## 5. Admin Dashboard
### Location
- Path: `/accounts/admin/dashboard/`

### Features
- Total staff count
- Admin count
- Active/Inactive staff
- Recent audit trail (10 latest)
- Recent deletions (5 latest)
- Recent password changes (5 latest)

## 6. Admin Staff List
### Location
- Path: `/accounts/admin/staff/`

### Features
- View all staff members
- Search by username, name, email, phone
- Filter by active status
- Filter by role
- View staff details
- Quick actions: Edit, Reset Password, Delete

## 7. Audit & History Views
### Audit Trail View
- Path: `/accounts/admin/audit-trail/`
- All changes tracked
- Filterable by change type, admin, target user, date range
- Shows detailed before/after values

### Password Change History
- Path: `/accounts/admin/password-history/`
- All password changes tracked
- Who changed, when, why
- For which staff member

### Staff Deletion History
- Path: `/accounts/admin/deletion-history/`
- All deleted staff accounts
- Who deleted, when, why
- Original staff details archived

## 8. Login/Logout Tracking
- Admin logins/logouts automatically tracked
- IP address and user agent recorded
- Timestamp recorded
- Visible in audit trail

---

# தமிழ் மொழிতে விளக்கம் (Tamil Explanation)

## நிர்வாகன்-மட்டுமே அணுக முடியும் சிஸ்டம் மற்றும் மாற்றம் பதிவு

### மூல கொள்கை:
1. **Admin மட்டுமே** - Staff கணக்கு உருவாக்க, மாற்ற, நீக்க
2. **Staff** - Log in செய்யலாம், வேலை செய்யலாம், Password மாற்ற முடியாது
3. **அனைத்து மாற்றங்களும் பதிவிடப்படுகிறது** - யார், என்ன, எப்போது, எங்கிருந்து

### 1. Admin Login
- Admin பயனர் `is_pawnshop_admin = True` என்ற Flag வைத்திருப்பார்
- Regular Staff - இந்த Flag இல்லாமல் இருப்பார்
- Admin மட்டுமே Admin Dashboard அணுக முடியும்

### 2. Staff கணக்கு உருவாக்கம் (Admin மட்டுமே)
**எங்கே**: `/accounts/admin/staff/add/`

**என்ன நடக்கும்?**
1. Admin புதிய Staff username, email, பெயர், phone, role, branch  உள்ளிடுவார்
2. System தானாக Temporary Password உருவாக்கும்
3. Admin Password பார்க்கிறார் - Staff-க்கு Safely சொல்லலாம்
4. மாற்றம் Audit Trail-ல் பதிவாகிறது

### 3. Staff கணக்கு மாற்றியமைத்தல் (Admin மட்டுமே)
**எங்கே**: `/accounts/admin/staff/<id>/edit/`

**என்ன மாற்ற முடியும்?**
- Email பாக்கு
- பெயர்
- Phone எண்
- Role (வேலை வகை)
- Branch (கிளை)
- Active/Inactive நிலை

**பதிவு**: ஒவ்வொரு மாற்றமும் - பழைய மதிப்பு, புதிய மதிப்பு, யார் மாற்றினார், எப்போது

### 4. Staff கணக்கு நீக்கம் (Admin மட்டுமே)
**எங்கே**: `/accounts/admin/staff/<id>/delete/`

**என்ன பதிவாகிறது?**
- நீக்கப்பட்ட Staff பெயர், email
- யார் நீக்கினார் (Admin)
- எப்போது நீக்கினார்
- ஏன் நீக்கினார் (Reason)
- எங்கிருந்து நீக்கினார் (IP Address)
- Browser/Device info

### 5. Password மாற்றம்

**Staff Forgot Password?**
1. Staff `/accounts/password-reset/` க்கு செல்வார்
2. Email address உள்ளிடுவார்
3. Admin-ஐ கேட்க வேண்டும் - Admin மட்டுமே New Password உருவாக்க முடியும்

**Admin Password Reset (/accounts/admin/staff/<id>/reset-password/)**
1. Admin Staff name அல்லது ID தேடுவார்
2. "Reset Password" button கிளிக் செய்வார்
3. System புதிய Temporary Password உருவாக்கும்
4. Admin এந்த Password Staff-ஐ கொடுக்கிறார்
5. பதிவு: ஏ Admin, எந்த Staff, எப்போது மாற்றினார்

**Admin தனது Password மாற்றக்கூடும்**
1. `/accounts/password-change/` க்கு செல்லலாம்
2. Staff இந்த பக்கத்தில் Error கிடைக்கும்

### 6. அனைத்து மாற்றத்தின் பூர்ண பதிவு

**Audit Trail என்ன சேமிக்கிறது?**
- **யார் மாற்றினார்**: Admin பயனரின் பெயர்
- **என்ன செய்தார்**: Create, Update, Delete, Password Reset, Login, Logout
- **யாருக்கு**:  Staff பயனரின் பெயர்
- **என்ன மாற்றினார்**: Field name (email, name, role, etc.)
- **பழைய மதிப்பு**: மாற்றத்திற்கு முன்
- **புதிய மதிப்பு**: மாற்றத்திற்கு பின்
- **எப்போது**: Timestamp
- **எங்கிருந்து**: IP Address

**Password மாற்றத்தின் பதிவு:**
- ஏ Staff
- ஏ Admin reset செய்தார்
- மாற்றத்தின் தரவு: admin_reset, forgot_password
- Timestamp
- IP Address
- விளக்கம்

**Deleted Staff வரலாறு:**
- நீக்கப்பட்ட Staff முழு பதிவு தக்கவைக்கப்பட்டுள்ளது
- ஏ Admin நீக்கினார்
- ஏ நேரத்தில் நீக்கினார்
- ஏன் நீக்கினார்

### 7. Admin Dashboard
**எங்கே**: `/accounts/admin/dashboard/`

**இங்கு என்ன பார்க்கலாம்?**
- Total Staff எண்ணிக்கை
- Admin எண்ணிக்கை
- Active Staff எண்ணிக்கை
- Inactive Staff எண்ணிக்கை
- கடைசி 10 மாற்றங்கள் (Audit Trail)
- கடைசி 5 நீக்கப்பட்ட Staff
- கடைசி 5 Password மாற்றங்கள்

### 8. Staff List
**எங்கே**: `/accounts/admin/staff/`

**இங்கு என்ன செய்யலாம்?**
- அனைத்து Staff பார்க்கலாம்
- Search செய்யலாம் (பெயர், email, phone)
- Filter செய்யலாம் (active, role)
- Staff பிறப்பியைப் பார்க்கலாம்
- Edit செய்யலாம்
- Password Reset செய்யலாம்
- Delete செய்யலாம்

### 9. வரலாறு பார்க்கலாம்

**Audit Trail** (`/accounts/admin/audit-trail/`)
- அனைத்து மாற்றங்கள் இங்கு உள்ளன
- Filter செய்யலாம்: மாற்றத்தின் தரவு, Admin, Staff, தேதி வரம்பு

**Password Change History** (`/accounts/admin/password-history/`)
- அனைத்து Password மாற்றங்கள்
- யார் மாற்றினார், எப்போது
- ஏ Staff

**Deletion History** (`/accounts/admin/deletion-history/`)
- நீக்கப்பட்ட Staff பூரண வரலாறு
- ஏ Admin நீக்கினார்
- ஏ தேதியில் நீக்கினார்
- ஏன் நீக்கினார்

### 10. Login/Logout பদிவு
- Admin Login செய்யும் போது பதிவாகிறது
- Admin Logout செய்யும் போது பதிவாகிறது
- Time, IP Address, Browser info பதிவாகிறது

---

## Database Models / தரவுத்தளம் மாதிரிகள்

### AuditTrail Model
```
- admin_user (Foreign Key to CustomUser)
- change_type (Create, Update, Delete, Password Change, etc.)
- model_name (CustomUser, etc.)
- object_id (ID of changed object)
- object_str (String representation)
- field_name (For updates)
- old_value (Previous value)
- new_value (New value)
- timestamp (When)
- ip_address (Where from)
- user_agent (Browser info)
- target_user (Staff affected)
- description (Details)
```

### PasswordChangeHistory Model
```
- user (Staff پایہuser)
- changed_by_admin (Admin user)
- change_type (admin_reset, forgot_password)
- timestamp (When)
- ip_address (Where from)
- description (Why)
```

### StaffDeletion Model
```
- staff_user (Deleted user reference)
- deleted_by_admin (Admin user)
- username, email, first_name, last_name (Archived)
- role_name (What role they had)
- reason_for_deletion (Why)
- deletion_timestamp (When)
- ip_address (Where from)
```

### CustomUser Model - New Field
```
- is_pawnshop_admin (Boolean) - True for admins only
```

---

## API Endpoints / நுழைவுப் புள்ளிகள்

### Admin Routes
```
/accounts/admin/dashboard/                 - Admin Dashboard
/accounts/admin/staff/                     - Staff List
/accounts/admin/staff/add/                 - Create Staff
/accounts/admin/staff/<id>/edit/           - Edit Staff
/accounts/admin/staff/<id>/                - View Staff Details
/accounts/admin/staff/<id>/reset-password/ - Reset Password
/accounts/admin/staff/<id>/delete/         - Delete Staff
/accounts/admin/audit-trail/               - View Audit Trail
/accounts/admin/password-history/          - View Password Changes
/accounts/admin/deletion-history/          - View Deletions
```

---

## Utilities / பயன்பாட்டு செயல்பாடுகள்

### audit.py Functions
```python
log_audit_trail()           - Log any change
log_password_change()       - Log password change
log_staff_creation()        - Log staff creation
log_staff_update()          - Log staff update
log_staff_deletion()        - Log staff deletion
log_permission_change()     - Log permission change
log_login()                 - Log admin login
log_logout()                - Log admin logout
get_request_info()          - Extract IP, user agent
```

---

## Admin Panel Integration / Admin Panel ஒருங்கிணைப்பு

Django Admin में सभی तीनों नई models दिखाई देंगी:
- AuditTrail (Read-only)
- PasswordChangeHistory (Read-only)
- StaffDeletion (Read-only)

---

## Security Features / பாதுகாப்பு அம்சங்கள்

1. **Staff self-password change disabled** - Staff தங்கள் password மாற்ற முடியாது
2. **Admin password reset for staff** - Staff password மாற்ற Admin மட்டுமே
3. **Full audit trail** - அனைத்து செயல்பாடு பதிவிடப்படுகிறது
4. **IP tracking** - எங்கிருந்து மாற்றப்பட்டது பதிவிடப்படுகிறது
5. **Read-only history** - Audit records மாற்ற முடியாது

---

## Migration Files / பெயர்வு கோப்புகளை

- `0014_customuser_is_pawnshop_admin_audittrail_and_more.py`
  - Adds `is_pawnshop_admin` field to CustomUser
  - Creates AuditTrail model
  - Creates PasswordChangeHistory model
  - Creates StaffDeletion model

---

## Usage Examples / பயன்பாட்டு உதாரணங்கள்

### Create New Staff (Python code)
```python
from accounts.models import CustomUser, Role
from accounts.audit import log_staff_creation

# Create staff user
staff_user = CustomUser.objects.create_user(
    username='jsmith',
    email='john@example.com',
    first_name='John',
    last_name='Smith',
    phone='1234567890',
    role=Role.objects.get(name='Cashier'),
    is_pawnshop_admin=False
)

staff_user.set_password('TempPassword123!')
staff_user.save()

# Log creation
admin_user = CustomUser.objects.get(username='admin')
log_staff_creation(
    admin_user=admin_user,
    staff_user=staff_user,
    description="Created new cashier"
)
```

### Reset Staff Password
```python
from accounts.audit import log_password_change
import string, random

# Generate password
password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

# Reset
staff_user.set_password(password)
staff_user.save()

# Log
log_password_change(
    user=staff_user,
    changed_by_admin=admin_user,
    change_type='admin_reset',
    description='Password reset requested by staff'
)
```

### View Audit Trail
```python
from accounts.models import AuditTrail

# All changes for a staff member
changes = AuditTrail.objects.filter(target_user=staff_user).order_by('-timestamp')

# All changes by an admin
actions = AuditTrail.objects.filter(admin_user=admin_user).order_by('-timestamp')

# Password changes only
password_changes = AuditTrail.objects.filter(
    change_type='password_change'
).order_by('-timestamp')
```

---

## Installation & Setup / நிறுவல் மற்றும் அமைப்பு

1. **Database Migration**
```bash
python manage.py migrate accounts
```

2. **Create Admin Account**
```python
from accounts.models import CustomUser
admin = CustomUser.objects.create_superuser(
    username='admin',
    email='admin@example.com',
    password='secure_password',
    is_pawnshop_admin=True
)
```

3. **Access Admin Dashboard**
- Login as admin at `/accounts/login/`
- Navigate to `/accounts/admin/dashboard/`

---

## Notes / குறிப்புகள்

- All timestamps are stored in UTC
- IP addresses are extracted from request headers
- User agents are logged for device identification
- Audit records are read-only to maintain integrity
- Staff members cannot modify their own records
- Only admins can manage staff accounts
