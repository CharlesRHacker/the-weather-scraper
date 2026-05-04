import config
import logging
from datetime import timedelta, date
import lxml.html as lh
import requests
from tqdm import tqdm

log = logging.getLogger(__name__)

# How far on either side of a probe date to look for data when deciding
# whether the station was active. Must be larger than typical gap runs in
# real PWS data so a single-day or week-long outage doesn't get mistaken
# for "station did not exist yet". 30 days handles every gap pattern
# observed in practice while keeping probe counts bounded.
PROBE_RADIUS_DAYS = 30


class Utils:
    session = requests.Session()
    weather_station_url = None

    def __init__(self, session, weather_station_url):
        self.session = session
        self.weather_station_url = weather_station_url

    @classmethod
    def date_range_generator(cls, start, end=date.today()):
        for i in range(int((end - start).days) + 1):
            yield start + timedelta(i)

    @classmethod
    def date_url_generator(cls, weather_station_url, start_date, end_date=date.today()):
        date_range = Utils.date_range_generator(start_date, end_date)
        for d in date_range:
            date_string = d.strftime("%Y-%m-%d")
            url = f'{weather_station_url}/table/{date_string}/{date_string}/daily'
            yield date_string, url

    @classmethod
    def fetch_data_table(cls, url):
        """Returns True if the wunderground page at `url` has any data rows."""
        try:
            html_string = cls.session.get(url, timeout=10)
            doc = lh.fromstring(html_string.content)
            data_table = doc.xpath('//*[@id="main-page-content"]/div/div/div/lib-history/div[2]/lib-history-table/div/div/div/table/tbody/tr')
            return bool(data_table)
        except Exception as e:
            log.warning(f'fetch_data_table error for {url}: {e}')
            return False

    @classmethod
    def has_data_on_date(cls, weather_station_url, d):
        date_string = d.strftime("%Y-%m-%d")
        url = f'{weather_station_url}/table/{date_string}/{date_string}/daily'
        return cls.fetch_data_table(url)

    @classmethod
    def data_in_window(cls, weather_station_url, center, radius, lower_bound, upper_bound):
        """Robust monotonic predicate for binary search.

        Returns True if ANY date in [center - radius, center + radius] (clipped
        to [lower_bound, upper_bound]) has data. A single positive proves the
        station was active near `center`. Probes outward from the center and
        short-circuits on first hit so typical cases are cheap.
        """
        for offset in range(0, radius + 1):
            for sign in ((1, -1) if offset else (1,)):
                probe = center + timedelta(days=sign * offset)
                if probe < lower_bound or probe > upper_bound:
                    continue
                if cls.has_data_on_date(weather_station_url, probe):
                    return True
        return False

    @classmethod
    def find_first_data_entry(cls, weather_station_url, start_date, end_date=None):
        """Finds the first date with logged data for a station.

        Safeguards against the original implementation's failure modes:
          1. Window probes (radius PROBE_RADIUS_DAYS) so isolated gaps in real
             data can't be mistaken for "before the station existed".
          2. End-date sanity check: refuses to run if no data exists near the
             search ceiling, since the predicate would be False everywhere.
          3. Linear-scan refinement after binary convergence to pin down the
             exact first day inside the converged window.
          4. All probes clipped to [start_date, end_date]; never queries
             outside the configured range.

        Returns the first date with data, or -1 if no data was found anywhere
        in the search range. On -1 the caller should fall back to start_date
        rather than skipping the station.
        """
        if end_date is None:
            end_date = date.today()

        if start_date > end_date:
            log.warning(f'start_date {start_date} > end_date {end_date}; skipping search')
            return -1

        radius = PROBE_RADIUS_DAYS
        total_days = (end_date - start_date).days
        log.info(
            f'Searching for first data entry between {start_date} and {end_date} '
            f'(probe radius {radius} days)'
        )

        # Sanity check: if there is no data anywhere near end_date, the
        # predicate is False across the whole range and binary search would
        # converge on a meaningless answer.
        if not cls.data_in_window(weather_station_url, end_date, radius, start_date, end_date):
            log.warning(
                f'No data found within {radius} days of end_date {end_date}; '
                f'aborting binary search'
            )
            return -1

        # Binary search: smallest date d in [start_date, end_date] where
        # data_in_window(d) is True. Progress bar tracks how much of the
        # initial range has been eliminated.
        low = start_date
        high = end_date
        search_bar = tqdm(
            total=total_days,
            desc='Finding first date',
            unit='day',
            leave=False,
        )
        prev_remaining = (high - low).days
        while low < high:
            mid = low + timedelta(days=((high - low).days // 2))
            if cls.data_in_window(weather_station_url, mid, radius, start_date, end_date):
                high = mid
            else:
                low = mid + timedelta(days=1)
            log.debug(f'binary search: low={low} high={high}')
            remaining = (high - low).days
            search_bar.update(prev_remaining - remaining)
            prev_remaining = remaining
        search_bar.close()

        # `low` is now the smallest date whose ±radius window contains data.
        # The actual first data day lies in [low - radius, low + radius],
        # clipped to start_date. Linear scan forward to find it.
        scan_start = max(start_date, low - timedelta(days=radius))
        scan_end = min(end_date, low + timedelta(days=radius))
        log.info(f'Refining: linear scan {scan_start} -> {scan_end}')

        scan_total = (scan_end - scan_start).days + 1
        cursor = scan_start
        for _ in tqdm(range(scan_total), desc='Refining first date', unit='day', leave=False):
            if cls.has_data_on_date(weather_station_url, cursor):
                log.info(f'First data entry: {cursor}')
                return cursor
            cursor += timedelta(days=1)

        log.warning(
            'Binary search converged but linear scan within the window found '
            'no data. This usually means probe radius is too small for the gap '
            'pattern of this station. Falling back.'
        )
        return -1
