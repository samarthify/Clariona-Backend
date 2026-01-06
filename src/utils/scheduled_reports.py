#!/usr/bin/env python3
"""
Scheduled email reporting module for the Sentiment Analysis System.
"""

import os
import time
import logging
import schedule
import threading
from datetime import datetime, timedelta
from pathlib import Path
import sys
from typing import Optional, List

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.mail_sender import MailSender
# Add DB imports
from sqlalchemy.orm import sessionmaker, Session

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class ReportScheduler:
    """
    Handles scheduling and sending of periodic sentiment analysis reports.
    Requires a database session factory for MailSender.
    """
    
    def __init__(self, db_factory: sessionmaker, recipients: Optional[List[str]] = None):
        """
        Initialize the report scheduler.
        
        Args:
            db_factory (sessionmaker): SQLAlchemy session factory.
            recipients (Optional[List[str]], optional): List of email recipients for reports.
                                                    If None, will try env var or default to empty.
        """
        self.db_factory = db_factory
        self.mail_sender = MailSender() # MailSender itself only holds credentials now
        self.recipients = recipients if recipients is not None else []
        self.stop_event = threading.Event()
        self.scheduler_thread = None
        
        # Load recipients from environment only if not provided explicitly
        if not self.recipients:
            env_recipients = os.getenv("REPORT_RECIPIENTS")
            if env_recipients:
                self.recipients = [r.strip() for r in env_recipients.split(",")]
                logger.info(f"Loaded recipients from env var REPORT_RECIPIENTS: {self.recipients}")
            else:
                logger.debug("No explicit recipients provided and REPORT_RECIPIENTS env var not set.")
    
    def add_recipient(self, email):
        """Add an email recipient to the list."""
        if email not in self.recipients:
            self.recipients.append(email)
            logger.info(f"Added recipient: {email}")
    
    def remove_recipient(self, email):
        """Remove an email recipient from the list."""
        if email in self.recipients:
            self.recipients.remove(email)
            logger.info(f"Removed recipient: {email}")
    
    def _send_report_with_db(self, subject_template: str, report_content: str):
        """Internal helper to send report using a DB session."""
        if not self.recipients:
            logger.warning(f"No recipients configured for report: {subject_template}")
            return
            
        try:
            with self.db_factory() as db:
                success = self.mail_sender.send_report_email(
                    db=db,
                    recipients=self.recipients, # Use recipients held by scheduler instance
                    subject=subject_template, 
                    report_content=report_content
                )
                if success:
                    logger.info(f"Report '{subject_template}' sent successfully to {len(self.recipients)} recipients")
                else:
                    logger.error(f"Failed to send report: {subject_template}")
        except Exception as e:
            logger.error(f"Error sending report '{subject_template}': {e}", exc_info=True)

    def send_daily_report(self):
        """Generate and send a daily sentiment analysis report."""
        logger.info("Generating daily sentiment report...")
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime("%B %d, %Y")
        subject = f"Daily Sentiment Report - {date_str}"
        # ... (generate actual report_content based on analysis) ...
        report_content = f"<h2>Daily Report {date_str}</h2><p>Content placeholder...</p>"
        self._send_report_with_db(subject, report_content)
    
    def send_weekly_report(self):
        """Generate and send a weekly sentiment analysis report."""
        logger.info("Generating weekly sentiment report...")
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        date_range = f"{week_ago.strftime('%B %d')} - {today.strftime('%B %d, %Y')}"
        subject = f"Weekly Sentiment Report - {date_range}"
        # ... (generate actual report_content based on analysis) ...
        report_content = f"<h2>Weekly Report {date_range}</h2><p>Content placeholder...</p>"
        self._send_report_with_db(subject, report_content)
    
    def send_monthly_report(self):
        """Generate and send a monthly sentiment analysis report."""
        logger.info("Generating monthly sentiment report...")
        today = datetime.now()
        month_name = today.strftime("%B %Y")
        subject = f"Monthly Sentiment Report - {month_name}"
        # ... (generate actual report_content based on analysis) ...
        report_content = f"<h2>Monthly Report {month_name}</h2><p>Content placeholder...</p>"
        self._send_report_with_db(subject, report_content)
    
    def schedule_reports(self, daily_time="08:00", weekly_day="Monday", monthly_day=1):
        """
        Schedule regular reports.
        
        Args:
            daily_time (str): Time for daily reports (24-hour format, HH:MM)
            weekly_day (str): Day of week for weekly reports
            monthly_day (int): Day of month for monthly reports (1-28)
        """
        # Schedule daily reports
        schedule.every().day.at(daily_time).do(self.send_daily_report)
        logger.info(f"Scheduled daily reports at {daily_time}")
        
        # Schedule weekly reports
        getattr(schedule.every(), weekly_day.lower()).at(daily_time).do(self.send_weekly_report)
        logger.info(f"Scheduled weekly reports on {weekly_day}s at {daily_time}")
        
        # Schedule monthly reports
        if 1 <= monthly_day <= 28:
            schedule.every().month.at(f"{monthly_day:02d} {daily_time}").do(self.send_monthly_report)
            logger.info(f"Scheduled monthly reports on day {monthly_day} at {daily_time}")
        else:
            logger.error(f"Invalid monthly day: {monthly_day}. Must be between 1 and 28.")
    
    def start(self):
        """Start the scheduler in a background thread."""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            logger.warning("Scheduler is already running")
            return
        
        self.stop_event.clear()
        self.scheduler_thread = threading.Thread(target=self._run_scheduler)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        logger.info("Report scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.stop_event.set()
            self.scheduler_thread.join(timeout=5)
            logger.info("Report scheduler stopped")
        else:
            logger.warning("Scheduler is not running")
    
    def _run_scheduler(self):
        """Run the scheduler loop."""
        while not self.stop_event.is_set():
            schedule.run_pending()
            time.sleep(1)


def main():
    """Example usage of the report scheduler."""
    # Get email recipients
    recipients = input("Enter email recipients (comma-separated): ").split(",")
    recipients = [r.strip() for r in recipients if r.strip()]
    
    if not recipients:
        logger.error("No recipients specified. Exiting.")
        return
    
    # Create scheduler
    scheduler = ReportScheduler(recipients)
    
    # Schedule reports
    scheduler.schedule_reports()
    
    try:
        # Start scheduler
        scheduler.start()
        logger.info("Press Ctrl+C to stop...")
        
        # Run indefinitely until interrupted
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Stopping scheduler...")
        scheduler.stop()
        logger.info("Done!")


if __name__ == "__main__":
    main() 
