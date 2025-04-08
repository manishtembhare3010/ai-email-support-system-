from fastapi import FastAPI
from typing import List, Optional
from pydantic import BaseModel
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
from fastapi import HTTPException

# Load environment variables
load_dotenv()

# Import DB_CONFIG after loading environment variables
from database import DB_CONFIG

app = FastAPI()

class Email(BaseModel):
    sender_email: str
    sender_id: int
    session_id: str
    message_id: str
    in_reply_to: Optional[str] = None
    subject: str
    message: str
    role: str
    received_at: str

@app.get("/emails/", response_model=List[Email])
def get_emails():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        c = conn.cursor()
        
        # Add logging to help debug
        logger = logging.getLogger(__name__)
        logger.info("Attempting to fetch emails from database")
        
        c.execute('''SELECT sender_email, sender_id, session_id, message_id, in_reply_to, subject, message, role, received_at 
                     FROM emails
                     ORDER BY received_at DESC''')
        db_emails = c.fetchall()
        
        logger.info(f"Retrieved {len(db_emails)} emails from database")
        
        emails = []
        for email in db_emails:
            # Format the datetime for display
            received_time = email[8]
            if isinstance(received_time, datetime):
                formatted_time = received_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                formatted_time = str(received_time)
                
            emails.append(Email(
                sender_email=email[0],
                sender_id=email[1],
                session_id=email[2],
                message_id=email[3],
                in_reply_to=email[4],
                subject=email[5],
                message=email[6],
                role=email[7],
                received_at=formatted_time
            ))
        
        conn.close()
        logger.info(f"Successfully processed {len(emails)} emails")
        return emails
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching emails: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching emails: {str(e)}")

@app.get("/logs/")
def get_logs():
    """Endpoint to retrieve the most recent log entries"""
    try:
        log_file = "email_service.log"
        if not os.path.exists(log_file):
            return {"error": "Log file not found"}
            
        # Read the last 100 lines of the log file
        with open(log_file, 'r') as f:
            # Read all lines and get the last 100
            lines = f.readlines()
            last_lines = lines[-100:] if len(lines) > 100 else lines
            
        return {"logs": last_lines}
    except Exception as e:
        return {"error": f"Error retrieving logs: {str(e)}"}

# Run the server with: uvicorn api:app --reload 


