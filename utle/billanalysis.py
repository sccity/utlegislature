# **********************************************************
# * CATEGORY  SOFTWARE
# * GROUP     GOV. AFFAIRS
# * AUTHOR    LANCE HAYNIE <LHAYNIE@SCCITY.ORG>
# * FILE      BILLANALYSIS.PY
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
import os, sys, time, logging, requests
from PyPDF2 import PdfReader
from openai import AsyncOpenAI, OpenAI
from .settings import settings_data
from .database import connect


class OpenAIConnector:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    def split_bill(self, bill_text, lines_per_page=60):
        lines = bill_text.split("\n")
        return [
            lines[i : i + lines_per_page] for i in range(0, len(lines), lines_per_page)
        ]

    def summarize_page(self, text):
        role_system = {
            "role": "system",
            "content": (
                "You are a legislative analyst familiar with Utah municipal affairs. "
                "Your task is to review and analyze legislative bills. "
                "You will review a single page of a bill and give a brief summary between 1 to 3 sentences. "
            ),
        }

        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[role_system, {"role": "user", "content": text}],
        )
        return response.choices[0].message.content.strip()

    def summarize_bill(self, text):
        role_system = {
            "role": "system",
            "content": (
                "You are a legislative analyst familiar with Utah municipal affairs. "
                "Your task is to review and analyze page summaries from a bill and create an overall summary and in-depth analysis. "
                "Craft a comprehensive analysis that aids decision-makers in understanding the impacts of the bill. "
            ),
        }

        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[role_system, {"role": "user", "content": text}],
        )
        return response.choices[0].message.content.strip()

    def analyze_bill(self, bill_text):
        pages = self.split_bill(bill_text, 60)

        summarized_pages = [self.summarize_page("\n".join(page)) for page in pages]
        summary = self.summarize_bill("\n".join(summarized_pages))

        return summary


class BillProcessor:
    def __init__(self, openai_connector):
        self.openai_connector = openai_connector

    def process_bills(self):
        print("getting bills to analyze")
        try:
            db = connect()
            cursor = db.cursor()
            cursor.execute(
                "SELECT id, bill_text, pdflink FROM aia_billanalysis WHERE ai_analysis IS NULL or ai_analysis = ''"
            )
            rows = cursor.fetchall()
            cursor.close()
            db.close()

            print("looping over bills")
            for row in rows:
                try:
                    print("unpacking values")
                    bill_id, bill_text, pdflink = row  # Unpack values from the row

                    print(f"Processing bill with id: {bill_id}")

                    if bill_text is None and pdflink is not None:
                        print("processing bills with a pdf")
                        try:
                            print("downloading pdf")
                            response = requests.get(pdflink)
                            response.raise_for_status() 
                            with open("/tmp/bill.pdf", "wb") as pdf_file:
                                pdf_file.write(response.content)

                            text = ""
                            print("converting pdf to txt")
                            with open("/tmp/bill.pdf", "rb") as pdf_file:
                                pdf_reader = PdfReader(pdf_file)
                                for page_num in range(len(pdf_reader.pages)):
                                    text += pdf_reader.pages[page_num].extract_text()

                            db = connect()
                            cursor = db.cursor()
                            print("updating bill text in table")
                            update_sql = "UPDATE aia_billanalysis SET bill_text = %s WHERE id = %s"
                            cursor.execute(update_sql, (text, bill_id))
                            db.commit()
                            cursor.close()
                            db.close()

                            print("analyzing text with ai")
                            analysis = self.openai_connector.analyze_bill(text)
                            print("updating analysis to table")
                            self.update_bill_analysis(bill_id, analysis)

                        except requests.exceptions.RequestException as req_err:
                            print(
                                f"Error fetching PDF for bill with id {bill_id}: {req_err}"
                            )
                            continue

                    elif bill_text is not None and bill_text.strip():
                        print("processing bills with bill text but no pdf")
                        try:
                            print("Performing analysis...")
                            analysis = self.openai_connector.analyze_bill(bill_text)
                            self.update_bill_analysis(bill_id, analysis)
                        except Exception as analysis_err:
                            print(
                                f"Error performing analysis for bill with id {bill_id}: {analysis_err}"
                            )
                    else:
                        print(
                            f"Skipping processing for bill with id {bill_id} due to empty or None bill_text"
                        )

                except Exception as outer_err:
                    print(
                        f"An error occurred while processing bill with id {bill_id}: {outer_err}"
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
            update_query = "UPDATE aia_billanalysis SET ai_analysis = %s WHERE id = %s"
            cursor.execute(update_query, (analysis, id))
            db.commit()
            cursor.close()
            db.close()
        except Exception as err:
            print(f"An error occurred while updating analysis: {err}")
            cursor.close()
            db.close()


def bill_analysis():
    openai_api_key = settings_data["api"]["openai"]
    openai_connector = OpenAIConnector(openai_api_key)
    bill_processor = BillProcessor(openai_connector)

    while True:
        try:
            bill_processor.process_bills()
            time.sleep(60)
        except Exception as e:
            print(f"An error occurred: {e}")


if __name__ == "__main__":
    bill_analysis()
