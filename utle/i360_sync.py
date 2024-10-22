# **********************************************************
# * CATEGORY  SOFTWARE
# * GROUP     GOV. AFFAIRS
# * AUTHOR    LANCE HAYNIE <LHAYNIE@SCCITY.ORG>
# * FILE      I360_SYNC.PY
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
import pymysql
import logging
from .settings import settings_data


class DataSync:
    def __init__(self, db_host, db_user, db_password, db_name):
        self.db_host = db_host
        self.db_user = db_user
        self.db_password = db_password
        self.db_name = db_name
        self.connection = None
        self.cursor = None

    def setup(self):
        logging.basicConfig(
            level=settings_data["global"]["loglevel"],
            filename="datasync.log",
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.debug("Setting up DataSync instance...")
        self.connection = pymysql.connect(
            host=self.db_host,
            user=self.db_user,
            password=self.db_password,
            database=self.db_name,
        )
        self.cursor = self.connection.cursor()
        logging.debug("Database connection established.")

    def bills(self):
        try:
            insert_query = """
            INSERT INTO influence360.bills (
              guid, tracking_id, bill_year, session, bill_number, short_title, 
              general_provisions, highlighted_provisions, subjects, code_sections, 
              appropriations, last_action, last_action_owner, last_action_date, 
              bill_link, sponsor, floor_sponsor, ai_analysis, ai_impact_rating, 
              ai_impact_rating_explanation, level, position, date_entered, is_tracked, 
              created_at, updated_at
            )
            SELECT
              guid,
              tracking_id,
              bill_year,
              session,
              bill_number,
              short_title,
              general_provisions,
              highlighted_provisions,
              subjects,
              code_sections,
              appropriations,
              last_action,
              last_action_owner,
              last_action_date,
              bill_link,
              sponsor,
              floor_sponsor,
              ai_analysis,
              ai_impact_rating,
              ai_impact_rating_explanation,
              level,
              position,
              date_entered,
              0 AS is_tracked,
              date_entered,
              date_entered
            FROM
              govaffairs.bills
            ON DUPLICATE KEY UPDATE
              tracking_id = VALUES(tracking_id),
              bill_year = VALUES(bill_year),
              session = VALUES(session),
              bill_number = VALUES(bill_number),
              short_title = VALUES(short_title),
              general_provisions = VALUES(general_provisions),
              highlighted_provisions = VALUES(highlighted_provisions),
              subjects = VALUES(subjects),
              code_sections = VALUES(code_sections),
              appropriations = VALUES(appropriations),
              last_action = VALUES(last_action),
              last_action_owner = VALUES(last_action_owner),
              last_action_date = VALUES(last_action_date),
              bill_link = VALUES(bill_link),
              sponsor = VALUES(sponsor),
              floor_sponsor = VALUES(floor_sponsor),
              ai_analysis = VALUES(ai_analysis),
              ai_impact_rating = VALUES(ai_impact_rating),
              ai_impact_rating_explanation = VALUES(ai_impact_rating_explanation),
              level = VALUES(level),
              position = VALUES(position),
              created_at = VALUES(date_entered),
              updated_at = VALUES(date_entered);
            """
            logging.debug("Executing bill query...")
            self.cursor.execute(insert_query)
            self.connection.commit()
            logging.debug("Bill data inserted successfully.")

        except pymysql.Error as db_error:
            logging.error(f"MySQL error: {db_error}")
        except Exception as ex:
            logging.error(f"General error: {ex}")

    def billfiles(self):
        try:
            insert_query = """
                INSERT INTO influence360.bill_files (billid, guid, name, status, session, year, is_tracked, sponsor, created_at, updated_at)
                SELECT id, guid, name, status, session, year, 0 AS is_tracked, sponsor, date_entered, date_modified
                FROM govaffairs.bill_files
                ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                status = VALUES(status),
                session = VALUES(session),
                year = VALUES(year),
                sponsor = VALUES(sponsor),
                created_at = VALUES(created_at),
                updated_at = VALUES(updated_at);
            """
            logging.debug("Mogrified query: %s", self.cursor.mogrify(insert_query))
            logging.debug("Executing bill files query...")
            self.cursor.execute(insert_query)
            self.connection.commit()
            logging.debug("Bill files data inserted successfully.")

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
        self.bills()
        self.billfiles()
        self.close_connection()

    @staticmethod
    def sync_data():
        sync = DataSync(
            db_host=settings_data["database"]["host"],
            db_user=settings_data["database"]["user"],
            db_password=settings_data["database"]["password"],
            db_name=settings_data["database"]["schema"],
        )
        sync.run()


if __name__ == "__main__":
    DataSync.sync_data()
