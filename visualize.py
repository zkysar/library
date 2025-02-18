from flask import Flask, render_template, jsonify
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import pandas as pd
from datetime import datetime
import json
import os
import logging
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize geocoder
geolocator = Nominatim(user_agent="library_events")

def get_coordinates(address):
    """Get coordinates for an address using geocoding"""
    if not address:
        log.warning(f"Empty address provided")
        return None
        
    try:
        # Add 'USA' to the address if not present
        if 'USA' not in address and 'US' not in address:
            search_address = f"{address}, USA"
        else:
            search_address = address
            
        # Try with full address first
        location = geolocator.geocode(search_address, timeout=10)
        
        # If that fails, try with just city and state
        if not location and ', CA' in search_address:
            city_state = re.search(r'([^,]+),\s*CA', search_address)
            if city_state:
                city = city_state.group(1).strip()
                location = geolocator.geocode(f"{city}, CA, USA", timeout=10)
        
        if location:
            log.info(f"Found coordinates for {address}: {location.latitude}, {location.longitude}")
            return [location.latitude, location.longitude]
        else:
            log.warning(f"No coordinates found for address: {address}")
            
    except GeocoderTimedOut:
        log.error(f"Geocoding timeout for address: {address}")
    except Exception as e:
        log.error(f"Error geocoding address {address}: {str(e)}")
    return None

def clean_date_string(date_str):
    """Clean and normalize date string"""
    if not date_str:
        return date_str
        
    # Convert to string if not already
    date_str = str(date_str)
    
    # Remove ordinal indicators
    ordinal_patterns = [
        (r'(\d+)st', r'\1'),  # 1st -> 1
        (r'(\d+)nd', r'\1'),  # 2nd -> 2
        (r'(\d+)rd', r'\1'),  # 3rd -> 3
        (r'(\d+)th', r'\1'),  # 4th -> 4
    ]
    
    result = date_str
    for pattern, replacement in ordinal_patterns:
        result = re.sub(pattern, replacement, result)
    
    # Extract date part from strings with times
    time_pattern = r'^([^,]+, [^,]+)(?:,\s*\d+:\d+(?:am|pm).+)?$'
    time_match = re.match(time_pattern, result, re.IGNORECASE)
    if time_match:
        result = time_match.group(1)
    
    # Remove day of week if present
    weekday_pattern = r'^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*(.+)$'
    weekday_match = re.match(weekday_pattern, result, re.IGNORECASE)
    if weekday_match:
        result = weekday_match.group(1)
    
    return result.strip()

def parse_date(date_str):
    """Parse date string in various formats"""
    if not pd.notna(date_str):
        return None
    
    try:
        # Clean and normalize the date string
        cleaned_date = clean_date_string(str(date_str))
        log.info(f"Cleaned date: {cleaned_date} (original: {date_str})")
        
        # Add the current year if not present
        if re.match(r'^[A-Za-z]+ \d+$', cleaned_date):
            cleaned_date = f"{cleaned_date}, 2025"
        
        date_formats = [
            '%B %d, %Y',          # February 17, 2025
            '%b %d, %Y',          # Feb 17, 2025
            '%Y-%m-%d',           # 2025-02-17
            '%m/%d/%Y',           # 02/17/2025
            '%d/%m/%Y',           # 17/02/2025
            '%Y/%m/%d',           # 2025/02/17
            '%d-%m-%Y',           # 17-02-2025
            '%m-%d-%Y',           # 02-17-2025
            '%B %d',              # February 17
            '%b %d'               # Feb 17
        ]
    
        for date_format in date_formats:
            try:
                parsed_date = datetime.strptime(cleaned_date, date_format)
                # Ensure year is set for formats without year
                if parsed_date.year == 1900:
                    parsed_date = parsed_date.replace(year=2025)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        log.warning(f"Could not parse date: {date_str} (cleaned: {cleaned_date})")
        return None
        
    except Exception as e:
        log.error(f"Error parsing date '{date_str}': {str(e)}")
        return None

def load_events():
    """Load and process events from CSV"""
    if not os.path.exists('library_events.csv'):
        log.warning("library_events.csv not found")
        return [], []

    # Read CSV and handle missing values
    df = pd.read_csv('library_events.csv')
    
    # Replace NaN values with empty strings for text fields
    text_columns = ['event_title', 'event_description', 'event_link', 'library_name', 'library_address']
    df[text_columns] = df[text_columns].fillna('')
    
    # Group recurring events
    df['recurring'] = df.duplicated(subset=['event_title', 'library_url'], keep=False)
    
    # Sort by date if available
    if 'event_date' in df.columns:
        df = df.sort_values('event_date', na_position='last')
    
    # Process events for calendar
    calendar_events = []
    for _, row in df.iterrows():
        try:
            # Skip events without titles
            if not row['event_title'].strip():
                continue
                
            # Parse date if available
            date = parse_date(row['event_date']) if pd.notna(row['event_date']) else None
            
            # Create event description
            description_parts = []
            if row['event_description'].strip():
                description_parts.append(row['event_description'])
            if row['library_name'].strip():
                description_parts.append(f"Library: {row['library_name']}")
            if row['library_address'].strip():
                description_parts.append(f"Address: {row['library_address']}")
            if row['recurring']:
                description_parts.append("\n(This is a recurring event)")
                
            event = {
                'title': row['event_title'],
                'description': '\n\n'.join(description_parts),
                'url': row['event_link'] if row['event_link'].strip() else None,
                'backgroundColor': '#3788d8' if not row['recurring'] else '#28a745',
                'borderColor': '#2c6aa0' if not row['recurring'] else '#1e7e34'
            }
            
            # Add date if available
            if date:
                event['start'] = date
                calendar_events.append(event)
            # For events without dates, add to a special 'Ongoing Events' section
            else:
                event['start'] = '2025-02-17'  # Today's date
                event['backgroundColor'] = '#6c757d'  # Gray for undated events
                event['borderColor'] = '#5a6268'
                event['classNames'] = ['ongoing-event']
                calendar_events.append(event)
                
        except Exception as e:
            log.error(f"Error processing calendar event: {e}")
            continue

    # Process events for map
    map_events = []
    library_groups = df.groupby(['library_url', 'library_name', 'library_address'])
    
    for (url, name, address), group in library_groups:
        try:
            # Get coordinates using full address
            coords = get_coordinates(address)
            if coords:
                # Get upcoming events for this library
                upcoming_events = []
                for _, event in group.iterrows():
                    if pd.notna(event['event_date']):
                        upcoming_events.append({
                            'title': event['event_title'],
                            'date': event['event_date'],
                            'description': event['event_description']
                        })
                
                map_events.append({
                    'name': name,
                    'address': address,
                    'coordinates': coords,
                    'event_count': len(group),
                    'url': url,
                    'upcoming_events': upcoming_events[:3]  # Show up to 3 upcoming events
                })
        except Exception as e:
            log.error(f"Error processing library {name}: {e}")
            continue

    return calendar_events, map_events

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/events')
def get_event_data():
    try:
        calendar_events, map_events = load_events()
        return jsonify({
            'calendar_events': calendar_events,
            'map_events': map_events
        })
    except Exception as e:
        log.error(f"Error loading events: {str(e)}")
        return jsonify({
            'error': 'Failed to load events',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
