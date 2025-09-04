#!/bin/bash

# Invoice Parser API Test Script
API_URL="https://invoice-parser-41815171183.us-central1.run.app"

echo "======================================"
echo "Invoice Parser API Test"
echo "API URL: $API_URL"
echo "======================================"

# Test 1: Health Check
echo -e "\n1. Testing Health Endpoint..."
curl -s "$API_URL/health" | python3 -m json.tool

# Test 2: Root Endpoint
echo -e "\n2. Testing Root Endpoint..."
curl -s "$API_URL/" | python3 -m json.tool

# Test 3: Parse Invoice (requires a PDF file)
if [ -f "sample_invoice.pdf" ]; then
    echo -e "\n3. Testing Invoice Parse Endpoint..."
    curl -X POST "$API_URL/api/v1/parse-invoice" \
        -F "file=@sample_invoice.pdf" \
        -F "extract_tables=true" \
        -F "extract_line_items=true" \
        | python3 -m json.tool
else
    echo -e "\n3. Skipping Invoice Parse Test (no sample_invoice.pdf found)"
    echo "To test parsing, create a sample_invoice.pdf file"
fi

echo -e "\n======================================"
echo "Test Complete!"
echo "======================================" 