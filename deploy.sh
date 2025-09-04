#!/bin/bash
# Deploy script for invoice parser with NetSuite integration

set -e

# Configuration
PROJECT_ID="sis-sandbox-463113"
REGION="us-central1"
SERVICE_NAME="invoice-parser"

echo "🚀 Deploying Invoice Parser with NetSuite Integration"
echo "======================================================="
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI is not installed"
    exit 1
fi

# Set the project
echo "Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Deploy directly from source (builds in Cloud Run)
echo ""
echo "📦 Building and deploying from local source..."
echo "This will build the Docker image in Cloud Run and deploy it"
echo ""

gcloud run deploy $SERVICE_NAME \
    --source . \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --max-instances 10 \
    --set-env-vars "PROJECT_ID=$PROJECT_ID,BUCKET_NAME=invoice-parsing-bucket,PROCESSOR_ID=86f1d13896882e30,PROCESSOR_LOCATION=us,SERVICE_ACCOUNT_EMAIL=invoice-parser-sa@sis-sandbox-463113.iam.gserviceaccount.com"

# Get the service URL
echo ""
echo "🔍 Getting service URL..."
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Service URL: $SERVICE_URL"
echo ""
echo "Test endpoints:"
echo "  Health:         $SERVICE_URL/health"
echo "  Vendor Search:  $SERVICE_URL/api/v1/netsuite/vendors/search?q=amazon"
echo "  GL Accounts:    $SERVICE_URL/api/v1/netsuite/accounts/expense"
echo ""
echo "📱 Update your React app .env file:"
echo "  REACT_APP_API_URL=$SERVICE_URL"