from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail, Message
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, EmailField
from wtforms.validators import DataRequired, Email, Length
import os
import logging
from datetime import datetime, timedelta
import secrets
from dotenv import load_dotenv
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables
load_dotenv()

app = Flask(__name__)

# ===== Configuration =====
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-super-secret-key-here-chouaib-2024'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///portfolio.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Email configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'chouaibbouguerba20@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'tpjaegcxvnzdwcdc')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'chouaibbouguerba20@gmail.com')
    
    # Rate limiting
    RATELIMIT_STORAGE_URI = 'memory://'
    
    # Security
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = os.environ.get('CSRF_SECRET_KEY') or secrets.token_hex(32)

app.config.from_object(Config)

# ===== Extensions =====
db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# ===== Forms =====
class ContactForm(FlaskForm):
    name = StringField('Name', validators=[
        DataRequired(),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters')
    ])
    email = EmailField('Email', validators=[
        DataRequired(),
        Email(message='Please enter a valid email address'),
        Length(max=120)
    ])
    subject = StringField('Subject', validators=[
        DataRequired(),
        Length(min=5, max=200, message='Subject must be between 5 and 200 characters')
    ])
    message = TextAreaField('Message', validators=[
        DataRequired(),
        Length(min=10, max=2000, message='Message must be between 10 and 2000 characters')
    ])

# ===== Database Models =====
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(45))  # IPv6 support
    user_agent = db.Column(db.Text)
    date_sent = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    spam_score = db.Column(db.Float, default=0.0)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'subject': self.subject,
            'message': self.message[:100] + '...' if len(self.message) > 100 else self.message,
            'date_sent': self.date_sent.isoformat(),
            'is_read': self.is_read
        }

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    technologies = db.Column(db.String(500))
    github_url = db.Column(db.String(500))
    live_url = db.Column(db.String(500))
    image_url = db.Column(db.String(500))
    featured = db.Column(db.Boolean, default=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'technologies': self.technologies.split(',') if self.technologies else [],
            'github_url': self.github_url,
            'live_url': self.live_url,
            'image_url': self.image_url,
            'featured': self.featured
        }

# ===== Utility Functions =====
def is_spam_message(message_text, email):
    """Basic spam detection"""
    spam_indicators = [
        r'\b(viagra|cialis|casino|porn)\b',
        r'\b(free.*money|make.*money)\b',
        r'\b(urgent|emergency)\b.*\b(money|help)\b',
        r'http[s]?://[^\s]*',
    ]
    
    score = 0
    for pattern in spam_indicators:
        if re.search(pattern, message_text, re.IGNORECASE):
            score += 0.25
    
    if re.search(r'\d{5,}@', email):
        score += 0.25
    
    return min(score, 1.0)

def send_notification_email(message):
    """Send email notification using SMTP"""
    try:
        # Use configuration from environment
        sender_email = app.config['MAIL_USERNAME']
        sender_password = app.config['MAIL_PASSWORD']
        receiver_email = sender_email  # Send to yourself
        
        print(f"🔄 Attempting to send email from {sender_email} to {receiver_email}")
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = f"🎯 New Portfolio Message: {message.subject}"
        
        # Email body with better formatting
        body = f"""
🌟 NEW MESSAGE FROM YOUR PORTFOLIO WEBSITE 🌟

📋 Contact Information:
────────────────────
• Name: {message.name}
• Email: {message.email}
• Subject: {message.subject}

💬 Message Content:
─────────────────
{message.message}

📊 Technical Details:
───────────────────
• Date: {message.date_sent.strftime('%Y-%m-%d %H:%M:%S')}
• IP Address: {message.ip_address}
• User Agent: {message.user_agent[:100] if message.user_agent else 'N/A'}

⚡ Action Required: Please respond to this message within 24 hours!

---
This email was automatically sent from your portfolio website.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email using SMTP
        with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            
        print("✅ Email sent successfully!")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ SMTP Authentication Failed: {e}")
        print("💡 Please check your email password and ensure 2-factor authentication is enabled with app passwords")
        return False
    except Exception as e:
        print(f"❌ Failed to send email: {str(e)}")
        return False

def send_notification_email_flask_mail(message):
    """Alternative method using Flask-Mail"""
    try:
        msg = Message(
            subject=f"📧 Portfolio Message: {message.subject}",
            recipients=[app.config['MAIL_USERNAME']],
            sender=app.config['MAIL_DEFAULT_SENDER'],
            body=f"""
