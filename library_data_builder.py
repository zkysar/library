import csv
import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright
import agentql
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure AgentQL
AGENTQL_API_KEY = os.getenv('AGENTQL_API_KEY')
if not AGENTQL_API_KEY:
    raise ValueError("AGENTQL_API_KEY not found in .env file")
agentql.configure(api_key=AGENTQL_API_KEY)

# File paths
INPUT_CSV = 'FY22-23-California-Public-Libraries-Data-updated-2024-06.csv'
OUTPUT_CSV = 'library_events.csv'
PROGRESS_FILE = 'scraping_progress.txt'


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def get_events_from_library(url):
    """Scrape events from a library website using AgentQL"""
    try:
        calendar_url = find_calendar_website(url)
        if not calendar_url:
            log.warning(f"No calendar URL found for library: {url}")
            return []
        events = get_events_list(calendar_url)
        return events
    except Exception as e:
        log.error(f"Error getting events from library {url}: {str(e)}")
        return []

def get_last_processed_library():
    """Get the name of the last processed library from progress file"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_progress(library_name):
    """Save the name of the last processed library"""
    with open(PROGRESS_FILE, 'w') as f:
        f.write(library_name)

def process_libraries():
    """Process all libraries from CSV and scrape their events"""
    log.info("Starting library processing...")
    last_processed = get_last_processed_library()
    should_process = True  # Always start processing
    if last_processed:
        log.info(f"Will resume from library: {last_processed}")
    else:
        log.info("Starting from the beginning")

    # Create output file with headers if it doesn't exist
    if not os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['timestamp', 'library_name', 'library_url', 'library_address', 'event_data'])

    # Read library URLs from input CSV
    libraries = []
    try:
        log.info(f"Reading library data from {INPUT_CSV}")
        with open(INPUT_CSV, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            header = next(reader)  # Skip header row
            log.info(f"CSV Headers: {header}")
            row_count = 0
            for row in reader:
                row_count += 1
                # Column indices from CSV:
                # Name: 0
                # Address: 13
                # City: 14
                # ZIP: 15
                # Website: 19
                if len(row) > 19 and row[19].strip() and row[19].startswith('http'):
                    library_info = {
                        'url': row[19].strip(),
                        'name': row[0].strip(),
                        'address': f"{row[13].strip()}, {row[14].strip()}, CA {row[15].strip()}"
                    }
                    libraries.append(library_info)
            log.info(f"Found {len(libraries)} libraries with websites out of {row_count} total rows")
    except Exception as e:
        log.error(f"Error reading input CSV: {str(e)}")
        return

    # Process each library and write events to CSV
    with open(OUTPUT_CSV, 'a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        
        log.info(f"Processing {len(libraries)} libraries")
        processed_count = 0

        for library in libraries:
            processed_count += 1
            log.info(f"Progress: {processed_count}/{len(libraries)} libraries")
            
            # Skip libraries until we reach the last processed one
            if last_processed and library['name'] <= last_processed:
                log.info(f"Skipping {library['name']} - already processed")
                continue

            try:
                log.info(f"Processing library: {library['name']} ({library['url']})")
                log.info(f"Address: {library['address']}")
                events = get_events_from_library(library['url'])
                
                # Clean and format event data
                cleaned_events = []
                for event in events:
                    cleaned_event = {
                        'event_title': event.get('event_title', ''),
                        'event_description': event.get('event_description', ''),
                        'event_date': event.get('event_date', ''),
                        'event_link': event.get('event_link', '')
                    }
                    cleaned_events.append(cleaned_event)
                
                # Convert to JSON string with double quotes
                event_data = json.dumps(cleaned_events, ensure_ascii=False)
                
                timestamp = datetime.now().isoformat()
                writer.writerow([timestamp, library['name'], library['url'], library['address'], event_data])
                save_progress(library['name'])
                log.info(f"Successfully processed {library['name']} - Found {len(events)} events")
            except Exception as e:
                log.error(f"Error processing {library['name']}: {str(e)}")
                continue
            

def find_calendar_website(url : str):
    try:
        log.info(f"Finding calendar URL for library website: {url}")
        with sync_playwright() as p, p.chromium.launch(headless=True) as browser:
            # Create a new page in the browser and wrap it to get access to the AgentQL's querying API
            page = agentql.wrap(browser.new_page())

            # Navigate to the desired URL
            log.info(f"Navigating to {url}")
            page.goto(url)
            query = """
            {
                calendar_url
            }
            """

            log.info("Executing AgentQL query for calendar URL")
            response = page.query_data(query)
            log.info(f"AgentQL response: {response}")
            
            if not response or 'calendar_url' not in response:
                log.warning(f"No calendar URL found in response for {url}")
                return None
            return response["calendar_url"]
    except Exception as e:
        log.error(f"Error finding calendar URL for {url}: {str(e)}")
        return None
        
def get_events_list(url : str):
    if not url:
        log.warning("No URL provided to get_events_list")
        return []
    
    try:
        with sync_playwright() as p, p.chromium.launch(headless=True) as browser:
            page = agentql.wrap(browser.new_page())
            page.goto(url)
            
            query = """
            {
                events[] {
                    event_title
                    event_description
                    event_date
                    event_link
                }
            }
            """

            response = page.query_data(query)
            if not response or 'events' not in response:
                log.warning(f"No events found in response for {url}")
                return []
            return response["events"]
    except Exception as e:
        log.error(f"Error getting events from {url}: {str(e)}")
        return []

if __name__ == "__main__":
    process_libraries()

