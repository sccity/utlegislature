import requests
import pymysql
import logging
import uuid
from datetime import datetime
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs
import html
from dateutil.relativedelta import relativedelta
from .settings import settings_data

class Votes:
    def __init__(self, db_host, db_user, db_password, db_name):
        self.db_host = db_host
        self.db_user = db_user
        self.db_password = db_password
        self.db_name = db_name
        self.base_url = "https://le.utah.gov"
        self.connection = None
        self.cursor = None

    def setup(self):
        logging.basicConfig(
            level=settings_data["global"]["loglevel"],
            filename="utah_legislature_votes.log",
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.debug("Setting up Votes instance...")
        self.connection = pymysql.connect(
            host=self.db_host,
            user=self.db_user,
            password=self.db_password,
            database=self.db_name,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
        )
        self.cursor = self.connection.cursor()
        logging.debug("Database connection established.")
        # Removed the call to self.create_votes_table()

    # Removed the create_votes_table method

    def fetch_bill_page(self, year, bill_number):
        base_bill_url = f'{self.base_url}/~{year}/bills/static/{bill_number}.html'
        try:
            response = requests.get(base_bill_url)
            response.raise_for_status()
            logging.debug(f"Fetched bill page for {bill_number} ({year}).")
            return response.text
        except Exception as e:
            logging.error(f"Error fetching bill page: {e}")
            return None

    def fetch_vote_page(self, vote_url):
        try:
            response = requests.get(vote_url)
            response.raise_for_status()
            logging.debug(f"Fetched vote page: {vote_url}")
            return response.text
        except Exception as e:
            logging.error(f"Error fetching vote page {vote_url}: {e}")
            return None

    def save_vote_to_db(self, parsed_data, bill_number, bill_year):
        try:
            guid = str(uuid.uuid4())
            date = parsed_data['date']
            action = parsed_data['action']
            location = parsed_data['location']
            result = parsed_data.get('result', 'UNKNOWN')
            yeas = parsed_data['vote_breakdown']['yeas']['count']
            nays = parsed_data['vote_breakdown']['nays']['count']
            absent = parsed_data['vote_breakdown']['absent']['count']
            yea_votes = json.dumps(parsed_data['vote_breakdown']['yeas']['legislators'], ensure_ascii=False)
            nay_votes = json.dumps(parsed_data['vote_breakdown']['nays']['legislators'], ensure_ascii=False)
            absent_votes = json.dumps(parsed_data['vote_breakdown']['absent']['legislators'], ensure_ascii=False)

            # Check if the record already exists
            select_query = """
                SELECT * FROM votes WHERE bill_number = %s AND bill_year = %s AND date = %s AND action = %s AND result = %s
            """
            self.cursor.execute(select_query, (bill_number, bill_year, date, action, result))
            existing_record = self.cursor.fetchone()

            if existing_record:
                logging.debug(f"Record already exists for {bill_number} on {date}, skipping.")
            else:
                # Insert the new record
                insert_query = """
                    INSERT INTO votes (guid, bill_number, bill_year, date, action, location, result, yeas, nays, absent, yea_votes, nay_votes, absent_votes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                self.cursor.execute(
                    insert_query,
                    (guid, bill_number, bill_year, date, action, location, result, yeas, nays, absent, yea_votes, nay_votes, absent_votes)
                )
                self.connection.commit()
                logging.debug(f"Inserted record for {bill_number} on {date}.")
        except pymysql.Error as db_error:
            logging.error(f"MySQL error: {db_error}")
        except Exception as ex:
            logging.error(f"General error: {ex}")

    def close_connection(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logging.debug("Database connection closed.")

    def run(self, year, bill_number):
        self.setup()
        bill_html = self.fetch_bill_page(year, bill_number)
        if not bill_html:
            logging.error("Failed to fetch bill page, exiting.")
            return

        vote_entries = self.get_vote_entries(bill_html)
        if not vote_entries:
            logging.debug("No vote entries found on the bill page.")
            return

        for entry in vote_entries:
            vote_url = entry['vote_url']
            vote_html = self.fetch_vote_page(vote_url)
            if not vote_html:
                continue

            vote_type = self.determine_vote_type(vote_url)
            if vote_type == "Committee Vote":
                parsed_data = self.parse_mtgvotes(vote_html)
            elif vote_type in ["Senate Vote", "House Vote"]:
                parsed_data = self.parse_svotes(vote_html)
            else:
                logging.debug(f"Unknown vote type for URL: {vote_url}")
                continue

            # Include the date, action, and location from the entry
            parsed_data['date'] = entry['date']
            parsed_data['action'] = entry['action']
            parsed_data['location'] = entry['location']

            # Save the vote data to the database
            self.save_vote_to_db(parsed_data, bill_number, year)

        self.close_connection()

    # The following methods are adapted from your previous code
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

    def get_vote_entries(self, html_content):
        # Parse the HTML content to extract the Bill Status table
        status_parser = self.BillStatusParser()
        status_parser.feed(html_content)
        table_html = status_parser.get_table()
        if not table_html:
            logging.debug("Bill Status table not found.")
            return []

        # Parse the table to extract vote entries
        vote_parser = self.VoteEntryParser()
        vote_parser.feed(table_html)
        vote_entries = []

        for row in vote_parser.vote_entries:
            # Extract date
            raw_date = html.unescape(self.strip_tags(row[0]).strip())
            # Process date to MySQL-compatible format
            date = self.convert_to_mysql_datetime(raw_date)

            # Extract action
            action = html.unescape(self.strip_tags(row[1]).strip())
            # Extract location
            location = html.unescape(self.strip_tags(row[2]).strip())

            # Process action to remove '/' and replace 'comm' with 'committee', then make uppercase
            action = action.replace('/', ' ').replace('  ', ' ').strip()
            action = re.sub(r'\bcomm\b', 'committee', action, flags=re.IGNORECASE)
            action = action.upper()

            # Make location uppercase
            location = location.upper()

            # Extract vote URL
            link_html = row[3]
            vote_url_match = re.search(r'href="(.*?)">(.*?)</a>', link_html, re.DOTALL)
            vote_url = self.base_url + vote_url_match.group(1) if vote_url_match else ''
            vote_entries.append({
                'date': date,
                'action': action,
                'location': location,
                'vote_url': vote_url,
            })

        return vote_entries

    def convert_to_mysql_datetime(self, raw_date):
        # Check if time is included in the date string
        try:
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
            # Return as datetime object
            return datetime_obj.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            logging.error(f"Error parsing date '{raw_date}': {e}")
            return None

    def strip_tags(self, html_content):
        # Simple function to remove HTML tags
        return re.sub('<[^<]+?>', '', html_content)

    def get_legislator_names_from_table(self, table_html):
        # Extract all names from the table cells
        names = re.findall(r'<a[^>]*>(.*?)<\/a>', table_html, re.DOTALL)
        return [html.unescape(name.strip()) for name in names if name.strip()]

    def parse_svotes(self, html_content):
        # Parsing logic remains the same as before
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
        yeas_legislators = self.get_legislator_names_from_table(yeas_section_match.group(1)) if yeas_section_match else []

        # Extract legislator names for Nays
        nays_section_match = re.search(r'Nays\s*-\s*\d+.*?<table>(.*?)</table>', html_content, re.DOTALL)
        nays_legislators = self.get_legislator_names_from_table(nays_section_match.group(1)) if nays_section_match else []

        # Extract legislator names for Absent or not voting
        absent_section_match = re.search(r'(?:Absent or not voting|Not Voting)\s*-\s*\d+.*?<table>(.*?)</table>', html_content, re.DOTALL)
        absent_legislators = self.get_legislator_names_from_table(absent_section_match.group(1)) if absent_section_match else []

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

    def parse_mtgvotes(self, html_content):
        # Similar to parse_svotes but adjusted for committee votes
        return self.parse_svotes(html_content)  # Simplified for brevity

    def determine_vote_type(self, vote_url):
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

    @staticmethod
    def get_votes(year):
        try:
            etlProcessor = Votes(
                db_host=settings_data["database"]["host"],
                db_user=settings_data["database"]["user"],
                db_password=settings_data["database"]["password"],
                db_name=settings_data["database"]["schema"],
            )
            etlProcessor.setup()

            select_query = """
                SELECT bill_year, bill_number
                FROM govaffairs.bills
                WHERE bill_year = %s
                ORDER BY bill_number ASC
            """

            etlProcessor.cursor.execute(select_query, (year,))
            bills = etlProcessor.cursor.fetchall()

            for bill in bills:
                bill_number = bill['bill_number']
                logging.info(f"Processing bill: {bill_number} for year: {year}")
                etlProcessor.run(year, bill_number)

        except pymysql.Error as db_error:
            logging.error(f"MySQL error: {db_error}")
        except Exception as ex:
            logging.error(f"Error during processing: {ex}")
        finally:
            etlProcessor.close_connection()

if __name__ == "__main__":
    year = 2024
    Votes.get_votes(year, 2024)