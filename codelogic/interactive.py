# **********************************************************
# * CATEGORY  SOFTWARE
# * GROUP     GOV. AFFAIRS
# * AUTHOR    LANCE HAYNIE <LHAYNIE@SCCITY.ORG>
# * FILE      INTERACTIVE.PY
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
from langchain.chat_models import ChatOpenAI
from types import FunctionType
from llama_index import (
    ServiceContext,
    GPTVectorStoreIndex,
    LLMPredictor,
    PromptHelper,
    SimpleDirectoryReader,
    load_index_from_storage,
)
from utle.settings import settings_data
import sys
import os
import time

os.environ["OPENAI_API_KEY"] = settings_data["api"]["openai"]
from llama_index.node_parser import SimpleNodeParser

from llama_index import StorageContext, load_index_from_storage
from langchain.chat_models import ChatOpenAI

parser = SimpleNodeParser.from_defaults()


def run():
    storage_context = StorageContext.from_defaults(persist_dir="data/")
    index = load_index_from_storage(storage_context)
    query_engine = index.as_query_engine()
    while True:
        text_input = input("You: ")
        response = query_engine.query(text_input)
        print("CodeLogicAI: ", response)
        print("\n")