New message from your portfolio:

Name: {message.name}
Email: {message.email}
Subject: {message.subject}

Message:
{message.message}

Date: {message.date_sent}
IP: {message.ip_address}
            """
        )
        mail.send(msg)
        print("✅ Email sent via Flask-Mail!")
        return True
    except Exception as e:
        print(f"❌ Flask-Mail failed: {str(e)}")
        return False

# ===== Routes =====
@app.route('/')
def index():
    """Main portfolio page"""
    featured_projects = Project.query.filter_by(featured=True).all()
    return render_template('index.html', 
                         featured_projects=[p.to_dict() for p in featured_projects])

@app.route('/test-email')
def test_email():
    """Test email functionality"""
    try:
        print("🧪 Testing email configuration...")
        print(f"📧 Using: {app.config['MAIL_USERNAME']}")
        print(f"🔑 Password: {'*' * len(app.config['MAIL_PASSWORD'])}")
        
        # Test message
        test_msg = type('TestMessage', (), {
            'name': 'Test User',
            'email': 'test@example.com', 
            'subject': '🧪 Test Message - Portfolio Email System',
            'message': 'This is a test message to verify that the email system is working correctly! If you receive this, everything is configured properly. 🎉',
            'date_sent': datetime.utcnow(),
            'ip_address': '127.0.0.1',
            'user_agent': 'Test Browser'
        })()
        
        print("🔄 Sending test email via SMTP...")
        result = send_notification_email(test_msg)
        
        if result:
            return """
            <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif;">
                <h1 style="color: green;">✅ Test Email Sent Successfully!</h1>
                <p>Check your inbox at <strong>chouaibbouguerba20@gmail.com</strong></p>
                <p>If you don't see the email, check your spam folder.</p>
                <a href="/" style="color: blue;">← Back to Portfolio</a>
            </div>
            """
        else:
            return """
            <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif;">
                <h1 style="color: red;">❌ Test Email Failed</h1>
                <p>Check the terminal for error messages.</p>
                <p>Common issues:</p>
                <ul style="text-align: left; display: inline-block;">
                    <li>Incorrect app password</li>
                    <li>2-factor authentication not enabled</li>
                    <li>Gmail security settings</li>
                </ul>
                <a href="/" style="color: blue;">← Back to Portfolio</a>
            </div>
            """
            
    except Exception as e:
        return f"""
        <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif;">
            <h1 style="color: red;">❌ Error: {str(e)}</h1>
            <a href="/" style="color: blue;">← Back to Portfolio</a>
        </div>
        """

@app.route('/contact', methods=['POST'])
@limiter.limit("10 per minute")
def contact():
    """Handle contact form submissions"""
    try:
        # Get form data
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message_text = request.form.get('message')

        # Validation
        if not all([name, email, subject, message_text]):
            return jsonify({'success': False, 'error': 'Please fill all fields!'}), 400

        # Spam detection
        spam_score = is_spam_message(message_text, email)
        
        # Save to database
        new_message = Message(
            name=name.strip(),
            email=email.strip().lower(),
            subject=subject.strip(),
            message=message_text.strip(),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            spam_score=spam_score
        )
        
        db.session.add(new_message)
        db.session.commit()

        print(f"✅ Message saved to database! (Spam score: {spam_score})")
        
        # Send email notification (only if not likely spam)
        if spam_score < 0.7:
            email_sent = send_notification_email(new_message)
            if email_sent:
                print("✅ Email notification sent!")
            else:
                print("⚠️ Message saved but email failed - trying Flask-Mail...")
                send_notification_email_flask_mail(new_message)
        else:
            print("🚫 High spam score - email not sent")

        return jsonify({
            'success': True, 
            'message': 'Your message has been sent successfully! I\'ll get back to you soon.'
        })

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error processing message: {str(e)}")
        return jsonify({
            'success': False, 
            'error': 'Sorry, there was an error sending your message. Please try again.'
        }), 500

# ===== API Routes =====
@app.route('/api/messages')
@limiter.limit("60 per hour")
def api_messages():
    """API endpoint to get messages"""
    if app.debug:
        messages = Message.query.order_by(Message.date_sent.desc()).limit(10).all()
        return jsonify([msg.to_dict() for msg in messages])
    else:
        return jsonify({'error': 'Not available in production'}), 403

@app.route('/api/projects')
def api_projects():
    """API endpoint to get projects"""
    projects = Project.query.filter_by(featured=True).all()
    return jsonify([p.to_dict() for p in projects])

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'Chouaib Portfolio API'
    })

# ===== Error Handlers =====
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        'success': False, 
        'error': 'Too many requests. Please slow down.'
    }), 429

# ===== Template Context =====
@app.context_processor
def inject_utilities():
    """Inject utilities into all templates"""
    return {
        'current_year': datetime.utcnow().year,
        'get_flashed_messages': flash,
        'form': ContactForm(),
        'app_name': 'Chouaib Portfolio'
    }

# ===== CLI Commands =====
@app.cli.command("init-db")
def init_db():
    """Initialize the database with sample data"""
    with app.app_context():
        db.create_all()
        
        # Add sample projects
        sample_projects = [
            Project(
                title="Enterprise AI Platform",
                description="A comprehensive AI platform that enables businesses to integrate machine learning models into their workflows with minimal setup.",
                technologies="Python,TensorFlow,React,AWS",
                github_url="https://github.com/chouaib/ai-platform",
                live_url="https://ai-platform.demo.com",
                image_url="https://images.unsplash.com/photo-1555066931-4365d14bab8c",
                featured=True
            ),
            Project(
                title="E-commerce Solution",
                description="A full-featured e-commerce platform with inventory management, payment processing, and analytics dashboard.",
                technologies="Node.js,MongoDB,React,Stripe",
                github_url="https://github.com/chouaib/ecommerce",
                live_url="https://ecommerce.demo.com",
                image_url="https://images.unsplash.com/photo-1551650975-87deedd944c3",
                featured=True
            ),
            Project(
                title="Data Analytics Dashboard",
                description="An interactive dashboard for visualizing complex datasets with real-time updates and predictive analytics.",
                technologies="Python,D3.js,Flask,PostgreSQL",
                github_url="https://github.com/chouaib/analytics-dashboard",
                live_url="https://analytics.demo.com",
                image_url="https://images.unsplash.com/photo-1551288049-bebda4e38f71",
                featured=True
            )
        ]
        
        for project in sample_projects:
            if not Project.query.filter_by(title=project.title).first():
                db.session.add(project)
        
        db.session.commit()
        print("✅ Database initialized with sample data!")

@app.cli.command("clear-messages")
def clear_messages():
    """Clear all messages from the database"""
    with app.app_context():
        if input("Are you sure you want to delete all messages? (y/N): ").lower() == 'y':
            count = Message.query.count()
            Message.query.delete()
            db.session.commit()
            print(f"✅ All {count} messages deleted!")
        else:
            print("Operation cancelled.")

@app.cli.command("stats")
def show_stats():
    """Show database statistics"""
    with app.app_context():
        message_count = Message.query.count()
        project_count = Project.query.count()
        unread_count = Message.query.filter_by(is_read=False).count()
        
        print("📊 Portfolio Statistics:")
        print(f"   Messages: {message_count}")
        print(f"   Unread: {unread_count}")
        print(f"   Projects: {project_count}")

# ===== Application Setup =====
def create_app():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler('portfolio.log'),
            logging.StreamHandler()
        ]
    )
    
    with app.app_context():
        db.create_all()
    
    return app


# ===== DO NOT USE app.run IN RENDER =====
create_app()
