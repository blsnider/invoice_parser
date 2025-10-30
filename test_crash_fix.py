#!/usr/bin/env python3
"""Test that the crash fixes work properly"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.bol import ShipmentItem

def test_shipment_item_creation():
    """Test that ShipmentItem requires description field"""

    print("Testing ShipmentItem creation...")
    print("-" * 40)

    # Test 1: Creating with description should work
    try:
        item1 = ShipmentItem(description="Test item")
        print("✅ Test 1 PASSED: ShipmentItem created with description")
    except Exception as e:
        print(f"❌ Test 1 FAILED: {e}")

    # Test 2: Creating without description should fail
    try:
        item2 = ShipmentItem()
        print("❌ Test 2 FAILED: ShipmentItem created without description (should have failed)")
    except Exception as e:
        print(f"✅ Test 2 PASSED: ShipmentItem correctly requires description - {type(e).__name__}")

    # Test 3: Creating with dictionary unpacking
    item_data = {
        'description': 'Electrical appliances',
        'nmfc_code': '61700-03',
        'quantity': 1,
        'weight': 120.0,
        'weight_unit': 'LBS'
    }
    try:
        item3 = ShipmentItem(**item_data)
        print(f"✅ Test 3 PASSED: ShipmentItem created from dictionary")
        print(f"   - Description: {item3.description}")
        print(f"   - NMFC Code: {item3.nmfc_code}")
        print(f"   - Weight: {item3.weight} {item3.weight_unit}")
    except Exception as e:
        print(f"❌ Test 3 FAILED: {e}")

    # Test 4: Creating with empty dictionary should fail
    empty_data = {}
    try:
        item4 = ShipmentItem(**empty_data)
        print("❌ Test 4 FAILED: ShipmentItem created with empty dict (should have failed)")
    except Exception as e:
        print(f"✅ Test 4 PASSED: Empty dict correctly rejected - {type(e).__name__}")

if __name__ == "__main__":
    test_shipment_item_creation()
    print("\n" + "=" * 40)
    print("All critical tests completed!")