import requests
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs
import html
import re
from datetime import datetime

# Custom HTML parser to extract the Bill Status table
class BillStatusParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture_table = False
        self.table_data = ''
        self.table_level = 0
        self.found_heading = False

    def handle_starttag(self, tag, attrs):
        if tag == 'span':
            for attr in attrs:
                if attr == ('class', 'heading'):
                    self.found_heading = True
                    break
        elif self.found_heading and tag == 'table':
            self.capture_table = True
            self.table_level += 1
            self.table_data += self.get_starttag_text()
        elif self.capture_table:
            if tag == 'table':
                self.table_level += 1
            self.table_data += self.get_starttag_text()

    def handle_endtag(self, tag):
        if self.capture_table:
            self.table_data += f'</{tag}>'
            if tag == 'table':
                self.table_level -= 1
                if self.table_level == 0:
                    self.capture_table = False
                    self.found_heading = False

    def handle_data(self, data):
        if self.capture_table:
            self.table_data += data

    def get_table(self):
        return self.table_data

# Custom HTML parser to extract vote entries from the Bill Status table
class VoteEntryParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_row = False
        self.in_cell = False
        self.cell_data = ''
        self.current_row = []
        self.vote_entries = []

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.in_row = True
            self.current_row = []
        elif self.in_row and tag == 'td':
            self.in_cell = True
            self.cell_data = ''
        elif self.in_cell:
            self.cell_data += self.get_starttag_text()
        elif self.in_row and tag == 'a':
            self.cell_data += self.get_starttag_text()

    def handle_endtag(self, tag):
        if tag == 'td' and self.in_cell:
            self.in_cell = False
            self.current_row.append(self.cell_data)
        elif tag == 'tr' and self.in_row:
            self.in_row = False
            if len(self.current_row) >= 4:
                # Check if the last cell contains a vote link
                if ('href="/mtgvotes.jsp' in self.current_row[3] or
                    'href="/DynaBill' in self.current_row[3] or
                    'href="/votes' in self.current_row[3]):
                    self.vote_entries.append(self.current_row)
        elif self.in_cell:
            self.cell_data += f'</{tag}>'
        elif self.in_row and tag == 'a':
            self.cell_data += f'</{tag}>'

    def handle_data(self, data):
        if self.in_cell:
            self.cell_data += data

def get_vote_entries(html_content):
    # Parse the HTML content to extract the Bill Status table
    status_parser = BillStatusParser()
    status_parser.feed(html_content)
    table_html = status_parser.get_table()
    if not table_html:
        print("Bill Status table not found.")
        return []

    # Parse the table to extract vote entries
    vote_parser = VoteEntryParser()
    vote_parser.feed(table_html)
    vote_entries = []

    for row in vote_parser.vote_entries:
        # Extract date
        raw_date = html.unescape(strip_tags(row[0]).strip())
        # Process date to MySQL-compatible format
        date = convert_to_mysql_datetime(raw_date)

        # Extract action
        action = html.unescape(strip_tags(row[1]).strip())
        # Extract location
        location = html.unescape(strip_tags(row[2]).strip())

        # Process action to remove '/' and replace 'comm' with 'committee', then make uppercase
        action = action.replace('/', ' ').replace('  ', ' ').strip()
        action = re.sub(r'\bcomm\b', 'committee', action, flags=re.IGNORECASE)
        action = action.upper()

        # Make location uppercase
        location = location.upper()

        # Extract vote URL
        link_html = row[3]
        vote_url_match = re.search(r'href="(.*?)">(.*?)</a>', link_html, re.DOTALL)
        vote_url = 'https://le.utah.gov' + vote_url_match.group(1) if vote_url_match else ''
        vote_entries.append({
            'date': date,
            'action': action,
            'location': location,
            'vote_url': vote_url,
        })

    return vote_entries

def convert_to_mysql_datetime(raw_date):
    # Check if time is included in the date string
    if '(' in raw_date and ')' in raw_date:
        # Extract date and time
        date_part, time_part = re.match(r'(.*?)\s*\((.*?)\)', raw_date).groups()
        date_part = date_part.strip()
        time_part = time_part.strip()
        # Parse date and time
        datetime_obj = datetime.strptime(f"{date_part} {time_part}", '%m/%d/%Y %I:%M:%S %p')
    else:
        # Parse date only, set time to midnight
        datetime_obj = datetime.strptime(raw_date, '%m/%d/%Y')
        datetime_obj = datetime_obj.replace(hour=0, minute=0, second=0)

    # Convert to MySQL datetime format
    return datetime_obj.strftime('%Y-%m-%d %H:%M:%S')

def strip_tags(html_content):
    # Simple function to remove HTML tags
    return re.sub('<[^<]+?>', '', html_content)

