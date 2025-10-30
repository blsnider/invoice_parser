#!/usr/bin/env python3
"""
Test script for BOL parsing endpoint
"""

import requests
import json
from pathlib import Path


def test_bol_endpoint():
    """Test the BOL parsing endpoint"""

    # Configuration
    base_url = "http://localhost:8080"
    endpoint = f"{base_url}/api/v1/parse-bol"

    # Check if service is running
    try:
        health_response = requests.get(f"{base_url}/health")
        print("Health Check Response:")
        print(json.dumps(health_response.json(), indent=2))
        print("-" * 50)
    except Exception as e:
        print(f"Error: Service not running at {base_url}")
        print(f"Error details: {e}")
        return

    # Create a test PDF file (you'll need to provide an actual BOL PDF)
    test_pdf = Path("sample_bol.pdf")

    if not test_pdf.exists():
        print(f"Warning: No test BOL PDF found at {test_pdf}")
        print("Creating a dummy test to verify the endpoint structure...")

        # Test without file to verify endpoint exists
        try:
            response = requests.post(endpoint)
            print(f"Endpoint exists. Status: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"Endpoint error: {e}")
        return

    # Test with actual BOL PDF
    with open(test_pdf, 'rb') as f:
        files = {'file': (test_pdf.name, f, 'application/pdf')}
        data = {
            'extract_tables': True,
            'extract_items': True,
            'language_hints': 'en'
        }

        print(f"Sending BOL PDF to {endpoint}")
        response = requests.post(endpoint, files=files, data=data)

    print(f"Status Code: {response.status_code}")
    print("\nResponse:")

    if response.status_code == 200:
        result = response.json()
        print(json.dumps(result, indent=2, default=str))

        if result.get('success'):
            print("\n✅ BOL parsed successfully!")
            print(f"BOL ID: {result.get('document_id')}")
            if result.get('data'):
                data = result['data']
                print(f"BOL Number: {data.get('bol_number')}")
                print(f"Shipper: {data.get('shipper')}")
                print(f"Consignee: {data.get('consignee')}")
                print(f"Items Count: {len(data.get('shipment_items', []))}")
        else:
            print("\n❌ BOL parsing failed")
            print(f"Message: {result.get('message')}")
    else:
        print(response.text)


def test_endpoints_available():
    """Check if all BOL endpoints are available"""
    base_url = "http://localhost:8080"

    endpoints = [
        "/",
        "/health",
        "/api/v1/parse-bol",
        "/api/v1/parse-batch-bol",
        "/api/v1/bols"
    ]

    print("Checking BOL endpoints availability:\n")
    for endpoint in endpoints:
        try:
            if "parse" in endpoint and "batch" not in endpoint:
                response = requests.post(f"{base_url}{endpoint}")
            else:
                response = requests.get(f"{base_url}{endpoint}")
            print(f"✅ {endpoint} - Status: {response.status_code}")
        except Exception as e:
            print(f"❌ {endpoint} - Error: {e}")


if __name__ == "__main__":
    print("BOL Parsing Service Test")
    print("=" * 50)

    test_endpoints_available()
    print("\n" + "=" * 50 + "\n")
    test_bol_endpoint()