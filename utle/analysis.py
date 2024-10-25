# **********************************************************
# * CATEGORY  SOFTWARE
# * GROUP     GOV. AFFAIRS
# * AUTHOR    LANCE HAYNIE <LHAYNIE@SCCITY.ORG>
# * FILE      ANALYSIS.PY
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
import logging
import os
import sys
import time

import pymysql
import yaml
from openai import AsyncOpenAI, OpenAI

from .database import connect
from .settings import settings_data


class OpenAIConnector:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    def get_options(self):
        try:
            db = connect()
            cursor = db.cursor()

            query = """
                SELECT name, value 
                FROM options 
                WHERE name IN ('analysis_system_prompt', 'analysis_prompt')
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()
            db.close()

            prompt_data = {}
            for row in rows:
                name, value = row
                prompt_data[name] = value

            return prompt_data
        except Exception as e:
            print(f"Error fetching prompt data from database: {e}")
            return None

    def analyze_provisions(self, provisions):
        prompt_data = self.get_options()
        if prompt_data is None:
            return "Error: Could not fetch prompt data."

        role_system_value = prompt_data.get("score_system_prompt", "")
        prompt_value = prompt_data.get("score_prompt", "")

        role_system = {"role": "system", "content": role_system_value}

        prompt = prompt_value.replace("{provisions}", provisions)

        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[role_system, {"role": "user", "content": prompt}],
        )

        return response.choices[0].message.content.strip()


class BillProcessor:
    def __init__(self, openai_connector):
        self.openai_connector = openai_connector

    def process_bills(self):
        try:
            db = connect()
            cursor = db.cursor()

            cursor.execute(
                "SELECT guid, highlighted_provisions FROM bills WHERE ai_analysis IS NULL AND last_action_owner NOT LIKE '%not pass%' and bill_year >= 2024"
            )
            rows = cursor.fetchall()
            cursor.close()
            db.close()

            for row in rows:
                id, highlighted_provisions = row
                try:
                    print(f"Processing bill with id: {id}")
                    if (
                        highlighted_provisions is not None
                        and highlighted_provisions.strip()
                    ):
                        print("Performing analysis...")
                        analysis = self.openai_connector.analyze_provisions(
                            highlighted_provisions
                        )
                        self.update_bill_analysis(id, analysis)
                    else:
                        print(
                            f"Skipping processing for bill with id {id} due to empty or None highlighted_provisions"
                        )
                except Exception as inner_err:
                    print(
                        f"An error occurred while processing bill with id {id}: {inner_err}"
                    )
                    continue

        except Exception as process_err:
            print(f"An error occurred while processing bills: {process_err}")
            cursor.close()
            db.close()

    def update_bill_analysis(self, id, analysis):
        try:
            db = connect()
            cursor = db.cursor()
            update_query = "UPDATE bills SET ai_analysis = %s WHERE guid = %s"
            cursor.execute(update_query, (analysis, id))
            db.commit()
            cursor.close()
            db.close()
        except Exception as err:
            print(f"An error occurred while updating analysis: {err}")
            cursor.close()
            db.close()


def process_analysis():
    openai_api_key = settings_data["api"]["openai"]
    openai_connector = OpenAIConnector(openai_api_key)
    bill_processor = BillProcessor(openai_connector)
    bill_processor.process_bills()


if __name__ == "__main__":
    process_analysis()
