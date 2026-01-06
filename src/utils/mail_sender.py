import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Optional

# Import necessary SQLAlchemy parts and the model
from sqlalchemy.orm import Session
# Adjust the import path based on your project structure
# Assuming models.py is in src/api/
from src.api.models import EmailConfiguration 

# Load environment variables ONLY from the main API .env for credentials
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / "src" / "api" / ".env") # Load from src/api/.env

logger = logging.getLogger(__name__)

class MailSender:
    """
    Utility class for sending emails. 
    Loads credentials AND server config from .env, gets status/recipients from DB.
    """
    
    def __init__(self):
        """Initialize email configuration from environment variables."""
        # Load SMTP configuration from .env
        self.smtp_server = os.getenv("EMAIL_SERVER")
        self.smtp_port = int(os.getenv("EMAIL_PORT", 587)) # Default to 587 if not set
        self.smtp_username = os.getenv("EMAIL_USERNAME")
        self.smtp_password = os.getenv("EMAIL_PASSWORD")
        self.sender_email = os.getenv("EMAIL_SENDER")
        
        # Basic validation for SMTP configuration
        if not all([self.smtp_server, self.smtp_port, self.smtp_username, self.smtp_password, self.sender_email]):
            logger.debug(
                "Email SMTP configuration incomplete in src/api/.env file. Check EMAIL_SERVER, "
                "EMAIL_PORT, EMAIL_USERNAME, EMAIL_PASSWORD, and EMAIL_SENDER."
            )
            self.valid_config = False
        else:
            self.valid_config = True
            
    def _get_latest_config(self, db: Session) -> Optional[EmailConfiguration]:
        """Helper function to get the latest email config from DB"""
        try:
            return db.query(EmailConfiguration).order_by(EmailConfiguration.created_at.desc()).first()
        except Exception as e:
            logger.error(f"Failed to fetch email configuration from DB: {e}", exc_info=True)
            return None

    def send_email(self, db: Session, subject: str, body: str, recipients: Optional[List[str]] = None, attachments: Optional[List[str]] = None, html: bool = False) -> bool:
        """
        Send an email. Uses recipients from DB if not provided explicitly.
        
        Args:
            db (Session): SQLAlchemy database session.
            subject (str): Email subject
            body (str): Email body content
            recipients (Optional[List[str]], optional): Explicit list of recipients. 
                                                    If None or empty, uses recipients from DB config.
            attachments (Optional[List[str]], optional): List of file paths to attach.
            html (bool, optional): Whether the body is HTML content.
            
        Returns:
            bool: True if sent successfully, False otherwise.
        """
        # Use config loaded from .env file first
        if not self.valid_config:
            logger.error("Cannot send email: SMTP configuration in src/api/.env is incomplete or invalid.")
            return False
            
        # Fetch latest config from DB (needed ONLY for enabled status and maybe recipients)
        latest_db_config = self._get_latest_config(db)
        
        if not latest_db_config:
            logger.error("Cannot send email: Failed to retrieve email configuration from database.")
            return False
            
        # Check if email sending is enabled in DB
        if not latest_db_config.enabled:
            logger.info("Email notifications are disabled in the current DB configuration. Skipping send.")
            return False
            
        # Determine recipients list
        final_recipients = []
        if recipients: # Use explicitly provided list if available
            final_recipients = recipients
        elif latest_db_config.recipients: # Otherwise, use list from DB config
            final_recipients = latest_db_config.recipients
        
        if not final_recipients:
            logger.warning("Cannot send email: No recipients specified explicitly or found in DB configuration.")
            return False
            
        # Log the configuration being used for debugging
        username_masked = self.smtp_username[:3] + '***' if self.smtp_username else 'None'
        logger.info(f"Attempting to send email via SMTP:")
        logger.info(f"  Server: {self.smtp_server}") # Use self.smtp_server from .env
        logger.info(f"  Port: {self.smtp_port}")
        logger.info(f"  Username: {username_masked}")
        logger.info(f"  Sender: {self.sender_email}")
        logger.info(f"  Recipients: {', '.join(final_recipients)}")

        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = ", ".join(final_recipients) # Use final_recipients list
            msg['Subject'] = subject
            
            # Attach body
            if html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
                
            # Attach files if provided
            if attachments:
                for file_path in attachments:
                    try:
                        with open(file_path, 'rb') as file:
                            part = MIMEApplication(file.read(), Name=Path(file_path).name)
                            part['Content-Disposition'] = f'attachment; filename="{Path(file_path).name}"'
                            msg.attach(part)
                    except Exception as e:
                        logger.error(f"Failed to attach file {file_path}: {str(e)}")
            
            # Send email using configured SMTP settings from .env
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server: # Use self.smtp_server
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
                
            logger.info(f"Email sent successfully to {', '.join(final_recipients)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
    
    def send_report_email(self, db: Session, subject: str, report_content: str, recipients: Optional[List[str]] = None, report_file: Optional[str] = None) -> bool:
        """
        Send a sentiment analysis report via email. Uses recipients from DB if not provided explicitly.
        
        Args:
            db (Session): SQLAlchemy database session.
            subject (str): Email subject
            report_content (str): HTML content for the report
            recipients (Optional[List[str]], optional): Explicit list of recipients. 
                                                    If None or empty, uses recipients from DB config.
            report_file (str, optional): Path to a report file to attach.
            
        Returns:
            bool: True if sent successfully, False otherwise.
        """
        # Create basic HTML template
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #2c3e50; }}
                .content {{ margin: 20px 0; }}
                .footer {{ color: #7f8c8d; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <h1>Sentiment Analysis Report</h1>
            <div class="content">
                {report_content}
            </div>
            <div class="footer">
                <p>This is an automated message from your Sentiment Analysis System.</p>
            </div>
        </body>
        </html>
        """
        
        attachments = [report_file] if report_file else None
        # Pass the db session and potentially None for recipients to send_email
        return self.send_email(db=db, subject=subject, body=html_body, recipients=recipients, attachments=attachments, html=True)

# Remove the convenience function send_notification as it doesn't fit the new pattern
# (needs a db session)
# def send_notification(recipients, subject, message):
#     ... 
