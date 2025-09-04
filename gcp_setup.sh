#!/bin/bash

# GCP Resource Setup Script for Invoice Parsing Service
# This script will set up all required GCP resources for the new sis-sandbox-463113 project

set -e

# Configuration
PROJECT_ID="sis-sandbox-463113"
REGION="us-central1"
BUCKET_NAME="invoice-parsing-bucket"
PROCESSOR_DISPLAY_NAME="Invoice Parser"
SERVICE_ACCOUNT_NAME="invoice-parser-sa"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "🚀 Setting up GCP resources for Invoice Parsing Service"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "."; then
    echo "❌ Please authenticate with gcloud first:"
    echo "gcloud auth login"
    exit 1
fi

# Set the project
echo "🔧 Setting project to $PROJECT_ID"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "📋 Enabling required APIs..."
gcloud services enable documentai.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable iam.googleapis.com

echo "⏳ Waiting for APIs to be fully enabled..."
sleep 30

# Create GCS bucket
echo "🪣 Creating Cloud Storage bucket: $BUCKET_NAME"
if gsutil ls gs://$BUCKET_NAME > /dev/null 2>&1; then
    echo "✅ Bucket $BUCKET_NAME already exists"
else
    gsutil mb -p $PROJECT_ID -l $REGION gs://$BUCKET_NAME
    echo "✅ Created bucket: $BUCKET_NAME"
fi

# Create folder structure in bucket
echo "📁 Creating folder structure in bucket..."
echo "" | gsutil cp - gs://$BUCKET_NAME/invoices/.keep
echo "" | gsutil cp - gs://$BUCKET_NAME/parsed/.keep
echo "✅ Created folder structure"

# Create service account
echo "👤 Creating service account: $SERVICE_ACCOUNT_NAME"
if gcloud iam service-accounts describe $SERVICE_ACCOUNT_EMAIL > /dev/null 2>&1; then
    echo "✅ Service account already exists"
else
    gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
        --display-name="Invoice Parser Service Account" \
        --description="Service account for invoice parsing service"
    echo "✅ Created service account: $SERVICE_ACCOUNT_EMAIL"
fi

# Grant necessary IAM roles to service account
echo "🔐 Granting IAM roles to service account..."
ROLES=(
    "roles/documentai.apiUser"
    "roles/storage.objectAdmin"
    "roles/run.invoker"
    "roles/logging.logWriter"
    "roles/monitoring.metricWriter"
)

for role in "${ROLES[@]}"; do
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
        --role="$role" \
        --quiet
    echo "  ✅ Granted $role"
done

# Create Document AI processor
echo "🤖 Creating Document AI processor..."
echo "⚠️  Note: Document AI processors must be created through the GCP Console"
echo "   1. Go to: https://console.cloud.google.com/ai/document-ai/processors"
echo "   2. Make sure project '$PROJECT_ID' is selected"
echo "   3. Click 'Create Processor'"
echo "   4. Select 'Invoice Parser'"
echo "   5. Name it '$PROCESSOR_DISPLAY_NAME'"
echo "   6. Select region '$REGION'"
echo "   7. Copy the Processor ID for your environment variables"

echo ""
echo "📋 After creating the processor, you'll need the Processor ID."
echo "   It looks like: 1234567890abcdef"
echo "   You can find it in the processor details page."

# Create service account key (for local development)
KEY_FILE="service-account-key.json"
echo "🗝️  Creating service account key for local development..."
if [[ -f "$KEY_FILE" ]]; then
    echo "⚠️  Service account key file already exists: $KEY_FILE"
    echo "   Delete it first if you want to create a new one."
else
    gcloud iam service-accounts keys create $KEY_FILE \
        --iam-account=$SERVICE_ACCOUNT_EMAIL
    echo "✅ Created service account key: $KEY_FILE"
    echo "⚠️  Keep this file secure and never commit it to version control!"
fi

# Set up Cloud Storage permissions
echo "🔒 Setting up Cloud Storage permissions..."
gsutil iam ch serviceAccount:$SERVICE_ACCOUNT_EMAIL:objectAdmin gs://$BUCKET_NAME
echo "✅ Granted storage permissions"

echo ""
echo "🎉 GCP setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Create the Document AI processor using the console link above"
echo "2. Update your environment variables:"
echo "   export PROJECT_ID='$PROJECT_ID'"
echo "   export BUCKET_NAME='$BUCKET_NAME'"
echo "   export PROCESSOR_ID='your-processor-id-from-console'"
echo "   export GOOGLE_APPLICATION_CREDENTIALS='$(pwd)/$KEY_FILE'"
echo ""
echo "3. Test the setup:"
echo "   gsutil ls gs://$BUCKET_NAME"
echo ""
echo "🌐 Useful links:"
echo "   - Document AI Console: https://console.cloud.google.com/ai/document-ai/processors"
echo "   - Storage Console: https://console.cloud.google.com/storage/browser/$BUCKET_NAME"
echo "   - Cloud Run Console: https://console.cloud.google.com/run"

# Save environment variables to .env file for convenience
cat > .env << EOF
# Invoice Parsing Service Environment Variables
PROJECT_ID=$PROJECT_ID
BUCKET_NAME=$BUCKET_NAME
PROCESSOR_ID=your-processor-id-from-console
LOCATION=$REGION
GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/$KEY_FILE
LOG_LEVEL=INFO
UPLOAD_PREFIX=invoices/
PARSED_PREFIX=parsed/
EOF

echo ""
echo "📄 Created .env file with your configuration"
echo "   Remember to update PROCESSOR_ID after creating the processor!"