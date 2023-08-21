# **********************************************************
# * CATEGORY  SOFTWARE
# * GROUP     GOV. AFFAIRS
# * AUTHOR    LANCE HAYNIE <LHAYNIE@SCCITY.ORG>
# * FILE      BILLS.PY
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
import argparse, requests, json, pymysql, logging, uuid, openai
import os, sys, yaml
from datetime import datetime
from cachetools import cached, TTLCache
from .settings import settings_data

class UtahLegislature:
    cache = TTLCache(maxsize=100, ttl=3600)
    
    def __init__(self, db_host, db_user, db_password, db_name, api_key, ai_api_key, session, year):
        self.api_key = api_key
        self.ai_api_key = ai_api_key
        self.db_host = db_host
        self.db_user = db_user
        self.db_password = db_password
        self.db_name = db_name
        self.session = session
        self.year = year
        self.base_bill_url = None
        self.bill_list_url = None
        self.connection = None
        self.cursor = None

    def setup(self):
        logging.basicConfig(level=logging.DEBUG, filename='bills.log', format='%(asctime)s - %(levelname)s - %(message)s')
        logging.debug("Setting up UtahLegislature instance...")
        self.base_bill_url = "https://glen.le.utah.gov/bills/{year}{session}/".format(year=self.year, session=self.session)
        self.bill_list_url = "{base_bill_url}billlist/{api_key}".format(base_bill_url=self.base_bill_url, api_key=self.api_key)
        logging.debug("Base bill URL: {}, Bill list URL: {}".format(self.base_bill_url, self.bill_list_url))
        self.connection = pymysql.connect(host=self.db_host, user=self.db_user, password=self.db_password, database=self.db_name)
        self.cursor = self.connection.cursor()
        logging.debug("Database connection established.")
        logging.debug("Setup complete. Base bill URL: {}, Bill list URL: {}".format(self.base_bill_url, self.bill_list_url))

    @cached(cache)
    def fetch_bill_list_data(self):
        try:
            logging.debug("Fetching bill list data...")
            bill_list_response = requests.get(self.bill_list_url)
            if bill_list_response.status_code == 200:
                bill_list_data = bill_list_response.json()
                if 'bills' in bill_list_data:
                    logging.debug("Fetched bill list data successfully.")
                    return bill_list_data['bills']
                else:
                    logging.error("Invalid JSON response: 'bills' key not found")
                    return None
            else:
                logging.error(f"API request failed with status code: {bill_list_response.status_code}")
                return None
        except (requests.exceptions.RequestException, ValueError, KeyError) as error:
            logging.error(f"Error fetching bill list data: {error}")
            return None

    @cached(cache)
    def fetch_bill_detail_data(self, bill_number):
        try:
            bill_detail_url = "{base_bill_url}{bill_number}/{api_key}".format(base_bill_url=self.base_bill_url, bill_number=bill_number, api_key=self.api_key)
            bill_detail_response = requests.get(bill_detail_url)
            bill_detail_data = bill_detail_response.json()
            logging.debug("Fetched bill detail data for bill number: {}".format(bill_number))
            return bill_detail_data
        except requests.exceptions.RequestException as error:
            logging.error("Error fetching bill details for bill {}: {}".format(bill_number, error))
            return None

    def insert_or_update_bill(self, bill_data):
        try:
            bill_number = bill_data['bill']
            logging.debug("Processing bill for Insert or Update: {}".format(bill_number))
            last_action_date_str = bill_data['lastactiontime']
            last_action_date = datetime.strptime(last_action_date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            last_action = bill_data['lastaction']
            last_action_owner = bill_data['lastactionowner']
            
            self.cursor.execute("SELECT * FROM bills WHERE bill_number = %s AND bill_year = %s AND session = %s", (bill_number, self.year, self.session))
            existing_bill = self.cursor.fetchone()
            
            sponsor_id = bill_data['sponsor']
            floor_sponsor_id = bill_data['floorsponsor']
            sponsor = self.get_formatted_name(sponsor_id) if sponsor_id else None
            floor_sponsor = self.get_formatted_name(floor_sponsor_id) if floor_sponsor_id else None
            
    
            if existing_bill:
                
                existing_last_action_date = existing_bill[12]
                if last_action_date > existing_last_action_date:
                    update_query = (
                        "UPDATE bills "
                        "SET last_action = %s, last_action_owner = %s, last_action_date = %s, "
                        "sponsor = %s, floor_sponsor = %s "
                        "WHERE bill_number = %s AND bill_year = %s AND session = %s"
                    )
                    update_values = (last_action, last_action_owner, last_action_date,
                                     sponsor, floor_sponsor, bill_number, self.year, self.session)
                    self.cursor.execute(update_query, update_values)
                    self.connection.commit()
            else:
                guid = str(uuid.uuid4())
                highlighted_provisions = bill_data.get('hilightedprovisions', '')
                subjects = ', '.join(bill_data.get('subjects', []))
                code_sections = ', '.join(bill_data.get('codesections', []))
                appropriations = bill_data['monies'].encode('utf-8', 'replace') if 'monies' in bill_data else b''
                analyzed_provisions = self.analyze_provisions(highlighted_provisions)
                bill_link = f"https://le.utah.gov/~{self.year}/bills/static/{bill_number}.html"
                
                insert_query = (
                    "INSERT INTO bills "
                    "(guid, bill_year, session, bill_number, short_title, general_provisions, highlighted_provisions, "
                    "subjects, code_sections, appropriations, last_action, last_action_owner, last_action_date, "
                    "bill_link, sponsor, floor_sponsor, ai_analysis) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                )
                insert_values = (
                    guid, self.year, self.session, bill_number,
                    bill_data.get('shorttitle', ''), bill_data.get('generalprovisions', ''),
                    highlighted_provisions, subjects, code_sections, appropriations,
                    last_action, last_action_owner, last_action_date,
                    bill_link, sponsor, floor_sponsor, analyzed_provisions
                )
                
                self.cursor.execute(insert_query, insert_values)
                self.connection.commit()
                logging.debug("Inserted bill: {} (Year: {}, Session: {})".format(bill_number, self.year, self.session))
        except pymysql.Error as db_error:
            logging.error("MySQL error: {}".format(db_error))

    @cached(cache)
    def analyze_provisions(self, provisions):
        openai.api_key = self.ai_api_key
        prompt = "Summarize in a single sentence whether the highlighted provisions have a potential impact on municipalities in Utah. Then, provide an in-depth analysis of the following provisions: {}\n\nFocus on both positive and negative effects across economic, social, and legal dimensions. Provide insights into local government operations, community resources, resident well-being, and legal frameworks. In your analysis, address specific examples: How might these provisions affect local businesses and tax revenue? Are there implications for community services and residents' quality of life? Do the provisions align with existing municipal laws and regulations? Craft a comprehensive analysis that guides decision-makers in understanding the consequences of these provisions for municipalities.".format(provisions)
        logging.debug("Generating AI analysis for provisions: {}".format(provisions))
        response = openai.Completion.create(
            engine="text-davinci-003", prompt=prompt, max_tokens=1500
        )
        return response.choices[0].text.strip()

    @cached(cache)
    def get_formatted_name(self, legislator_id):
        legislator_url = "https://glen.le.utah.gov/legislator/{legislator_id}/{api_key}".format(legislator_id=legislator_id, api_key=self.api_key)
        try:
            logging.debug("Fetching formatted name for legislator ID: {}".format(legislator_id))
            response = requests.get(legislator_url)
            if response.status_code == 200:
                legislator_data = response.json()
                formatted_name = legislator_data.get('formatName')
                if formatted_name:
                    logging.debug("Formatted name retrieved successfully: {}".format(formatted_name))
                    return formatted_name
                else:
                    logging.debug("Formatted name not found in response.")
                    return None
            else:
                logging.error("API request failed with status code: {}".format(response.status_code))
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
        bill_list_data = self.fetch_bill_list_data()
        if bill_list_data:
            logging.debug("Fetched bill list data successfully. Total bills: {}".format(len(bill_list_data)))
            for bill in bill_list_data:
                logging.debug("Processing bill: {}".format(bill['number']))
                bill_detail_data = self.fetch_bill_detail_data(bill['number'])
                if bill_detail_data:
                    logging.debug("Fetched bill detail data successfully for bill: {}".format(bill['number']))
                    self.insert_or_update_bill(bill_detail_data)
        else:
            logging.debug("No bill list data fetched.")
        self.close_connection()
        
    def import_bills(year=None, session="GS"):
        current_year = datetime.now().year
        year = year if year else current_year

        etlProcessor = UtahLegislature(
            api_key=settings_data["api"]["utle"],
            ai_api_key=settings_data["api"]["openai"],
            db_host=settings_data["database"]["host"],
            db_user=settings_data["database"]["user"],
            db_password=settings_data["database"]["password"],
            db_name=settings_data["database"]["schema"],
            session=session,
            year=year
        )
        etlProcessor.run()

if __name__ == "__main__":
    import_bills()
