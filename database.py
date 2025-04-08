import mysql.connector
import pytz
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
import re

# Load environment variables
load_dotenv()

# Database configuration from environment variables
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

logger = logging.getLogger(__name__)

def init_db():
    try:
        print("Initializing database")
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        c = conn.cursor()
        
        # First, create the database if it doesn't exist
        db_name = os.getenv('DB_NAME')
        c.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        c.execute(f"USE {db_name}")
        
        # Create emails table with sender_email column and session_id
        c.execute('''CREATE TABLE IF NOT EXISTS emails
                     (id INT AUTO_INCREMENT PRIMARY KEY,
                      sender_id INT,
                      sender_email VARCHAR(255) NOT NULL,
                      session_id VARCHAR(255),
                      message_id VARCHAR(255) NOT NULL,
                      in_reply_to VARCHAR(255),
                      subject TEXT,
                      message TEXT,
                      role VARCHAR(10) NOT NULL,
                      received_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        conn.commit()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        raise

def extract_email_address(email_string):
    """Extract clean email address from a string like 'Name <email@example.com>'"""
    match = re.search(r'<([^>]+)>', email_string)
    if match:
        return match.group(1).lower()
    return email_string.strip().lower()

def get_conversation_id(c, sender_email, subject, in_reply_to=None):
    """
    Determine the conversation ID based on multiple factors:
    1. If in_reply_to exists, find its session_id
    2. If not, create a new session_id for this conversation
    """
    clean_sender = extract_email_address(sender_email)
    
    # 1. Check if this is a direct reply to a message we have
    if in_reply_to:
        c.execute("SELECT session_id FROM emails WHERE message_id = %s", (in_reply_to,))
        result = c.fetchone()
        if result and result[0]:
            logger.info(f"Found session_id {result[0]} from in_reply_to")
            return result[0]
    
    # 2. For all other cases, create a new session_id
    # This ensures each new email starts a fresh conversation
    return None  # Returning None will cause a new session_id to be created

def save_email(sender_email, message_id, in_reply_to, subject, message, role='user'):
    try:
        logger.debug(f"Saving email from {sender_email} with Message-ID: {message_id}")
        conn = mysql.connector.connect(**DB_CONFIG)
        c = conn.cursor()
        
        # Generate a simple sender_id based on email hash
        sender_id = hash(sender_email) % 10000000
        
        # Get current datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # First, check if this exact message already exists (avoid duplicates)
        c.execute("SELECT id FROM emails WHERE message_id = %s", (message_id,))
        if c.fetchone():
            logger.debug(f"Message with ID {message_id} already exists in database. Skipping.")
            conn.close()
            return
        
        # Determine the session_id using our improved algorithm
        session_id = get_conversation_id(c, sender_email, subject, in_reply_to)
        
        # If no existing session found, create a new one based on this message
        if not session_id:
            session_id = message_id
            logger.info(f"Created new session_id: {session_id}")
        
        # Insert the email into the database
        c.execute("""INSERT INTO emails 
                    (sender_id, sender_email, session_id, message_id, in_reply_to, subject, message, role, received_at) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                  (sender_id, sender_email, session_id, message_id, in_reply_to, subject, message, role, now))
        
        # Update any existing emails that might be part of this conversation but have different session_ids
        if role == 'user':  # Only do this for incoming user emails to avoid unnecessary updates
            # Find emails with matching sender or similar subject but different session_id
            clean_subject = re.sub(r'^(?:Re|Fwd|FW|RE|FWD):\s*', '', subject, flags=re.IGNORECASE).strip().lower()
            clean_sender = extract_email_address(sender_email)
            
            c.execute("""
                UPDATE emails 
                SET session_id = %s 
                WHERE session_id != %s 
                AND (
                    (sender_email = %s OR sender_email LIKE %s)
                    OR LOWER(REPLACE(subject, 'Re: ', '')) = %s
                )
            """, (session_id, session_id, clean_sender, f"%{clean_sender}%", clean_subject))
            
            if c.rowcount > 0:
                logger.info(f"Updated {c.rowcount} existing emails to use session_id: {session_id}")
        
        conn.commit()
        conn.close()
        logger.debug(f"Email saved successfully with session_id: {session_id}")
        return session_id
    except Exception as e:
        logger.error(f"Error saving email: {e}", exc_info=True)
        raise

def get_all_emails():
    conn = mysql.connector.connect(**DB_CONFIG)
    c = conn.cursor()
    
    c.execute('''SELECT * FROM emails ORDER BY received_at DESC''')
    emails = c.fetchall()
    conn.close()
    return emails

def display_emails():
    try:
        logger.debug("Fetching emails for display")
        conn = mysql.connector.connect(**DB_CONFIG)
        c = conn.cursor()
        
        c.execute('''SELECT sender_email, message_id, in_reply_to, session_id, subject, message, role, received_at 
                     FROM emails
                     ORDER BY received_at DESC''')
        emails = c.fetchall()
        
        print("\nSaved Emails:")
        print("-" * 50)
        for email in emails:
            print(f"From: {email[0]}")
            print(f"Role: {email[6]}")
            print(f"Message-ID: {email[1]}")
            if email[2]:
                print(f"In-Reply-To: {email[2]}")
            print(f"Session-ID: {email[3]}")
            print(f"Subject: {email[4]}")
            print(f"Received: {email[7]}")
            print(f"Message: {email[5][:100]}...")  # Display first 100 chars of message
            print("-" * 50)
        
        conn.close()
        logger.debug(f"Displayed {len(emails)} emails")
    except Exception as e:
        logger.error(f"Error displaying emails: {e}", exc_info=True)

def check_message_processed(message_id):
    """Check if a message has already been processed"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        c = conn.cursor()
        
        # Check if we have already processed this message
        c.execute("SELECT id FROM emails WHERE message_id = %s OR in_reply_to = %s", (message_id, message_id))
        result = c.fetchone()
        conn.close()
        
        return result is not None
    except Exception as e:
        logger.error(f"Error checking message status: {e}", exc_info=True)
        return False  # If in doubt, process the message

# Initialize database when module is imported
init_db() 