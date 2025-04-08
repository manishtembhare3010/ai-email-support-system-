import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import make_msgid
import time
import os
from dotenv import load_dotenv
from database import save_email, display_emails, check_message_processed
import yaml
import logging
import requests
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("email_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Email credentials from environment variables
EMAIL = os.getenv('EMAIL')
PASSWORD = os.getenv('PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER')
IMAP_SERVER = os.getenv('IMAP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))
IMAP_PORT = int(os.getenv('IMAP_PORT'))

def load_email_templates():
    """Load email templates from YAML file"""
    try:
        with open('templates.yml', 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        logger.error(f"Error loading templates: {e}")
        # Fallback template in case file can't be loaded
        return {
            "default_reply": {
                "subject": "Re: {subject}",
                "body": "Thank you for your email. We have received your message and will respond shortly.\n\nYour message:\n{message_preview}..."
            }
        }

def read_emails():
    try:
        # Specify which email address to monitor
        monitored_email = "mtembhare50@gmail.com"  # You can change this or load from config
        
        logger.info(f"Checking for new emails from {monitored_email}...")
        
        # Load email templates
        templates = load_email_templates()
        
        # Connect to IMAP server
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL, PASSWORD)
        mail.select('inbox')

        # Search for unread emails from specific sender that don't have our custom flag
        search_criteria = f'(UNSEEN FROM "{monitored_email}" NOT KEYWORD "Processed-By-System")'
        status, messages = mail.search(None, search_criteria)
        email_ids = messages[0].split()
        
        if not email_ids:
            logger.info("No new emails found.")
            return
            
        logger.info(f"Found {len(email_ids)} new email(s) from {monitored_email}")
        
        # Connect to SMTP server
        smtp_server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        smtp_server.starttls()
        smtp_server.login(EMAIL, PASSWORD)

        for email_id in email_ids:
            try:
                logger.info(f"Processing email ID: {email_id.decode()}")
                status, msg_data = mail.fetch(email_id, '(BODY.PEEK[])')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        sender_email = msg['from']
                        subject = msg['subject']
                        message_id = msg['Message-ID']
                        in_reply_to = msg['In-Reply-To']
                        
                        logger.info(f"Processing email - Subject: {subject}, From: {sender_email}")
                        
                        # Get message body
                        message_body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == 'text/plain':
                                    payload = part.get_payload(decode=True)
                                    if payload is not None:
                                        message_body = payload.decode('utf-8', errors='replace')
                                    break
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload is not None:
                                message_body = payload.decode('utf-8', errors='replace')
                        
                        # Check if we've already processed this message_id
                        if check_message_processed(message_id):
                            logger.info(f"Email with Message-ID {message_id} already processed. Skipping.")
                            # Optionally mark as read to avoid future processing
                            mail.store(email_id, '+FLAGS', '\\Seen')
                            continue
                        
                        # Save to database
                        logger.info(f"Saving email from {sender_email} to database")
                        save_email(sender_email, message_id, in_reply_to, subject, message_body, 'user')
                        
                        # Create reply message
                        logger.info("Creating AI-generated reply...")
                        reply_msg = MIMEMultipart()
                        reply_msg['From'] = EMAIL
                        reply_msg['To'] = sender_email
                        
                        # Generate AI reply
                        ai_reply = generate_email_reply(sender_email, subject, message_body)
                        
                        # Set subject
                        reply_subject = f"Re: {subject}" if not subject.startswith("Re:") else subject
                        reply_msg['Subject'] = reply_subject
                        
                        # Generate Message-ID for reply
                        domain = EMAIL.split('@')[1]
                        reply_message_id = make_msgid(domain=domain)
                        reply_msg['Message-ID'] = reply_message_id
                        
                        # Set threading headers
                        if in_reply_to:
                            reply_msg['In-Reply-To'] = in_reply_to
                            reply_msg['References'] = in_reply_to
                        else:
                            reply_msg['In-Reply-To'] = message_id
                            reply_msg['References'] = message_id
                        
                        # Attach the AI-generated reply
                        reply_msg.attach(MIMEText(ai_reply, 'plain'))
                        
                        # Send the reply
                        logger.info(f"Sending AI-generated reply to {sender_email}")
                        smtp_server.send_message(reply_msg)
                        logger.info("AI reply sent successfully")
                        
                        # Save the reply to the database
                        logger.info("Saving AI reply to database")
                        clean_reply_id = reply_message_id.strip('<>')
                        save_email(EMAIL, clean_reply_id, message_id, reply_msg['Subject'], ai_reply, 'host')
                        logger.info("AI reply saved to database")
                        
                        # After successful processing, mark with our custom flag
                        mail.store(email_id, '+FLAGS', '(Processed-By-System)')
                        logger.info(f"Marked email {email_id.decode()} as processed")
                            
            except Exception as e:
                logger.error(f"Failed to process email {email_id}: {str(e)}", exc_info=True)
                continue

    except Exception as e:
        logger.error(f"Email processing failed: {str(e)}", exc_info=True)
    finally:
        try:
            if 'mail' in locals():
                mail.logout()
            if 'smtp_server' in locals():
                smtp_server.quit()
        except Exception as e:
            logger.error(f"Error closing connections: {str(e)}")

def run_live():
    logger.info("Starting email monitoring service")
    while True:
        try:
            read_emails()
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error in run_live: {e}", exc_info=True)
            time.sleep(5)

def ask_ollama(prompt, model="llama2", max_retries=3, timeout=60):
    """Send a prompt to Ollama and get a response"""
    url = "http://localhost:11434/api/generate"
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False  # Set to True if you want streaming responses
    }
    
    retries = 0
    while retries < max_retries:
        try:
            logger.info(f"Sending prompt to Ollama model: {model}")
            response = requests.post(url, json=data, timeout=timeout)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            result = response.json()
            logger.info("Successfully received response from Ollama")
            return result.get("response", "")
        except requests.exceptions.RequestException as e:
            retries += 1
            logger.warning(f"Ollama request failed (attempt {retries}/{max_retries}): {e}")
            if retries < max_retries:
                time.sleep(2)  # Wait before retrying
            else:
                logger.error(f"Failed to get response from Ollama after {max_retries} attempts")
                return "Thank you for your email. We'll get back to you shortly."

def generate_email_reply(sender_email, subject, message_body):
    """Generate a reply to an email using Ollama"""
    # Create a prompt that gives context to the AI model
    prompt = f"""
You are an official customer support email assistant. Your role is to:
1. Provide professional and helpful responses to customer queries
2. Collect necessary information to create support tickets
3. Follow standard templates for different types of queries
4. Maintain a friendly yet professional tone

For each email, follow these steps:
1. Analyze the customer's issue
2. Identify what type of issue it is (payment, account, technical, etc.)
3. Request any missing information needed to create a support ticket
4. Provide a clear resolution path or next steps

Required Information to Collect:
- Customer ID if applicable
- Transaction ID or Reference Number
- Contact number associated with the account
- Date and time of the issue
- Detailed description of the problem

Response Template:
1. Greeting: "Dear Customer,"
2. Acknowledge: "Thank you for reaching out to customer support."
3. Issue Summary: "We understand you're facing [briefly describe issue]."
4. Information Request: "To assist you better, we need the following details:"
5. Next Steps: "Once we receive this information, we will [explain next steps]."
6. Closing: "We appreciate your patience and look forward to resolving your issue."

Current Email Details:
From: {sender_email}
Subject: {subject}
Message:
{message_body}

Please generate an appropriate response following the above guidelines.
"""

    # Get response from Ollama
    reply = ask_ollama(prompt)
    
    # Ensure we have a fallback if Ollama fails
    if not reply or len(reply.strip()) < 10:
        logger.warning("Ollama response was too short or empty, using fallback")
        return f"""Dear Customer,

Thank you for reaching out to customer support. We're currently reviewing your query regarding '{subject}'. 

To assist you better, could you please provide us with:
1. Your registered contact number
2. Transaction ID (if applicable)
3. Date and time of the issue
4. Any error messages you received

We look forward to resolving your issue at the earliest.

Best regards,
Customer Support Team"""

    return reply

# Start the email monitoring
if __name__ == "__main__":
    logger.info("Email service starting up")
    display_emails()
    run_live()
