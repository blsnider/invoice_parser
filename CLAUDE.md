# CLAUDE.md

This file provides guidance to Claude Code when working with the Invoice Parsing Service for GCP Cloud Run deployment.

## Project Overview

This is a FastAPI-based invoice parsing service that uses Google Cloud Document AI to extract data from PDF invoices. The service is designed to be deployed on Google Cloud Run and integrates with Google Cloud Storage for file handling.

## Development Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Run with specific environment
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
export PROJECT_ID="your-project-id"
export BUCKET_NAME="your-bucket-name"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### Testing
```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_parsing.py -v
```

### Docker Commands
```bash
# Build Docker image
docker build -t invoice-parser .

# Run container locally
docker run -p 8080:8080 -e PROJECT_ID=your-project-id invoice-parser

# Test container
curl http://localhost:8080/health
```

### GCP Deployment Commands
```bash
# Build and deploy to Cloud Run
gcloud run deploy invoice-parser \
    --source . \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars PROJECT_ID=your-project-id,BUCKET_NAME=your-bucket-name

# Deploy with custom settings
gcloud run deploy invoice-parser \
    --source . \
    --platform managed \
    --region us-central1 \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --max-instances 10 \
    --set-env-vars PROJECT_ID=your-project-id,BUCKET_NAME=your-bucket-name

# View logs
gcloud run services logs read invoice-parser --region us-central1

# Get service URL
gcloud run services describe invoice-parser --region us-central1 --format="value(status.url)"
```

## High-Level Architecture

### Service Structure
```
app/
├── main.py              # FastAPI application entry point
├── models/              # Pydantic models and schemas
│   ├── __init__.py
│   ├── invoice.py       # Invoice data models
│   └── responses.py     # API response models
├── services/            # Business logic services
│   ├── __init__.py
│   ├── document_ai.py   # Document AI integration
│   ├── storage.py       # GCS integration
│   └── parser.py        # Invoice parsing logic
├── api/                 # API route handlers
│   ├── __init__.py
│   └── parsing.py       # Parsing endpoints
├── core/                # Core configuration and utilities
│   ├── __init__.py
│   ├── config.py        # Application configuration
│   └── logging.py       # Logging configuration
└── utils/               # Utility functions
    ├── __init__.py
    ├── validation.py    # Input validation
    └── exceptions.py    # Custom exceptions
```

### Key Architectural Patterns

#### FastAPI Application Structure
- **Dependency Injection**: Services are injected into route handlers
- **Pydantic Models**: Strong typing for request/response validation
- **Async/Await**: Full async support for I/O operations
- **Error Handling**: Structured exception handling with proper HTTP status codes

#### Google Cloud Integration
- **Document AI**: Used for PDF text extraction and field recognition
- **Cloud Storage**: Stores uploaded PDFs and parsed JSON results
- **Cloud Run**: Serverless deployment with auto-scaling
- **Service Account**: Authentication for GCP services

### API Endpoints

#### Core Endpoints
```
POST /parse-invoice     # Parse single invoice PDF
POST /parse-batch       # Parse multiple PDFs
GET  /health           # Health check endpoint
GET  /invoice/{id}/preview  # Get signed URL for PDF preview
GET  /invoice/{id}/data     # Get parsed invoice data
```

#### Request/Response Flow
1. **File Upload**: PDF received via multipart/form-data
2. **Storage**: PDF stored in GCS with unique identifier
3. **Processing**: Document AI processes the PDF
4. **Extraction**: Structured data extracted from AI response
5. **Validation**: Data validated and confidence scores calculated
6. **Storage**: Parsed JSON stored in GCS
7. **Response**: Structured response with parsed data and preview URL

### Configuration Management

Environment variables used:
- `PROJECT_ID`: Google Cloud project ID
- `BUCKET_NAME`: GCS bucket for file storage
- `PROCESSOR_ID`: Document AI processor ID
- `LOCATION`: GCP region for Document AI
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

### Error Handling Strategy

#### Exception Types
- `DocumentAIError`: Issues with Document AI processing
- `StorageError`: GCS storage/retrieval problems
- `ValidationError`: Input validation failures
- `ParseError`: General parsing errors

#### Error Response Format
```json
{
  "error": true,
  "message": "Human readable error message",
  "code": "ERROR_CODE",
  "details": {
    "field_errors": [],
    "processing_info": {}
  }
}
```

### Deployment Considerations

#### Cloud Run Configuration
- **Memory**: 2GB recommended for PDF processing
- **CPU**: 2 vCPUs for parallel processing
- **Timeout**: 300 seconds for large batch operations
- **Concurrency**: 10 concurrent requests per instance
- **Auto-scaling**: 0 to 10 instances based on load

#### Security
- **IAM Roles**: Service account with minimal required permissions
- **HTTPS**: All traffic encrypted in transit
- **CORS**: Configured for your C# application domain
- **Input Validation**: All inputs validated before processing

### Performance Optimization

#### Async Processing
- All I/O operations are async (GCS, Document AI)
- Batch operations process files concurrently
- Connection pooling for external services

#### Caching Strategy
- Parsed results cached in GCS
- Duplicate detection prevents reprocessing
- Signed URLs cached for 15 minutes

### Monitoring and Logging

#### Structured Logging
- JSON formatted logs for Cloud Logging
- Request/response tracking
- Performance metrics
- Error tracking with stack traces

#### Health Checks
- `/health` endpoint for container health
- Dependency health checks (GCS, Document AI)
- Performance metrics exposure

### Testing Strategy

#### Test Categories
- **Unit Tests**: Individual function testing
- **Integration Tests**: GCP service integration
- **API Tests**: End-to-end API testing
- **Performance Tests**: Load testing for batch operations

#### Test Data
- Sample PDF files for different invoice formats
- Mock responses for GCP services
- Edge case scenarios (corrupted PDFs, invalid data)

### Development Workflow

#### Local Development
1. Set up local service account credentials
2. Use local GCS emulator for development (optional)
3. Hot reload enabled for rapid development
4. Local testing with sample PDF files

#### CI/CD Pipeline
1. **Code Quality**: Linting with black, flake8
2. **Testing**: Automated test execution
3. **Security**: Dependency scanning
4. **Deployment**: Automated Cloud Run deployment

### Integration Points

#### C# Application Integration
- RESTful API designed for easy HTTP client integration
- Standardized response formats
- Proper HTTP status codes
- CORS enabled for browser requests

#### Future Enhancements
- Email inbox integration preparation
- Webhook support for async processing notifications
- Batch job status tracking
- Advanced duplicate detection

### Important Notes

1. **Service Account**: Ensure proper IAM roles for Document AI and Storage
2. **Resource Limits**: Monitor memory usage with large PDF files
3. **Cost Management**: Document AI has per-page pricing
4. **Regional Deployment**: Deploy in same region as your C# application
5. **Backup Strategy**: Consider backing up parsed results
6. **Compliance**: Ensure PDF handling meets your security requirements