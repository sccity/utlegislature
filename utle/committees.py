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
import json
from cachetools import cached, TTLCache
from .settings import settings_data


class Committees:
    committee_cache = TTLCache(maxsize=1024, ttl=360)

    def __init__(self, db_host, db_user, db_password, db_name, api_key):
        self.api_key = api_key
        self.db_host = db_host
        self.db_user = db_user
        self.db_password = db_password
        self.db_name = db_name
        self.base_url = f"https://glen.le.utah.gov/committees/{self.api_key}"
        self.connection = None
        self.cursor = None

    def setup(self):
        logging.basicConfig(
            level=settings_data["global"]["loglevel"],
            filename="committees.log",
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.debug("Setting up Committees instance...")
        self.connection = pymysql.connect(
            host=self.db_host,
            user=self.db_user,
            password=self.db_password,
            database=self.db_name,
        )
        self.cursor = self.connection.cursor()
        logging.debug("Database connection established.")

    @cached(committee_cache)
    def fetch_committee_list(self):
        try:
            logging.debug("Fetching committee list...")
            response = requests.get(self.base_url)
            if response.status_code == 200:
                committee_data = response.json()
                return committee_data.get("committees", [])
            else:
                logging.error(
                    f"API request failed with status code: {response.status_code}"
                )
                return []
        except (requests.exceptions.RequestException, ValueError) as error:
            logging.error(f"Error fetching committee list: {error}")
            return []

    def insert_or_update_committee(self, committee_data):
        try:
            committee_id = committee_data["id"]
            logging.debug(f"Processing committee for Insert or Update: {committee_id}")

            description = committee_data.get("description", "")
            link = committee_data.get("link", "")
            meetings = committee_data.get("meetings", [])
            members = committee_data.get("members", [])

            meetings_json = json.dumps(meetings)
            members_json = json.dumps(members)

            self.cursor.execute("""
                SELECT description, link, meetings, members 
                FROM committees 
                WHERE id = %s
            """, (committee_id,))
            existing_committee = self.cursor.fetchone()

            if existing_committee:
                if (
                    existing_committee[0] != description
                    or existing_committee[1] != link
                    or existing_committee[2] != meetings_json
                    or existing_committee[3] != members_json
                ):
                    logging.debug(f"Fields have changed, updating committee: {committee_id}")
                    update_query = """
                        UPDATE committees 
                        SET description = %s, link = %s, meetings = %s, members = %s, active = 1, date_modified = NOW()
                        WHERE id = %s
                    """
                    update_values = (description, link, meetings_json, members_json, committee_id)
                    self.cursor.execute(update_query, update_values)
                    self.connection.commit()
                    logging.debug(f"Updated committee: {committee_id}")
                else:
                    logging.debug(f"No changes detected for committee: {committee_id}")
            else:
                logging.debug(f"Committee {committee_id} does not exist, inserting new record.")
                guid = str(uuid.uuid4())
                insert_query = """
                    INSERT INTO committees (guid, id, description, link, meetings, members, active, date_entered)
                    VALUES (%s, %s, %s, %s, %s, %s, 1, NOW())
                """
                insert_values = (guid, committee_id, description, link, meetings_json, members_json)
                self.cursor.execute(insert_query, insert_values)
                self.connection.commit()
                logging.debug(f"Inserted committee: {committee_id}")

        except pymysql.Error as db_error:
            logging.error(f"MySQL error: {db_error}")
        except Exception as ex:
            logging.error(f"General error: {ex}")

    def deactivate_committees(self, current_committee_ids):
        try:
            self.cursor.execute("SELECT id FROM committees")
            db_committees = self.cursor.fetchall()

            db_committee_ids = [row[0] for row in db_committees]

            missing_committees = set(db_committee_ids) - set(current_committee_ids)

            if missing_committees:
                for committee_id in missing_committees:
                    logging.debug(f"Deactivating committee: {committee_id}")
                    self.cursor.execute(
                        "UPDATE committees SET active = 0 WHERE id = %s",
                        (committee_id,),
                    )
                self.connection.commit()
                logging.debug(f"Deactivated {len(missing_committees)} committees missing from API.")
            else:
                logging.debug("No committees to deactivate.")
        except pymysql.Error as db_error:
            logging.error(f"MySQL error while deactivating committees: {db_error}")

    def close_connection(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def run(self):
        self.setup()
        committees = self.fetch_committee_list()
        if committees:
            logging.debug(
                f"Fetched committee list successfully. Total committees: {len(committees)}"
            )

            current_committee_ids = []

            for committee in committees:
                current_committee_ids.append(committee["id"])
                self.insert_or_update_committee(committee)

            self.deactivate_committees(current_committee_ids)
        else:
            logging.debug("No committee data fetched.")

        self.close_connection()

    @staticmethod
    def update_committees():
        etlProcessor = Committees(
            api_key=settings_data["api"]["utle"],
            db_host=settings_data["database"]["host"],
            db_user=settings_data["database"]["user"],
            db_password=settings_data["database"]["password"],
            db_name=settings_data["database"]["schema"],
        )
        etlProcessor.run()


if __name__ == "__main__":
    Committees.update_committees()