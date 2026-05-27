#!/usr/bin/env python3
"""
Fix corrupted Tamil text in transactions/views.py in-place
Uses direct file operations to handle complex encoding issues
"""

import os
import sys
import re

def fix_corrupted_tamil_labels(file_path):
    """
    Replace corrupted Tamil text in labels dict and terms list
    with proper Unicode Tamil text
    """
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Correct Tamil text mapping
    corrections = {
        # These are real-world corruptions - we're replacing the exact corrupted strings
        # with proper Tamil Unicode
       'ÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â®Ã¢â€žÂ¢ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã¢â‚¬Â¢ÃƒÂ Ã‚Â®Ã¢â‚¬Â¢ÃƒÂ Ã‚Â¯Ã‚Â ÃƒÂ Ã‚Â®Ã¢â‚¬Â¢ÃƒÂ Ã‚Â®Ã…Â¸ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â¯Ã‚Â ÃƒÂ Ã‚Â®Ã¢â‚¬â„¢ÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¨ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â®Ã‚Â®ÃƒÂ Ã‚Â¯Ã‚Â': 'பொன் கடன் ஒப்பந்தம்',
    }
    
    # Instead of trying to replace all corrupted strings individually,
    # we'll use a regex-based replacement strategy for common patterns
    
    # Count corrupted entries
    corrupted_count = content.count('ÃƒÂ ')
    print(f"Found {corrupted_count // 10} likely corrupted Tamil text blocks")
    
    # The safest approach: read the original function and replace it wholesale
    # First, let's just mark where the function needs fixing
    print(f"File path: {file_path}")
    print(f"File size: {len(content)} bytes")
    
    # Find the function start
    func_start = content.find('def build_loan_pdf_language_context(loan, current_language):')
    if func_start == -1:
        print("ERROR: Could not find function build_loan_pdf_language_context")
        return False
    
    # Find the next function definition to know where this one ends
    next_func_start = content.find('\ndef ', func_start + 1)
    if next_func_start == -1:
        print("ERROR: Could not find end of function")
        return False
    
    print(f"Function found at position {func_start}")
    print(f"Function ends around position {next_func_start}")
    print("\n✓ Function boundaries identified successfully")
    print(f"  Start: line {content[:func_start].count(chr(10)) + 1}")
    print(f"  End:   line {content[:next_func_start].count(chr(10)) + 1}")
    
    return True

if __name__ == '__main__':
    filepath = 'transactions/views.py'
    if fix_corrupted_tamil_labels(filepath):
        print("\n✓ Analysis complete. Function is ready for replacement.")
        print("\nNext step: Use multi_replace_string_in_file with the corrected function")
    else:
        print("\n✗ Error during analysis")
        sys.exit(1)
