# Railway Deployment Guide

## 🚀 Step-by-Step Deployment to Railway

### 1. Prepare Your Repository

Since you're using your existing repository, just commit the new `pdf-service` folder:

```bash
# From your main project root
git add pdf-service/
git commit -m "Add PDF processing microservice"
git push origin main
```

### 2. Deploy to Railway

1. **Sign up/Login to Railway**
   - Go to [railway.app](https://railway.app)
   - Sign in with GitHub

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your existing `accounting-app` repository
   - **Important**: Set the root directory to `pdf-service` in Railway settings

3. **Configure Root Directory**
   - After connecting your repo, go to Settings → Build & Deploy
   - Set **Root Directory** to `pdf-service`
   - This tells Railway to deploy only the microservice folder

4. **Configure Environment Variables**
   Go to your project settings and add these variables:
   ```
   SUPABASE_URL=https://your-project-id.supabase.co
   SUPABASE_KEY=your-supabase-anon-key
   PORT=8000
   ```

5. **Deploy**
   - Railway will automatically detect Python and use the `requirements.txt`
   - The `railway.json` file configures the start command
   - Deployment typically takes 2-3 minutes

### 3. Get Your Service URL

After deployment, you'll get a URL like:
```
https://your-service-name.railway.app
```

### 4. Test the Deployment

Test the health endpoint:
```bash
curl https://your-service-name.railway.app/health
```

Test PDF processing:
```bash
curl -X POST "https://your-service-name.railway.app/process" \
  -F "file=@test-statement.pdf" \
  -F "user_id=test_user" \
  -F "bank_account_id=test_account"
```

## 🔧 Frontend Integration

### Update Your Vercel App

In your Next.js app, create an API route to call the Railway service:

```typescript
// app/api/process-pdf/route.ts
import { NextRequest, NextResponse } from 'next/server';

const PDF_SERVICE_URL = process.env.PDF_SERVICE_URL || 'https://your-service-name.railway.app';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    
    // Forward the request to Railway service
    const response = await fetch(`${PDF_SERVICE_URL}/process`, {
      method: 'POST',
      body: formData,
    });
    
    const result = await response.json();
    
    if (!response.ok) {
      throw new Error(result.detail || 'PDF processing failed');
    }
    
    return NextResponse.json(result);
  } catch (error) {
    console.error('PDF processing error:', error);
    return NextResponse.json(
      { error: 'Failed to process PDF' },
      { status: 500 }
    );
  }
}
```

### Environment Variables for Vercel

Add to your Vercel project settings:
```
PDF_SERVICE_URL=https://your-service-name.railway.app
```

### Update CORS Origins

In your Railway deployment, update the CORS origins in `main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-actual-vercel-domain.com",
        "https://maherduit.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001"
    ],
    # ...
)
```

## 🔒 Security Considerations

1. **Environment Variables**: Never commit sensitive keys to Git
2. **CORS**: Only allow your actual domain in production
3. **File Upload Limits**: The service has built-in file size limits
4. **Rate Limiting**: Consider adding rate limiting for production use

## 📊 Monitoring

Railway provides built-in monitoring:
- **Logs**: View real-time logs in the Railway dashboard
- **Metrics**: Monitor CPU, memory, and request metrics
- **Alerts**: Set up alerts for errors or high resource usage

## 🔄 Continuous Deployment

Railway automatically deploys when you push to your main branch:
```bash
git add .
git commit -m "Update PDF processing logic"
git push origin main
```

## 🐛 Troubleshooting

### Common Issues:

1. **Build Failures**
   - Check `requirements.txt` for correct package versions
   - Ensure all dependencies are compatible

2. **Memory Issues**
   - Large PDFs may cause memory problems
   - Consider upgrading Railway plan for more resources

3. **Timeout Errors**
   - Adjust timeout settings in Railway dashboard
   - Optimize PDF processing for large files

4. **CORS Errors**
   - Verify allowed origins in `main.py`
   - Check that your frontend domain is included

### Debug Commands:

```bash
# View logs
railway logs

# Check deployment status
railway status

# Restart service
railway restart
```

## 📈 Scaling

For production use:
1. **Upgrade Railway Plan**: More CPU and memory for better performance
2. **Add Redis**: Cache frequently processed PDFs
3. **Queue System**: Handle batch processing with background jobs
4. **Database**: Store processing results for faster retrieval

## 🔧 Local Development

Test locally before deploying:
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SUPABASE_URL=your_url
export SUPABASE_KEY=your_key

# Run locally
uvicorn main:app --reload --port 8000
```

## 📝 Next Steps

1. **Test with Real PDFs**: Upload actual bank statements
2. **Monitor Performance**: Check processing times and error rates
3. **Add Features**: Implement additional bank support as needed
4. **Optimize**: Profile and optimize for better performance