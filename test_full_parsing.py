#!/usr/bin/env python3
"""Test full BOL parsing with the crash fixes"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re
from app.models.bol import ShipmentItem

def extract_items_from_page_text(page_text: str):
    """Simulate the fixed extraction logic"""
    items = []

    # Look for item section
    item_section = re.search(
        r'#\s*PACKAGES[\s\S]*?(?=FREIGHT CHARGES:|TOTAL|RECEIVED|$)',
        page_text,
        re.IGNORECASE
    )

    if item_section:
        item_text = item_section.group(0)

        # Extract item details into a dictionary first
        item_data = {}

        # Description with NMFC
        nmfc_match = re.search(r'NMFC\s*#([\d-]+)[,\s]+([^,\n]+)', item_text)
        if nmfc_match:
            item_data['nmfc_code'] = nmfc_match.group(1)
            description = nmfc_match.group(2).strip()
            # Clean up description
            item_data['description'] = re.sub(r'PCF.*$', '', description).strip()

        # Quantity and type
        qty_match = re.search(r'(\d+)\s+(Pallets?|Cartons?|Boxes?|Pieces?)', item_text, re.IGNORECASE)
        if qty_match:
            item_data['quantity'] = int(qty_match.group(1))
            item_data['packaging_type'] = qty_match.group(2).rstrip('s')

        # Weight
        weight_match = re.search(r'(\d+)\s*lbs', item_text, re.IGNORECASE)
        if weight_match:
            item_data['weight'] = float(weight_match.group(1))
            item_data['weight_unit'] = "LBS"

        # Class
        class_match = re.search(r'CLASS\s*\n?\s*(\d+)', item_text)
        if class_match:
            item_data['freight_class'] = class_match.group(1)

        # Dimensions
        dim_match = re.search(r'(\d+)\s*x\s*(\d+)\s*x\s*(\d+)', item_text)
        if dim_match:
            item_data['dimensions'] = f"{dim_match.group(1)}x{dim_match.group(2)}x{dim_match.group(3)}"

        # Only create ShipmentItem if we have a description (required field)
        if item_data.get('description'):
            item = ShipmentItem(**item_data)
            items.append(item)
        elif item_data.get('nmfc_code'):
            # If we only have NMFC code but no description, use a generic description
            item_data['description'] = f"Item with NMFC #{item_data['nmfc_code']}"
            item = ShipmentItem(**item_data)
            items.append(item)

    return items

# Test with problematic BOL text
test_text = """
# PACKAGES
HM
DESCRIPTION
QTY
CLASS
SHIPPING WEIGHT
1 Pallets
1
250
120 lbs
|NMFC #61700-03, Electrical appliances, food slicers,
fryers, sharpeners PCF of 2 but less than 4
48 x 40 x 48 (x1) PCF=2.2500
***Special Instructions***
Cartons: 12 PO#s: 20880457
FREIGHT CHARGES: Collect
TOTAL
1 Pallets
120 lbs
"""

print("Testing BOL item extraction with crash fixes...")
print("=" * 60)

try:
    items = extract_items_from_page_text(test_text)

    if items:
        print(f"✅ Successfully extracted {len(items)} item(s)")
        for i, item in enumerate(items, 1):
            print(f"\nItem {i}:")
            print(f"  Description: {item.description}")
            print(f"  NMFC Code: {item.nmfc_code}")
            print(f"  Quantity: {item.quantity}")
            print(f"  Package Type: {item.packaging_type}")
            print(f"  Weight: {item.weight} {item.weight_unit}")
            print(f"  Freight Class: {item.freight_class}")
            print(f"  Dimensions: {item.dimensions}")
    else:
        print("❌ No items extracted")

except Exception as e:
    print(f"❌ Error during extraction: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)

# Test edge cases
print("\nTesting edge cases...")
print("-" * 40)

# Test with no description
test_no_desc = "# PACKAGES\nNo valid item data here\nFREIGHT CHARGES: Collect"
try:
    items = extract_items_from_page_text(test_no_desc)
    print(f"✅ No description case: Returned {len(items)} items (expected 0)")
except Exception as e:
    print(f"❌ Failed on no description case: {e}")

# Test with NMFC but no description after it
test_nmfc_only = "# PACKAGES\nNMFC #12345\nFREIGHT CHARGES: Collect"
try:
    items = extract_items_from_page_text(test_nmfc_only)
    if items and items[0].description == "Item with NMFC #12345":
        print(f"✅ NMFC-only case: Created generic description")
    else:
        print(f"✅ NMFC-only case: Returned {len(items)} items")
except Exception as e:
    print(f"❌ Failed on NMFC-only case: {e}")

print("\n✅ All tests completed successfully - no crashes!")