# Railway Deployment Instructions

## 🚀 Deploy FastAPI PDF Service to Railway

### Prerequisites
- Railway account: https://railway.app
- Repository pushed to GitHub (recommended)

### Deployment Steps

#### 1. Railway Project Setup
1. Go to https://railway.app/dashboard
2. Click "New Project"
3. Select "Deploy from GitHub repo" or "Empty Project"

#### 2. Service Configuration
- **Root Directory**: `pdf-service` (if deploying from main repo)
- **Build Command**: Auto-detected by Nixpacks
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

#### 3. Environment Variables
Add these in Railway Dashboard > Variables:

```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-anon-key
PORT=8000
```

#### 4. Deployment Files Already Configured
✅ `railway.json` - Railway configuration
✅ `requirements.txt` - Python dependencies  
✅ `Procfile` - Process definition
✅ `main.py` - FastAPI application

#### 5. Expected Endpoints After Deployment
- `GET /` - Health check
- `GET /health` - Detailed health check
- `POST /process` - Process single PDF
- `POST /process-batch` - Process multiple PDFs (max 10)

#### 6. Post-Deployment
- Railway will provide a public URL (e.g., `https://your-service.railway.app`)
- Update your Next.js app to use this URL instead of localhost
- Test all endpoints to ensure proper functionality

### Troubleshooting
- Check Railway logs in dashboard for any deployment issues
- Verify environment variables are set correctly
- Ensure Supabase credentials are valid