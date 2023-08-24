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
import argparse
import utle as le

def bills(year, session):
    if year and session:
        print(f"Processing bills for year {year} and session {session}")
        le.UtahLegislature.import_bills(year=year, session=f"{session}")
    else:
        print("Processing bills for current year and general session")
        le.UtahLegislature.import_bills()

def main():
    parser = argparse.ArgumentParser(description="Utah Legislature Automation")
    subparsers = parser.add_subparsers(dest="command", help="Choose a Command")

    bills_parser = subparsers.add_parser("bills", help="Process Legislative Bills")
    bills_parser.add_argument("--year", type=int, help="Specify the Year")
    bills_parser.add_argument("--session", type=str, help="Specify the Session")

    analysis_parser = subparsers.add_parser("impact", help="Provide an in-depth analysis")
    
    impact_parser = subparsers.add_parser("analysis", help="Calculate Impact Ratings")

    args = parser.parse_args()

    if args.command == "bills":
        bills(args.year, args.session)
    elif args.command == "impact":
        le.process_impact()
    elif args.command == "analysis":
        le.process_analysis()
    else:
        print("Invalid command. Use 'bills' or 'impact'.")

if __name__ == "__main__":
    main()
