from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sqlite3
import tweepy
from datetime import datetime
import threading
import time
import os
from dotenv import load_dotenv
import json
from werkzeug.utils import secure_filename
import base64
import urllib.parse

# Try to import PostgreSQL driver
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

load_dotenv()

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs('uploads', exist_ok=True)

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL')
USE_POSTGRES = DATABASE_URL and PSYCOPG2_AVAILABLE

# Twitter API credentials - set these in .env file
BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')
API_KEY = os.getenv('TWITTER_API_KEY')
API_SECRET = os.getenv('TWITTER_API_SECRET')
ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

# Initialize Twitter clients
client = None
api_v1 = None  # API v1.1 for media uploads
if all([BEARER_TOKEN, API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
    try:
        # API v2 client for posting tweets
        client = tweepy.Client(
            bearer_token=BEARER_TOKEN,
            consumer_key=API_KEY,
            consumer_secret=API_SECRET,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_TOKEN_SECRET,
            wait_on_rate_limit=True
        )
        # API v1.1 client for media uploads
        auth = tweepy.OAuth1UserHandler(
            API_KEY,
            API_SECRET,
            ACCESS_TOKEN,
            ACCESS_TOKEN_SECRET
        )
        api_v1 = tweepy.API(auth, wait_on_rate_limit=True)
    except Exception as e:
        print(f"Error initializing Twitter client: {e}")

# Database connection helper
def get_db_connection():
    """Get database connection (PostgreSQL or SQLite)"""
    if USE_POSTGRES:
        # Parse DATABASE_URL (format: postgresql://user:password@host:port/database)
        parsed = urllib.parse.urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=parsed.path[1:],  # Remove leading /
            user=parsed.username,
            password=parsed.password,
            host=parsed.hostname,
            port=parsed.port
        )
        return conn
    else:
        return sqlite3.connect('scheduler.db')

# Initialize database
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    if USE_POSTGRES:
        c.execute('''
            CREATE TABLE IF NOT EXISTS tweets (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                posted INTEGER DEFAULT 0,
                image_paths TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Add image_paths column if it doesn't exist
        try:
            c.execute('ALTER TABLE tweets ADD COLUMN image_paths TEXT')
        except psycopg2.errors.DuplicateColumn:
            pass  # Column already exists
    else:
        c.execute('''
            CREATE TABLE IF NOT EXISTS tweets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                posted INTEGER DEFAULT 0,
                image_paths TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Add image_paths column if it doesn't exist
        try:
            c.execute('ALTER TABLE tweets ADD COLUMN image_paths TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/schedule', methods=['POST'])
def schedule_tweet():
    try:
        # Handle multipart form data for file uploads
        if request.is_json:
            data = request.json
            image_paths = data.get('image_paths', [])
        else:
            data = request.form.to_dict()
            content = data.get('content', '').strip()
            scheduled_time = data.get('scheduled_time', '')
            
            # Handle file uploads
            image_paths = []
            if 'images[]' in request.files:
                files = request.files.getlist('images[]')
                for file in files:
                    if file and file.filename:
                        filename = secure_filename(file.filename)
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                        filename = timestamp + filename
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)
                        image_paths.append(filename)  # Store just filename
        
        content = data.get('content', '').strip()
        scheduled_time = data.get('scheduled_time', '')
        
        if not content:
            return jsonify({'error': 'Tweet content is required'}), 400
        
        if not scheduled_time:
            return jsonify({'error': 'Scheduled time is required'}), 400
        
        if len(image_paths) > 4:
            return jsonify({'error': 'Maximum 4 images allowed'}), 400
        
        # Parse scheduled time
        scheduled_datetime = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
        now = datetime.now(scheduled_datetime.tzinfo)
        
        if scheduled_datetime < now:
            return jsonify({'error': 'Scheduled time must be in the future'}), 400
        
        # Save to database
        conn = get_db_connection()
        c = conn.cursor()
        image_paths_json = json.dumps(image_paths) if image_paths else None
        
        if USE_POSTGRES:
            c.execute('''
                INSERT INTO tweets (content, scheduled_time, posted, image_paths)
                VALUES (%s, %s, 0, %s)
                RETURNING id
            ''', (content, scheduled_time, image_paths_json))
            tweet_id = c.fetchone()[0]
        else:
            c.execute('''
                INSERT INTO tweets (content, scheduled_time, posted, image_paths)
                VALUES (?, ?, 0, ?)
            ''', (content, scheduled_time, image_paths_json))
            tweet_id = c.lastrowid
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'id': tweet_id,
            'message': 'Tweet scheduled successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/tweets', methods=['GET'])
def get_tweets():
    conn = get_db_connection()
    c = conn.cursor()
    
    if USE_POSTGRES:
        c.execute('''
            SELECT id, content, scheduled_time, posted, image_paths, created_at
            FROM tweets
            ORDER BY scheduled_time DESC
            LIMIT 50
        ''')
    else:
        c.execute('''
            SELECT id, content, scheduled_time, posted, image_paths, created_at
            FROM tweets
            ORDER BY scheduled_time DESC
            LIMIT 50
        ''')
    
    tweets = []
    for row in c.fetchall():
        image_paths = []
        if row[4]:
            try:
                image_paths = json.loads(row[4])
            except:
                pass
        tweets.append({
            'id': row[0],
            'content': row[1],
            'scheduled_time': row[2],
            'posted': bool(row[3]),
            'image_paths': image_paths,
            'created_at': str(row[5]) if row[5] else None
        })
    conn.close()
    return jsonify(tweets)

