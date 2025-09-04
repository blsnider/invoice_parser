# Invoice Parsing Service

A FastAPI-based microservice that uses Google Cloud Document AI to extract structured data from PDF invoices. Designed for deployment on Google Cloud Run with integration to existing C# applications.

## Features

- 🔍 **PDF Invoice Parsing**: Extract structured data from PDF invoices using Google Cloud Document AI
- 📁 **Batch Processing**: Handle single invoices or batch upload multiple files
- ☁️ **Cloud Storage**: Automatic storage of PDFs and parsed results in Google Cloud Storage  
- 🔗 **Preview URLs**: Generate signed URLs for PDF preview in web applications
- ⚡ **Async Processing**: High-performance async processing for concurrent requests
- 🛡️ **Error Handling**: Comprehensive error handling with detailed field-level feedback
- 📊 **Confidence Scoring**: AI confidence scores for extracted fields
- 🔄 **Duplicate Detection**: Prevent reprocessing of identical invoices

## Quick Start

### Prerequisites

- Python 3.9+
- Google Cloud Project with enabled APIs:
  - Document AI API
  - Cloud Storage API
  - Cloud Run API
- Service account with appropriate permissions

### Local Development Setup

1. **Clone and install dependencies**
```bash
git clone <repository-url>
cd invoice-parsing-service
pip install -r requirements.txt
```

2. **Set up Google Cloud credentials**
```bash
# Download service account key from GCP Console
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"
export PROJECT_ID="your-gcp-project-id"
export BUCKET_NAME="your-storage-bucket"
export PROCESSOR_ID="your-document-ai-processor-id"
```

3. **Run locally**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

4. **Test the service**
```bash
curl http://localhost:8080/health
```

## API Documentation

### Endpoints

#### `POST /parse-invoice`
Parse a single PDF invoice.

**Request:**
```bash
curl -X POST "http://localhost:8080/parse-invoice" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@invoice.pdf"
```

**Response:**
```json
{
  "success": true,
  "invoice_id": "uuid-string",
  "parsed_data": {
    "invoice_id": "INV-12345",
    "supplier_name": "ABC Company",
    "total_amount": "1250.00",
    "currency": "USD",
    "due_date": "2024-03-15",
    "document_confidence": 0.95
  },
  "preview_url": "https://storage.googleapis.com/...",
  "gcs_uri": "gs://bucket/invoices/uuid.pdf"
}
```

#### `POST /parse-batch`
Parse multiple PDF invoices.

**Request:**
```bash
curl -X POST "http://localhost:8080/parse-batch" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@invoice1.pdf" \
  -F "files=@invoice2.pdf"
```

#### `GET /health`
Health check endpoint.

#### `GET /invoice/{invoice_id}/preview`
Get signed URL for PDF preview.

#### `GET /invoice/{invoice_id}/data`
Retrieve parsed invoice data.

## Deployment to Google Cloud Run

### Method 1: Using gcloud CLI

1. **Enable required APIs**
```bash
gcloud services enable run.googleapis.com
gcloud services enable documentai.googleapis.com
gcloud services enable storage.googleapis.com
```

2. **Deploy to Cloud Run**
```bash
gcloud run deploy invoice-parser \
    --source . \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --set-env-vars PROJECT_ID=your-project-id,BUCKET_NAME=your-bucket-name,PROCESSOR_ID=your-processor-id
```

### Method 2: Using Docker

1. **Build Docker image**
```bash
docker build -t gcr.io/PROJECT_ID/invoice-parser .
docker push gcr.io/PROJECT_ID/invoice-parser
```

2. **Deploy to Cloud Run**
```bash
gcloud run deploy invoice-parser \
    --image gcr.io/PROJECT_ID/invoice-parser \
    --platform managed \
    --region us-central1
```

## Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `PROJECT_ID` | Yes | Google Cloud Project ID | - |
| `BUCKET_NAME` | Yes | GCS bucket name for storage | - |
| `PROCESSOR_ID` | Yes | Document AI processor ID | - |
| `LOCATION` | No | GCP region for Document AI | "us" |
| `LOG_LEVEL` | No | Logging level | "INFO" |
| `UPLOAD_PREFIX` | No | GCS prefix for uploads | "invoices/" |
| `PARSED_PREFIX` | No | GCS prefix for parsed JSON | "parsed/" |

### Google Cloud Setup

