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
from utle.settings import settings_data, version_data


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
def legislators():
    """Process Legislator Information"""
    le.Legislators.update_legislators()

@main.command()
def committees():
    """Process Committee Information"""
    le.Committees.update_committees()

@main.command()
def calendar():
    """Process Legislative Calendar"""
    le.LegislativeCalendar.update_calendar()

@main.command()
def i360():
    """Sync I360 Data"""
    le.DataSync.sync_data()


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

if __name__ == "__main__":
    main()
