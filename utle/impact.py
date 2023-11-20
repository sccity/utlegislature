# **********************************************************
# * CATEGORY  SOFTWARE
# * GROUP     GOV. AFFAIRS
# * AUTHOR    LANCE HAYNIE <LHAYNIE@SCCITY.ORG>
# * FILE      IMPACT.PY
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
import os, sys, yaml, pymysql, openai, time, logging
from .settings import settings_data

class DatabaseConnector:
    def __init__(self, user, password, host, database):
        self.db_config = {
            'user': user,
            'password': password,
            'host': host,
            'db': database
        }
        self.conn = None
        self.cursor = None

    def connect(self):
        try:
            self.conn = pymysql.connect(**self.db_config)
            self.cursor = self.conn.cursor()
        except pymysql.Error as err:
            print(f"Error connecting to the database: {err}")
            raise

    def disconnect(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

class OpenAIConnector:
    def __init__(self, api_key):
        openai.api_key = api_key
        
    def rate_impact(self, text, highlighted_provisions, code_sections, max_retries=5, retry_delay=5):
        for attempt in range(max_retries):
            try:
                role_system = {"role": "system", "content": "You're a legislative analyst for a Utah municipality, tasked with rating the impact of legislative bills on cities in Utah."}
                
                prompt = (
                    "Rate the potential negative impact on Utah municipalities from the provided text on a scale of 1 to 5, using whole numbers only. "
                    "Consider highlighted provisions, impact analysis, and Utah Code references for your rating. "
                    "If the referenced Utah Code is not in the specified categories (10, 11, 13, 17, 17B, 35A, 52, 53, 54, 59, 63A), rate it as 1. "
                    "Areas to consider include local government operations, revenue, budgets, ordinances, and new restrictions on municipalities. "
                    "Be objective; bills related to leisure have less impact than revenue-related bills. "
                    "Bills necessitating local operational changes have a higher impact. "
                    "Provide only the numeric rating based on the mentioned criteria.\n\n"
                    "Provisions: {}\n\nAnalysis: {}\n\nImpacted Utah Code: {}."
                ).format(highlighted_provisions, text, code_sections)

                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[role_system, {"role": "user", "content": prompt}],
                    max_tokens=1
                )
    
                rating = int(response.choices[0].message["content"].strip())
                
                return rating
            except openai.OpenAIError as err:
                print(f"OpenAI API error: {err}")
                if "Rate limit reached" in str(err):
                    print("Rate limit reached. Waiting for 60 seconds...")
                    time.sleep(60)  # Wait for 60 seconds
                elif "Bad gateway" in str(err):
                    print("Retrying in a few seconds...")
                    time.sleep(retry_delay)
                else:
                    print("Error occurred during impact rating calculation. Continuing to the next bill...")
                    break
        return None  # or raise an exception, depending on your needs

class BillProcessor:
    def __init__(self, db_connector, openai_connector):
        self.db_connector = db_connector
        self.openai_connector = openai_connector

    def process_bills(self):
        try:
            self.db_connector.connect()
            self.db_connector.conn.begin()  # Begin a transaction

            self.db_connector.cursor.execute(
                "SELECT guid, ai_analysis, highlighted_provisions, code_sections FROM bills WHERE ai_impact_rating IS NULL OR ai_impact_rating = 0 AND last_action_owner NOT LIKE '%not pass%'"
            )
            rows = self.db_connector.cursor.fetchall()

            for row in rows:
                guid, ai_analysis, highlighted_provisions, code_sections = row
                try:
                    print(f"Processing bill with guid: {guid}")
                    if ai_analysis is not None and ai_analysis.strip():
                        print("Performing impact rating...")
                        rating = self.openai_connector.rate_impact(ai_analysis, highlighted_provisions, code_sections)
                        self.update_bill_rating(guid, rating)
                        self.db_connector.conn.commit()  # Commit changes after each iteration
                    else:
                        print(f"Skipping processing for bill with guid {guid} due to empty or None ai_analysis")
                except Exception as inner_err:
                    print(f"An error occurred while processing bill with guid {guid}: {inner_err}")
                    continue  # Skip to the next bill record on error

            self.db_connector.conn.commit()  # Commit the transaction
        except Exception as process_err:
            print(f"An error occurred while processing bills: {process_err}")
            self.db_connector.conn.rollback()  # Rollback in case of error
        finally:
            self.db_connector.disconnect()

    def update_bill_rating(self, guid, rating):
        update_query = "UPDATE bills SET ai_impact_rating = %s WHERE guid = %s"
        self.db_connector.cursor.execute(update_query, (rating, guid))

def process_impact():
    db_host = settings_data["database"]["host"]
    db_user = settings_data["database"]["user"]
    db_password = settings_data["database"]["password"]
    db_name = settings_data["database"]["schema"]
    openai_api_key = settings_data["api"]["openai"]
    
    db_connector = DatabaseConnector(db_user, db_password, db_host, db_name)
    openai_connector = OpenAIConnector(openai_api_key)
    bill_processor = BillProcessor(db_connector, openai_connector)
    bill_processor.process_bills()
    
if __name__ == "__main__":
    process_impact()
