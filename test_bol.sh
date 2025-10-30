#!/bin/bash

echo "BOL Parsing Service Test"
echo "========================"

BASE_URL="http://localhost:8080"

echo -e "\n1. Testing Health Endpoint:"
curl -s "$BASE_URL/health" | python -m json.tool

echo -e "\n2. Testing Root Endpoint (should show BOL endpoints):"
curl -s "$BASE_URL/" | python -m json.tool

echo -e "\n3. Testing BOL Parse Endpoint (without file, to check structure):"
curl -X POST "$BASE_URL/api/v1/parse-bol" -s | python -m json.tool

echo -e "\n4. Testing BOL List Endpoint:"
curl -s "$BASE_URL/api/v1/bols" | python -m json.tool

echo -e "\nIf you have a sample BOL PDF, test with:"
echo "curl -X POST '$BASE_URL/api/v1/parse-bol' \\"
echo "  -F 'file=@sample_bol.pdf' \\"
echo "  -F 'extract_tables=true' \\"
echo "  -F 'extract_items=true' | python -m json.tool"