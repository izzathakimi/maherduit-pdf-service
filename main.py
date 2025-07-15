from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import tempfile
import uuid
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime
from supabase import create_client, Client
from pdf_parser import PDFTransactionParser
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MaherDuit PDF Processing Service",
    description="Processes Malaysian bank statement PDFs and extracts transaction data",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-vercel-domain.com",
        "https://maherduit.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

class ProcessingResponse:
    def __init__(self, success: bool, message: str, data: Optional[Dict] = None, error: Optional[str] = None):
        self.success = success
        self.message = message
        self.data = data or {}
        self.error = error

@app.get("/")
async def root():
    return {"message": "MaherDuit PDF Processing Service", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/process")
async def process_pdf(
    file: Optional[UploadFile] = File(None),
    supabase_url: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
    bank_account_id: Optional[str] = Form(None)
):
    """
    Process a PDF bank statement and extract transaction data.
    
    Args:
        file: PDF file upload (optional if supabase_url provided)
        supabase_url: Supabase Storage public URL (optional if file provided)
        user_id: User ID for tracking
        bank_account_id: Bank account ID for transaction association
    
    Returns:
        JSON response with parsed transactions and CSV download link
    """
    try:
        # Validate input
        if not file and not supabase_url:
            raise HTTPException(
                status_code=400,
                detail="Either file upload or supabase_url must be provided"
            )
        
        # Generate unique processing ID
        processing_id = str(uuid.uuid4())
        logger.info(f"Starting PDF processing: {processing_id}")
        
        # Handle file input
        temp_file_path = None
        if file:
            # Validate file type
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(
                    status_code=400,
                    detail="Only PDF files are supported"
                )
            
            # Save uploaded file to temporary location
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file_path = temp_file.name
                content = await file.read()
                temp_file.write(content)
            
            logger.info(f"PDF file saved to: {temp_file_path}")
        
        elif supabase_url:
            # Download file from Supabase Storage
            import requests
            
            try:
                response = requests.get(supabase_url)
                response.raise_for_status()
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    temp_file_path = temp_file.name
                    temp_file.write(response.content)
                
                logger.info(f"PDF downloaded from Supabase to: {temp_file_path}")
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to download PDF from Supabase: {str(e)}"
                )
        
        # Initialize PDF parser
        parser = PDFTransactionParser()
        
        # Process the PDF
        result = parser.process_pdf(temp_file_path, processing_id)
        
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        
        # Upload CSV to Supabase Storage if configured
        csv_download_url = None
        if supabase and result.get('csv_content'):
            csv_filename = f"processed_{processing_id}.csv"
            csv_path = f"processed-statements/{user_id}/{csv_filename}"
            
            try:
                # Upload CSV to Supabase Storage
                csv_response = supabase.storage.from_("statements").upload(
                    csv_path,
                    result['csv_content'].encode('utf-8'),
                    file_options={"content-type": "text/csv"}
                )
                
                if csv_response:
                    # Get public URL
                    csv_download_url = supabase.storage.from_("statements").get_public_url(csv_path)
                    logger.info(f"CSV uploaded to Supabase: {csv_download_url}")
                    
            except Exception as e:
                logger.warning(f"Failed to upload CSV to Supabase: {str(e)}")
        
        # Prepare response
        response_data = {
            "processing_id": processing_id,
            "bank_detected": result.get('bank_type'),
            "transactions": result.get('transactions', []),
            "transaction_count": len(result.get('transactions', [])),
            "csv_download_url": csv_download_url,
            "processing_time": result.get('processing_time'),
            "summary": result.get('summary', {}),
            "metadata": {
                "user_id": user_id,
                "bank_account_id": bank_account_id,
                "processed_at": datetime.now().isoformat()
            }
        }
        
        logger.info(f"PDF processing completed: {processing_id}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "PDF processed successfully",
                "data": response_data
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.post("/process-batch")
async def process_batch_pdfs(
    files: List[UploadFile] = File(...),
    user_id: Optional[str] = Form(None),
    bank_account_id: Optional[str] = Form(None)
):
    """
    Process multiple PDF files in batch.
    
    Args:
        files: List of PDF files to process
        user_id: User ID for tracking
        bank_account_id: Bank account ID for transaction association
    
    Returns:
        JSON response with batch processing results
    """
    try:
        if len(files) > 10:
            raise HTTPException(
                status_code=400,
                detail="Maximum 10 files allowed per batch"
            )
        
        batch_id = str(uuid.uuid4())
        results = []
        
        for i, file in enumerate(files):
            try:
                # Process each file individually
                result = await process_pdf(
                    file=file,
                    user_id=user_id,
                    bank_account_id=bank_account_id
                )
                
                # Extract data from JSONResponse
                result_data = json.loads(result.body.decode())
                results.append({
                    "file_index": i,
                    "filename": file.filename,
                    "success": True,
                    "data": result_data["data"]
                })
                
            except Exception as e:
                results.append({
                    "file_index": i,
                    "filename": file.filename,
                    "success": False,
                    "error": str(e)
                })
        
        # Calculate batch summary
        successful_files = [r for r in results if r["success"]]
        total_transactions = sum(
            r["data"]["transaction_count"] for r in successful_files
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Batch processing completed",
                "data": {
                    "batch_id": batch_id,
                    "total_files": len(files),
                    "successful_files": len(successful_files),
                    "failed_files": len(files) - len(successful_files),
                    "total_transactions": total_transactions,
                    "results": results,
                    "processed_at": datetime.now().isoformat()
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Batch processing error: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)