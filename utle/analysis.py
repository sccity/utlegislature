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
import os, sys, yaml, pymysql, time, logging
from openai import AsyncOpenAI, OpenAI
from cachetools import cached, TTLCache
from .settings import settings_data


class DatabaseConnector:
    def __init__(self, user, password, host, database):
        self.db_config = {
            "user": user,
            "password": password,
            "host": host,
            "db": database,
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
    cache = TTLCache(maxsize=100, ttl=3600)

    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    @cached(cache)
    def analyze_provisions(self, provisions):
        role_system = {
            "role": "system",
            "content": (
                "You are a legislative analyst familiar with Utah municipal affairs. "
                "Your task is to review and analyze legislative bills that could impact municipalities in Utah. "
                "Your analysis should cover economic, social, and legal aspects, considering local government operations, "
                "community resources, resident well-being, and legal frameworks. Provide insights into potential effects on local businesses, "
                "tax revenue, community services, and residents' quality of life. Your goal is to offer comprehensive insights "
                "that aid decision-makers in understanding the potential consequences of these provisions for Utah municipalities."
            ),
        }
        prompt = (
            f"Summarize in a single sentence whether the highlighted provisions have a potential impact on municipalities in Utah. "
            f"Then, provide an in-depth analysis of the following provisions: {provisions}\n\n"
            f"Focus on both positive and negative effects across economic, social, and legal dimensions. "
            f"Provide insights into local government operations, community resources, resident well-being, and legal frameworks. "
            f"In your analysis, address specific examples: How might these provisions affect local businesses and tax revenue? "
            f"Are there implications for community services and residents' quality of life? Do the provisions align with existing municipal laws and regulations? "
            f"Craft a comprehensive analysis that guides decision-makers in understanding the consequences of these provisions for municipalities."
        )
        
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[role_system, {"role": "user", "content": prompt}],
        )

        return response.choices[0].message.content.strip()


class BillProcessor:
    def __init__(self, db_connector, openai_connector):
        self.db_connector = db_connector
        self.openai_connector = openai_connector

    def process_bills(self):
        try:
            self.db_connector.connect()
            self.db_connector.conn.begin()  # Begin a transaction

            self.db_connector.cursor.execute(
                "SELECT guid, highlighted_provisions FROM bills WHERE ai_analysis IS NULL AND last_action_owner NOT LIKE '%not pass%'"
            )
            rows = self.db_connector.cursor.fetchall()

            for row in rows:
                guid, highlighted_provisions = row
                try:
                    print(f"Processing bill with guid: {guid}")
                    if (
                        highlighted_provisions is not None
                        and highlighted_provisions.strip()
                    ):
                        print("Performing analysis...")
                        analysis = self.openai_connector.analyze_provisions(
                            highlighted_provisions
                        )
                        self.update_bill_analysis(guid, analysis)
                        self.db_connector.conn.commit()  # Commit changes after each iteration
                    else:
                        print(
                            f"Skipping processing for bill with guid {guid} due to empty or None highlighted_provisions"
                        )
                except Exception as inner_err:
                    print(
                        f"An error occurred while processing bill with guid {guid}: {inner_err}"
                    )
                    continue  # Skip to the next bill record on error

            self.db_connector.conn.commit()  # Commit the transaction
        except Exception as process_err:
            print(f"An error occurred while processing bills: {process_err}")
            self.db_connector.conn.rollback()  # Rollback in case of error
        finally:
            self.db_connector.disconnect()

    def update_bill_analysis(self, guid, analysis):
        update_query = "UPDATE bills SET ai_analysis = %s WHERE guid = %s"
        self.db_connector.cursor.execute(update_query, (analysis, guid))


def process_analysis():
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
