# **********************************************************
# * CATEGORY  SOFTWARE
# * GROUP     GOV. AFFAIRS
# * AUTHOR    LANCE HAYNIE <LHAYNIE@SCCITY.ORG>
# * FILE      TRAIN.PY
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
    max_input_size = 4096
    num_outputs = 500
    chunk_size_limit = 1024

    file_metadata = lambda x: {"filename": x}
    reader = SimpleDirectoryReader("utcode/", file_metadata=file_metadata)
    documents = reader.load_data()

    prompt_helper = PromptHelper(
        max_input_size,
        num_outputs,
        chunk_overlap_ratio=0.1,
        chunk_size_limit=chunk_size_limit,
    )

    llm_predictor = LLMPredictor(
        llm=ChatOpenAI(
            temperature=0, model_name="gpt-3.5-turbo", max_tokens=num_outputs
        )
    )

    service_context = ServiceContext.from_defaults(
        llm_predictor=llm_predictor, prompt_helper=prompt_helper
    )

    index = GPTVectorStoreIndex.from_documents(
        documents=documents, service_context=service_context, show_progress=True
    )

    index.storage_context.persist("data/")
    return index
