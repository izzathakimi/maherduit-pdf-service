# MaherDuit PDF Processing Service

A FastAPI microservice for processing Malaysian bank statement PDFs and extracting transaction data.

## Features

- **Multi-bank Support**: Maybank, CIMB, Alliance Bank, and Credit Cards
- **Automatic Bank Detection**: Identifies bank type from PDF content
- **Transaction Extraction**: Parses dates, amounts, descriptions, and balances
- **CSV Generation**: Creates standardized CSV output
- **Batch Processing**: Handle multiple PDFs simultaneously
- **Supabase Integration**: Upload results to Supabase Storage
- **CORS Enabled**: Ready for frontend integration

## API Endpoints

### `POST /process`
Process a single PDF file.

**Parameters:**
- `file`: PDF file upload (optional if `supabase_url` provided)
- `supabase_url`: Supabase Storage public URL (optional if `file` provided)
- `user_id`: User ID for tracking
- `bank_account_id`: Bank account ID for transaction association

**Response:**
```json
{
  "success": true,
  "message": "PDF processed successfully",
  "data": {
    "processing_id": "uuid",
    "bank_detected": "maybank",
    "transactions": [...],
    "transaction_count": 25,
    "csv_download_url": "https://...",
    "processing_time": 2.34,
    "summary": {...}
  }
}
```

### `POST /process-batch`
Process multiple PDF files in batch (max 10 files).

### `GET /health`
Health check endpoint.

## Supported Banks

1. **Maybank**: Personal and business accounts
2. **CIMB Bank**: Savings and current accounts
3. **Alliance Bank**: Various account types
4. **Credit Cards**: Maybank credit card statements

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn main:app --reload --port 8000

# Test the API
curl -X POST "http://localhost:8000/process" \
  -F "file=@statement.pdf" \
  -F "user_id=test_user"
```

## Environment Variables

```bash
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
PORT=8000
```

## Deployment

This service is configured for Railway deployment with automatic detection of requirements and start commands.