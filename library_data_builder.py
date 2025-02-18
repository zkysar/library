import csv
import os
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


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def get_events_from_library(url):
    """Scrape events from a library website using AgentQL"""
    calendar_url = find_calendar_website(url)
    events = get_events_list(calendar_url)
    return events

def process_libraries():
    """Process all libraries from CSV and scrape their events"""
    # Delete existing output file if it exists
    if os.path.exists(OUTPUT_CSV):
        os.remove(OUTPUT_CSV)
        print(f"Deleted existing {OUTPUT_CSV}")

    # Read library URLs from input CSV
    libraries = []
    try:
        with open(INPUT_CSV, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                if row[19]:  # Website URL is in column 20 (index 19)
                    library_info = {
                        'url': row[19],
                        'name': row[0],  # Library name
                        'address': f"{row[13]}, {row[14]}, CA {row[15]}",  # Address, City, ZIP
                    }
                    libraries.append(library_info)
    except Exception as e:
        log.error(f"Error reading input CSV: {str(e)}")
        return

    # Process each library and write events to CSV
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=[
            'library_url', 'library_name', 'library_address',
            'event_title', 'event_date', 'event_description', 'event_link'
        ])
        writer.writeheader()

        for library_info in libraries:
            print(f"\nProcessing library: {library_info['name']} ({library_info['url']})")
            print(f"Address: {library_info['address']}")
            events = get_events_from_library(library_info['url'])
            for event in events:
                event['library_url'] = library_info['url']
                event['library_name'] = library_info['name']
                event['library_address'] = library_info['address']
                writer.writerow(event)
            print(f"Found {len(events)} events")
            

def find_calendar_website(url : str):
    with sync_playwright() as p, p.chromium.launch(headless=True) as browser:
        # Create a new page in the browser and wrap it to get access to the AgentQL's querying API
        page = agentql.wrap(browser.new_page())

        # Navigate to the desired URL
        page.goto(url)
        query = """
        {
            calendar_url
        }
        """

        response = page.query_data(query)
        print(response)
        return response["calendar_url"]
        
def get_events_list(url : str):
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
        print(response)
        return response["events"]

if __name__ == "__main__":
    process_libraries()
