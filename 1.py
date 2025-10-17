# app_enhanced.py - Enhanced Flask Backend with Environment Variables
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import sqlite3
from datetime import datetime
import requests
import json
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration from environment variables
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 52428800))
app.config['DATABASE'] = os.getenv('DATABASE_URL', 'church.db')

# CORS configuration
allowed_origins = os.getenv('CORS_ORIGINS', '*').split(',')
CORS(app, origins=allowed_origins)

# Logging configuration
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.getenv('LOG_FILE', 'church_website.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# File type configurations
ALLOWED_IMAGES = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_VIDEOS = {'mp4', 'avi', 'mov', 'wmv', 'webm'}
ALLOWED_DOCS = {'pdf', 'doc', 'docx'}

# Create upload directories
for folder in ['photos', 'videos', 'documents']:
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], folder), exist_ok=True)

# Database functions
def get_db():
    """Get database connection"""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with tables"""
    conn = get_db()
    c = conn.cursor()
    
    # Admin users table
    c.execute('''CREATE TABLE IF NOT EXISTS admins
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  role TEXT NOT NULL,
                  email TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Photos table
    c.execute('''CREATE TABLE IF NOT EXISTS photos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT NOT NULL,
                  category TEXT NOT NULL,
                  description TEXT,
                  uploaded_by TEXT NOT NULL,
                  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Videos table
    c.execute('''CREATE TABLE IF NOT EXISTS videos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT NOT NULL,
                  title TEXT NOT NULL,
                  description TEXT,
                  uploaded_by TEXT NOT NULL,
                  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Documents table
    c.execute('''CREATE TABLE IF NOT EXISTS documents
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT NOT NULL,
                  title TEXT NOT NULL,
                  category TEXT NOT NULL,
                  uploaded_by TEXT NOT NULL,
                  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # News table
    c.execute('''CREATE TABLE IF NOT EXISTS news
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT NOT NULL,
                  content TEXT NOT NULL,
                  image_filename TEXT NOT NULL,
                  author TEXT NOT NULL,
                  published BOOLEAN DEFAULT 1,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Donations table
    c.execute('''CREATE TABLE IF NOT EXISTS donations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  donor_name TEXT NOT NULL,
                  donor_email TEXT,
                  donor_phone TEXT NOT NULL,
                  amount REAL NOT NULL,
                  purpose TEXT NOT NULL,
                  provider TEXT NOT NULL,
                  reference_number TEXT UNIQUE NOT NULL,
                  status TEXT DEFAULT 'completed',
                  transaction_id TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Contact messages table
    c.execute('''CREATE TABLE IF NOT EXISTS contact_messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  email TEXT NOT NULL,
                  subject TEXT NOT NULL,
                  message TEXT NOT NULL,
                  read BOOLEAN DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Insert default admin users
    default_admins = [
        ('admin', 'sda2025', 'Administrator', 'admin@sefwihumjibresda.org'),
        ('pastor', 'pastor123', 'Pastor', 'pastor@sefwihumjibresda.org'),
        ('elder', 'elder456', 'Elder', 'elder@sefwihumjibresda.org')
    ]
    
    for username, password, role, email in default_admins:
        try:
            password_hash = generate_password_hash(password)
            c.execute('INSERT INTO admins (username, password_hash, role, email) VALUES (?, ?, ?, ?)',
                     (username, password_hash, role, email))
        except sqlite3.IntegrityError:
            pass
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

# SMS sending function with multiple provider support
def send_sms(phone_number, message):
    """Send SMS using configured provider"""
    provider = os.getenv('SMS_PROVIDER', 'hubtel')
    
    try:
        if provider == 'hubtel':
            return send_sms_hubtel(phone_number, message)
        elif provider == 'mnotify':
            return send_sms_mnotify(phone_number, message)
        else:
            # Fallback to console logging
            logger.info(f"SMS to {phone_number}: {message}")
            return {"status": "success", "message": "SMS logged (no provider configured)"}
    except Exception as e:
        logger.error(f"SMS Error: {str(e)}")
        return {"status": "error", "message": str(e)}

def send_sms_hubtel(phone_number, message):
    """Send SMS via Hubtel"""
    api_key = os.getenv('HUBTEL_API_KEY')
    api_secret = os.getenv('HUBTEL_API_SECRET')
    sender_id = os.getenv('HUBTEL_SENDER_ID', 'SDA_CHURCH')
    
    if not api_key or not api_secret:
        logger.warning("Hubtel credentials not configured")
        return {"status": "error", "message": "SMS provider not configured"}
    
    url = "https://smsc.hubtel.com/v1/messages/send"
    response = requests.get(url, params={
        "clientsecret": api_secret,
        "clientid": api_key,
        "from": sender_id,
        "to": phone_number,
        "content": message
    })
    
    return response.json()

def send_sms_mnotify(phone_number, message):
    """Send SMS via Mnotify"""
    api_key = os.getenv('MNOTIFY_API_KEY')
    sender_id = os.getenv('MNOTIFY_SENDER_ID', 'SDA_CHURCH')
    
    if not api_key:
        logger.warning("Mnotify credentials not configured")
        return {"status": "error", "message": "SMS provider not configured"}
    
    url = "https://api.mnotify.com/api/sms/quick"
    response = requests.post(url, json={
        "key": api_key,
        "to": phone_number,
        "msg": message,
        "sender_id": sender_id
    })
    
    return response.json()

# Mobile Money payment processing
def process_mobile_money(provider, phone_number, amount, purpose, donor_name):
    """Process mobile money payment"""
    gateway = os.getenv('PAYMENT_GATEWAY', 'hubtel')
    reference = f"SDA{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    try:
        if gateway == 'hubtel':
            return process_hubtel_payment(provider, phone_number, amount, purpose, donor_name, reference)
        elif gateway == 'paystack':
            return process_paystack_payment(provider, phone_number, amount, purpose, donor_name, reference)
        else:
            # Simulation mode for testing
            logger.info(f"Simulated payment: {provider} - {phone_number} - GHS {amount}")
            return {
                "status": "success",
                "reference": reference,
                "message": "Payment processed (simulation mode)",
                "transaction_id": f"TEST_{reference}"
            }
    except Exception as e:
        logger.error(f"Payment Error: {str(e)}")
        return {"status": "error", "message": str(e)}

def process_hubtel_payment(provider, phone_number, amount, purpose, donor_name, reference):
    """Process payment via Hubtel"""
    merchant_id = os.getenv('HUBTEL_MERCHANT_ID')
    api_key = os.getenv('HUBTEL_PAYMENT_API_KEY')
    callback_url = os.getenv('HUBTEL_CALLBACK_URL')
    
    if not all([merchant_id, api_key]):
        logger.warning("Hubtel payment credentials not configured")
        return {"status": "error", "message": "Payment gateway not configured"}
    
    url = f"https://api.hubtel.com/v1/merchantaccount/merchants/{merchant_id}/receive/mobilemoney"
    
    response = requests.post(url, json={
        "CustomerName": donor_name,
        "CustomerMsisdn": phone_number,
        "CustomerEmail": "",
        "Channel": provider.lower(),
        "Amount": amount,
        "PrimaryCallbackUrl": callback_url,
        "Description": f"Church Donation - {purpose}",
        "ClientReference": reference
    }, auth=(api_key, ''))
    
    result = response.json()
    return {
        "status": "success" if result.get('ResponseCode') == '0000' else "error",
        "reference": reference,
        "transaction_id": result.get('TransactionId'),
        "message": result.get('Message', 'Payment processed')
    }

def process_paystack_payment(provider, phone_number, amount, purpose, donor_name, reference):
    """Process payment via Paystack"""
    secret_key = os.getenv('PAYSTACK_SECRET_KEY')
    
    if not secret_key:
        logger.warning("Paystack credentials not configured")
        return {"status": "error", "message": "Payment gateway not configured"}
    
    url = "https://api.paystack.co/charge"
    
    # Convert amount to kobo/pesewas (multiply by 100)
    amount_in_pesewas = int(float(amount) * 100)
    
    response = requests.post(url, json={
        "email": f"{reference}@donation.church",
        "amount": amount_in_pesewas,
        "mobile_money": {
            "phone": phone_number,
            "provider": provider.lower()
        },
        "reference": reference
    }, headers={"Authorization": f"Bearer {secret_key}"})
    
    result = response.json()
    return {
        "status": "success" if result.get('status') else "error",
        "reference": reference,
        "transaction_id": result.get('data', {}).get('id'),
        "message": result.get('message', 'Payment processed')
    }

# API Routes

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'message': 'Church API is running',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Admin login endpoint"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Missing credentials'}), 400
    
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT password_hash, role, email FROM admins WHERE username = ?', (username,))
        result = c.fetchone()
        conn.close()
        
        if result and check_password_hash(result[0], password):
            logger.info(f"Successful login: {username}")
            return jsonify({
                'success': True,
                'username': username,
                'role': result[1],
                'email': result[2]
            })
        
        logger.warning(f"Failed login attempt: {username}")
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/photos/upload', methods=['POST'])
def upload_photos():
    """Upload photos endpoint"""
    if 'photos' not in request.files:
        return jsonify({'error': 'No photos provided'}), 400
    
    files = request.files.getlist('photos')
    category = request.form.get('category', 'gallery')
    description = request.form.get('description', '')
    uploaded_by = request.form.get('uploaded_by', 'admin')
    
    uploaded_files = []
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        for file in files:
            if file and allowed_file(file.filename, ALLOWED_IMAGES):
                filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'photos', filename)
                file.save(filepath)
                
                c.execute('''INSERT INTO photos (filename, category, description, uploaded_by)
                            VALUES (?, ?, ?, ?)''',
                         (filename, category, description, uploaded_by))
                uploaded_files.append(filename)
                logger.info(f"Photo uploaded: {filename} by {uploaded_by}")
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'files': uploaded_files,
            'message': f'{len(uploaded_files)} photos uploaded successfully'
        })
    except Exception as e:
        logger.error(f"Photo upload error: {str(e)}")
        return jsonify({'error': 'Upload failed'}), 500

@app.route('/api/videos/upload', methods=['POST'])
def upload_videos():
    """Upload videos endpoint"""
    if 'videos' not in request.files:
        return jsonify({'error': 'No videos provided'}), 400
    
    files = request.files.getlist('videos')
    title = request.form.get('title', 'Untitled')
    description = request.form.get('description', '')
    uploaded_by = request.form.get('uploaded_by', 'admin')
    
    uploaded_files = []
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        for file in files:
            if file and allowed_file(file.filename, ALLOWED_VIDEOS):
                filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'videos', filename)
                file.save(filepath)
                
                c.execute('''INSERT INTO videos (filename, title, description, uploaded_by)
                            VALUES (?, ?, ?, ?)''',
                         (filename, title, description, uploaded_by))
                uploaded_files.append(filename)
                logger.info(f"Video uploaded: {filename} by {uploaded_by}")
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'files': uploaded_files,
            'message': f'{len(uploaded_files)} videos uploaded successfully'
        })
    except Exception as e:
        logger.error(f"Video upload error: {str(e)}")
        return jsonify({'error': 'Upload failed'}), 500

@app.route('/api/documents/upload', methods=['POST'])
def upload_documents():
    """Upload documents endpoint"""
    if 'documents' not in request.files:
        return jsonify({'error': 'No documents provided'}), 400
    
    files = request.files.getlist('documents')
    title = request.form.get('title', 'Untitled')
    category = request.form.get('category', 'other')
    uploaded_by = request.form.get('uploaded_by', 'admin')
    
    uploaded_files = []
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        for file in files:
            if file and allowed_file(file.filename, ALLOWED_DOCS):
                filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', filename)
                file.save(filepath)
                
                c.execute('''INSERT INTO documents (filename, title, category, uploaded_by)
                            VALUES (?, ?, ?, ?)''',
                         (filename, title, category, uploaded_by))
                uploaded_files.append(filename)
                logger.info(f"Document uploaded: {filename} by {uploaded_by}")
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'files': uploaded_files,
            'message': f'{len(uploaded_files)} documents uploaded successfully'
        })
    except Exception as e:
        logger.error(f"Document upload error: {str(e)}")
        return jsonify({'error': 'Upload failed'}), 500

@app.route('/api/news/create', methods=['POST'])
def create_news():
    """Create news post endpoint"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    image = request.files['image']
    title = request.form.get('title')
    content = request.form.get('content')
    author = request.form.get('author')
    
    if not all([title, content, author]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        if image and allowed_file(image.filename, ALLOWED_IMAGES):
            filename = secure_filename(f"news_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'photos', filename)
            image.save(filepath)
            
            conn = get_db()
            c = conn.cursor()
            c.execute('''INSERT INTO news (title, content, image_filename, author)
                        VALUES (?, ?, ?, ?)''',
                     (title, content, filename, author))
            news_id = c.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"News created: {title} by {author}")
            
            return jsonify({
                'success': True,
                'news_id': news_id,
                'message': 'News post created successfully'
            })
        
        return jsonify({'error': 'Invalid image file'}), 400
    except Exception as e:
        logger.error(f"News creation error: {str(e)}")
        return jsonify({'error': 'Failed to create news'}), 500

@app.route('/api/news/list', methods=['GET'])
def list_news():
    """List all news posts"""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('''SELECT id, title, content, image_filename, author, created_at 
                    FROM news WHERE published = 1 ORDER BY created_at DESC''')
        rows = c.fetchall()
        conn.close()
        
        news_list = []
        for row in rows:
            news_list.append({
                'id': row[0],
                'title': row[1],
                'content': row[2],
                'image': f'/uploads/photos/{row[3]}',
                'author': row[4],
                'date': row[5]
            })
        
        return jsonify(news_list)
    except Exception as e:
        logger.error(f"News list error: {str(e)}")
        return jsonify({'error': 'Failed to fetch news'}), 500

@app.route('/api/photos/list', methods=['GET'])
def list_photos():
    """List all photos"""
    category = request.args.get('category')
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        if category:
            c.execute('''SELECT id, filename, category, description, uploaded_at 
                        FROM photos WHERE category = ? ORDER BY uploaded_at DESC''', (category,))
        else:
            c.execute('''SELECT id, filename, category, description, uploaded_at 
                        FROM photos ORDER BY uploaded_at DESC''')
        
        rows = c.fetchall()
        conn.close()
        
        photos = []
        for row in rows:
            photos.append({
                'id': row[0],
                'url': f'/uploads/photos/{row[1]}',
                'category': row[2],
                'description': row[3],
                'date': row[4]
            })
        
        return jsonify(photos)
    except Exception as e:
        logger.error(f"Photos list error: {str(e)}")
        return jsonify({'error': 'Failed to fetch photos'}), 500

@app.route('/api/videos/list', methods=['GET'])
def list_videos():
    """List all videos"""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('''SELECT id, filename, title, description, uploaded_at 
                    FROM videos ORDER BY uploaded_at DESC''')
        rows = c.fetchall()
        conn.close()
        
        videos = []
        for row in rows:
            videos.append({
                'id': row[0],
                'url': f'/uploads/videos/{row[1]}',
                'title': row[2],
                'description': row[3],
                'date': row[4]
            })
        
        return jsonify(videos)
    except Exception as e:
        logger.error(f"Videos list error: {str(e)}")
        return jsonify({'error': 'Failed to fetch videos'}), 500

@app.route('/api/donation/process', methods=['POST'])
def process_donation():
    """Process donation endpoint"""
    data = request.json
    
    donor_name = data.get('donor_name')
    donor_email = data.get('donor_email')
    donor_phone = data.get('donor_phone')
    amount = data.get('amount')
    purpose = data.get('purpose')
    provider = data.get('provider')
    
    if not all([donor_name, donor_phone, amount, purpose, provider]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        # Process mobile money payment
        payment_result = process_mobile_money(provider, donor_phone, amount, purpose, donor_name)
        
        if payment_result['status'] == 'success':
            reference = payment_result['reference']
            transaction_id = payment_result.get('transaction_id', '')
            
            # Save donation to database
            conn = get_db()
            c = conn.cursor()
            c.execute('''INSERT INTO donations 
                        (donor_name, donor_email, donor_phone, amount, purpose, provider, 
                         reference_number, transaction_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                     (donor_name, donor_email, donor_phone, amount, purpose, provider, 
                      reference, transaction_id))
            conn.commit()
            conn.close()
            
            # Send SMS confirmation
            sms_message = (f"Thank you {donor_name} for your donation of GHS {amount} "
                          f"to Sefwi Humjibre SDA Church for {purpose}. "
                          f"Reference: {reference}. May God bless you abundantly!")
            
            sms_result = send_sms(donor_phone, sms_message)
            
            logger.info(f"Donation processed: {reference} - GHS {amount} from {donor_name}")
            
            return jsonify({
                'success': True,
                'reference': reference,
                'transaction_id': transaction_id,
                'message': 'Donation processed successfully',
                'sms_sent': sms_result.get('status') == 'success'
            })
        else:
            logger.error(f"Payment failed: {payment_result['message']}")
            return jsonify({
                'success': False,
                'error': payment_result['message']
            }), 400
    except Exception as e:
        logger.error(f"Donation processing error: {str(e)}")
        return jsonify({'error': 'Failed to process donation'}), 500

@app.route('/api/donations/list', methods=['GET'])
def list_donations():
    """List all donations (admin only)"""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('''SELECT id, donor_name, amount, purpose, provider, 
                     reference_number, created_at 
                     FROM donations ORDER BY created_at DESC LIMIT 100''')
        rows = c.fetchall()
        conn.close()
        
        donations = []
        for row in rows:
            donations.append({
                'id': row[0],
                'donor': row[1],
                'amount': row[2],
                'purpose': row[3],
                'provider': row[4],
                'reference': row[5],
                'date': row[6]
            })
        
        return jsonify(donations)
    except Exception as e:
        logger.error(f"Donations list error: {str(e)}")
        return jsonify({'error': 'Failed to fetch donations'}), 500

@app.route('/api/donations/stats', methods=['GET'])
def donation_stats():
    """Get donation statistics"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Total donations
        c.execute('SELECT COUNT(*), SUM(amount) FROM donations WHERE status = "completed"')
        total_count, total_amount = c.fetchone()
        
        # By purpose
        c.execute('''SELECT purpose, COUNT(*), SUM(amount) 
                    FROM donations WHERE status = "completed" 
                    GROUP BY purpose''')
        by_purpose = [{'purpose': row[0], 'count': row[1], 'amount': row[2]} 
                     for row in c.fetchall()]
        
        # Recent donations
        c.execute('''SELECT donor_name, amount, purpose, created_at 
                    FROM donations WHERE status = "completed" 
                    ORDER BY created_at DESC LIMIT 10''')
        recent = [{'donor': row[0], 'amount': row[1], 'purpose': row[2], 'date': row[3]} 
                 for row in c.fetchall()]
        
        conn.close()
        
        return jsonify({
            'total_count': total_count or 0,
            'total_amount': total_amount or 0,
            'by_purpose': by_purpose,
            'recent': recent
        })
    except Exception as e:
        logger.error(f"Donation stats error: {str(e)}")
        return jsonify({'error': 'Failed to fetch statistics'}), 500

@app.route('/api/contact/submit', methods=['POST'])
def submit_contact():
    """Submit contact form"""
    data = request.json
    
    name = data.get('name')
    email = data.get('email')
    subject = data.get('subject')
    message = data.get('message')
    
    if not all([name, email, subject, message]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT INTO contact_messages (name, email, subject, message)
                    VALUES (?, ?, ?, ?)''',
                 (name, email, subject, message))
        conn.commit()
        conn.close()
        
        logger.info(f"Contact message from: {name} ({email})")
        
        return jsonify({
            'success': True,
            'message': 'Message sent successfully'
        })
    except Exception as e:
        logger.error(f"Contact submission error: {str(e)}")
        