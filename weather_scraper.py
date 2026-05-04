# Made with love by Karl
# Contact me on Telegram: @karlpy

import requests
import csv
import logging
import lxml.html as lh
from tqdm import tqdm

import config

from util.UnitConverter import ConvertToSystem
from util.Parser import Parser
from util.Utils import Utils

# logging: everything non-progress-bar goes to a .log file
logging.basicConfig(
    filename='weather_scraper.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    encoding='utf-8',
)
log = logging.getLogger(__name__)

# configuration
stations_file = open('stations.txt', 'r')
URLS = stations_file.readlines()
# Date format: YYYY-MM-DD
START_DATE = config.START_DATE
END_DATE = config.END_DATE

# set to "metric" or "imperial"
UNIT_SYSTEM = config.UNIT_SYSTEM
# find the first data entry automatically
FIND_FIRST_DATE = config.FIND_FIRST_DATE


def scrap_station(weather_station_url):

    session = requests.Session()
    timeout = 5

    station_start = START_DATE
    if FIND_FIRST_DATE:
        first_date_with_data = Utils.find_first_data_entry(
            weather_station_url=weather_station_url,
            start_date=START_DATE,
            end_date=END_DATE,
        )
        if first_date_with_data != -1:
            station_start = first_date_with_data
        else:
            log.warning(f'first-date search returned no result; falling back to {START_DATE}')

    date_url_pairs = list(Utils.date_url_generator(weather_station_url, station_start, END_DATE))
    station_name = weather_station_url.split('/')[-1]
    file_name = f'{station_name}.csv'

    with open(file_name, 'a+', newline='') as csvfile:
        fieldnames = ['Date', 'Time',	'Temperature',	'Dew_Point',	'Humidity',	'Wind',	'Speed',	'Gust',	'Pressure',	'Precip_Rate',	'Precip_Accum',	'UV',   'Solar']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # Write the correct headers to the CSV file
        if UNIT_SYSTEM == "metric":
            # 12:04 AM	24.4 C	18.3 C	69 %	SW	0.0 km/h	0.0 km/h	1,013.88 hPa	0.00 mm	0.00 mm	0	0 w/m²
            writer.writerow({'Date': 'Date', 'Time': 'Time',	'Temperature': 'Temperature_C',	'Dew_Point': 'Dew_Point_C',	'Humidity': 'Humidity_%',	'Wind': 'Wind',	'Speed': 'Speed_kmh',	'Gust': 'Gust_kmh',	'Pressure': 'Pressure_hPa',	'Precip_Rate': 'Precip_Rate_mm',	'Precip_Accum': 'Precip_Accum_mm',	'UV': 'UV',   'Solar': 'Solar_w/m2'})
        elif UNIT_SYSTEM == "imperial":
            # 12:04 AM	75.9 F	65.0 F	69 %	SW	0.0 mph	0.0 mph	29.94 in	0.00 in	0.00 in	0	0 w/m²
            writer.writerow({'Date': 'Date', 'Time': 'Time',	'Temperature': 'Temperature_F',	'Dew_Point': 'Dew_Point_F',	'Humidity': 'Humidity_%',	'Wind': 'Wind',	'Speed': 'Speed_mph',	'Gust': 'Gust_mph',	'Pressure': 'Pressure_in',	'Precip_Rate': 'Precip_Rate_in',	'Precip_Accum': 'Precip_Accum_in',	'UV': 'UV',   'Solar': 'Solar_w/m2'})
        else:
            raise Exception("please set 'unit_system' to either \"metric\" or \"imperial\"! ")

        progress = tqdm(date_url_pairs, desc=station_name, unit='day')
        for date_string, url in progress:
            try:
                log.info(f'Scraping data from {url}')
                history_table = False
                max_attempts = 4
                for attempt in range(1, max_attempts + 1):
                    html_string = session.get(url, timeout=timeout)
                    doc = lh.fromstring(html_string.content)
                    history_table = doc.xpath('//*[@id="main-page-content"]/div/div/div/lib-history/div[2]/lib-history-table/div/div/div/table/tbody')
                    if history_table:
                        break
                    log.info(f'no history table on attempt {attempt} for {date_string}; refreshing session')
                    session = requests.Session()
                if not history_table:
                    log.warning(f'giving up on {date_string} after {max_attempts} attempts (no history table)')
                    continue

                # parse html table rows
                data_rows = Parser.parse_html_table(date_string, history_table)

                # convert to metric system
                converter = ConvertToSystem(UNIT_SYSTEM)
                data_to_write = converter.clean_and_convert(data_rows)

                log.info(f'Saving {len(data_to_write)} rows for {date_string}')
                progress.set_postfix(rows=len(data_to_write), date=date_string)
                writer.writerows(data_to_write)
            except Exception as e:
                log.warning(f'{date_string}: {e}')


for url in URLS:
    url = url.strip()
    log.info(f'Station: {url}')
    scrap_station(url)