1. **Create Document AI Processor**
```bash
# Create an Invoice Parser processor in the GCP Console
# Document AI > Processors > Create Processor > Invoice Parser
```

2. **Create GCS Bucket**
```bash
gsutil mb gs://your-bucket-name
```

3. **Set up IAM permissions**
```bash
# Grant service account necessary roles:
# - Document AI API User
# - Storage Object Admin
# - Cloud Run Developer
```

## Project Structure

```
invoice-parsing-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── models/              # Pydantic models
│   │   ├── invoice.py
│   │   └── responses.py
│   ├── services/            # Business logic
│   │   ├── document_ai.py
│   │   ├── storage.py
│   │   └── parser.py
│   ├── api/                 # API routes
│   │   └── parsing.py
│   ├── core/                # Configuration
│   │   ├── config.py
│   │   └── logging.py
│   └── utils/               # Utilities
│       ├── validation.py
│       └── exceptions.py
├── tests/                   # Test files
├── requirements.txt         # Python dependencies
├── Dockerfile              # Container configuration
├── .dockerignore           # Docker ignore file
├── .gitignore              # Git ignore file
├── README.md               # This file
└── CLAUDE.md               # Claude Code guidance
```

## Testing

### Run Tests
```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific test file
pytest tests/test_parsing.py -v
```

### Test with Sample Files
```bash
# Test single invoice
curl -X POST "http://localhost:8080/parse-invoice" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@tests/sample_invoices/sample_invoice.pdf"
```

## Error Handling

The service provides detailed error responses:

```json
{
  "error": true,
  "message": "Document AI processing failed",
  "code": "DOCUMENT_AI_ERROR",
  "details": {
    "processor_id": "123456789",
    "confidence_threshold": 0.7
  }
}
```

### Common Error Codes
- `INVALID_FILE_FORMAT`: Non-PDF file uploaded
- `DOCUMENT_AI_ERROR`: Document AI processing failed
- `STORAGE_ERROR`: GCS storage/retrieval error
- `VALIDATION_ERROR`: Input validation failed
- `DUPLICATE_INVOICE`: Invoice already processed

## Performance Considerations

- **Memory**: Recommended 2GB for large PDF processing
- **CPU**: 2 vCPUs for optimal concurrent processing
- **Timeout**: 300 seconds for batch operations
- **Concurrency**: Configure based on Document AI quotas

## Monitoring

### Health Checks
- `/health` endpoint returns service status
- Includes checks for GCS and Document AI connectivity

### Logging
- Structured JSON logging to Google Cloud Logging
- Request/response correlation IDs
- Performance metrics and error tracking

## Integration with C# Application

### HTTP Client Example (C#)
```csharp
public class InvoiceParsingService : IInvoiceParsingService
{
    private readonly HttpClient _httpClient;
    
    public async Task<ParsedInvoiceResult> ParseInvoiceAsync(IFormFile file)
    {
        using var content = new MultipartFormDataContent();
        content.Add(new StreamContent(file.OpenReadStream()), "file", file.FileName);
        
        var response = await _httpClient.PostAsync("/parse-invoice", content);
        return await response.Content.ReadFromJsonAsync<ParsedInvoiceResult>();
    }
}
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make changes and add tests
4. Run tests: `pytest`
5. Commit changes: `git commit -am 'Add new feature'`
6. Push to branch: `git push origin feature/new-feature`
7. Submit a Pull Request

## Security

- All endpoints use HTTPS in production
- Service account follows principle of least privilege
- Input validation on all file uploads
- Signed URLs expire after 15 minutes
- No sensitive data stored in logs

## Cost Optimization

- Document AI charged per page processed
- Cloud Run scales to zero when not in use
- GCS lifecycle policies for automated cleanup
- Duplicate detection prevents unnecessary processing

## Troubleshooting

### Common Issues

1. **Authentication errors**: Verify service account and permissions
2. **Document AI quota exceeded**: Check quota limits in GCP Console
3. **Large file uploads**: Increase Cloud Run timeout settings
4. **Memory errors**: Increase Cloud Run memory allocation

### Debugging

```bash
# View Cloud Run logs
gcloud run services logs read invoice-parser --region us-central1

# Local debugging
export LOG_LEVEL=DEBUG
uvicorn app.main:app --reload
```

## License

[Your License Here]

## Support

For issues and questions:
- Create GitHub issue
- Check Cloud Run logs for deployment issues
- Verify GCP service quotas and permissions