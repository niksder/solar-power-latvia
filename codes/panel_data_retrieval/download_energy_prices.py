import os
import csv
from collections import defaultdict
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import requests
from tenacity import sleep
from dotenv import load_dotenv

load_dotenv()
ENTSOE_KEY = os.getenv('ENTSOE_KEY')
DATA_DIR = os.getenv('PANEL_DATA_DIR')
ENERGY_PRICES_DIR = os.getenv('ENERGY_PRICES_DIR')
SLEEP_TIME = float(os.getenv('SLEEP_TIME', 0.3))

NS = 'urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3'
YEARS = range(2020, 2026) # exclude 2026 since it's not complete yet


def _download_zone_year(zone, year):
    """Download raw XML energy price data for one bidding zone and year."""
    api_url = 'https://web-api.tp.entsoe.eu/api'
    params = {
        'documentType': 'A44',
        'out_Domain': zone['code'],
        'in_Domain': zone['code'],
        'periodStart': str(year) + '01010000',
        'periodEnd': str(year) + '12312359',
        'securityToken': ENTSOE_KEY,
    }

    response = requests.get(api_url, params=params)

    if response.status_code == 200:
        file_path = os.path.join(
            DATA_DIR, ENERGY_PRICES_DIR,
            f'energy_prices_{zone["name"]}_{year}.xml'
        )
        with open(file_path, 'wb') as f:
            f.write(response.content)
        print(f'Downloaded energy prices for {zone["name"]} {year} -> {file_path}')
    else:
        print(f'Failed to download energy prices for {zone["name"]} {year}. Status code: {response.status_code}')


def _parse_zone_year(zone, year):
    """Parse one zone/year XML file and return {time_str: avg_hourly_price}."""
    file_path = os.path.join(
        DATA_DIR, ENERGY_PRICES_DIR,
        f'energy_prices_{zone["name"]}_{year}.xml'
    )
    tree = ET.parse(file_path)
    root = tree.getroot()

    hour_prices = defaultdict(list)

    for ts in root.findall(f'{{{NS}}}TimeSeries'):
        for period in ts.findall(f'{{{NS}}}Period'):
            start_str = period.find(f'{{{NS}}}timeInterval/{{{NS}}}start').text
            resolution_str = period.find(f'{{{NS}}}resolution').text

            start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))

            if resolution_str == 'PT60M':
                delta = timedelta(hours=1)
            elif resolution_str == 'PT15M':
                delta = timedelta(minutes=15)
            else:
                raise ValueError(f'Unexpected resolution: {resolution_str}')

            for point in period.findall(f'{{{NS}}}Point'):
                position = int(point.find(f'{{{NS}}}position').text)
                price = float(point.find(f'{{{NS}}}price.amount').text)
                dt = start_dt + (position - 1) * delta
                dt_hour = dt.replace(minute=0, second=0, microsecond=0)
                hour_prices[dt_hour.strftime('%Y-%m-%d %H:%M:%S')].append(price)

    return {t: sum(prices) / len(prices) for t, prices in hour_prices.items()}


def download_energy_prices(zone, years=YEARS):
    """Download and convert energy prices for one bidding zone.

    Downloads raw ENTSO-E XML files for each year in ``years``, parses them,
    and writes a single hourly CSV to ``{DATA_DIR}/{ENERGY_PRICES_DIR}/energy_prices_{zone_name}.csv``.

    Parameters
    ----------
    zone : dict
        A bidding zone dict with at least ``code`` and ``name`` keys.
    years : iterable of int
        Years to download. Defaults to 2020-2025.
    """
    os.makedirs(os.path.join(DATA_DIR, ENERGY_PRICES_DIR), exist_ok=True)

    output_path = os.path.join(DATA_DIR, ENERGY_PRICES_DIR, f'energy_prices_{zone["name"]}.csv')
    if os.path.exists(output_path):
        print(f'Skipping energy prices for {zone["name"]} (already exists)')
        return

    for year in years:
        sleep(SLEEP_TIME)
        _download_zone_year(zone, year)

    hour_prices = defaultdict(list)
    for year in years:
        try:
            yearly = _parse_zone_year(zone, year)
        except FileNotFoundError:
            print(f'Missing file for {zone["name"]} {year}, skipping.')
            continue
        for time_str, price in yearly.items():
            hour_prices[time_str].append(price)
        xml_path = os.path.join(DATA_DIR, ENERGY_PRICES_DIR, f'energy_prices_{zone["name"]}_{year}.xml')
        os.remove(xml_path)

    # Each year should have distinct timestamps, but average within hour just in case
    unique_rows = sorted(
        [(t, sum(prices) / len(prices)) for t, prices in hour_prices.items()],
        key=lambda r: r[0],
    )

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['time', 'price'])
        writer.writerows(unique_rows)

    print(f'Wrote {len(unique_rows)} rows to {output_path}')
