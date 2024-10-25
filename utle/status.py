# **********************************************************
# * CATEGORY  SOFTWARE
# * GROUP     GOV. AFFAIRS
# * AUTHOR    LANCE HAYNIE <LHAYNIE@SCCITY.ORG>
# * FILE      STATUS.PY
# **********************************************************
# Utah Legislature Automation
# Copyright Santa Clara City
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import requests
import pymysql
import uuid
from html.parser import HTMLParser
import re
import logging
from datetime import datetime
from .settings import settings_data

# Setup logging
# logging.basicConfig(
#    level=logging.DEBUG,
#    format='%(asctime)s - %(levelname)s - %(message)s',
#    filename='status.log',
#    filemode='a'
# )


class StatusEntry(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_row = False
        self.in_cell = False
        self.cell_data = ""
        self.current_row = []
        self.status_entries = []
        self.is_header = True  # New flag to track the header row

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.in_row = True
            self.current_row = []
        elif self.in_row and tag == "td":
            self.in_cell = True
            self.cell_data = ""
        elif self.in_cell:
            self.cell_data += self.get_starttag_text()

    def handle_endtag(self, tag):
        if tag == "td" and self.in_cell:
            self.in_cell = False
            self.current_row.append(self.cell_data)
        elif tag == "tr" and self.in_row:
            self.in_row = False
            # Skip the header row
            if self.is_header:
                self.is_header = False  # Header row is done
            else:
                if len(self.current_row) >= 4:
                    self.status_entries.append(self.current_row)
        elif self.in_cell:
            self.cell_data += f"</{tag}>"

    def handle_data(self, data):
        if self.in_cell:
            self.cell_data += data


class Status:
    def __init__(self, bill_year, bill_number, db_host, db_user, db_password, db_name):
        self.bill_year = bill_year
        self.bill_number = bill_number
        self.base_url = f"https://le.utah.gov/~{self.bill_year}/bills/static/{self.bill_number}.html"
        logging.debug(
            f"Initializing Status class for bill {self.bill_number} for year {self.bill_year}."
        )
        self.connection = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        self.cursor = self.connection.cursor()
        self.status_entries = []

    def fetch_page(self):
        try:
            logging.debug(f"Fetching bill page from URL: {self.base_url}")
            response = requests.get(self.base_url)
            response.raise_for_status()
            logging.debug(f"Fetched page successfully: {self.base_url}")
            return response.text
        except Exception as e:
            logging.error(f"Error fetching bill page {self.base_url}: {e}")
            return None

    class BillStatus(HTMLParser):
        def __init__(self):
            super().__init__()
            self.capture_table = False
            self.table_data = ""
            self.table_level = 0
            self.found_heading = False

        def handle_starttag(self, tag, attrs):
            if tag == "span":
                for attr in attrs:
                    if attr == ("class", "heading"):
                        self.found_heading = True
                        break
            elif self.found_heading and tag == "table":
                self.capture_table = True
                self.table_level += 1
                self.table_data += self.get_starttag_text()
            elif self.capture_table:
                if tag == "table":
                    self.table_level += 1
                self.table_data += self.get_starttag_text()

        def handle_endtag(self, tag):
            if self.capture_table:
                self.table_data += f"</{tag}>"
                if tag == "table":
                    self.table_level -= 1
                    if self.table_level == 0:
                        self.capture_table = False
                        self.found_heading = False

        def handle_data(self, data):
            if self.capture_table:
                self.table_data += data

        def get_table(self):
            return self.table_data

    def get_status_entries(self, html_content):
        status_parser = self.BillStatus()
        status_parser.feed(html_content)
        table_html = status_parser.get_table()

        if not table_html:
            logging.debug("Bill Status table not found.")
            return []

        entry_parser = StatusEntry()  # Correct instantiation
        entry_parser.feed(table_html)
        status_entries = []

        for row in entry_parser.status_entries:
            raw_date = self.strip_tags(row[0]).strip()
            date = self.convert_to_mysql_datetime(raw_date)
            action = (
                self.strip_tags(row[1]).strip().upper()
            )  # Ensure action is uppercase
            location = self.strip_tags(row[2]).strip()

            action = action.replace("/", " ").replace("  ", " ").strip()
            location = location.upper()

            status_entries.append(
                {
                    "date": date,
                    "action": action,
                    "location": location,
                }
            )

        logging.debug(f"Parsed {len(status_entries)} status entries.")
        return status_entries

    def convert_to_mysql_datetime(self, raw_date):
        try:
            if "(" in raw_date and ")" in raw_date:
                date_part, time_part = re.match(r"(.*?)\s*\((.*?)\)", raw_date).groups()
                date_part = date_part.strip()
                time_part = time_part.strip()
                datetime_obj = datetime.strptime(
                    f"{date_part} {time_part}", "%m/%d/%Y %I:%M:%S %p"
                )
            else:
                datetime_obj = datetime.strptime(raw_date, "%m/%d/%Y")
            return datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logging.error(f"Error parsing date '{raw_date}': {e}")
            return None

    def strip_tags(self, html_content):
        return re.sub("<[^<]+?>", "", html_content)

    def save_to_db(self, entry):
        try:
            # Check for duplicates based on bill_number, bill_year, and date
            select_query = """
                SELECT guid FROM bill_status 
                WHERE bill_number = %s AND bill_year = %s AND date = %s
            """
            self.cursor.execute(
                select_query, (self.bill_number, self.bill_year, entry["date"])
            )
            existing_record = self.cursor.fetchone()

            if existing_record:
                logging.debug(
                    f"Duplicate entry found for {self.bill_number} on {entry['date']}, skipping insert."
                )
            else:
                guid = str(uuid.uuid4())
                insert_query = """
                    INSERT INTO bill_status (guid, bill_number, bill_year, date, action, location)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                self.cursor.execute(
                    insert_query,
                    (
                        guid,
                        self.bill_number,
                        self.bill_year,
                        entry["date"],
                        entry["action"],
                        entry["location"],
                    ),
                )
                self.connection.commit()
                logging.debug(
                    f"Inserted record for {self.bill_number} on {entry['date']}."
                )
        except pymysql.Error as db_error:
            logging.error(f"MySQL error: {db_error}")

    def run(self):
        page_html = self.fetch_page()
        if not page_html:
            logging.error("Failed to fetch the page, exiting.")
            return

        self.status_entries = self.get_status_entries(page_html)
        for entry in self.status_entries:
            logging.debug(f"Processing status entry: {entry}")
            self.save_to_db(entry)

        self.connection.close()
        logging.debug(f"Closed database connection for bill {self.bill_number}.")

    @staticmethod
    def get_status(year):
        try:
            etlProcessor = Status(
                db_host=settings_data["database"]["host"],
                db_user=settings_data["database"]["user"],
                db_password=settings_data["database"]["password"],
                db_name=settings_data["database"]["schema"],
                bill_year=year,
                bill_number="",  # Placeholder, actual bill number will be fetched
            )

            select_query = """
                SELECT bill_year, bill_number
                FROM govaffairs.bills
                WHERE bill_year = %s
                ORDER BY bill_number ASC
            """

            etlProcessor.cursor.execute(select_query, (year,))
            bills = etlProcessor.cursor.fetchall()

            for bill in bills:
                bill_number = bill["bill_number"]
                logging.info(f"Processing bill: {bill_number} for year: {year}")
                scraper = Status(
                    year,
                    bill_number,
                    settings_data["database"]["host"],
                    settings_data["database"]["user"],
                    settings_data["database"]["password"],
                    settings_data["database"]["schema"],
                )
                scraper.run()

        except pymysql.Error as db_error:
            logging.error(f"MySQL error: {db_error}")
        except Exception as ex:
            logging.error(f"Error during processing: {ex}")
        finally:
            etlProcessor.connection.close()
            logging.debug(
                f"Closed database connection after processing all bills for year {year}."
            )

    @staticmethod
    def get_status_history():
        try:
            for year in range(2017, 2025):
                logging.info(f"Processing bills for year: {year}")
                Status.get_status(year)

        except Exception as ex:
            logging.error(f"Error during processing: {ex}")


if __name__ == "__main__":
    year = 2024
    Status.get_status(year)
