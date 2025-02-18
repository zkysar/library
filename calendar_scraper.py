import logging

import agentql
from agentql.ext.playwright.sync_api import Page
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os


def main():
    # Load environment variables
    load_dotenv()

    # Get AgentQL API key
    AGENTQL_API_KEY = os.getenv('AGENTQL_API_KEY')
    if not AGENTQL_API_KEY:
        raise ValueError("AGENTQL_API_KEY not found in .env file")

    # Set up logging
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(__name__)

    calendar_url = find_calendar_website("https://www.akspl.org/")
    if not calendar_url:
        logging.error("No calendar found")
        return

    events_list = get_events_list(calendar_url)
    if not events_list:
        logging.error("No events found")
        return
    print(events_list)


def find_calendar_website(url: str):
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


def get_events_list(url: str):
    with sync_playwright() as p, p.chromium.launch(headless=True) as browser:
        page = agentql.wrap(browser.new_page())
        page.goto(url)

        query = """
        {
            events[] {
                title
                description
                start
                end
            }
        }
            """

        response = page.query_data(query)
        print(response)
        return response["events"]


if __name__ == "__main__":
    main()
