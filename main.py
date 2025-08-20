# Standard library imports
import time
import sqlite3
import smtplib
import os
from datetime import datetime
from email.mime.text import MIMEText

# Third-party imports
import requests
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()  

# Email configuration
FROM_EMAIL = os.getenv("FROM_EMAIL")          # Gmail address for sending alerts
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Gmail App Password if 2FA enabled
TO_EMAIL = os.getenv("TO_EMAIL")              # Recipient email address

# Monitoring configuration
CHECK_INTERVAL_MINUTES = 30  # How often to check for new jobs (in minutes)
DB = "seen.db"               # SQLite database file to track seen jobs

# GitHub repository JSON endpoints containing job listings
JSON_URLS = [
    "https://raw.githubusercontent.com/vanshb03/Summer2026-Internships/refs/heads/dev/.github/scripts/listings.json",
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships/refs/heads/dev/.github/scripts/listings.json"
]

# SQLite initialization, database for tracking previously seen job postings
conn = sqlite3.connect(DB)
cur = conn.cursor()

# Create table to store unique IDs of jobs that have already been processed
# This prevents sending duplicate notifications for the same job
cur.execute("CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY)")
conn.commit()


def get_unique_id(listing: dict) -> str:
    """
    Generate a unique identifier for a job listing to prevent duplicates.
    
    Args:
        listing (dict): Job listing data from JSON API
        
    Returns:
        str: Unique identifier string or None if invalid data
        
    The ID format is: "company::title::location"
    This ensures we can detect the same job even if other fields change.
    """

    # Extract necessary fields from the listing
    company = listing.get('company_name')
    title = listing.get('title')
    locations = listing.get('locations')

    # Validate that all required fields are present
    if not company or not title or not locations:
        return None

    # Handle location data, use the first location if it's a list
    location = locations[0] if isinstance(locations, list) and locations else "N/A"

    # Create unique identifier
    return f"{company}::{title}::{location}"


def fetch_listings() -> list:
    """
    Fetch job listings from all configured GitHub repository JSON endpoints.
    
    Returns:
        list: Combined list of all job listings from all repositories
        
    Raises:
        requests.exceptions.RequestException: If any HTTP request fails
    """

    results = []
    
    # Iterate through each configured JSON URL
    for url in JSON_URLS:
        try:
            # Make HTTP GET request to fetch JSON data
            resp = requests.get(url)
            resp.raise_for_status()  # Raise exception for bad status codes
            
            # Parse JSON and extend results list
            results.extend(resp.json())
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching from {url}: {e}")
            continue
    
    return results


def send_email(subject: str, body: str):
    """
    Send email notification using Gmail SMTP.
    
    Args:
        subject (str): Email subject line
        body (str): Email body content
        
    Raises:
        smtplib.SMTPException: If email sending fails
    """

    # Create email message object
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = FROM_EMAIL
    msg['To'] = TO_EMAIL

    # Send email using Gmail's SMTP server with SSL
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(FROM_EMAIL, EMAIL_PASSWORD)
        server.send_message(msg)


