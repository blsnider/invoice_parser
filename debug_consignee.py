#!/usr/bin/env python3
"""Debug consignee address extraction"""

import re

test_text = """58 - Omaha Scheels
CONSIGNEE:
17202 Davenport Street
Omaha, NE 68118
Shipping & Receiving
402-289-5666"""

print("Debugging consignee address extraction")
print("=" * 60)
print("Test text:")
print(test_text)
print("-" * 40)

# Test the pattern
consignee_block = re.search(
    r'CONSIGNEE:[\s\n]+([\s\S]*?)(?:DOCK TYPE|ACCESS\.|DELIVERY #|PICK UP #|NOTES|FREIGHT|Shipping)',
    test_text
)

if consignee_block:
    print(f"✅ Consignee block found:")
    print(f"'{consignee_block.group(1)}'")

    consignee_text = consignee_block.group(1)

    # Test address pattern
    addr_match = re.search(
        r'(\d+[^\n]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Circle|Way)[^\n]*)(?:[\s\n]+(?:Ste|Suite|Apt|Unit)\s+[^\n]+)?[\s\n]+([^,\n]+,\s*[A-Z]{2}\s+\d{5})',
        consignee_text
    )

    if addr_match:
        print(f"\n✅ Address match found:")
        print(f"  Street: {addr_match.group(1)}")
        print(f"  City/State/Zip: {addr_match.group(2)}")
    else:
        print("\n❌ No address match")
        print("\nTrying simpler pattern:")
        simple_match = re.search(r'(\d+[^\n]+)', consignee_text)
        if simple_match:
            print(f"  Found: {simple_match.group(1)}")
else:
    print("❌ No consignee block found")

print("\nTrying alternate approach - capture everything:")
alt_match = re.search(
    r'CONSIGNEE:[\s\n]+(\d+[^\n]+)[\s\n]+([^,\n]+,\s*[A-Z]{2}\s+\d{5})',
    test_text
)
if alt_match:
    print(f"✅ Alternate match:")
    print(f"  Street: {alt_match.group(1)}")
    print(f"  City/State/Zip: {alt_match.group(2)}")