def get_legislator_names_from_table(table_html):
    # Extract all names from the table cells
    names = re.findall(r'<a[^>]*>(.*?)<\/a>', table_html, re.DOTALL)
    return [html.unescape(name.strip()) for name in names if name.strip()]

def parse_svotes(html_content):
    # Extract the text inside <b> tags
    b_tag_content_match = re.search(r'<b>(.*?)</b>', html_content, re.DOTALL)
    if b_tag_content_match:
        b_content = b_tag_content_match.group(1)
        # Search for "Passed on voice vote" or "Failed on voice vote"
        voice_vote_match = re.search(r'(Passed|Failed)\s+on\s+voice\s+vote', b_content, re.IGNORECASE)
        if voice_vote_match:
            result = voice_vote_match.group(1).upper()
            yeas_count = nays_count = absent_count = 0
            yeas_legislators = nays_legislators = absent_legislators = []
            return {
                'result': result,
                'vote_breakdown': {
                    'yeas': {'count': yeas_count, 'legislators': yeas_legislators},
                    'nays': {'count': nays_count, 'legislators': nays_legislators},
                    'absent': {'count': absent_count, 'legislators': absent_legislators},
                }
            }
    # Existing code to parse recorded votes
    # Extract vote counts
    vote_counts_match = re.search(r'Yeas\s*(\d+).*?Nays\s*(\d+).*?(?:N/V|Absent or not voting|Not Voting)\s*(\d+)', html_content, re.DOTALL)
    if vote_counts_match:
        yeas_count = int(vote_counts_match.group(1))
        nays_count = int(vote_counts_match.group(2))
        absent_count = int(vote_counts_match.group(3))
    else:
        yeas_count = nays_count = absent_count = 0

    # Extract legislator names for Yeas
    yeas_section_match = re.search(r'Yeas\s*-\s*\d+.*?<table>(.*?)</table>', html_content, re.DOTALL)
    yeas_legislators = get_legislator_names_from_table(yeas_section_match.group(1)) if yeas_section_match else []

    # Extract legislator names for Nays
    nays_section_match = re.search(r'Nays\s*-\s*\d+.*?<table>(.*?)</table>', html_content, re.DOTALL)
    nays_legislators = get_legislator_names_from_table(nays_section_match.group(1)) if nays_section_match else []

    # Extract legislator names for Absent or not voting
    absent_section_match = re.search(r'(?:Absent or not voting|Not Voting)\s*-\s*\d+.*?<table>(.*?)</table>', html_content, re.DOTALL)
    absent_legislators = get_legislator_names_from_table(absent_section_match.group(1)) if absent_section_match else []

    # Update counts if they were not correctly parsed
    yeas_count = len(yeas_legislators)
    nays_count = len(nays_legislators)
    absent_count = len(absent_legislators)

    # Determine the result based on counts
    if yeas_count > nays_count:
        result = 'PASSED'
    else:
        result = 'FAILED'

    return {
        'result': result,
        'vote_breakdown': {
            'yeas': {'count': yeas_count, 'legislators': yeas_legislators},
            'nays': {'count': nays_count, 'legislators': nays_legislators},
            'absent': {'count': absent_count, 'legislators': absent_legislators},
        }
    }

def parse_mtgvotes(html_content):
    # Extract the text inside <b> tags
    b_tag_content_match = re.search(r'<b>(.*?)</b>', html_content, re.DOTALL)
    if b_tag_content_match:
        b_content = b_tag_content_match.group(1)
        # Search for "Passed on voice vote" or "Failed on voice vote"
        voice_vote_match = re.search(r'(Passed|Failed)\s+on\s+voice\s+vote', b_content, re.IGNORECASE)
        if voice_vote_match:
            result = voice_vote_match.group(1).upper()
            yeas_count = nays_count = absent_count = 0
            yeas_legislators = nays_legislators = absent_legislators = []
            return {
                'result': result,
                'vote_breakdown': {
                    'yeas': {'count': yeas_count, 'legislators': yeas_legislators},
                    'nays': {'count': nays_count, 'legislators': nays_legislators},
                    'absent': {'count': absent_count, 'legislators': absent_legislators},
                }
            }
    # Existing code to parse recorded votes
    # Extract vote counts
    vote_counts_match = re.search(
        r'Yeas\s*-\s*(\d+).*?Nays\s*-\s*(\d+).*?(?:Absent|Excused|Not Present)\s*-\s*(\d+)', html_content, re.DOTALL)
    if vote_counts_match:
        yeas_count = int(vote_counts_match.group(1))
        nays_count = int(vote_counts_match.group(2))
        absent_count = int(vote_counts_match.group(3))
    else:
        yeas_count = nays_count = absent_count = 0

    # Extract legislator names
    names_section_match = re.search(
        r'<tr>\s*<td valign="top">(.*?)</td>\s*<td></td>\s*<td valign="top">(.*?)</td>\s*<td></td>\s*<td valign="top">(.*?)</td>',
        html_content, re.DOTALL)
    if names_section_match:
        yeas_section = names_section_match.group(1)
        nays_section = names_section_match.group(2)
        absent_section = names_section_match.group(3)
        yeas_legislators = [html.unescape(strip_tags(name.strip())) for name in re.split(r'<br\s*/?>', yeas_section) if name.strip()]
        nays_legislators = [html.unescape(strip_tags(name.strip())) for name in re.split(r'<br\s*/?>', nays_section) if name.strip()]
        absent_legislators = [html.unescape(strip_tags(name.strip())) for name in re.split(r'<br\s*/?>', absent_section) if name.strip()]
    else:
        yeas_legislators = nays_legislators = absent_legislators = []

    # Update counts if they were not correctly parsed
    yeas_count = len(yeas_legislators)
    nays_count = len(nays_legislators)
    absent_count = len(absent_legislators)

    # Determine the result based on counts
    if yeas_count > nays_count:
        result = 'PASSED'
    else:
        result = 'FAILED'

    return {
        'result': result,
        'vote_breakdown': {
            'yeas': {'count': yeas_count, 'legislators': yeas_legislators},
            'nays': {'count': nays_count, 'legislators': nays_legislators},
            'absent': {'count': absent_count, 'legislators': absent_legislators},
        }
    }

