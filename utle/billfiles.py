import requests
import pymysql
import logging
from datetime import datetime
from cachetools import cached, TTLCache
from .settings import settings_data

class UtahLegislatureFiles:
    billfile_cache = TTLCache(maxsize=1024, ttl=360)
    legislator_cache = TTLCache(maxsize=1024, ttl=360)

    def __init__(self, db_host, db_user, db_password, db_name, api_key, session, year):
        self.api_key = api_key
        self.db_host = db_host
        self.db_user = db_user
        self.db_password = db_password
        self.db_name = db_name
        self.session = session
        self.year = year
        self.base_file_url = None
        self.file_list_url = None
        self.connection = None
        self.cursor = None

    def setup(self):
        logging.basicConfig(
            level=settings_data["global"]["loglevel"],
            filename="billfiles.log",
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.debug("Setting up UtahLegislature instance for bill files...")
        self.base_file_url = "https://glen.le.utah.gov/bills/{year}{session}/".format(
            year=self.year, session=self.session
        )
        self.file_list_url = "{base_file_url}filelist/{api_key}".format(
            base_file_url=self.base_file_url, api_key=self.api_key
        )
        logging.debug(
            "Base file URL: {}, File list URL: {}".format(
                self.base_file_url, self.file_list_url
            )
        )
        self.connection = pymysql.connect(
            host=self.db_host,
            user=self.db_user,
            password=self.db_password,
            database=self.db_name,
        )
        self.cursor = self.connection.cursor()
        logging.debug("Database connection established.")
        logging.debug(
            "Setup complete. Base file URL: {}, File list URL: {}".format(
                self.base_file_url, self.file_list_url
            )
        )

    @cached(billfile_cache)
    def fetch_file_list_data(self):
        try:
            logging.debug("Fetching file list data...")
            file_list_response = requests.get(self.file_list_url)
            if file_list_response.status_code == 200:
                file_list_data = file_list_response.json()
                if "files" in file_list_data:
                    logging.debug("Fetched file list data successfully.")
                    return file_list_data["files"]
                else:
                    logging.error("Invalid JSON response: 'files' key not found")
                    return None
            else:
                logging.error(
                    f"API request failed with status code: {file_list_response.status_code}"
                )
                return None
        except (requests.exceptions.RequestException, ValueError, KeyError) as error:
            logging.error(f"Error fetching file list data: {error}")
            return None

    def insert_or_update_file(self, file_data):
        try:
            tracking_id = file_data["trackingid"]
            logging.debug("Processing file for Insert or Update: {}".format(tracking_id))
            short_title = file_data["shorttitle"]
            sponsor_id = file_data["sponsor"]
            status = file_data["status"]

            # Fetch formatted name of the sponsor
            sponsor = self.get_formatted_name(sponsor_id) if sponsor_id else None

            # Check if the record exists based on tracking_id, year, and session
            self.cursor.execute(
                "SELECT * FROM billfiles WHERE tracking_id = %s AND year = %s AND session = %s",
                (tracking_id, self.year, self.session),
            )
            existing_file = self.cursor.fetchone()

            if existing_file:
                # Check if any data has changed
                if (
                    existing_file[3] != short_title
                    or existing_file[4] != sponsor
                    or existing_file[5] != status
                ):
                    update_query = (
                        "UPDATE billfiles SET short_title = %s, sponsor = %s, status = %s WHERE tracking_id = %s AND year = %s AND session = %s"
                    )
                    update_values = (short_title, sponsor, status, tracking_id, self.year, self.session)
                    self.cursor.execute(update_query, update_values)
                    self.connection.commit()
            else:
                # Insert new record with year and session
                insert_query = "INSERT INTO billfiles (tracking_id, year, session, short_title, sponsor, status) VALUES (%s, %s, %s, %s, %s, %s)"
                insert_values = (tracking_id, self.year, self.session, short_title, sponsor, status)
                self.cursor.execute(insert_query, insert_values)
                self.connection.commit()
                logging.debug("Inserted file: {}".format(tracking_id))
        except pymysql.Error as db_error:
            logging.error("MySQL error: {}".format(db_error))

    @cached(legislator_cache)
    def get_formatted_name(self, legislator_id):
        legislator_url = (
            "https://glen.le.utah.gov/legislator/{legislator_id}/{api_key}".format(
                legislator_id=legislator_id, api_key=self.api_key
            )
        )
        try:
            logging.debug(
                "Fetching formatted name for legislator ID: {}".format(legislator_id)
            )
            response = requests.get(legislator_url, timeout=15)
            if response.status_code == 200:
                legislator_data = response.json()
                formatted_name = legislator_data.get("formatName")
                if formatted_name:
                    logging.debug(
                        "Formatted name retrieved successfully: {}".format(
                            formatted_name
                        )
                    )
                    return formatted_name
                else:
                    logging.debug("Formatted name not found in response.")
                    return None
            else:
                logging.error(
                    "API request failed with status code: {}".format(
                        response.status_code
                    )
                )
                return None
        except (requests.exceptions.RequestException, ValueError) as error:
            logging.error("Error fetching formatted name: {}".format(error))
            return None

    def close_connection(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def run(self):
        self.setup()
        file_list_data = self.fetch_file_list_data()
        if file_list_data:
            logging.debug(
                "Fetched file list data successfully. Total files: {}".format(
                    len(file_list_data)
                )
            )
            for file in file_list_data:
                logging.debug("Processing file: {}".format(file["trackingid"]))
                self.insert_or_update_file(file)
        else:
            logging.debug("No file list data fetched.")
        self.close_connection()

    def import_files(year=None, session="GS"):
        current_year = datetime.now().year
        year = year if year else current_year

        etlProcessor = UtahLegislatureFiles(
            api_key=settings_data["api"]["utle"],
            db_host=settings_data["database"]["host"],
            db_user=settings_data["database"]["user"],
            db_password=settings_data["database"]["password"],
            db_name=settings_data["database"]["schema"],
            session=session,
            year=year,
        )
        etlProcessor.run()


if __name__ == "__main__":
    UtahLegislatureFiles.import_files()