def upload_media_to_twitter(image_paths):
    """Upload images to Twitter and return media_ids"""
    if not api_v1 or not image_paths:
        return []
    
    media_ids = []
    for image_filename in image_paths:
        try:
            # Construct full path
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            if os.path.exists(image_path):
                media = api_v1.media_upload(image_path)
                media_ids.append(media.media_id)
            else:
                print(f"Image file not found: {image_path}")
        except Exception as e:
            print(f"Error uploading media {image_filename}: {e}")
            continue
    return media_ids

@app.route('/api/post-now', methods=['POST'])
def post_now():
    if not client:
        return jsonify({'error': 'Twitter API credentials not configured'}), 500
    
    try:
        # Handle multipart form data for file uploads
        if request.is_json:
            data = request.json
            image_paths = data.get('image_paths', [])
        else:
            data = request.form.to_dict()
            content = data.get('content', '').strip()
            
            # Handle file uploads
            image_paths = []
            if 'images[]' in request.files:
                files = request.files.getlist('images[]')
                for file in files:
                    if file and file.filename:
                        filename = secure_filename(file.filename)
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                        filename = timestamp + filename
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)
                        image_paths.append(filename)  # Store just filename
        
        content = data.get('content', '').strip()
        
        if not content:
            return jsonify({'error': 'Tweet content is required'}), 400
        
        if len(content) > 280:
            return jsonify({'error': 'Tweet content exceeds 280 characters'}), 400
        
        if len(image_paths) > 4:
            return jsonify({'error': 'Maximum 4 images allowed'}), 400
        
        # Upload media if images provided (convert filepaths to filenames if needed)
        image_filenames = [path.split('/')[-1] if '/' in path else path.split('\\')[-1] if '\\' in path else path for path in image_paths]
        media_ids = upload_media_to_twitter(image_filenames) if image_filenames else None
        
        # Post tweet with or without media
        if media_ids:
            response = client.create_tweet(text=content, media_ids=media_ids)
        else:
            response = client.create_tweet(text=content)
        
        return jsonify({
            'success': True,
            'tweet_id': response.data['id'],
            'message': 'Tweet posted successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

def check_and_post_tweets():
    """Background thread to check and post scheduled tweets"""
    while True:
        try:
            conn = get_db_connection()
            c = conn.cursor()
            now = datetime.now().isoformat()
            
            # Get tweets with image paths
            if USE_POSTGRES:
                c.execute('''
                    SELECT id, content, image_paths FROM tweets
                    WHERE posted = 0 AND scheduled_time <= %s
                ''', (now,))
            else:
                c.execute('''
                    SELECT id, content, image_paths FROM tweets
                    WHERE posted = 0 AND scheduled_time <= ?
                ''', (now,))
            
            tweets_to_post = c.fetchall()
            
            for tweet_id, content, image_paths_json in tweets_to_post:
                if client:
                    try:
                        if len(content) <= 280:
                            # Parse image paths
                            image_paths = []
                            if image_paths_json:
                                try:
                                    image_paths = json.loads(image_paths_json)
                                except:
                                    pass
                            
                            # Upload media if images exist
                            media_ids = upload_media_to_twitter(image_paths) if image_paths else None
                            
                            # Post tweet with or without media
                            if media_ids:
                                response = client.create_tweet(text=content, media_ids=media_ids)
                            else:
                                response = client.create_tweet(text=content)
                            
                            # Mark as posted
                            if USE_POSTGRES:
                                c.execute('UPDATE tweets SET posted = 1 WHERE id = %s', (tweet_id,))
                            else:
                                c.execute('UPDATE tweets SET posted = 1 WHERE id = ?', (tweet_id,))
                            conn.commit()
                            print(f"Posted tweet {tweet_id}: {content[:50]}...")
                        else:
                            print(f"Skipping tweet {tweet_id}: exceeds 280 characters")
                            if USE_POSTGRES:
                                c.execute('UPDATE tweets SET posted = 1 WHERE id = %s', (tweet_id,))
                            else:
                                c.execute('UPDATE tweets SET posted = 1 WHERE id = ?', (tweet_id,))
                            conn.commit()
                    except Exception as e:
                        print(f"Error posting tweet {tweet_id}: {e}")
                else:
                    print("Twitter client not initialized. Skipping tweet posting.")
            
            conn.close()
        except Exception as e:
            print(f"Error in scheduler thread: {e}")
        
        # Check every 60 seconds
        time.sleep(60)

# Start background scheduler thread
scheduler_thread = threading.Thread(target=check_and_post_tweets, daemon=True)
scheduler_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print("Starting Twitter Scheduler...")
    print(f"Database: {'PostgreSQL' if USE_POSTGRES else 'SQLite'}")
    print(f"Open http://localhost:{port} in your browser")
    app.run(debug=True, host='0.0.0.0', port=port)

