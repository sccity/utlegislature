import os
import urllib.request
from xml.etree import ElementTree as ET
import mysql.connector
from cachetools import cached, TTLCache
from utle.settings import settings_data

class UtahCodeDatabase:
    cache = TTLCache(maxsize=100, ttl=3600)

    def __init__(self):
        self.api = settings_data["api"]["utle"]
        self.db_connection = mysql.connector.connect(
            host=settings_data["database"]["host"],
            user=settings_data["database"]["user"],
            password=settings_data["database"]["password"],
            database=settings_data["database"]["schema"]
        )
        self.cursor = self.db_connection.cursor()

        # Create the 'utcode' table if it doesn't exist
        self.create_utcode_table()

    def close_db_connection(self):
        self.cursor.close()
        self.db_connection.close()

    def create_utcode_table(self):
        create_table_query = """
        CREATE TABLE IF NOT EXISTS utcode (
            code_id VARCHAR(255) PRIMARY KEY,
            title_number VARCHAR(50) NOT NULL,
            title_name TEXT,
            chapter_number VARCHAR(50),
            chapter_name TEXT,
            section_number VARCHAR(50),
            section_name TEXT,
            section_content TEXT,
            subsection_number VARCHAR(50),
            xref_text TEXT,
            subsection_content TEXT
        )
        """
        self.cursor.execute(create_table_query)
        self.db_connection.commit()

    @staticmethod
    @cached(cache)
    def get_title_list(list_url):
        with urllib.request.urlopen(list_url) as response:
            return response.read().decode("utf-8")

    @cached(cache)
    def get_title_data(self, url):
        with urllib.request.urlopen(url) as response:
            return ET.fromstring(response.read().decode("utf-8"))

    def insert_or_update(self, table, data):
        # Construct the code_id
        code_id = (
            f"{data['title_number']:03d}"
            f"{data['chapter_number'].replace('-', '') if data['chapter_number'] else '0'}"
            f"{data['section_number'].replace('-', '') if data['section_number'] else '0'}"
            f"{data['subsection_number'].replace('-', '') if data['subsection_number'] else '0'}"
        )

        # Check if the record already exists
        existing_data = self.get_existing_data(table, code_id)

        if existing_data:
            # Update fields that have changed
            update_fields = {key: data[key] for key in data.keys() if data[key] != existing_data[key]}
            if update_fields:
                # Construct the update query with placeholders
                update_query = f"UPDATE {table} SET {', '.join([f'{key} = %s' for key in update_fields.keys()])} WHERE code_id = %s"
                # Use a tuple for the query values
                update_values = tuple(update_fields.values()) + (code_id,)
                # Execute the update query with placeholders
                self.cursor.execute(update_query, update_values)
        else:
            # Record doesn't exist, insert a new one
            insert_query = f"INSERT INTO {table} (code_id, {', '.join(data.keys())}) VALUES (%s, {', '.join(['%s' for _ in data.keys()])})"
            # Use a tuple for the query values
            insert_values = (code_id,) + tuple(data.values())
            # Execute the insert query with placeholders
            self.cursor.execute(insert_query, insert_values)

        # Commit the changes to the database
        self.db_connection.commit()

    def get_existing_data(self, table, code_id):
        # Query the database for existing data
        self.cursor.execute(f"SELECT * FROM {table} WHERE code_id = %s", (code_id,))
        return self.cursor.fetchone()

    def process_title(self, title_number, title_data):
        # Process chapters, sections, and subsections
        chapters = title_data.findall(".//chapter")
        for chapter in chapters:
            chapter_number = chapter.attrib["number"].replace("-", ".")

            # Prepare data for chapter
            chapter_data = {
                'code_id': (
                    f"{title_number:03d}"
                    f"{chapter_number.replace('-', '') if chapter_number else '0'}000"
                ),
                'title_number': f"{title_number:03d}",
                'chapter_number': chapter_number,
                'chapter_name': chapter.find(".//catchline").text if chapter.find(".//catchline") is not None else ""
            }

            # Insert or update chapter information
            self.insert_or_update('utcode', chapter_data)

            sections = chapter.findall(".//section")
            for section in sections:
                section_number = section.attrib['number']

                # Prepare data for section
                section_data = {
                    'code_id': (
                        f"{title_number:03d}"
                        f"{chapter_number.replace('-', '') if chapter_number else '0'}"
                        f"{section_number.replace('-', '') if section_number else '0'}00"
                    ),
                    'title_number': f"{title_number:03d}",
                    'chapter_number': chapter_number,
                    'section_number': section_number,
                    'section_name': section.find(".//catchline").text if section.find(".//catchline") is not None else "",
                    'section_content': section.find(".//tab").tail.strip() if section.find(".//tab") is not None and section.find(".//tab").tail else ""
                }

                # Insert or update section information
                self.insert_or_update('utcode', section_data)

                # Insert or update subsection information
                subsections = section.findall(".//subsection")
                for subsection in subsections:
                    subsection_number = subsection.attrib['number']
                    xrefs = subsection.findall(".//xref")
                    xref_text = "; ".join(xref.text.strip() if xref.text else "" for xref in xrefs)

                    # Prepare data for subsection
                    subsection_data = {
                        'code_id': (
                            f"{title_number:03d}"
                            f"{chapter_number.replace('-', '') if chapter_number else '0'}"
                            f"{section_number.replace('-', '') if section_number else '0'}"
                            f"{subsection_number.replace('-', '') if subsection_number else '0'}"
                        ),
                        'title_number': f"{title_number:03d}",
                        'chapter_number': chapter_number,
                        'section_number': section_number,
                        'subsection_number': subsection_number,
                        'xref_text': xref_text,
                        'subsection_content': subsection.text.strip() if subsection.text else ""
                    }

                    # Insert or update subsection information
                    self.insert_or_update('utcode', subsection_data)

    def update(self):
        list_url = "https://glen.le.utah.gov/code/list/" + self.api
        data_url_template = "https://glen.le.utah.gov/code/{}/" + self.api

        title_list_data = self.get_title_list(list_url)

        if title_list_data:
            title_data_root = ET.fromstring(title_list_data)

            for title_number, _ in [
                (title.attrib["number"], title.find(".//catchline").text)
                for title in title_data_root.findall(".//title")
            ]:
                data_url = data_url_template.format(title_number)
                title_data = self.get_title_data(data_url)

                if title_data:
                    self.process_title(title_number, title_data)

if __name__ == "__main__":
    utah_code_db = UtahCodeDatabase()
    utah_code_db.update()
    utah_code_db.close_db_connection()
