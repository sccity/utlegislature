# **********************************************************
# * CATEGORY  SOFTWARE
# * GROUP     GOV. AFFAIRS
# * AUTHOR    LANCE HAYNIE <LHAYNIE@SCCITY.ORG>
# * FILE      SCORE.PY
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
import uuid
from openai import AsyncOpenAI, OpenAI
from .settings import settings_data
from .database import connect


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
                WHERE name IN ('score_system_prompt', 'score_prompt')
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

    def score_bill(self, bill_report):
        prompt_data = self.get_options()
        if prompt_data is None:
            return "Error: Could not fetch prompt data."

        role_system_value = prompt_data.get("score_system_prompt", "")
        prompt_value = prompt_data.get("score_prompt", "")

        role_system = {"role": "system", "content": role_system_value}

        prompt = prompt_value.replace("{provisions}", bill_report)

        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[role_system, {"role": "user", "content": prompt}],
        )

        return response.choices[0].message.content.strip()

    def parse_scores(self, analysis):
        score_mapping = {
            "PREEMPTION": None,
            "PARTNERSHIP": None,
            "LOCAL_CONTROL": None,
            "UNFUNDED_MANDATE": None,
            "FLEXIBILITY": None,
            "FISCAL_IMPACT": None,
            "UNIVERSAL_APPROACH": None,
        }
        detail_mapping = {
            "PREEMPTION": "",
            "PARTNERSHIP": "",
            "LOCAL_CONTROL": "",
            "UNFUNDED_MANDATE": "",
            "FLEXIBILITY": "",
            "FISCAL_IMPACT": "",
            "UNIVERSAL_APPROACH": "",
        }

        lines = analysis.split("\n")

        for line in lines:
            line = line.strip()

            if line.startswith("PREEMPTION:"):
                score_mapping["PREEMPTION"] = int(line.split(":")[1].strip())
            elif line.startswith("PARTNERSHIP:"):
                score_mapping["PARTNERSHIP"] = int(line.split(":")[1].strip())
            elif line.startswith("LOCAL_CONTROL:"):
                score_mapping["LOCAL_CONTROL"] = int(line.split(":")[1].strip())
            elif line.startswith("UNFUNDED_MANDATE:"):
                score_mapping["UNFUNDED_MANDATE"] = int(line.split(":")[1].strip())
            elif line.startswith("FLEXIBILITY:"):
                score_mapping["FLEXIBILITY"] = int(line.split(":")[1].strip())
            elif line.startswith("FISCAL_IMPACT:"):
                score_mapping["FISCAL_IMPACT"] = int(line.split(":")[1].strip())
            elif line.startswith("UNIVERSAL_APPROACH:"):
                score_mapping["UNIVERSAL_APPROACH"] = int(line.split(":")[1].strip())

            elif line.startswith("PREEMPTION_DETAIL:"):
                detail_mapping["PREEMPTION"] = line.split("PREEMPTION_DETAIL:")[
                    1
                ].strip()
            elif line.startswith("PARTNERSHIP_DETAIL:"):
                detail_mapping["PARTNERSHIP"] = line.split("PARTNERSHIP_DETAIL:")[
                    1
                ].strip()
            elif line.startswith("LOCAL_CONTROL_DETAIL:"):
                detail_mapping["LOCAL_CONTROL"] = line.split("LOCAL_CONTROL_DETAIL:")[
                    1
                ].strip()
            elif line.startswith("UNFUNDED_MANDATE_DETAIL:"):
                detail_mapping["UNFUNDED_MANDATE"] = line.split(
                    "UNFUNDED_MANDATE_DETAIL:"
                )[1].strip()
            elif line.startswith("FLEXIBILITY_DETAIL:"):
                detail_mapping["FLEXIBILITY"] = line.split("FLEXIBILITY_DETAIL:")[
                    1
                ].strip()
            elif line.startswith("FISCAL_IMPACT_DETAIL:"):
                detail_mapping["FISCAL_IMPACT"] = line.split("FISCAL_IMPACT_DETAIL:")[
                    1
                ].strip()
            elif line.startswith("UNIVERSAL_APPROACH_DETAIL:"):
                detail_mapping["UNIVERSAL_APPROACH"] = line.split(
                    "UNIVERSAL_APPROACH_DETAIL:"
                )[1].strip()

        return score_mapping, detail_mapping


