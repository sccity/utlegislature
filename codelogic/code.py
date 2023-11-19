# **********************************************************
# * CATEGORY  SOFTWARE
# * GROUP     GOV. AFFAIRS
# * AUTHOR    LANCE HAYNIE <LHAYNIE@SCCITY.ORG>
# * FILE      CODE.PY
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
import os
import urllib.request
from xml.etree import ElementTree as ET
from html import escape
from utle.settings import settings_data
from cachetools import cached, TTLCache

class UtahCode:
    cache = TTLCache(maxsize=100, ttl=3600)
    
    def __init__(self):
        self.api = settings_data["api"]["utle"]
    
    @staticmethod
    @cached(cache)
    def get_title_list(list_url):
        with urllib.request.urlopen(list_url) as response:
            return response.read().decode('utf-8')
    
    @cached(cache)
    def get_title_data(self, url):
        with urllib.request.urlopen(url) as response:
            return ET.fromstring(response.read().decode('utf-8'))
    
    def create_txt_file(self, title_number, title_data):
        os.makedirs(os.path.dirname("utcode/"), exist_ok=True)
        with open(f"utcode/uca_title_{title_number}.txt", 'w', encoding='utf-8') as file:
            page_title = f"Utah Code Annotated - Title {title_number} - {title_data.find('.//catchline').text}"
            file.write(f"{page_title}\n{'=' * len(page_title)}\n\n")
    
            chapters = title_data.findall('.//chapter')
            for chapter in chapters:
                chapter_number = chapter.attrib['number'].replace('-', '.')
                chapter_catchline = chapter.find('.//catchline')
                if chapter_catchline is not None:
                    chapter_title = f"Utah Code Annotated - Title {title_number} - Chapter {chapter_number.split('.')[1]} - {chapter_catchline.text}"
                    file.write(f"{chapter_title}\n{'*' * len(chapter_title)}\n\n")
                    
                sections = chapter.findall('.//section')
                for section in sections:
                    section_catchline_text = section.find('.//catchline').text if section.find('.//catchline') is not None else ""
                    section_content = section.find('.//tab').tail.strip() if section.find('.//tab') is not None and section.find('.//tab').tail else ""
                    section_title = f"Utah Code Annotated § {section.attrib['number']} {section_catchline_text}"
                    file.write(f"{section_title}\n{'-' * len(section_title)}\n{section_content}")

                    subsections = section.findall('.//subsection')
                    for subsection in subsections:
                        xrefs = subsection.findall('.//xref')
                        xref_text = "; ".join(xref.text.strip() if xref.text else "" for xref in xrefs)
                        subsection_content = f"{xref_text} {subsection.text.strip()}" if xref_text and subsection.text else (xref_text or subsection.text or "").strip()
                        subsection_title = f"Utah Code Annotated § {subsection.attrib['number']}"
                        file.write(f"{subsection_title}: {subsection_content}\n")
                    
                    file.write("\n\n")

    def update(self):
        list_url = "https://glen.le.utah.gov/code/list/" + self.api
        data_url_template = "https://glen.le.utah.gov/code/{}/" + self.api
    
        title_list_data = self.get_title_list(list_url)
    
        if title_list_data:
            title_data_root = ET.fromstring(title_list_data)
    
            for title_number, _ in [(title.attrib['number'], title.find('.//catchline').text) for title in title_data_root.findall('.//title')]:
                data_url = data_url_template.format(title_number)
                title_data = self.get_title_data(data_url)
    
                if title_data:
                    self.create_txt_file(title_number, title_data)

