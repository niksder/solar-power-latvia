import os
import csv
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import requests
from tenacity import sleep
from dotenv import load_dotenv

load_dotenv()
ENTSOE_KEY = os.getenv('ENTSOE_KEY')
DATA_DIR = os.getenv('PANEL_DATA_DIR')
ENERGY_SOURCES_DIR = os.getenv('ENERGY_SOURCES_DIR')
SLEEP_TIME = float(os.getenv('SLEEP_TIME', 0.3))

NS = 'urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0'
YEARS = range(2020, 2027)
PSR_TYPES = ['B01', 'B04', 'B11', 'B16', 'B19', 'B20']


def _download_zone_year_psr(zone, year, psr_type):
    """Download raw XML generation-by-source data for one zone, year and PSR type."""
    api_url = 'https://web-api.tp.entsoe.eu/api'
    params = {
        'documentType': 'A75',
        'processType': 'A16',
        'out_Domain': zone['code'],
        'in_Domain': zone['code'],
        'periodStart': str(year) + '01010000',
        'periodEnd': str(year) + '12312359',
        'psrType': psr_type,
        'securityToken': ENTSOE_KEY,
    }

    response = requests.get(api_url, params=params)

    if response.status_code == 200:
        file_path = os.path.join(
            DATA_DIR, ENERGY_SOURCES_DIR,
            f'energy_sources_{zone["name"]}_{year}_{psr_type}.xml'
        )
        with open(file_path, 'wb') as f:
            f.write(response.content)
        print(f'Downloaded energy sources for {zone["name"]} {year} {psr_type} -> {file_path}')
    else:
        print(f'Failed to download energy sources for {zone["name"]} {year} {psr_type}. Status code: {response.status_code}')


def _parse_zone_year_psr(zone, year, psr_type):
    """Parse one zone/year/PSR XML file and return {time_str: quantity}."""
    file_path = os.path.join(
        DATA_DIR, ENERGY_SOURCES_DIR,
        f'energy_sources_{zone["name"]}_{year}_{psr_type}.xml'
    )
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Skip acknowledgement documents (no data)
    if root.tag != f'{{{NS}}}GL_MarketDocument':
        return {}

    result = {}

    for ts in root.findall(f'{{{NS}}}TimeSeries'):
        for period in ts.findall(f'{{{NS}}}Period'):
            start_str = period.find(f'{{{NS}}}timeInterval/{{{NS}}}start').text
            end_str = period.find(f'{{{NS}}}timeInterval/{{{NS}}}end').text
            resolution_str = period.find(f'{{{NS}}}resolution').text

            start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))

            if resolution_str == 'PT60M':
                delta = timedelta(hours=1)
            elif resolution_str == 'PT15M':
                delta = timedelta(minutes=15)
            else:
                raise ValueError(f'Unexpected resolution: {resolution_str}')

            total_points = int((end_dt - start_dt) / delta)

            # Collect sparse points
            sparse = {}
            for point in period.findall(f'{{{NS}}}Point'):
                pos = int(point.find(f'{{{NS}}}position').text)
                qty = float(point.find(f'{{{NS}}}quantity').text)
                sparse[pos] = qty

            # Expand with forward-fill (A03 curve type)
            current_qty = 0.0
            for pos in range(1, total_points + 1):
                if pos in sparse:
                    current_qty = sparse[pos]
                dt = start_dt + (pos - 1) * delta
                result[dt.strftime('%Y-%m-%d %H:%M:%S')] = current_qty

    return result


def download_sources(zone, years=YEARS, psr_types=PSR_TYPES):
    """Download and convert energy generation by source for one bidding zone.

    Downloads raw ENTSO-E XML files for each year and PSR type in ``years`` /
    ``psr_types``, parses them, deletes the XML files, and writes a single
    hourly CSV to ``{DATA_DIR}/{ENERGY_SOURCES_DIR}/energy_sources_{zone_name}.csv``.

    Parameters
    ----------
    zone : dict
        A bidding zone dict with at least ``code`` and ``name`` keys.
    years : iterable of int
        Years to download. Defaults to 2020-2026.
    psr_types : iterable of str
        ENTSO-E PSR type codes to download. Defaults to B01, B04, B11, B16, B19, B20.
    """
    os.makedirs(os.path.join(DATA_DIR, ENERGY_SOURCES_DIR), exist_ok=True)

    output_path = os.path.join(DATA_DIR, ENERGY_SOURCES_DIR, f'energy_sources_{zone["name"]}.csv')
    if os.path.exists(output_path):
        print(f'Skipping energy sources for {zone["name"]} (already exists)')
        return

    for year in years:
        for psr_type in psr_types:
            sleep(SLEEP_TIME)
            _download_zone_year_psr(zone, year, psr_type)

    # data[time_str][psr_type] = quantity
    data = {}
    for year in years:
        for psr_type in psr_types:
            xml_path = os.path.join(
                DATA_DIR, ENERGY_SOURCES_DIR,
                f'energy_sources_{zone["name"]}_{year}_{psr_type}.xml'
            )
            try:
                parsed = _parse_zone_year_psr(zone, year, psr_type)
            except FileNotFoundError:
                print(f'Missing file for {zone["name"]} {year} {psr_type}, skipping.')
                continue
            finally:
                if os.path.exists(xml_path):
                    os.remove(xml_path)

            for time_str, qty in parsed.items():
                if time_str not in data:
                    data[time_str] = {}
                data[time_str][psr_type] = qty

    all_times = sorted(data.keys())
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['time'] + list(psr_types))
        for t in all_times:
            row = [t] + [data[t].get(psr, '') for psr in psr_types]
            writer.writerow(row)

    print(f'Wrote {len(all_times)} rows to {output_path}')
