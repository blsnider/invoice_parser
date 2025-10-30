#!/usr/bin/env python3
"""Analyze what shipper name is coming through vs what's expected"""

import json

# The JSON result you showed me
current_result = {
    "shipper": {
        "name": None,  # This is the problem - it's null
        "street": "MOTIVATIONAL FULFILLMENT",  # Street has the company name
        "city": None,
        "state": None,
        "postal_code": None,
        "country": "USA",
        "contact_name": None,
        "contact_phone": None
    }
}

# What should be extracted
expected_result = {
    "shipper": {
        "name": "SHARKNINJA SALES COMPANY",  # Or "MOTIVATIONAL FULFILLMENT"?
        "street": "15785 MOUNTAIN AVENUE",
        "city": "Chino",
        "state": "CA",
        "postal_code": "91708",
        "country": "USA",
        "contact_name": "Donna Merlin",
        "contact_phone": "514-234-0004"
    }
}

print("Current vs Expected Shipper Information")
print("=" * 60)

print("\n🔴 CURRENT (Wrong):")
print(json.dumps(current_result['shipper'], indent=2))

print("\n✅ EXPECTED:")
print(json.dumps(expected_result['shipper'], indent=2))

print("\n" + "=" * 60)
print("Analysis of the problem:")
print("-" * 40)
print("1. Shipper 'name' field is null/None")
print("2. Shipper 'street' field contains 'MOTIVATIONAL FULFILLMENT' (which is actually a company name)")
print("3. Missing actual street address '15785 MOUNTAIN AVENUE'")
print("4. Missing city, state, postal code")
print("5. Missing contact info (Donna Merlin, 514-234-0004)")

print("\nThe confusion:")
print("- SHARKNINJA SALES COMPANY is listed as 'SHIPPER'")
print("- MOTIVATIONAL FULFILLMENT is listed after 'ORIGIN:' (fulfillment center)")
print("- Which one should be the shipper name?")
print("  Option 1: SHARKNINJA SALES COMPANY (the actual shipper)")
print("  Option 2: MOTIVATIONAL FULFILLMENT (the origin/fulfillment center)")
print("  Option 3: Both? (SHARKNINJA via MOTIVATIONAL FULFILLMENT)")

print("\nRecommendation:")
print("- Use 'SHARKNINJA SALES COMPANY' as the shipper name")
print("- Keep 'MOTIVATIONAL FULFILLMENT' as part of the address or in a separate field")