def add_to_notion(listing):
    """
    Add a job listing to Notion database for tracking and organization.
    
    Args:
        listing (dict): Job listing data to add to Notion
        
    The function creates a new page in the Notion database with structured
    properties for easy filtering and searching.
    """

    # Notion API endpoint for creating new pages
    url = "https://api.notion.com/v1/pages"

    # Set up authentication and headers for Notion API
    headers = {
        "Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    # Process location data (convert list to comma-separated string)
    locations = listing.get('locations')
    location_str = "; ".join(locations) if locations and isinstance(locations, list) else "N/A"

    # Convert Unix timestamp to ISO format for Notion date field
    date_posted_ts = listing.get('date_posted')
    date_posted_iso = datetime.fromtimestamp(date_posted_ts).isoformat() if date_posted_ts else None

    # Process term/season information - handle both repository formats
    # vanshb03 uses "season": "Fall", SimplifyJobs uses "terms": ["Summer 2024"]
    terms = listing.get('terms', [])
    season = listing.get('season')
    
    if terms and isinstance(terms, list):
        # SimplifyJobs format: ["Summer 2024"]
        term_str = ", ".join(terms)
    elif season:
        # vanshb03 format: "Fall"
        term_str = season
    else:
        term_str = "N/A"

    # Structure the data according to Notion's page creation format
    data = {
        "parent": {"database_id": os.getenv('NOTION_DB_ID')},
        "properties": {
            "Company": {"title": [{"text": {"content": listing.get('company_name', 'N/A')}}]},
            "Title": {"rich_text": [{"text": {"content": listing.get('title', 'N/A')}}]},
            "Term": {"rich_text": [{"text": {"content": term_str}}]},
            "Location(s)": {"rich_text": [{"text": {"content": location_str}}]},
            "Date Posted": {"date": {"start": date_posted_iso}},
            "Sponsorship": {"rich_text": [{"text": {"content": listing.get('sponsorship', 'N/A')}}]}
        }
    }

    # Make API request to create the new page
    response = requests.post(url, headers=headers, json=data)

    # Log the result
    if response.status_code == 200 or response.status_code == 201:
        print(f"Added {listing.get('title')} at {listing.get('company_name')} to Notion.")
    else:
        print(f"Failed to add to Notion: {response.status_code}, {response.text}")



def check_for_new_jobs():
    """
    Checks for new job listings and processes them.
    
    This function:
    1. Fetches all current job listings from configured sources
    2. Checks each listing against the database of previously seen jobs
    3. For new jobs, sends email notification and adds to Notion
    4. Updates the database to mark the job as seen
    """

    # Fetch all current job listings
    listings = fetch_listings()
    print(f"Fetched {len(listings)} listings")  # debug

    # Process each job listing
    for l in listings:
        # Generate unique identifier for this job
        uid = get_unique_id(l)

        # Skip listings with invalid/incomplete data
        if not uid:
            print("Skipping invalid listing:", l)
            continue

        # Check if the job has already been seen
        cur.execute("SELECT 1 FROM seen WHERE id=?", (uid,))
        if not cur.fetchone():
            print(f"New listing found: {uid}")  # debug

            # Combine all locations into a comma-separated string
            locations = l.get('locations')
            location_str = "; ".join(locations) if locations and isinstance(locations, list) else "N/A"

            # Convert timestamp to readable date
            date_posted_ts = l.get('date_posted')
            if date_posted_ts:
                date_posted = datetime.fromtimestamp(date_posted_ts).strftime("%b %d, %Y")
            else:
                date_posted = "N/A"

            # Extract sponsorship information
            sponsorship = l.get('sponsorship', 'N/A')

            # Extract term/season information - handle both repository formats
            # vanshb03 uses "season": "Fall", SimplifyJobs uses "terms": ["Summer 2024"]
            terms = l.get('terms', [])
            season = l.get('season')
            
            if terms and isinstance(terms, list):
                # SimplifyJobs format: ["Summer 2024"]
                term_str = ", ".join(terms)
            elif season:
                # vanshb03 format: "Fall"
                term_str = season
            else:
                term_str = "N/A"

            # Create email subject line
            subject = f"🎉 New Internship Alert: {l.get('company_name', 'N/A')} - {l.get('title', 'N/A')}"

            # Create detailed email body with all job information
            body = (
                f"Reeled in a new internship for you! 🎣\n\n"
                f"🏢 Company: {l.get('company_name', 'N/A')}\n"
                f"💼 Title: {l.get('title', 'N/A')}\n"
                f"📅 Term: {term_str}\n"
                f"📍 Location(s): {location_str}\n"
                f"🗓 Date Posted: {date_posted}\n"
                f"🎫 Sponsorship: {sponsorship}\n"
                f"🔗 Apply here: {l.get('url', 'N/A')}\n\n"
                f"Remember to swim fast, the best opportunities don't wait!\n"
                f"Opportuna 🐟"
            )

            try:
                # Send email notification
                send_email(subject, body)
                print(f"Email sent for: {l.get('company_name')} - {l.get('title')}")
                
                # Add to Notion database
                add_to_notion(l)
                
                # Mark as seen in local database to prevent future duplicates
                cur.execute("INSERT INTO seen(id) VALUES (?)", (uid,))
                conn.commit()
                
            except Exception as e:
                print(f"Error processing job {uid}: {e}")

        else:
            # Job already seen, skip processing
            print(f"Already seen: {uid}")


if __name__ == "__main__":
    """
    Main execution block - runs the monitoring loop.
    
    The bot runs continuously, checking for new jobs at regular intervals.
    Uses try-catch to handle errors gracefully and continue monitoring.
    """

    print("🐟 Opportuna Started!")
    print(f"⏰ Checking every {CHECK_INTERVAL_MINUTES} minutes")
    print(f"📂 Database: {DB}")
    print(f"📧 Notifications sent to: {TO_EMAIL}")
    print("=" * 50)

    # Main monitoring loop
    while True:
        try:
            # Check for new jobs
            check_for_new_jobs()
            
        except KeyboardInterrupt:
            # Graceful shutdown on Ctrl+C
            print("\nShutting down Opportuna...")
            break
            
        except Exception as e:
            # Log errors but continue monitoring
            print(f"Error while checking jobs: {e}")
            
        # Wait before next check
        print(f"Sleeping for {CHECK_INTERVAL_MINUTES} minutes...\n")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)
    
    # Close database connection on exit
    conn.close()
    print("Opportuna stopped. Database connection closed.")


 # todo make notion add to bottom not top of list