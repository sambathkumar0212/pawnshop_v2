#!/usr/bin/env python3
"""
FIX TAMIL PDF GENERATION - Direct file manipulation
Replaces corrupted Tamil text in build_loan_pdf_language_context() 
with proper Unicode text
"""

import os
import sys

# Get the path to transactions/views.py
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIEWS_FILE = os.path.join(SCRIPT_DIR, 'transactions', 'views.py')
CORRECTED_FUNC_FILE = os.path.join(SCRIPT_DIR, 'corrected_function.py')

def read_corrected_function():
    """Read the corrected function from corrected_function.py"""
    with open(CORRECTED_FUNC_FILE, 'r', encoding='utf-8') as f:
        # Read until we hit the next function def
        content = f.read()
        # Extract just the function (everything before the final return statement + 1 line)
        return content

def fix_views_file():
    """
    Replace the corrupted build_loan_pdf_language_context function
    with the corrected version
    """
    print("=" * 70)
    print("TAMIL PDF GENERATION FIX")
    print("=" * 70)
    
    # Read the corrected function
    print("\n1. Reading corrected function...")
    try:
        corrected_func = read_corrected_function()
        print(f"   ✓ Corrected function loaded ({len(corrected_func)} bytes)")
    except FileNotFoundError:
        print(f"   ✗ ERROR: {CORRECTED_FUNC_FILE} not found")
        return False
    except Exception as e:
        print(f"   ✗ ERROR reading corrected function: {e}")
        return False
    
    # Read the original views.py file
    print("\n2. Reading transactions/views.py...")
    try:
        with open(VIEWS_FILE, 'r', encoding='utf-8') as f:
            original_content = f.read()
        print(f"   ✓ Views file loaded ({len(original_content)} bytes)")
    except FileNotFoundError:
        print(f"   ✗ ERROR: {VIEWS_FILE} not found")
        return False
    except Exception as e:
        print(f"   ✗ ERROR reading views file: {e}")
        return False
    
    # Find the function boundaries
    print("\n3. Locating function boundaries...")
    func_marker = 'def build_loan_pdf_language_context(loan, current_language):'
    func_start = original_content.find(func_marker)
    
    if func_start == -1:
        print(f"   ✗ ERROR: Could not find function '{func_marker}'")
        return False
    
    print(f"   ✓ Function starts at position {func_start}")
    
    # Find the end of the function (next function definition)
    next_func_start = original_content.find('\ndef ', func_start + 100)
    
    if next_func_start == -1:
        print("   ✗ ERROR: Could not find end of function")
        return False
    
    # Back up to the actual newline before the next function
    func_end = original_content.rfind('\n', func_start, next_func_start)
    
    print(f"   ✓ Function ends at position {func_end}")
    line_start = original_content[:func_start].count('\n') + 1
    line_end = original_content[:func_end].count('\n') + 1
    print(f"   ✓ Function spans lines {line_start}-{line_end}")
    
    # Analyze corruption
    print("\n4. Analyzing corruption...")
    func_content = original_content[func_start:func_end]
    corrupted_indicators = func_content.count('ÃƒÂ ')
    print(f"   ✓ Found ~{corrupted_indicators // 100} corrupted Tamil text blocks")
    
    # Build the new content
    print("\n5. Building corrected version...")
    new_content = (
        original_content[:func_start] +
        corrected_func.rstrip() + '\n\n' +
        original_content[func_end:]
    )
    print(f"   ✓ New content assembled ({len(new_content)} bytes)")
    
    # Verify the replacement
    print("\n6. Verifying replacement...")
    if 'பொன் கடன் ஒப்பந்தம்' in new_content:
        print(f"   ✓ Proper Tamil Unicode found in new content")
    else:
        print(f"   ✗ ERROR: Tamil Unicode not found in result")
        return False
    
    if 'ÃƒÂ ' not in new_content[func_start:func_start+1000]:
        print(f"   ✓ Corrupted text removed from function start")
    else:
        print(f"   ! Warning: Corrupted text still present near function")
    
    # Write the corrected file
    print("\n7. Writing corrected file...")
    try:
        # Create backup
        backup_file = VIEWS_FILE + '.backup'
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(original_content)
        print(f"   ✓ Backup created: {backup_file}")
        
        # Write corrected version
        with open(VIEWS_FILE, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"   ✓ Corrected file written: {VIEWS_FILE}")
    except Exception as e:
        print(f"   ✗ ERROR writing file: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("✓ FIX COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Run tests: python manage.py test transactions")
    print("2. Test PDF generation: python manage.py shell")
    print("3. Run validation: python test_tamil_fixes.py")
    
    return True

if __name__ == '__main__':
    success = fix_views_file()
    sys.exit(0 if success else 1)
