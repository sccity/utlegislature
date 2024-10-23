# **********************************************************
# * CATEGORY  SOFTWARE
# * GROUP     GOV. AFFAIRS
# * AUTHOR    LANCE HAYNIE <LHAYNIE@SCCITY.ORG>
# * FILE      VOTES.PY
# **********************************************************
# Utah Legislature Automation
# Copyright Santa Clara City
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.#
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import requests
import pymysql
import logging
import uuid
from datetime import datetime
from fuzzywuzzy import fuzz
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
            filename="votes.log",
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.debug("Setting up Votes instance...")
        self.connection = pymysql.connect(
            host=self.db_host,
            user=self.db_user,
            password=self.db_password,
            database=self.db_name,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        self.cursor = self.connection.cursor()
        logging.debug("Database connection established.")

    def fetch_bill_page(self, year, bill_number):
        base_bill_url = f"{self.base_url}/~{year}/bills/static/{bill_number}.html"
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
            date = parsed_data["date"]
            action = parsed_data["action"]
            location = parsed_data["location"]
            result = parsed_data.get("result", "UNKNOWN")
            yeas = parsed_data["vote_breakdown"]["yeas"]["count"]
            nays = parsed_data["vote_breakdown"]["nays"]["count"]
            absent = parsed_data["vote_breakdown"]["absent"]["count"]
            yea_votes = json.dumps(
                parsed_data["vote_breakdown"]["yeas"]["legislators"], ensure_ascii=False
            )
            nay_votes = json.dumps(
                parsed_data["vote_breakdown"]["nays"]["legislators"], ensure_ascii=False
            )
            absent_votes = json.dumps(
                parsed_data["vote_breakdown"]["absent"]["legislators"],
                ensure_ascii=False,
            )

            select_query = """
                SELECT * FROM votes WHERE bill_number = %s AND bill_year = %s AND date = %s AND action = %s AND result = %s
            """
            self.cursor.execute(
                select_query, (bill_number, bill_year, date, action, result)
            )
            existing_record = self.cursor.fetchone()

            if existing_record:
                logging.debug(
                    f"Record already exists for {bill_number} on {date}, skipping."
                )
            else:
                insert_query = """
                    INSERT INTO votes (guid, bill_number, bill_year, date, action, location, result, yeas, nays, absent, yea_votes, nay_votes, absent_votes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                self.cursor.execute(
                    insert_query,
                    (
                        guid,
                        bill_number,
                        bill_year,
                        date,
                        action,
                        location,
                        result,
                        yeas,
                        nays,
                        absent,
                        yea_votes,
                        nay_votes,
                        absent_votes,
                    ),
                )
                self.connection.commit()
                logging.debug(f"Inserted record for {bill_number} on {date}.")

                self.process_legislator_votes(
                    parsed_data["vote_breakdown"]["yeas"]["legislators"], guid, "yea"
                )
                self.process_legislator_votes(
                    parsed_data["vote_breakdown"]["nays"]["legislators"], guid, "nay"
                )
                self.process_legislator_votes(
                    parsed_data["vote_breakdown"]["absent"]["legislators"],
                    guid,
                    "absent",
                )

        except pymysql.Error as db_error:
            logging.error(f"MySQL error: {db_error}")
        except Exception as ex:
            logging.error(f"General error: {ex}")

    def process_legislator_votes(self, legislators, vote_guid, vote_type):
        for legislator in legislators:
            # Split the legislator name (vote data) into last name and initials
            last_name, initials = legislator.split(", ")
            initials_clean = initials.replace(".", "").strip()
            first_initial = initials_clean[0]  # First initial
            middle_initial = initials_clean[1:] if len(initials_clean) > 1 else ""  # Middle initial, if exists
            last_name_clean = last_name.strip()

            logging.debug(f"Processing legislator: {legislator}")

            # Step 1: Try matching using full_name (removing periods)
            select_legislator_query = """
                SELECT guid, full_name FROM legislators 
                WHERE REPLACE(full_name, '.', '') LIKE %s
            """
            full_name_like = f"{last_name_clean}%, {first_initial}%"
            self.cursor.execute(select_legislator_query, (full_name_like,))
            legislator_record = self.cursor.fetchone()

            # Step 2: Try matching using format_name (removing periods)
            if not legislator_record:
                logging.debug(f"No match found for {legislator} in full_name, trying format_name.")
                select_legislator_query = """
                    SELECT guid, format_name FROM legislators 
                    WHERE REPLACE(format_name, '.', '') LIKE %s
                """
                format_name_like = f"{first_initial}%, {last_name_clean}%"
                self.cursor.execute(select_legislator_query, (format_name_like,))
                legislator_record = self.cursor.fetchone()

            # Step 3: Try matching with both initials (if available)
            if not legislator_record and middle_initial:
                logging.debug(f"Trying to match using both initials for {legislator}.")
                select_legislator_query = """
                    SELECT guid, full_name FROM legislators 
                    WHERE REPLACE(full_name, '.', '') LIKE %s AND REPLACE(full_name, '.', '') LIKE %s
                """
                full_name_like_first = f"{last_name_clean}%, {first_initial}%"
                full_name_like_middle = f"% {middle_initial}%"
                self.cursor.execute(select_legislator_query, (full_name_like_first, full_name_like_middle))
                legislator_record = self.cursor.fetchone()

            # Step 4: Fuzzy matching as a fallback if no match found
            if not legislator_record:
                logging.debug(f"No exact match found for {legislator}, attempting fuzzy matching.")
                all_legislators = self.get_all_legislators()  # Fetch all legislators from the DB
                best_match = None
                highest_score = 0
                for db_legislator in all_legislators:
                    normalized_db_name = db_legislator['full_name'].replace('.', '').strip()
                    normalized_vote_name = legislator.replace('.', '').strip()
                    similarity_score = fuzz.partial_ratio(normalized_db_name, normalized_vote_name)

                    if similarity_score > highest_score:
                        highest_score = similarity_score
                        best_match = db_legislator

                if highest_score > 80:  # 80% similarity threshold for fuzzy matching
                    legislator_record = best_match
                    logging.debug(f"Fuzzy match found: {legislator_record['full_name']} with score {highest_score} for {legislator}")
                else:
                    logging.warning(f"No match found for {legislator}, even after fuzzy matching.")

            # Insert into votes_legislators if a match was found
            if legislator_record:
                legislator_guid = legislator_record['guid']
                select_vote_legislator_query = """
                    SELECT * FROM votes_legislators WHERE vote_guid = %s AND legislator_guid = %s
                """
                self.cursor.execute(select_vote_legislator_query, (vote_guid, legislator_guid))
                vote_legislator_record = self.cursor.fetchone()

                # Insert new record if it doesn't exist yet
                if not vote_legislator_record:
                    insert_vote_legislator_query = """
                        INSERT INTO votes_legislators (guid, vote_guid, legislator_guid, vote)
                        VALUES (%s, %s, %s, %s)
                    """
                    self.cursor.execute(
                        insert_vote_legislator_query,
                        (str(uuid.uuid4()), vote_guid, legislator_guid, vote_type)
                    )
                    self.connection.commit()
                    logging.debug(f"Inserted legislator {legislator_guid} with vote {vote_type} for vote {vote_guid}.")
                else:
                    logging.debug(f"Vote record already exists for legislator {legislator_guid} and vote {vote_guid}, skipping.")
            else:
                logging.warning(f"Could not find legislator match for {legislator}.")

    def close_connection(self):
        if self.connection and self.connection.open:
            if self.cursor:
                self.cursor.close()
            self.connection.close()
            logging.debug("Database connection closed.")
        else:
            logging.debug("Database connection was already closed.")

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
            vote_url = entry["vote_url"]
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

            parsed_data["date"] = entry["date"]
            parsed_data["action"] = entry["action"]
            parsed_data["location"] = entry["location"]

            self.save_vote_to_db(parsed_data, bill_number, year)

        self.close_connection()

    class BillStatusParser(HTMLParser):
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

    class VoteEntryParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_row = False
            self.in_cell = False
            self.cell_data = ""
            self.current_row = []
            self.vote_entries = []

        def handle_starttag(self, tag, attrs):
            if tag == "tr":
                self.in_row = True
                self.current_row = []
            elif self.in_row and tag == "td":
                self.in_cell = True
                self.cell_data = ""
            elif self.in_cell:
                self.cell_data += self.get_starttag_text()
            elif self.in_row and tag == "a":
                self.cell_data += self.get_starttag_text()

        def handle_endtag(self, tag):
            if tag == "td" and self.in_cell:
                self.in_cell = False
                self.current_row.append(self.cell_data)
            elif tag == "tr" and self.in_row:
                self.in_row = False
                if len(self.current_row) >= 4:
                    # Check if the last cell contains a vote link
                    if (
                        'href="/mtgvotes.jsp' in self.current_row[3]
                        or 'href="/DynaBill' in self.current_row[3]
                        or 'href="/votes' in self.current_row[3]
                    ):
                        self.vote_entries.append(self.current_row)
            elif self.in_cell:
                self.cell_data += f"</{tag}>"
            elif self.in_row and tag == "a":
                self.cell_data += f"</{tag}>"

        def handle_data(self, data):
            if self.in_cell:
                self.cell_data += data

    def get_vote_entries(self, html_content):
        status_parser = self.BillStatusParser()
        status_parser.feed(html_content)
        table_html = status_parser.get_table()
        if not table_html:
            logging.debug("Bill Status table not found.")
            return []

        vote_parser = self.VoteEntryParser()
        vote_parser.feed(table_html)
        vote_entries = []

        for row in vote_parser.vote_entries:
            raw_date = html.unescape(self.strip_tags(row[0]).strip())
            date = self.convert_to_mysql_datetime(raw_date)
            action = html.unescape(self.strip_tags(row[1]).strip())
            location = html.unescape(self.strip_tags(row[2]).strip())

            action = action.replace("/", " ").replace("  ", " ").strip()
            action = re.sub(r"\bcomm\b", "committee", action, flags=re.IGNORECASE)
            action = action.upper()

            location = location.upper()

            link_html = row[3]
            vote_url_match = re.search(r'href="(.*?)">(.*?)</a>', link_html, re.DOTALL)
            vote_url = self.base_url + vote_url_match.group(1) if vote_url_match else ""
            vote_entries.append(
                {
                    "date": date,
                    "action": action,
                    "location": location,
                    "vote_url": vote_url,
                }
            )

        return vote_entries

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

    def get_legislator_names_from_table(self, table_html):
        names = re.findall(r"<a[^>]*>(.*?)<\/a>", table_html, re.DOTALL)
        return [html.unescape(name.strip()) for name in names if name.strip()]

    def parse_svotes(self, html_content):
        b_tag_content_match = re.search(r"<b>(.*?)</b>", html_content, re.DOTALL)
        if b_tag_content_match:
            b_content = b_tag_content_match.group(1)
            voice_vote_match = re.search(
                r"(Passed|Failed)\s+on\s+voice\s+vote", b_content, re.IGNORECASE
            )
            if voice_vote_match:
                result = voice_vote_match.group(1).upper()
                yeas_count = nays_count = absent_count = 0
                yeas_legislators = nays_legislators = absent_legislators = []
                return {
                    "result": result,
                    "vote_breakdown": {
                        "yeas": {"count": yeas_count, "legislators": yeas_legislators},
                        "nays": {"count": nays_count, "legislators": nays_legislators},
                        "absent": {
                            "count": absent_count,
                            "legislators": absent_legislators,
                        },
                    },
                }

        vote_counts_match = re.search(
            r"Yeas\s*(\d+).*?Nays\s*(\d+).*?(?:N/V|Absent or not voting|Not Voting)\s*(\d+)",
            html_content,
            re.DOTALL,
        )
        if vote_counts_match:
            yeas_count = int(vote_counts_match.group(1))
            nays_count = int(vote_counts_match.group(2))
            absent_count = int(vote_counts_match.group(3))
        else:
            yeas_count = nays_count = absent_count = 0

        yeas_section_match = re.search(
            r"Yeas\s*-\s*\d+.*?<table>(.*?)</table>", html_content, re.DOTALL
        )
        yeas_legislators = (
            self.get_legislator_names_from_table(yeas_section_match.group(1))
            if yeas_section_match
            else []
        )

        nays_section_match = re.search(
            r"Nays\s*-\s*\d+.*?<table>(.*?)</table>", html_content, re.DOTALL
        )
        nays_legislators = (
            self.get_legislator_names_from_table(nays_section_match.group(1))
            if nays_section_match
            else []
        )

        absent_section_match = re.search(
            r"(?:Absent or not voting|Not Voting)\s*-\s*\d+.*?<table>(.*?)</table>",
            html_content,
            re.DOTALL,
        )
        absent_legislators = (
            self.get_legislator_names_from_table(absent_section_match.group(1))
            if absent_section_match
            else []
        )

        yeas_count = len(yeas_legislators)
        nays_count = len(nays_legislators)
        absent_count = len(absent_legislators)

        if yeas_count > nays_count:
            result = "PASSED"
        else:
            result = "FAILED"

        return {
            "result": result,
            "vote_breakdown": {
                "yeas": {"count": yeas_count, "legislators": yeas_legislators},
                "nays": {"count": nays_count, "legislators": nays_legislators},
                "absent": {"count": absent_count, "legislators": absent_legislators},
            },
        }

    def parse_mtgvotes(self, html_content):
        return self.parse_svotes(html_content)

    def determine_vote_type(self, vote_url):
        parsed_url = urlparse(vote_url)
        query_params = parse_qs(parsed_url.query)
        house_param = query_params.get("house", [""])[0].lower()
        if "mtgvotes.jsp" in vote_url:
            return "Committee Vote"
        elif (
            "svotes.jsp" in vote_url or "hvotes.jsp" in vote_url or "/votes" in vote_url
        ):
            if house_param == "s":
                return "Senate Vote"
            elif house_param == "h":
                return "House Vote"
            else:
                if "senate" in vote_url.lower():
                    return "Senate Vote"
                elif "house" in vote_url.lower():
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
                bill_number = bill["bill_number"]
                logging.info(f"Processing bill: {bill_number} for year: {year}")
                etlProcessor.run(year, bill_number)

        except pymysql.Error as db_error:
            logging.error(f"MySQL error: {db_error}")
        except Exception as ex:
            logging.error(f"Error during processing: {ex}")
        finally:
            etlProcessor.close_connection()

    def get_vote_history():
        try:
            etlProcessor = Votes(
                db_host=settings_data["database"]["host"],
                db_user=settings_data["database"]["user"],
                db_password=settings_data["database"]["password"],
                db_name=settings_data["database"]["schema"],
            )
            etlProcessor.setup()

            for year in range(2017, 2025):
                logging.info(f"Processing bills for year: {year}")
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