def determine_vote_type(vote_url):
    parsed_url = urlparse(vote_url)
    query_params = parse_qs(parsed_url.query)
    house_param = query_params.get('house', [''])[0].lower()
    if 'mtgvotes.jsp' in vote_url:
        return "Committee Vote"
    elif 'svotes.jsp' in vote_url or 'hvotes.jsp' in vote_url or '/votes' in vote_url:
        if house_param == 's':
            return "Senate Vote"
        elif house_param == 'h':
            return "House Vote"
        else:
            # Fallback to check the URL path for 'senate' or 'house'
            if 'senate' in vote_url.lower():
                return "Senate Vote"
            elif 'house' in vote_url.lower():
                return "House Vote"
            else:
                return "Unknown Vote Type"
    else:
        return "Unknown Vote Type"

def print_vote_results(parsed_data, bill_number, bill_year):
    # Print Bill Number and Bill Year on separate lines
    print(f"Bill Number: {bill_number}")
    print(f"Bill Year: {bill_year}")

    print(f"Date: {parsed_data['date']}")
    print(f"Action: {parsed_data['action']}")
    print(f"Location: {parsed_data['location']}")

    # Use the result from parsed_data
    result = parsed_data.get('result', 'UNKNOWN')
    print(f"Result: {result}")

    # Continue printing the vote breakdown
    yeas = parsed_data['vote_breakdown']['yeas']
    nays = parsed_data['vote_breakdown']['nays']
    absent = parsed_data['vote_breakdown']['absent']
    print(f"Yeas: {yeas['count']}, Nays: {nays['count']}, Absent: {absent['count']}")
    print(f"Yea Votes: {yeas['legislators']}")
    print(f"Nay Votes: {nays['legislators']}")
    print(f"Absent Votes: {absent['legislators']}")
    print("------------")

def main(year, bill_number):
    # Fetch the bill page
    base_bill_url = f'https://le.utah.gov/~{year}/bills/static/{bill_number}.html'
    try:
        bill_response = requests.get(base_bill_url)
        bill_response.raise_for_status()
        bill_html = bill_response.text
    except Exception as e:
        print(f"Error fetching bill page: {e}")
        return

    # Extract vote entries from the bill status table
    vote_entries = get_vote_entries(bill_html)
    if not vote_entries:
        print("No vote entries found on the bill page.")
        return

    # Now fetch and parse each vote URL
    for entry in vote_entries:
        vote_url = entry['vote_url']
        try:
            vote_response = requests.get(vote_url)
            vote_response.raise_for_status()
            vote_html = vote_response.text
        except Exception as e:
            print(f"Error fetching vote page {vote_url}: {e}")
            continue

        # Determine vote type based on URL parameters
        vote_type = determine_vote_type(vote_url)

        # Parse the vote page based on the vote type
        if vote_type == "Committee Vote":
            parsed_data = parse_mtgvotes(vote_html)
        elif vote_type in ["Senate Vote", "House Vote"]:
            parsed_data = parse_svotes(vote_html)
        else:
            print(f"Unknown vote type for URL: {vote_url}")
            continue

        # Include the date, action, and location from the entry
        parsed_data['date'] = entry['date']
        parsed_data['action'] = entry['action']
        parsed_data['location'] = entry['location']

        # Print the results with Bill Number and Bill Year
        print_vote_results(parsed_data, bill_number, year)

if __name__ == '__main__':
    # Example inputs
    year = 2024
    bill_number = 'SB0200'  # Replace with the bill number you're interested in
    main(year, bill_number)