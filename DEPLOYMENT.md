# Cloud Deployment Guide

This guide will help you deploy your Twitter Scheduler to the cloud so it runs 24/7.

## Prerequisites

1. A GitHub account (for version control)
2. A Railway account (free tier: https://railway.app)
3. A Supabase account (free tier: https://supabase.com) for PostgreSQL database

## Step 1: Set Up PostgreSQL Database (Supabase)

1. Go to [Supabase](https://supabase.com) and create a free account
2. Create a new project
3. Go to **Settings** → **Database**
4. Copy the **Connection string** (URI format)
   - It will look like: `postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres`
5. Replace `[YOUR-PASSWORD]` with your actual database password (found in project settings)

## Step 2: Prepare Your Code

1. Make sure your code is in a Git repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. Push to GitHub:
   ```bash
   git remote add origin https://github.com/yourusername/twitter-scheduler.git
   git push -u origin main
   ```

## Step 3: Deploy to Railway

1. Go to [Railway](https://railway.app) and sign up/login
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Connect your GitHub account and select your repository
5. Railway will automatically detect it's a Python app and start building

## Step 4: Configure Environment Variables

In Railway, go to your project → **Variables** tab and add:

### Required Variables:
```
TWITTER_BEARER_TOKEN=your_bearer_token
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
DATABASE_URL=postgresql://postgres:password@host:port/database
```

### Optional Variables:
```
PORT=3000  # Railway sets this automatically, but you can override
```

**Important:** 
- Get your Twitter credentials from [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard)
- Use the Supabase connection string for `DATABASE_URL`

## Step 5: Add PostgreSQL Service (Optional)

Railway can also host your PostgreSQL database:

1. In your Railway project, click **"+ New"**
2. Select **"Database"** → **"Add PostgreSQL"**
3. Railway will automatically create a `DATABASE_URL` variable
4. Your app will automatically use it!

## Step 6: Access Your App

1. Railway will provide a URL like: `https://your-app-name.up.railway.app`
2. Click on it to access your Twitter Scheduler
3. The app will run 24/7 and automatically post scheduled tweets!

## Troubleshooting

### App not starting?
- Check Railway logs: Go to your project → **Deployments** → Click on the latest deployment → **View Logs**
- Make sure all environment variables are set correctly

### Database connection errors?
- Verify your `DATABASE_URL` is correct
- Check that your Supabase database is accessible (not paused)
- Make sure `psycopg2-binary` is in `requirements.txt`

### Tweets not posting?
- Check that Twitter API credentials are correct
- Verify your Twitter app has write permissions
- Check Railway logs for error messages

## Local Development

To run locally with PostgreSQL:

1. Set up a local PostgreSQL database OR use Supabase
2. Create a `.env` file with your credentials:
   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/twitter_scheduler
   TWITTER_BEARER_TOKEN=...
   # ... other Twitter credentials
   ```
3. Run: `python3 app.py`

The app will automatically use PostgreSQL if `DATABASE_URL` is set, otherwise it falls back to SQLite.

## Cost

- **Railway**: Free tier includes $5 credit/month (usually enough for small apps)
- **Supabase**: Free tier includes 500MB database, 2GB bandwidth
- **Total**: $0/month for small to medium usage!

## Alternative: Render Deployment

If you prefer Render:

1. Go to [Render](https://render.com)
2. Create a new **Web Service**
3. Connect your GitHub repository
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `gunicorn app:app --bind 0.0.0.0:$PORT`
6. Add environment variables (same as Railway)
7. Deploy!

Note: Render's free tier spins down after 15 minutes of inactivity. Consider using a ping service to keep it awake.

