#!/usr/bin/env python
"""Test script to debug email finder"""
import sys
import os
sys.path.insert(0, 'backend')

from email_finder import EmailFinder
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("=" * 60)
print("Testing Email Finder")
print("=" * 60)

finder = EmailFinder()

print("\n1. Testing pattern generation...")
patterns = finder.generate_patterns("Swapnil", "Sahu", "microsoft.com")
print(f"   Generated {len(patterns)} patterns")
print(f"   First 5 patterns: {patterns[:5]}")

print("\n2. Testing email finder (this may take a while)...")
print("   Note: SMTP checks can take 5-10 seconds per email")
print("   We'll check only first 3 patterns for speed...\n")

# Test with just first pattern to see what happens
if patterns:
    test_email = "contact@projexa.ai"
    print(f"3. Testing verification of: {test_email}")
    print("   Starting verification...\n")
    
    try:
        from email_verifier import EmailVerifier
        import os
        verifier = EmailVerifier()
        internet_checks = True
        print(f"   Internet checks enabled: {internet_checks}")
        result = verifier.verify_email(test_email, internet_checks=internet_checks)
        
        print("\n" + "=" * 60)
        print("VERIFICATION RESULT:")
        print("=" * 60)
        print(f"Email: {result['email']}")
        print(f"Status: {result['status']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Reason: {result['reason']}")
        print("\nDetails:")
        if 'details' in result:
            details = result['details']
            if 'mx_check' in details:
                print(f"  MX Check: {details['mx_check']}")
            if 'smtp_check' in details:
                print(f"  SMTP Check: {details['smtp_check']}")
            if 'deliverability' in details:
                print(f"  Deliverability: {details['deliverability']}")
            if 'catch_all' in details:
                print(f"  Catch-all: {details['catch_all']}")
            if internet_checks and 'internet_check' in details:
                print(f"  Internet Check: {details['internet_check']}")
    except Exception as e:
        print(f"\nERROR during verification: {str(e)}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)

