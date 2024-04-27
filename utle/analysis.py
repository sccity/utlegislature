# **********************************************************
# * CATEGORY  SOFTWARE
# * GROUP     GOV. AFFAIRS
# * AUTHOR    LANCE HAYNIE <LHAYNIE@SCCITY.ORG>
# * FILE      ANALYSIS.PY
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
from .settings import settings_data
from .database import connect

class OpenAIConnector:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

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
            f"Then, provide an in-depth one page analysis of the following provisions: {provisions}\n\n"
            f"Focus on both positive and negative effects across economic, social, and legal dimensions. "
            f"Provide insights into local government operations, community resources, resident well-being, and legal frameworks. "
            f"In your analysis, address specific examples: How might these provisions affect local businesses and tax revenue? "
            f"Are there implications for community services and residents' quality of life? Do the provisions align with existing municipal laws and regulations? "
            f"Craft a comprehensive analysis that ides decision-makers in understanding the consequences of these provisions for municipalities."
        )

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
                "SELECT id, highlighted_provisions FROM utle_bills WHERE ai_analysis IS NULL AND last_action_owner NOT LIKE '%not pass%' and bill_year >= 2023"
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
            update_query = "UPDATE utle_bills SET ai_analysis = %s WHERE id = %s"
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
