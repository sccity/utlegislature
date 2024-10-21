# **********************************************************
# * CATEGORY  SOFTWARE
# * GROUP     GOV. AFFAIRS
# * AUTHOR    LANCE HAYNIE <LHAYNIE@SCCITY.ORG>
# * FILE      LEGISLATORS.PY
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


class Legislators:
    legislator_cache = TTLCache(maxsize=1024, ttl=360)

    def __init__(self, db_host, db_user, db_password, db_name, api_key):
        self.api_key = api_key
        self.db_host = db_host
        self.db_user = db_user
        self.db_password = db_password
        self.db_name = db_name
        self.base_url = f"https://glen.le.utah.gov/legislators/{self.api_key}"
        self.connection = None
        self.cursor = None

    def setup(self):
        logging.basicConfig(
            level=settings_data["global"]["loglevel"],
            filename="legislators.log",
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.debug("Setting up Legislators instance...")
        self.connection = pymysql.connect(
            host=self.db_host,
            user=self.db_user,
            password=self.db_password,
            database=self.db_name,
        )
        self.cursor = self.connection.cursor()
        logging.debug("Database connection established.")

    @cached(legislator_cache)
    def fetch_legislator_list(self):
        try:
            logging.debug("Fetching legislator list...")
            response = requests.get(self.base_url)
            if response.status_code == 200:
                legislator_data = response.json()
                return legislator_data.get("legislators", [])
            else:
                logging.error(
                    f"API request failed with status code: {response.status_code}"
                )
                return []
        except (requests.exceptions.RequestException, ValueError) as error:
            logging.error(f"Error fetching legislator list: {error}")
            return []

    def insert_or_update_legislator(self, legislator_data):
        try:
            legislator_id = legislator_data["id"]
            logging.debug(
                f"Processing legislator for Insert or Update: {legislator_id}"
            )

            full_name = legislator_data.get("fullName", "")
            format_name = legislator_data.get("formatName", "")
            party = legislator_data.get("party", "")
            district = legislator_data.get("district", "")
            house = legislator_data.get("house", "")
            position = legislator_data.get("position", "")
            address = legislator_data.get("address", "")
            email = legislator_data.get("email", "")
            cell = legislator_data.get("cell", "")
            work_phone = legislator_data.get("workPhone", "")
            service_start = legislator_data.get("serviceStart", "")
            profession = legislator_data.get("profession", "")
            professional_affiliations = legislator_data.get(
                "professionalAffiliations", ""
            )
            education = legislator_data.get("education", "")
            recognitions_and_honors = legislator_data.get("recognitionsAndHonors", "")
            counties = legislator_data.get("counties", "")
            legislation_url = legislator_data.get("legislation", "")
            demographic_url = legislator_data.get("demographic", "")
            image_url = legislator_data.get("image", "")

            committees = legislator_data.get("committees", [])
            committees_json = json.dumps(committees)
            finance_report = legislator_data.get("FinanceReport", [])
            finance_report_json = json.dumps(finance_report)

            self.cursor.execute(
                """
                SELECT full_name, format_name, party, district, house, position, address,
                    email, cell, work_phone, counties, legislation_url, demographic_url,
                    image_url, committees, finance_report
                FROM legislators
                WHERE id = %s
            """,
                (legislator_id,),
            )
            existing_legislator = self.cursor.fetchone()

            if existing_legislator:
                if (
                    existing_legislator[0] != full_name
                    or existing_legislator[1] != format_name
                    or existing_legislator[2] != party
                    or existing_legislator[3] != district
                    or existing_legislator[4] != house
                    or existing_legislator[5] != position
                    or existing_legislator[6] != address
                    or existing_legislator[7] != email
                    or existing_legislator[8] != cell
                    or existing_legislator[9] != work_phone
                    or existing_legislator[10] != counties
                    or existing_legislator[11] != legislation_url
                    or existing_legislator[12] != demographic_url
                    or existing_legislator[13] != image_url
                    or existing_legislator[14] != committees_json
                    or existing_legislator[15] != finance_report_json
                ):
                    logging.debug(
                        f"Fields have changed, updating legislator: {legislator_id}"
                    )
                    update_query = """
                        UPDATE legislators 
                        SET full_name = %s, format_name = %s, party = %s, district = %s, house = %s, position = %s,
                            address = %s, email = %s, cell = %s, work_phone = %s, counties = %s, 
                            legislation_url = %s, demographic_url = %s, image_url = %s, committees = %s, finance_report = %s,
                            active = 1, date_modified = NOW()
                        WHERE id = %s
                    """
                    update_values = (
                        full_name,
                        format_name,
                        party,
                        district,
                        house,
                        position,
                        address,
                        email,
                        cell,
                        work_phone,
                        counties,
                        legislation_url,
                        demographic_url,
                        image_url,
                        committees_json,
                        finance_report_json,
                        legislator_id,
                    )

                    self.cursor.execute(update_query, update_values)
                    self.connection.commit()
                    logging.debug(f"Updated legislator: {legislator_id}")
                else:
                    logging.debug(
                        f"No changes detected for legislator: {legislator_id}"
                    )
            else:
                logging.debug(
                    f"Legislator {legislator_id} does not exist, inserting new record."
                )
                guid = str(uuid.uuid4())
                insert_query = """
                    INSERT INTO legislators (guid, id, full_name, format_name, party, district, house, position, address,
                        email, cell, work_phone, service_start, profession, professional_affiliations, education, 
                        recognitions_and_honors, counties, legislation_url, demographic_url, image_url, committees, 
                        finance_report, active, date_entered)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, NOW())
                """
                insert_values = (
                    guid,
                    legislator_id,
                    full_name,
                    format_name,
                    party,
                    district,
                    house,
                    position,
                    address,
                    email,
                    cell,
                    work_phone,
                    service_start,
                    profession,
                    professional_affiliations,
                    education,
                    recognitions_and_honors,
                    counties,
                    legislation_url,
                    demographic_url,
                    image_url,
                    committees_json,
                    finance_report_json,
                )

                self.cursor.execute(insert_query, insert_values)
                self.connection.commit()
                logging.debug(f"Inserted legislator: {legislator_id}")

        except pymysql.Error as db_error:
            logging.error(f"MySQL error: {db_error}")
        except Exception as ex:
            logging.error(f"General error: {ex}")

    def deactivate_legislators(self, current_legislator_ids):
        try:
            self.cursor.execute("SELECT id FROM legislators")
            db_legislators = self.cursor.fetchall()

            db_legislator_ids = [row[0] for row in db_legislators]

            missing_legislators = set(db_legislator_ids) - set(current_legislator_ids)

            if missing_legislators:
                for legislator_id in missing_legislators:
                    logging.debug(f"Deleting legislator: {legislator_id}")
                    self.cursor.execute(
                        "UPDATE legislators SET active = 0 WHERE id = %s",
                        (legislator_id,),
                    )
                self.connection.commit()
                logging.debug(
                    f"Deleted {len(missing_legislators)} legislators missing from API."
                )
            else:
                logging.debug("No legislators to delete.")
        except pymysql.Error as db_error:
            logging.error(f"MySQL error while deleting missing legislators: {db_error}")

    def close_connection(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def run(self):
        self.setup()
        legislators = self.fetch_legislator_list()
        if legislators:
            logging.debug(
                f"Fetched legislator list successfully. Total legislators: {len(legislators)}"
            )

            current_legislator_ids = []

            for legislator in legislators:
                current_legislator_ids.append(legislator["id"])
                self.insert_or_update_legislator(legislator)

            self.deactivate_legislators(current_legislator_ids)
        else:
            logging.debug("No legislator data fetched.")

        self.close_connection()

    @staticmethod
    def update_legislators():
        etlProcessor = Legislators(
            api_key=settings_data["api"]["utle"],
            db_host=settings_data["database"]["host"],
            db_user=settings_data["database"]["user"],
            db_password=settings_data["database"]["password"],
            db_name=settings_data["database"]["schema"],
        )
        etlProcessor.run()


if __name__ == "__main__":
    Legislators.update_legislators()
