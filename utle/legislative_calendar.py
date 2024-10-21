# **********************************************************
# * CATEGORY  SOFTWARE
# * GROUP     GOV. AFFAIRS
# * AUTHOR    LANCE HAYNIE <LHAYNIE@SCCITY.ORG>
# * FILE      COMMITTEES.PY
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
import pytz
from cachetools import cached, TTLCache
from .settings import settings_data
import re


class LegislativeCalendar:
    calendar_cache = TTLCache(maxsize=1024, ttl=360)

    def __init__(self, db_host, db_user, db_password, db_name, api_key):
        self.api_key = api_key
        self.db_host = db_host
        self.db_user = db_user
        self.db_password = db_password
        self.db_name = db_name
        self.base_url = f"https://glen.le.utah.gov/legcal/{self.api_key}"
        self.connection = None
        self.cursor = None

    def setup(self):
        logging.basicConfig(
            level=settings_data["global"]["loglevel"],
            filename="legislative_calendar.log",
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.debug("Setting up LegislativeCalendar instance...")
        self.connection = pymysql.connect(
            host=self.db_host,
            user=self.db_user,
            password=self.db_password,
            database=self.db_name,
        )
        self.cursor = self.connection.cursor()
        logging.debug("Database connection established.")

    @cached(calendar_cache)
    def fetch_calendar(self):
        try:
            logging.debug("Fetching legislative calendar...")
            response = requests.get(self.base_url)
            if response.status_code == 200:
                calendar_data = response.json()
                return calendar_data.get("items", [])
            else:
                logging.error(
                    f"API request failed with status code: {response.status_code}"
                )
                return []
        except (requests.exceptions.RequestException, ValueError) as error:
            logging.error(f"Error fetching calendar data: {error}")
            return []

    def convert_utc_to_mst(self, utc_time_str):
        utc_time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%S.000Z")
        utc_time = utc_time.replace(tzinfo=pytz.utc)
        denver_tz = pytz.timezone("America/Denver")
        local_time = utc_time.astimezone(denver_tz)
        return local_time

    def extract_committee_id(self, link):
        match = re.search(r"com=([A-Z0-9]+)", link)
        if match:
            return match.group(1)
        return None

    def insert_or_update_calendar(self, calendar_item):
        try:
            committee = calendar_item.get("committee", "")
            link = calendar_item.get("link", "")
            committee_id = self.extract_committee_id(link)
            mtg_time_utc = calendar_item.get("mtgTime", "")
            mtg_place = calendar_item.get("mtgPlace", "")

            if mtg_time_utc:
                mtg_time_local = self.convert_utc_to_mst(mtg_time_utc)
                meeting_date = mtg_time_local.date()
                meeting_time = mtg_time_local.time()
            else:
                logging.warning(f"No meeting time provided for committee: {committee}")
                return

            logging.debug(f"Processing meeting for {committee} on {meeting_date}")

            self.cursor.execute(
                """
                SELECT mtg_time, mtg_place
                FROM legislative_calendar
                WHERE committee_id = %s AND DATE(mtg_time) = %s
                """,
                (committee_id, meeting_date),
            )
            existing_meeting = self.cursor.fetchone()

            if existing_meeting:
                existing_time, existing_place = existing_meeting

                # Extract the time portion of both existing and new meeting times
                existing_time_portion = existing_time.time()
                new_time_portion = meeting_time

                # Check if the time portion or meeting place has changed
                if (
                    existing_time_portion != new_time_portion
                    or existing_place != mtg_place
                ):
                    logging.debug(
                        f"Updating meeting for {committee} at {mtg_time_local}"
                    )
                    update_query = """
                        UPDATE legislative_calendar 
                        SET mtg_time = %s, mtg_place = %s, date_modified = NOW()
                        WHERE committee_id = %s AND DATE(mtg_time) = %s
                    """
                    self.cursor.execute(
                        update_query,
                        (mtg_time_local, mtg_place, committee_id, meeting_date),
                    )
                    self.connection.commit()
                    logging.debug(f"Updated meeting for {committee} on {meeting_date}")
                else:
                    logging.debug(
                        f"No changes detected for meeting: {committee} on {meeting_date}"
                    )
            else:
                logging.debug(f"Inserting new meeting for {committee}")
                guid = str(uuid.uuid4())
                insert_query = """
                    INSERT INTO legislative_calendar (guid, committee, committee_id, link, mtg_time, mtg_place, date_entered)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """
                self.cursor.execute(
                    insert_query,
                    (guid, committee, committee_id, link, mtg_time_local, mtg_place),
                )
                self.connection.commit()
                logging.debug(f"Inserted new meeting for {committee} on {meeting_date}")

        except pymysql.Error as db_error:
            logging.error(f"MySQL error: {db_error}")
        except Exception as ex:
            logging.error(f"General error: {ex}")

    def close_connection(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def run(self):
        self.setup()
        calendar_items = self.fetch_calendar()
        if calendar_items:
            logging.debug(
                f"Fetched calendar successfully. Total items: {len(calendar_items)}"
            )

            for item in calendar_items:
                self.insert_or_update_calendar(item)
        else:
            logging.debug("No calendar data fetched.")

        self.close_connection()

    @staticmethod
    def update_calendar():
        etlProcessor = LegislativeCalendar(
            api_key=settings_data["api"]["utle"],
            db_host=settings_data["database"]["host"],
            db_user=settings_data["database"]["user"],
            db_password=settings_data["database"]["password"],
            db_name=settings_data["database"]["schema"],
        )
        etlProcessor.run()


if __name__ == "__main__":
    LegislativeCalendar.update_calendar()
