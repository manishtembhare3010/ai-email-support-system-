# AI-Powered Customer Support Email System

A sophisticated email automation solution that monitors incoming customer emails, generates contextual AI responses using a local LLM, stores communications in a database, and provides API access to the data.

## 🚀 Features

- **Intelligent Email Monitoring**: Continuously checks for new emails from specific senders
- **AI-Powered Auto-Replies**: Generates contextual responses based on email content using local LLM (Ollama)
- **Smart Email Threading**: Maintains conversation history with proper threading
- **MySQL Database Integration**: Stores all emails with robust conversation tracking
- **FastAPI REST Endpoints**: Provides clean API access to email data
- **Real-time Logging**: Comprehensive logging system with API access

## 🛠️ Tech Stack

- **Backend**: Python 3.8+
- **AI Integration**: Ollama API (local LLM)
- **Database**: MySQL
- **API Framework**: FastAPI
- **Email Protocol Handling**: imaplib/smtplib
- **Serialization**: Pydantic

## 📋 Prerequisites

- Python 3.8+
- MySQL database
- Local Ollama installation
- SMTP/IMAP email account

## 🔧 Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/ai-email-support-system.git
   cd ai-email-support-system
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file with the following variables:
   ```
   DB_HOST=localhost
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
   DB_NAME=your_db_name
   
   EMAIL=your_support@example.com
   PASSWORD=your_email_password
   SMTP_SERVER=smtp.example.com
   IMAP_SERVER=imap.example.com
   SMTP_PORT=587
   IMAP_PORT=993
   ```

5. Create a `.gitignore` file to exclude sensitive data:
   ```
   # Environment variables and secrets
   .env
   
   # Logs
   *.log
   email_service.log
   
   # Python
   __pycache__/
   *.py[cod]
   *$py.class
   venv/
   ```

## 🚀 Running the Application

1. Start the API server:
   ```
   uvicorn api:app --reload
   ```
   The API will be available at http://localhost:8000

2. Start the email processing service:
   ```
   python main.py
   ```

## 🔌 API Endpoints

- `GET /emails/` - Retrieve all emails in the database
- `GET /logs/` - Get the latest application logs

## 🗄️ Database Schema

### Emails Table
- `id`: Auto-increment primary key
- `sender_id`: Numeric ID for the sender
- `sender_email`: Email address of the sender
- `session_id`: ID for grouping related emails in a thread
- `message_id`: Unique ID for the email
- `in_reply_to`: Message ID this email is replying to
- `subject`: Email subject
- `message`: Email body content
- `role`: Either 'user' or 'host'
- `received_at`: Timestamp when the email was received

## ⚙️ How It Works

1. The system continuously monitors specified email accounts for new messages
2. When an email is received:
   - It's saved to the database with threading metadata
   - The content is processed through the local LLM (Ollama)
   - An intelligent, contextually appropriate response is generated
   - The response is sent to the user and stored in the database
3. All communications are accessible via the API, complete with threading information

## 📝 Customization

You can customize the AI response by modifying the prompt in `main.py`. The system can be adapted to various customer support scenarios by adjusting:

1. The monitored email address
2. The AI response template
3. The information collection requirements

## �� Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/yourusername/ai-email-support-system/issues).

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
