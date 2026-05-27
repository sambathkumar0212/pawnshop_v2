from django.core.management.base import BaseCommand
from django.conf import settings
from transactions.models import Loan
import json
import os
from PIL import Image, ImageDraw, ImageFont
import uuid

class Command(BaseCommand):
    help = 'Fix missing loan item photos by creating placeholder images or cleaning database references'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            type=str,
            choices=['placeholder', 'clean', 'report'],
            default='report',
            help='Mode: placeholder (create missing images), clean (remove DB refs), report (show status)'
        )
        parser.add_argument(
            '--fix-all',
            action='store_true',
            help='Fix all missing images without prompting'
        )

    def handle(self, *args, **options):
        mode = options['mode']
        fix_all = options['fix_all']
        
        self.stdout.write(self.style.SUCCESS(f'🔍 Scanning for missing loan item photos...'))
        
        # Find all loans with missing images
        missing_images_data = self.find_missing_images()
        
        if not missing_images_data:
            self.stdout.write(self.style.SUCCESS('✅ No missing images found!'))
            return
            
        total_missing = sum(len(data['missing_files']) for data in missing_images_data)
        
        self.stdout.write(
            self.style.WARNING(
                f'❌ Found {len(missing_images_data)} loans with {total_missing} missing image files'
            )
        )
        
        if mode == 'report':
            self.show_report(missing_images_data)
        elif mode == 'placeholder':
            self.create_placeholder_images(missing_images_data, fix_all)
        elif mode == 'clean':
            self.clean_database_references(missing_images_data, fix_all)

    def find_missing_images(self):
        """Find all loans with missing image files"""
        missing_images_data = []
        
        for loan in Loan.objects.exclude(item_photos__isnull=True).exclude(item_photos='').exclude(item_photos='[]'):
            try:
                if isinstance(loan.item_photos, str):
                    photos = json.loads(loan.item_photos)
                else:
                    photos = loan.item_photos
                    
                if isinstance(photos, list):
                    missing_files = []
                    for photo_url in photos:
                        if isinstance(photo_url, str) and photo_url.startswith('/media/'):
                            # Convert URL to file path
                            file_path = os.path.join(settings.BASE_DIR, photo_url.lstrip('/'))
                            if not os.path.exists(file_path):
                                missing_files.append({
                                    'url': photo_url,
                                    'path': file_path
                                })
                    
                    if missing_files:
                        missing_images_data.append({
                            'loan': loan,
                            'missing_files': missing_files
                        })
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing loan {loan.loan_number}: {e}')
                )
                
        return missing_images_data

    def show_report(self, missing_images_data):
        """Show detailed report of missing images"""
        self.stdout.write(self.style.WARNING('\n📋 MISSING IMAGES REPORT:'))
        self.stdout.write('=' * 50)
        
        for data in missing_images_data:
            loan = data['loan']
            missing_files = data['missing_files']
            
            self.stdout.write(f'\n🏷️  Loan: {loan.loan_number}')
            self.stdout.write(f'   Customer: {loan.customer.first_name} {loan.customer.last_name}')
            self.stdout.write(f'   Missing images: {len(missing_files)}')
            
            for i, file_info in enumerate(missing_files[:3], 1):  # Show first 3
                filename = os.path.basename(file_info['path'])
                self.stdout.write(f'     {i}. {filename}')
            
            if len(missing_files) > 3:
                self.stdout.write(f'     ... and {len(missing_files) - 3} more')
                
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('\n💡 Next steps:'))
        self.stdout.write('   • Run with --mode=placeholder to create placeholder images')
        self.stdout.write('   • Run with --mode=clean to remove database references')

    def create_placeholder_images(self, missing_images_data, fix_all):
        """Create placeholder images for missing files"""
        if not fix_all:
            confirm = input(f'\n🖼️  Create placeholder images for {sum(len(d["missing_files"]) for d in missing_images_data)} missing files? (y/N): ')
            if confirm.lower() != 'y':
                self.stdout.write('❌ Cancelled')
                return
                
        self.stdout.write(self.style.SUCCESS('\n🖼️  Creating placeholder images...'))
        
        created_count = 0
        for data in missing_images_data:
            loan = data['loan']
            
            for file_info in data['missing_files']:
                try:
                    self.create_placeholder_image(file_info['path'], loan)
                    created_count += 1
                    self.stdout.write(f'✅ Created: {os.path.basename(file_info["path"])}')
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Failed to create {os.path.basename(file_info["path"])}: {e}')
                    )
                    
        self.stdout.write(
            self.style.SUCCESS(f'\n🎉 Created {created_count} placeholder images!')
        )

    def create_placeholder_image(self, file_path, loan):
        """Create a single placeholder image"""
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Create a 400x300 placeholder image
        img = Image.new('RGB', (400, 300), color='#f8f9fa')
        draw = ImageDraw.Draw(img)
        
        # Try to use a better font, fall back to default
        try:
            font_large = ImageFont.truetype('/System/Library/Fonts/Arial.ttf', 24)
            font_small = ImageFont.truetype('/System/Library/Fonts/Arial.ttf', 16)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Draw border
        draw.rectangle([10, 10, 390, 290], outline='#dee2e6', width=2)
        
        # Draw icon (simplified camera icon)
        draw.rectangle([180, 120, 220, 150], fill='#6c757d')
        draw.rectangle([190, 110, 210, 120], fill='#6c757d')
        draw.ellipse([185, 125, 215, 155], outline='#6c757d', width=3)
        
        # Add text
        text1 = "Item Photo"
        text2 = f"Loan #{loan.loan_number}"
        text3 = "Placeholder Image"
        
        # Calculate text positions (center aligned)
        bbox1 = draw.textbbox((0, 0), text1, font=font_large)
        bbox2 = draw.textbbox((0, 0), text2, font=font_small)
        bbox3 = draw.textbbox((0, 0), text3, font=font_small)
        
        x1 = (400 - (bbox1[2] - bbox1[0])) // 2
        x2 = (400 - (bbox2[2] - bbox2[0])) // 2
        x3 = (400 - (bbox3[2] - bbox3[0])) // 2
        
        draw.text((x1, 180), text1, fill='#495057', font=font_large)
        draw.text((x2, 210), text2, fill='#6c757d', font=font_small)
        draw.text((x3, 235), text3, fill='#adb5bd', font=font_small)
        
        # Save the image
        img.save(file_path, 'JPEG', quality=85)

    def clean_database_references(self, missing_images_data, fix_all):
        """Remove references to missing images from database"""
        if not fix_all:
            confirm = input(f'\n🗑️  Remove database references to missing images for {len(missing_images_data)} loans? (y/N): ')
            if confirm.lower() != 'y':
                self.stdout.write('❌ Cancelled')
                return
                
        self.stdout.write(self.style.SUCCESS('\n🗑️  Cleaning database references...'))
        
        updated_count = 0
        for data in missing_images_data:
            loan = data['loan']
            missing_urls = [f['url'] for f in data['missing_files']]
            
            try:
                # Parse current photos
                if isinstance(loan.item_photos, str):
                    photos = json.loads(loan.item_photos)
                else:
                    photos = loan.item_photos
                    
                # Remove missing photos
                if isinstance(photos, list):
                    existing_photos = [p for p in photos if p not in missing_urls]
                    loan.item_photos = json.dumps(existing_photos)
                    loan.save(update_fields=['item_photos'])
                    updated_count += 1
                    
                    self.stdout.write(
                        f'✅ Loan {loan.loan_number}: Removed {len(missing_urls)} missing references'
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Failed to update loan {loan.loan_number}: {e}')
                )
                
        self.stdout.write(
            self.style.SUCCESS(f'\n🎉 Updated {updated_count} loan records!')
        )