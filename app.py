# **********************************************************
# * CATEGORY  SOFTWARE
# * GROUP     GOV. AFFAIRS
# * AUTHOR    LANCE HAYNIE <LHAYNIE@SCCITY.ORG>
# * FILE      APP.PY
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
import click
import utle as le
import codelogic as c
from utle.settings import settings_data, version_data
from flask import Flask, jsonify
from flask_restful import Api


@click.group()
def main():
    """Utah Legislature Automation"""


@main.command()
@click.option("--year", type=int, help="Specify the Year")
@click.option("--session", type=str, help="Specify the Session")
def bills(year, session):
    """Process Legislative Bills"""
    if year and session:
        click.echo(f"Processing bills for year {year} and session {session}")
        le.UtahLegislature.import_bills(year=year, session=session)
    else:
        click.echo("Processing bills for current year and general session")
        le.UtahLegislature.import_bills()


@main.command()
@click.option("--year", type=int, help="Specify the Year")
@click.option("--session", type=str, help="Specify the Session")
def billfiles(year, session):
    """Process Legislative Bill Files"""
    if year and session:
        click.echo(f"Processing bill files for year {year} and session {session}")
        le.UtahLegislatureFiles.import_files(year=year, session=session)
    else:
        click.echo("Processing bills for current year and general session")
        le.UtahLegislatureFiles.import_files()


@main.command()
def analysis():
    """Provide an In-depth Analysiss"""
    le.process_analysis()


@main.command()
def billanalysis():
    """Provide an In-depth Analysiss"""
    le.bill_analysis()


@main.command()
def impact():
    """Calculate Impact Analysis"""
    le.process_impact()


@main.command()
def updatecode():
    """Update Utah Code Files"""
    # uc = c.UtahCode()
    # uc.update()
    uc2db = c.UtahCodeDatabase()
    uc2db.update()
    uc2db.close_db_connection()


@main.command()
def train():
    """Train/Fine-Tune LLM"""
    c.train.run()


@main.command()
def codelogic():
    """Interactive Chat"""
    c.interactive.run()


@main.command()
def server():
    """Start the API Server"""
    app = Flask(__name__)
    api = Api(app)

    @app.route("/")
    def http_root():
        return jsonify(
            application=version_data["program"],
            version=version_data["version"],
            environment=settings_data["global"]["env"],
            copyright=version_data["copyright"],
            author=version_data["author"],
        )

    @app.errorhandler(404)
    def page_not_found(e):
        return jsonify(error=str(e)), 404

    c.api.init()
    api.add_resource(c.api, "/chat")

    from waitress import serve

    serve(app, host="0.0.0.0", port=settings_data["global"]["port"])


if __name__ == "__main__":
    main()
