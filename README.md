# Amazon Product Service API

A FastAPI application that helps generate Amazon product content including titles, descriptions, bullet points, and backend keywords.

## Deployment to Render

### Prerequisites

1. Create a [Render](https://render.com/) account if you don't have one
2. Have your OpenAI API key and Google service account credentials ready

### Deployment Steps

1. Fork or push this repository to GitHub
2. Log in to your Render dashboard
3. Click "New" and select "Web Service"
4. Connect your GitHub repository
5. Configure the service:
   - Name: `fastapi-amazon-service` (or your preferred name)
   - Environment: `Python`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   
6. Add the following environment variables:
   - `OPENAI_API_KEY`
   - `GOOGLE_PROJECT_ID`
   - `GOOGLE_PRIVATE_KEY_ID`
   - `GOOGLE_PRIVATE_KEY`
   - `GOOGLE_CLIENT_EMAIL`
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_AUTH_URI`
   - `GOOGLE_TOKEN_URI`
   - `GOOGLE_CERT_URL`
   - `GOOGLE_X509_CERT_URL`
   - `DOCUMENT_ID`

7. Click "Create Web Service"

### Important Notes

- Ensure your `google-credentials.json` file is properly secured
- The service uses OpenAI's API for content generation
- API endpoints are available at:
  - `/` - Root endpoint
  - `/hi` - Test endpoint
  - `/fun1` - Generate Amazon title
  - `/trigger` - Trigger all functions 