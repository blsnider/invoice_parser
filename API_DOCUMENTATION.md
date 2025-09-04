# Invoice Parsing Service API Documentation

## Overview

The Invoice Parsing Service is a RESTful API that processes PDF invoices using Google Cloud Document AI to extract structured data. The service is deployed on Google Cloud Run and provides endpoints for single and batch invoice processing, data retrieval, and file preview generation.

**Base URL**: `https://invoice-parser-41815171183.us-central1.run.app`  
**API Version**: `v1`  
**Content Type**: `application/json` (responses), `multipart/form-data` (file uploads)

## Authentication

Currently, the service is configured for internal use without authentication. For production, implement appropriate authentication headers.

## Common Response Structure

### Success Response
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": { ... }
}
```

### Error Response
```json
{
  "error": true,
  "message": "Human-readable error message",
  "code": "ERROR_CODE",
  "details": {
    "field_errors": [],
    "processing_info": {}
  }
}
```

## Error Codes

| Code | Description |
|------|-------------|
| `DOCUMENT_AI_ERROR` | Document AI processing failed |
| `STORAGE_ERROR` | Storage operation failed |
| `VALIDATION_ERROR` | Input validation failed |
| `PARSE_ERROR` | General parsing error |
| `INVALID_FILE_TYPE` | File type not supported |
| `FILE_SIZE_EXCEEDED` | File exceeds size limit |
| `INVOICE_NOT_FOUND` | Invoice ID not found |
| `BATCH_SIZE_EXCEEDED` | Too many files in batch |
| `INTERNAL_ERROR` | Internal server error |

## Data Models

### InvoiceData

The main invoice data structure returned by the parsing service:

```json
{
  "invoice_id": "uuid-string",
  "invoice_number": "INV-2024-001",
  "invoice_date": "2024-01-15",
  "due_date": "2024-02-15",
  
  "supplier_name": "ACME Corporation",
  "supplier_address": {
    "street": "123 Business St",
    "city": "New York",
    "state": "NY",
    "postal_code": "10001",
    "country": "USA"
  },
  "supplier_tax_id": "12-3456789",
  "supplier_email": "billing@acme.com",
  "supplier_phone": "+1-555-0100",
  
  "customer_name": "Customer Inc",
  "customer_address": {
    "street": "456 Client Ave",
    "city": "Los Angeles",
    "state": "CA",
    "postal_code": "90001",
    "country": "USA"
  },
  "customer_tax_id": "98-7654321",
  "customer_email": "accounts@customer.com",
  "customer_phone": "+1-555-0200",
  
  "currency": "USD",
  "subtotal": "1000.00",
  "tax_amount": "100.00",
  "total_amount": "1100.00",
  "amount_due": "1100.00",
  
  "line_items": [
    {
      "description": "Professional Services",
      "quantity": 10,
      "unit_price": "100.00",
      "amount": "1000.00",
      "tax_rate": 0.10,
      "tax_amount": "100.00"
    }
  ],
  
  "payment_terms": "Net 30",
  "payment_method": "Bank Transfer",
  "bank_details": {
    "account_number": "****1234",
    "routing_number": "****5678"
  },
  
  "confidence_scores": {
    "invoice_number": 0.95,
    "total_amount": 0.98,
    "overall": 0.92
  },
  
  "raw_text": "Full extracted text...",
  "metadata": {
    "page_count": 2,
    "processing_time": "2024-01-15T10:30:00Z"
  }
}
```

## API Endpoints

### 1. Parse Single Invoice

**Endpoint**: `POST /api/v1/parse-invoice`  
**Description**: Upload and parse a single PDF invoice

**Request**:
- Method: `POST`
- Content-Type: `multipart/form-data`

**Form Data Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | file | Yes | PDF file to parse (max 10MB) |
| `extract_tables` | boolean | No | Extract table data (default: true) |
| `extract_line_items` | boolean | No | Extract line items (default: true) |
| `language_hints` | string | No | Language hint (default: "en") |

**Response**: `200 OK`
```json
{
  "success": true,
  "invoice_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Invoice parsed successfully",
  "data": { /* InvoiceData object */ },
  "preview_url": "https://storage.googleapis.com/signed-url...",
  "storage_path": "parsed/550e8400/data.json",
  "processing_time": 2.5,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**C# Example**:
```csharp
using var client = new HttpClient();
using var content = new MultipartFormDataContent();
using var fileStream = File.OpenRead("invoice.pdf");
content.Add(new StreamContent(fileStream), "file", "invoice.pdf");
content.Add(new StringContent("true"), "extract_tables");
content.Add(new StringContent("true"), "extract_line_items");

var response = await client.PostAsync(
    "https://api-url/api/v1/parse-invoice", 
    content
);
var result = await response.Content.ReadAsStringAsync();
```

---

### 2. Parse Batch

**Endpoint**: `POST /api/v1/parse-batch`  
**Description**: Parse multiple PDF invoices in parallel

**Request**:
- Method: `POST`
- Content-Type: `multipart/form-data`

**Form Data Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `files` | file[] | Yes | Multiple PDF files (max 50 files, 10MB each) |
| `max_workers` | integer | No | Parallel workers (1-10, default: 5) |
| `extract_tables` | boolean | No | Extract table data (default: true) |
| `extract_line_items` | boolean | No | Extract line items (default: true) |

**Response**: `200 OK`
```json
{
  "success": true,
  "total_files": 5,
  "processed": 5,
  "failed": 0,
  "results": [
    { /* ParseResponse for file 1 */ },
    { /* ParseResponse for file 2 */ },
    // ... more results
  ],
  "processing_time": 8.5,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**C# Example**:
```csharp
using var client = new HttpClient();
using var content = new MultipartFormDataContent();

foreach (var filePath in filePaths)
{
    var fileStream = File.OpenRead(filePath);
    content.Add(new StreamContent(fileStream), "files", Path.GetFileName(filePath));
}
content.Add(new StringContent("5"), "max_workers");

var response = await client.PostAsync(
    "https://api-url/api/v1/parse-batch", 
    content
);
```

---

### 3. Get Invoice Preview URL

**Endpoint**: `GET /api/v1/invoice/{invoice_id}/preview`  
**Description**: Generate a signed URL for PDF preview

**Request**:
- Method: `GET`
- URL Parameters:
  - `invoice_id` (required): The invoice UUID

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `expires_in` | integer | No | URL expiration in seconds (default: 900) |

**Response**: `200 OK`
```json
{
  "invoice_id": "550e8400-e29b-41d4-a716-446655440000",
  "signed_url": "https://storage.googleapis.com/...",
  "expires_in": 900,
  "content_type": "application/pdf",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**C# Example**:
```csharp
var invoiceId = "550e8400-e29b-41d4-a716-446655440000";
var response = await client.GetAsync(
    $"https://api-url/api/v1/invoice/{invoiceId}/preview?expires_in=1800"
);
```

---

### 4. Get Invoice Data

**Endpoint**: `GET /api/v1/invoice/{invoice_id}/data`  
**Description**: Retrieve parsed invoice data

**Request**:
- Method: `GET`
- URL Parameters:
  - `invoice_id` (required): The invoice UUID

**Response**: `200 OK`
```json
{
  /* InvoiceData object */
}
```

**C# Example**:
```csharp
var invoiceId = "550e8400-e29b-41d4-a716-446655440000";
var response = await client.GetAsync(
    $"https://api-url/api/v1/invoice/{invoiceId}/data"
);
var invoiceData = JsonSerializer.Deserialize<InvoiceData>(
    await response.Content.ReadAsStringAsync()
);
```

---

### 5. List Invoices

**Endpoint**: `GET /api/v1/invoices`  
**Description**: List all processed invoices with pagination

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | No | Results per page (default: 100, max: 500) |
| `offset` | integer | No | Skip first N results (default: 0) |

**Response**: `200 OK`
```json
{
  "total": 150,
  "limit": 100,
  "offset": 0,
  "invoices": [
    {
      "invoice_id": "550e8400-e29b-41d4-a716-446655440000",
      "invoice_number": "INV-2024-001",
      "supplier_name": "ACME Corporation",
      "total_amount": "1100.00",
      "currency": "USD",
      "invoice_date": "2024-01-15"
    },
    // ... more invoices
  ]
}
```

---

### 6. Delete Invoice

**Endpoint**: `DELETE /api/v1/invoice/{invoice_id}`  
**Description**: Delete an invoice and its associated data

**Request**:
- Method: `DELETE`
- URL Parameters:
  - `invoice_id` (required): The invoice UUID

**Response**: `200 OK`
```json
{
  "success": true,
  "message": "Invoice 550e8400-e29b-41d4-a716-446655440000 deleted successfully"
}
```

---

### 7. Reprocess Invoice

**Endpoint**: `POST /api/v1/invoice/{invoice_id}/reprocess`  
**Description**: Reprocess an existing invoice PDF

**Request**:
- Method: `POST`
- URL Parameters:
  - `invoice_id` (required): The invoice UUID

**Response**: `200 OK`
```json
{
  "success": true,
  "invoice_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Invoice reprocessed successfully",
  "data": { /* Updated InvoiceData object */ },
  "preview_url": "https://storage.googleapis.com/...",
  "storage_path": "parsed/550e8400/data.json",
  "processing_time": 2.3
}
```

---

### 8. Health Check

**Endpoint**: `GET /health`  
**Description**: Service health check

**Response**: `200 OK`
```json
{
  "status": "healthy",
  "service": "invoice-parser",
  "version": "1.0.0"
}
```

## Integration Guide for C# Blazor

### 1. Create Service Models

```csharp
public class InvoiceData
{
    public string InvoiceId { get; set; }
    public string InvoiceNumber { get; set; }
    public DateTime? InvoiceDate { get; set; }
    public DateTime? DueDate { get; set; }
    public string SupplierName { get; set; }
    public Address SupplierAddress { get; set; }
    public string Currency { get; set; }
    public decimal? Subtotal { get; set; }
    public decimal? TaxAmount { get; set; }
    public decimal TotalAmount { get; set; }
    public List<LineItem> LineItems { get; set; }
    public Dictionary<string, float> ConfidenceScores { get; set; }
}

public class Address
{
    public string Street { get; set; }
    public string City { get; set; }
    public string State { get; set; }
    public string PostalCode { get; set; }
    public string Country { get; set; }
}

public class LineItem
{
    public string Description { get; set; }
    public float? Quantity { get; set; }
    public decimal? UnitPrice { get; set; }
    public decimal Amount { get; set; }
}

public class ParseResponse
{
    public bool Success { get; set; }
    public string InvoiceId { get; set; }
    public string Message { get; set; }
    public InvoiceData Data { get; set; }
    public string PreviewUrl { get; set; }
    public float? ProcessingTime { get; set; }
}
```

### 2. Create Service Client

```csharp
public class InvoiceParsingService
{
    private readonly HttpClient _httpClient;
    private readonly string _baseUrl;

    public InvoiceParsingService(HttpClient httpClient, IConfiguration configuration)
    {
        _httpClient = httpClient;
        _baseUrl = configuration["InvoiceParsingApi:BaseUrl"];
    }

    public async Task<ParseResponse> ParseInvoiceAsync(Stream fileStream, string fileName)
    {
        using var content = new MultipartFormDataContent();
        content.Add(new StreamContent(fileStream), "file", fileName);

        var response = await _httpClient.PostAsync(
            $"{_baseUrl}/api/v1/parse-invoice", 
            content
        );

        response.EnsureSuccessStatusCode();
        var json = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<ParseResponse>(json);
    }

    public async Task<InvoiceData> GetInvoiceDataAsync(string invoiceId)
    {
        var response = await _httpClient.GetAsync(
            $"{_baseUrl}/api/v1/invoice/{invoiceId}/data"
        );

        response.EnsureSuccessStatusCode();
        var json = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<InvoiceData>(json);
    }

    public async Task<string> GetPreviewUrlAsync(string invoiceId)
    {
        var response = await _httpClient.GetAsync(
            $"{_baseUrl}/api/v1/invoice/{invoiceId}/preview"
        );

        response.EnsureSuccessStatusCode();
        var json = await response.Content.ReadAsStringAsync();
        var result = JsonSerializer.Deserialize<PreviewResponse>(json);
        return result.SignedUrl;
    }
}
```

### 3. Register Service in Program.cs

```csharp
builder.Services.AddHttpClient<InvoiceParsingService>(client =>
{
    client.BaseAddress = new Uri(configuration["InvoiceParsingApi:BaseUrl"]);
    client.Timeout = TimeSpan.FromSeconds(30);
});
```

### 4. Use in Blazor Component

```razor
@page "/invoice-upload"
@inject InvoiceParsingService InvoiceService

<h3>Upload Invoice</h3>

<InputFile OnChange="@HandleFileSelected" />

@if (isProcessing)
{
    <p>Processing invoice...</p>
}

@if (invoiceData != null)
{
    <div>
        <h4>Invoice Details</h4>
        <p>Invoice Number: @invoiceData.InvoiceNumber</p>
        <p>Supplier: @invoiceData.SupplierName</p>
        <p>Total: @invoiceData.Currency @invoiceData.TotalAmount</p>
        
        @if (!string.IsNullOrEmpty(previewUrl))
        {
            <a href="@previewUrl" target="_blank">View PDF</a>
        }
    </div>
}

@code {
    private bool isProcessing = false;
    private InvoiceData invoiceData;
    private string previewUrl;

    private async Task HandleFileSelected(InputFileChangeEventArgs e)
    {
        isProcessing = true;
        
        try
        {
            var file = e.File;
            using var stream = file.OpenReadStream(maxAllowedSize: 10_485_760);
            
            var result = await InvoiceService.ParseInvoiceAsync(stream, file.Name);
            
            if (result.Success)
            {
                invoiceData = result.Data;
                previewUrl = result.PreviewUrl;
            }
        }
        catch (Exception ex)
        {
            // Handle error
            Console.Error.WriteLine($"Error processing invoice: {ex.Message}");
        }
        finally
        {
            isProcessing = false;
        }
    }
}
```

## Rate Limits & Performance

- **File Size Limit**: 10MB per file
- **Batch Size Limit**: 50 files per batch request
- **Concurrent Workers**: 1-10 (configurable per request)
- **Request Timeout**: 300 seconds
- **Signed URL Expiration**: 15 minutes (default, configurable)
- **Recommended**: Implement retry logic with exponential backoff

## Best Practices

1. **Error Handling**: Always check the `success` field in responses
2. **File Validation**: Validate file size and type before uploading
3. **Batch Processing**: Use batch endpoint for multiple files (more efficient)
4. **Caching**: Cache invoice data locally to reduce API calls
5. **Retry Logic**: Implement retry with exponential backoff for transient failures
6. **Progress Tracking**: For batch operations, show progress to users
7. **Confidence Scores**: Use confidence scores to flag low-quality extractions

## Testing

### Test PDF Files
Create test PDFs with various invoice formats to ensure robust parsing:
- Standard commercial invoices
- Service invoices
- Multi-page invoices
- Invoices with tables
- Different currencies and date formats

### API Testing with cURL

```bash
# Parse single invoice
curl -X POST "https://api-url/api/v1/parse-invoice" \
  -F "file=@invoice.pdf" \
  -F "extract_tables=true"

# Get invoice data
curl "https://api-url/api/v1/invoice/{invoice_id}/data"

# Get preview URL
curl "https://api-url/api/v1/invoice/{invoice_id}/preview"
```

## Support & Troubleshooting

### Common Issues

1. **File Upload Fails**
   - Check file size (< 10MB)
   - Ensure file is valid PDF
   - Verify content-type is `multipart/form-data`

2. **Low Confidence Scores**
   - Poor scan quality
   - Non-standard invoice format
   - Missing required fields

3. **Timeout Errors**
   - Large or complex PDFs
   - Consider reducing batch size
   - Implement client-side timeout handling

### Contact
For API issues or feature requests, contact the development team with:
- Invoice ID
- Error message and code
- Request timestamp
- Sample file (if possible)