class BillProcessor:
    def __init__(self, openai_connector):
        self.openai_connector = openai_connector

    def process_bills(self):
        try:
            db = connect()
            cursor = db.cursor()

            query = """
                SELECT b.guid, b.ai_analysis 
                FROM bills b 
                LEFT JOIN bill_scores bs ON b.guid = bs.bill_guid 
                WHERE b.ai_analysis IS NOT NULL 
                AND b.bill_year >= 2023 
                AND bs.guid IS NULL
            """

            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()
            db.close()

            for row in rows:
                bill_guid, ai_analysis = row
                try:
                    print(f"Processing bill with GUID: {bill_guid}")
                    if ai_analysis is not None and ai_analysis.strip():
                        print("Performing score analysis...")
                        analysis = self.openai_connector.score_bill(ai_analysis)
                        score_mapping, detail_mapping = (
                            self.openai_connector.parse_scores(analysis)
                        )
                        self.insert_bill_score(bill_guid, score_mapping, detail_mapping)
                    else:
                        print(
                            f"Skipping processing for bill with GUID {bill_guid} due to empty or None ai_analysis"
                        )
                except Exception as inner_err:
                    print(
                        f"An error occurred while processing bill with GUID {bill_guid}: {inner_err}"
                    )
                    continue

        except Exception as process_err:
            print(f"An error occurred while processing bills: {process_err}")
            cursor.close()
            db.close()

    def insert_bill_score(self, bill_guid, score_mapping, detail_mapping):
        try:
            db = connect()
            cursor = db.cursor()

            guid = str(uuid.uuid4())

            insert_query = """
                INSERT IGNORE INTO bill_scores 
                    (guid, bill_guid, preemption_score, preemption_detail, 
                    partnership_score, partnership_detail, 
                    local_control_score, local_control_detail, 
                    unfunded_mandate_score, unfunded_mandate_detail, 
                    flexibility_score, flexibility_detail, 
                    fiscal_impact_score, fiscal_impact_detail, 
                    universal_approach_score, universal_approach_detail) 
                VALUES 
                    (%s, %s, %s, %s, 
                    %s, %s, 
                    %s, %s, 
                    %s, %s, 
                    %s, %s, 
                    %s, %s, 
                    %s, %s)
            """

            cursor.execute(
                insert_query,
                (
                    guid,
                    bill_guid,
                    score_mapping["PREEMPTION"],
                    detail_mapping["PREEMPTION"],
                    score_mapping["PARTNERSHIP"],
                    detail_mapping["PARTNERSHIP"],
                    score_mapping["LOCAL_CONTROL"],
                    detail_mapping["LOCAL_CONTROL"],
                    score_mapping["UNFUNDED_MANDATE"],
                    detail_mapping["UNFUNDED_MANDATE"],
                    score_mapping["FLEXIBILITY"],
                    detail_mapping["FLEXIBILITY"],
                    score_mapping["FISCAL_IMPACT"],
                    detail_mapping["FISCAL_IMPACT"],
                    score_mapping["UNIVERSAL_APPROACH"],
                    detail_mapping["UNIVERSAL_APPROACH"],
                ),
            )

            db.commit()
            cursor.close()
            db.close()

        except Exception as err:
            print(
                f"An error occurred while inserting scores for bill with GUID {bill_guid}: {err}"
            )
            cursor.close()
            db.close()


def process_scores():
    openai_api_key = settings_data["api"]["openai"]
    openai_connector = OpenAIConnector(openai_api_key)
    bill_processor = BillProcessor(openai_connector)
    bill_processor.process_bills()


if __name__ == "__main__":
    process_scores()
