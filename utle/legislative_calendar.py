import requests
import pymysql
import logging
import uuid
from datetime import datetime, timedelta
import pytz
from cachetools import cached, TTLCache
from dateutil.relativedelta import relativedelta
from calendar import monthrange
from .settings import settings_data


class LegislativeCalendar:
    calendar_cache = TTLCache(maxsize=1024, ttl=360)

    def __init__(self, db_host, db_user, db_password, db_name, api_key):
        self.api_key = api_key
        self.db_host = db_host
        self.db_user = db_user
        self.db_password = db_password
        self.db_name = db_name
        self.base_url = "https://le.utah.gov/CalServ/CalServ"
        self.connection = None
        self.cursor = None

    def setup(self):
        logging.basicConfig(
            level=settings_data["global"]["loglevel"],
            filename="legislative_calendar.log",
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.debug("Setting up Legislative Calendar instance...")
        self.connection = pymysql.connect(
            host=self.db_host,
            user=self.db_user,
            password=self.db_password,
            database=self.db_name,
        )
        self.cursor = self.connection.cursor()
        logging.debug("Database connection established.")

    @cached(calendar_cache)
    def fetch_calendar(self, month, year):
        try:
            logging.debug(f"Fetching legislative calendar for {month}/{year}...")
            response = requests.get(f"{self.base_url}?month={month}&year={year}")
            if response.status_code == 200:
                calendar_data = response.json()
                return calendar_data.get("days", [])
            else:
                logging.error(
                    f"API request failed with status code: {response.status_code}"
                )
                return []
        except (requests.exceptions.RequestException, ValueError) as error:
            logging.error(f"Error fetching calendar data: {error}")
            return []

    def prepend_url(self, url):
        if url and not url.startswith("https://"):
            return f"https://le.utah.gov{url}"
        return url

    def insert_or_update_calendar(self, event_item, event_date):
        try:
            description = event_item.get("desc", "")
            link = self.prepend_url(event_item.get("itemurl", ""))
            agenda_url = self.prepend_url(event_item.get("agenda", ""))
            minutes_url = self.prepend_url(event_item.get("minutes", ""))
            media_url = self.prepend_url(event_item.get("mediaurl", ""))
            emtg_url = self.prepend_url(event_item.get("emtg", ""))
            ics_url = self.prepend_url(event_item.get("ics", ""))
            meeting_id = self.extract_meeting_id(link)
            event_type = event_item.get("type", "")
            start_time_str = event_item.get("time", "")
            end_time_str = event_item.get("endtime", "")
            location = event_item.get("location", "")

            start_time = self.convert_time(start_time_str)
            end_time = None

            if start_time and end_time_str:
                end_time = self.convert_time(end_time_str)
            elif start_time:
                end_time = (
                    datetime.combine(datetime.today(), start_time) + timedelta(hours=1)
                ).time()

            logging.debug(f"Processing event: {description} on {event_date}")

            self.cursor.execute(
                """
                SELECT agenda_url, minutes_url, media_url, emtg_url, ics_url, start_time, end_time, location
                FROM legislative_calendar
                WHERE description = %s AND event_type = %s AND mtg_date = %s
                """,
                (description, event_type, event_date),
            )
            existing_event = self.cursor.fetchone()

            if existing_event:
                (
                    existing_agenda_url,
                    existing_minutes_url,
                    existing_media_url,
                    existing_emtg_url,
                    existing_ics_url,
                    existing_start_time,
                    existing_end_time,
                    existing_location,
                ) = existing_event

                if (
                    existing_agenda_url != agenda_url
                    or existing_minutes_url != minutes_url
                    or existing_media_url != media_url
                    or existing_emtg_url != emtg_url
                    or existing_ics_url != ics_url
                    or existing_start_time != start_time
                    or existing_end_time != end_time
                    or existing_location != location
                ):
                    logging.debug(f"Updating event: {description}")
                    update_query = """
                        UPDATE legislative_calendar
                        SET agenda_url = %s, minutes_url = %s, media_url = %s, emtg_url = %s, ics_url = %s,
                            start_time = %s, end_time = %s, location = %s, date_modified = NOW()
                        WHERE description = %s AND event_type = %s AND mtg_date = %s
                    """
                    self.cursor.execute(
                        update_query,
                        (
                            agenda_url,
                            minutes_url,
                            media_url,
                            emtg_url,
                            ics_url,
                            start_time,
                            end_time,
                            location,
                            description,
                            event_type,
                            event_date,
                        ),
                    )
                    self.connection.commit()
                    logging.debug(f"Updated event: {description}")
                else:
                    logging.debug(f"No changes detected for event: {description}")
            else:
                logging.debug(f"Inserting new event: {description}")
                guid = str(uuid.uuid4())
                insert_query = """
                    INSERT INTO legislative_calendar (guid, description, meeting_id, event_type, link, mtg_date, 
                        start_time, end_time, location, agenda_url, minutes_url, media_url, emtg_url, ics_url, date_entered)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """
                self.cursor.execute(
                    insert_query,
                    (
                        guid,
                        description,
                        meeting_id,
                        event_type,
                        link,
                        event_date,
                        start_time,
                        end_time,
                        location,
                        agenda_url,
                        minutes_url,
                        media_url,
                        emtg_url,
                        ics_url,
                    ),
                )
                self.connection.commit()
                logging.debug(f"Inserted new event: {description}")

        except pymysql.Error as db_error:
            logging.error(f"MySQL error: {db_error}")
        except Exception as ex:
            logging.error(f"General error: {ex}")

    def extract_meeting_id(self, link):
        if link:
            return link.split("com=")[-1] if "com=" in link else None
        return None

    def convert_time(self, time_str):
        try:
            if time_str:
                return datetime.strptime(time_str, "%I:%M %p").time()
        except ValueError as e:
            logging.error(f"Error converting time: {e}")
        return None

    def process_calendar(self, month, year):
        calendar_days = self.fetch_calendar(month, year)
        if calendar_days:
            logging.debug(
                f"Fetched calendar successfully. Total days: {len(calendar_days)}"
            )
            for day_data in calendar_days:
                day = int(day_data["day"])
                if 1 <= day <= monthrange(year, month)[1]:
                    event_date = datetime(year, month, day).date()
                    for event in day_data.get("events", []):
                        self.insert_or_update_calendar(event, event_date)
                else:
                    logging.debug(f"Invalid day {day} for month {month}, year {year}")
        else:
            logging.debug("No calendar data fetched.")

    def close_connection(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def run(self, month, year):
        self.setup()
        self.process_calendar(month, year)
        self.close_connection()

    @staticmethod
    def update_calendar():
        current_date = datetime.now()
        start_date = current_date - relativedelta(months=3)
        etlProcessor = LegislativeCalendar(
            api_key=settings_data["api"]["utle"],
            db_host=settings_data["database"]["host"],
            db_user=settings_data["database"]["user"],
            db_password=settings_data["database"]["password"],
            db_name=settings_data["database"]["schema"],
        )
        for i in range(-3, 7):
            month_date = current_date + relativedelta(months=i)
            month = month_date.month
            year = month_date.year
            logging.debug(f"Updating calendar for {month}/{year}")
            print(f"Updating calendar for {month}/{year}")
            etlProcessor.run(month, year)


if __name__ == "__main__":
    LegislativeCalendar.update_calendar()
