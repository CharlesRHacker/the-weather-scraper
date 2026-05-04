import logging
import unicodedata
from datetime import datetime

log = logging.getLogger(__name__)


class Parser:
    @staticmethod
    def format_key(key: str) -> str:
        # Replace white space and delete dots
        return key.replace(' ', '_').replace('.', '')

    @staticmethod
    def parse_html_table(date_string: str, history_table: list) -> list:

        # `history_table` is the <tbody>; headers live in the sibling <thead>.
        tbody = history_table[0]
        table = tbody.getparent()
        header_ths = table.xpath('./thead//th') if table is not None else []
        if not header_ths:
            log.info(f'{date_string}: no <th> header cells found in table')
            return []

        headers_list = [th.text_content().strip() for th in header_ths]
        expected_cols = len(headers_list)

        data_trs = tbody.xpath('./tr')
        if not data_trs:
            log.info(f'{date_string}: no <tr> rows in history tbody')
            return []

        table_rows = []
        dropped = 0
        for tr in data_trs:
            if len(tr) == expected_cols:
                table_rows.append(tr)
            else:
                dropped += 1
        if dropped:
            log.info(f'{date_string}: dropped {dropped} row(s) with mismatched column count (expected {expected_cols})')

        data_rows = []
        for tr in table_rows:
            row_dict = {}
            for i, td in enumerate(tr.getchildren()):
                td_content = unicodedata.normalize("NFKD", td.text_content())

                # set date and time in the first 2 columns
                if i == 0:
                    date = datetime.strptime(date_string, "%Y-%m-%d")
                    try:
                        time = datetime.strptime(td_content, "%I:%M %p")
                        time_str = time.strftime('%I:%M %p')
                    except ValueError:
                        time_str = td_content
                    row_dict['Date'] = date.strftime('%Y/%m/%d')
                    row_dict['Time'] = time_str
                else:
                    header = headers_list[i] if i < len(headers_list) and headers_list[i] else f'col_{i}'
                    row_dict[Parser.format_key(header)] = td_content

            data_rows.append(row_dict)

        return data_rows
