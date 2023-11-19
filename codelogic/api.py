from langchain.chat_models import ChatOpenAI
from types import FunctionType
from llama_index import ServiceContext, GPTVectorStoreIndex, LLMPredictor, PromptHelper, SimpleDirectoryReader, load_index_from_storage
from flask_restful import Resource, Api, request
from flask import jsonify, abort
from utle.settings import settings_data
import sys
import os
import time 

os.environ["OPENAI_API_KEY"] = settings_data["api"]["openai"]
from llama_index.node_parser import SimpleNodeParser

from llama_index import StorageContext, load_index_from_storage
from langchain.chat_models import ChatOpenAI
parser = SimpleNodeParser.from_defaults()

class api(Resource):
    def init():
        global storage_context, index, query_engine
        storage_context = StorageContext.from_defaults(persist_dir="data/")
        index = load_index_from_storage(storage_context)
        query_engine = index.as_query_engine()
    
    def get(self):
        args = request.args
        text = args.get("text", default="", type=str)
        
        response = query_engine.query(text)
        
        return jsonify({'response': 'CodeLogic AI: ' + str(response)})
