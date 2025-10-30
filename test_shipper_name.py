#!/usr/bin/env python3
"""Test shipper name extraction"""

import re

def test_shipper_extraction(text):
    """Test current shipper extraction logic"""
    entities = {}

    # Current patterns
    shipper_patterns = [
        r'SHIPPER INFORMATION[\s\n]+([A-Z][A-Z\s]+(?:COMPANY|SALES|LLC|INC|CORP)?[^\n]*)',
        r'ORIGIN:[\s\n]+MOTIVATIONAL FULFILLMENT',
    ]

    for pattern in shipper_patterns:
        shipper_match = re.search(pattern, text)
        if shipper_match:
            if 'ORIGIN:' in pattern:
                entities['shipper_name'] = 'MOTIVATIONAL FULFILLMENT'
            else:
                shipper_name = shipper_match.group(1).strip()
                # Clean up the name
                shipper_name = re.sub(r'/\s*C\/O.*$', '', shipper_name).strip()
                if shipper_name and 'CONSIGNEE' not in shipper_name:
                    entities['shipper_name'] = shipper_name
            break

    return entities.get('shipper_name')

# Test cases
test_cases = [
    # Case 1: From the problematic BOL
    """SHIPPER INFORMATION
SHARKNINJA SALES COMPANY / C/O
ORIGIN:
MOTIVATIONAL FULFILLMENT""",

    # Case 2: Just the header section
    """CONSIGNEE INFORMATION
SHIPPER INFORMATION
SHARKNINJA SALES COMPANY / C/O
ORIGIN:
MOTIVATIONAL FULFILLMENT""",

    # Case 3: Full context from actual BOL
    """STRAIGHT BILL OF LADING - Master
NAME OF CARRIER
PRO #
DATE
BOL #
The Custom Companies Inc - Consolidation
9/18/2025
3608528
CONSIGNEE INFORMATION
SHIPPER INFORMATION
SHARKNINJA SALES COMPANY / C/O
ORIGIN:
MOTIVATIONAL FULFILLMENT
15785 MOUNTAIN AVENUE
Chino, CA 91708""",
]

print("Testing Shipper Name Extraction")
print("=" * 60)

for i, test_text in enumerate(test_cases, 1):
    print(f"\nTest Case {i}:")
    print("-" * 40)
    print(f"Input preview: {test_text[:100].replace(chr(10), ' ')}...")
    result = test_shipper_extraction(test_text)
    if result:
        print(f"✅ Extracted: '{result}'")
    else:
        print(f"❌ No shipper name extracted")

    # Show what the pattern is matching
    pattern1 = r'SHIPPER INFORMATION[\s\n]+([A-Z][A-Z\s]+(?:COMPANY|SALES|LLC|INC|CORP)?[^\n]*)'
    match1 = re.search(pattern1, test_text)
    if match1:
        print(f"   Pattern 1 matched: '{match1.group(1).strip()}'")
    else:
        print(f"   Pattern 1: No match")

print("\n" + "=" * 60)
print("\nIssue Analysis:")
print("-" * 40)

# Analyze the actual text structure
actual_text = """CONSIGNEE INFORMATION
SHIPPER INFORMATION
SHARKNINJA SALES COMPANY / C/O
ORIGIN:
MOTIVATIONAL FULFILLMENT"""

print("Looking at the actual structure:")
lines = actual_text.split('\n')
for i, line in enumerate(lines):
    print(f"  Line {i}: '{line}'")

print("\nThe problem:")
print("1. The pattern expects text AFTER 'SHIPPER INFORMATION'")
print("2. But the actual format has headers on same line: 'CONSIGNEE INFORMATION' and 'SHIPPER INFORMATION'")
print("3. The shipper name 'SHARKNINJA SALES COMPANY' appears on the NEXT line")
print("4. Current pattern captures 'SHARKNINJA SALES COMPANY / C/O' but includes headers")

# Test improved pattern
print("\n" + "=" * 60)
print("Testing improved pattern:")
improved_pattern = r'SHIPPER INFORMATION.*?\n([A-Z][A-Z\s]+(?:COMPANY|SALES|LLC|INC|CORP)?[^\n/]*)'
match = re.search(improved_pattern, actual_text, re.DOTALL)
if match:
    print(f"✅ Better match: '{match.group(1).strip()}'")