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
TOTAL_PRODUCTION_DIR = os.getenv('TOTAL_PRODUCTION_DIR', 'total_production')
SLEEP_TIME = float(os.getenv('SLEEP_TIME', 0.3))
MAX_RETRIES_ENERGY_SOURCES = int(os.getenv('MAX_RETRIES_ENERGY_SOURCES', 5))

NS = 'urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0'
YEARS = range(2016, 2026) # exclude 2026 since it's not complete yet
PSR_TYPES = ['B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B10', 'B11', 'B12', 'B16', 'B18', 'B19']
# [O] B01 = Biomass; B02 = Fossil Brown coal/Lignite; B03 = Fossil Coal-derived gas; B04 = Fossil Gas; B05 = Fossil Hard coal; B06 = Fossil Oil; B07 = Fossil Oil shale; B08 = Fossil Peat; B09 = Geothermal; B10 = Hydro Pumped Storage; B11 = Hydro Run-of-river and poundage; B12 = Hydro Water Reservoir; B13 = Marine; B14 = Nuclear; B15 = Other renewable; B16 = Solar; B17 = Waste; B18 = Wind Offshore; B19 = Wind Onshore; B20 = Other; B25 = Energy storage


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

    for attempt in range(1, MAX_RETRIES_ENERGY_SOURCES + 1):
        try:
            response = requests.get(api_url, params=params)
        except requests.exceptions.RequestException as e:
            print(f'Network error downloading energy sources for {zone["name"]} {year} {psr_type} (attempt {attempt}/{MAX_RETRIES_ENERGY_SOURCES}): {e}')
            if attempt < MAX_RETRIES_ENERGY_SOURCES:
                sleep(SLEEP_TIME)
            continue

        if response.status_code != 200:
            print(f'Failed to download energy sources for {zone["name"]} {year} {psr_type} (attempt {attempt}/{MAX_RETRIES_ENERGY_SOURCES}). Status code: {response.status_code}')
            if attempt < MAX_RETRIES_ENERGY_SOURCES:
                sleep(SLEEP_TIME)
            continue

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            print(f'Failed to parse XML response for {zone["name"]} {year} {psr_type} (attempt {attempt}/{MAX_RETRIES_ENERGY_SOURCES}): {e}')
            if attempt < MAX_RETRIES_ENERGY_SOURCES:
                sleep(SLEEP_TIME)
            continue

        if root.tag != f'{{{NS}}}GL_MarketDocument':
            print(f'Unexpected document type for {zone["name"]} {year} {psr_type} (attempt {attempt}/{MAX_RETRIES_ENERGY_SOURCES}): {root.tag}')
            if attempt < MAX_RETRIES_ENERGY_SOURCES:
                sleep(SLEEP_TIME)
            continue

        file_path = os.path.join(
            DATA_DIR, ENERGY_SOURCES_DIR,
            f'energy_sources_{zone["name"]}_{year}_{psr_type}.xml'
        )
        with open(file_path, 'wb') as f:
            f.write(response.content)
        print(f'Downloaded energy sources for {zone["name"]} {year} {psr_type} -> {file_path}')
        return

    print(f'Giving up on energy sources for {zone["name"]} {year} {psr_type} after {MAX_RETRIES_ENERGY_SOURCES} attempts.')


def _download_zone_year_total(zone, year):
    """Download raw XML total generation data for one zone and year (no PSR filter)."""
    api_url = 'https://web-api.tp.entsoe.eu/api'
    params = {
        'documentType': 'A75',
        'processType': 'A16',
        'out_Domain': zone['code'],
        'in_Domain': zone['code'],
        'periodStart': str(year) + '01010000',
        'periodEnd': str(year) + '12312359',
        'securityToken': ENTSOE_KEY,
    }

    for attempt in range(1, MAX_RETRIES_ENERGY_SOURCES + 1):
        try:
            response = requests.get(api_url, params=params)
        except requests.exceptions.RequestException as e:
            print(f'Network error downloading total generation for {zone["name"]} {year} (attempt {attempt}/{MAX_RETRIES_ENERGY_SOURCES}): {e}')
            if attempt < MAX_RETRIES_ENERGY_SOURCES:
                sleep(SLEEP_TIME)
            continue

        if response.status_code != 200:
            print(f'Failed to download total generation for {zone["name"]} {year} (attempt {attempt}/{MAX_RETRIES_ENERGY_SOURCES}). Status code: {response.status_code}')
            if attempt < MAX_RETRIES_ENERGY_SOURCES:
                sleep(SLEEP_TIME)
            continue

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            print(f'Failed to parse XML response for total generation {zone["name"]} {year} (attempt {attempt}/{MAX_RETRIES_ENERGY_SOURCES}): {e}')
            if attempt < MAX_RETRIES_ENERGY_SOURCES:
                sleep(SLEEP_TIME)
            continue

        if root.tag != f'{{{NS}}}GL_MarketDocument':
            print(f'Unexpected document type for total generation {zone["name"]} {year} (attempt {attempt}/{MAX_RETRIES_ENERGY_SOURCES}): {root.tag}')
            if attempt < MAX_RETRIES_ENERGY_SOURCES:
                sleep(SLEEP_TIME)
            continue

        file_path = os.path.join(
            DATA_DIR, TOTAL_PRODUCTION_DIR,
            f'energy_sources_{zone["name"]}_{year}_total.xml'
        )
        with open(file_path, 'wb') as f:
            f.write(response.content)
        print(f'Downloaded total generation for {zone["name"]} {year} -> {file_path}')
        return

    print(f'Giving up on total generation for {zone["name"]} {year} after {MAX_RETRIES_ENERGY_SOURCES} attempts.')


def _parse_zone_year_total(zone, year):
    """Parse one zone/year total generation XML and return {time_str: quantity} summed across all PSR types."""
    file_path = os.path.join(
        DATA_DIR, TOTAL_PRODUCTION_DIR,
        f'energy_sources_{zone["name"]}_{year}_total.xml'
    )
    tree = ET.parse(file_path)
    root = tree.getroot()

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
            elif resolution_str == 'PT30M':
                delta = timedelta(minutes=30)
            elif resolution_str == 'PT15M':
                delta = timedelta(minutes=15)
            else:
                raise ValueError(f'Unexpected resolution: {resolution_str}')

            total_points = int((end_dt - start_dt) / delta)

            sparse = {}
            for point in period.findall(f'{{{NS}}}Point'):
                pos = int(point.find(f'{{{NS}}}position').text)
                qty = float(point.find(f'{{{NS}}}quantity').text)
                sparse[pos] = qty

            if not sparse:
                print(f'Warning: period {start_str}\u2013{end_str} has no data points for {zone["name"]} {year} total, skipping.')
                continue

            current_qty = 0.0
            for pos in range(1, total_points + 1):
                if pos in sparse:
                    current_qty = sparse[pos]
                dt = start_dt + (pos - 1) * delta
                key = dt.strftime('%Y-%m-%d %H:%M:%S')
                result[key] = result.get(key, 0.0) + current_qty

    return result


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
            elif resolution_str == 'PT30M':
                delta = timedelta(minutes=30)
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

            if not sparse:
                print(f'Warning: period {start_str}\u2013{end_str} has no data points for {zone["name"]} {year} {psr_type}, skipping.')
                continue

            # Expand with forward-fill (A03 curve type); accumulate across TimeSeries
            current_qty = 0.0
            for pos in range(1, total_points + 1):
                if pos in sparse:
                    current_qty = sparse[pos]
                dt = start_dt + (pos - 1) * delta
                key = dt.strftime('%Y-%m-%d %H:%M:%S')
                result[key] = result.get(key, 0.0) + current_qty

    return result


def _get_existing_psr_types(output_path):
    """Return the set of PSR type columns already present in the CSV, or empty set if file doesn't exist."""
    if not os.path.exists(output_path):
        return set()
    with open(output_path, 'r', newline='') as f:
        reader = csv.reader(f)
        header = next(reader, [])
    return set(col for col in header if col != 'time')


def download_sources(zone, years=YEARS, psr_types=PSR_TYPES):
    """Download and convert energy generation by source for one bidding zone.

    Downloads raw ENTSO-E XML files for each year and PSR type in ``years`` /
    ``psr_types``, parses them, deletes the XML files, and writes a single
    hourly CSV to ``{DATA_DIR}/{ENERGY_SOURCES_DIR}/energy_sources_{zone_name}.csv``.
    If the CSV already exists, only PSR types not yet present as columns are
    downloaded and merged in.

    Parameters
    ----------
    zone : dict
        A bidding zone dict with at least ``code`` and ``name`` keys.
    years : iterable of int
        Years to download. Defaults to 2020-2025.
    psr_types : iterable of str
        ENTSO-E PSR type codes to download. Defaults to B01, B04, B11, B16, B19, B20.
    """
    os.makedirs(os.path.join(DATA_DIR, ENERGY_SOURCES_DIR), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, TOTAL_PRODUCTION_DIR), exist_ok=True)

    output_path = os.path.join(DATA_DIR, ENERGY_SOURCES_DIR, f'energy_sources_{zone["name"]}.csv')
    total_output_path = os.path.join(DATA_DIR, TOTAL_PRODUCTION_DIR, f'total_production_{zone["name"]}.csv')

    existing_psr_types = _get_existing_psr_types(output_path)
    missing_psr_types = [p for p in psr_types if p not in existing_psr_types]
    sources_complete = os.path.exists(output_path) and not missing_psr_types
    total_exists = os.path.exists(total_output_path)

    if sources_complete:
        print(f'Skipping energy sources for {zone["name"]} (already exists with all PSR types)')
    elif existing_psr_types:
        print(f'Energy sources for {zone["name"]} exists but missing PSR types: {missing_psr_types}')
    if total_exists:
        print(f'Skipping total production for {zone["name"]} (already exists)')
    if sources_complete and total_exists:
        return

    for year in years:
        if not sources_complete:
            for psr_type in missing_psr_types:
                sleep(SLEEP_TIME)
                _download_zone_year_psr(zone, year, psr_type)
        if not total_exists:
            sleep(SLEEP_TIME)
            _download_zone_year_total(zone, year)

    # new_data[time_str][psr_type] = quantity  (only for missing PSR types)
    new_data = {}
    total_data = {}
    for year in years:
        if not sources_complete:
            for psr_type in missing_psr_types:
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
                    if time_str not in new_data:
                        new_data[time_str] = {}
                    new_data[time_str][psr_type] = qty

        if not total_exists:
            total_xml_path = os.path.join(
                DATA_DIR, TOTAL_PRODUCTION_DIR,
                f'energy_sources_{zone["name"]}_{year}_total.xml'
            )
            try:
                parsed_total = _parse_zone_year_total(zone, year)
            except FileNotFoundError:
                print(f'Missing total generation file for {zone["name"]} {year}, skipping.')
                parsed_total = {}
            finally:
                if os.path.exists(total_xml_path):
                    os.remove(total_xml_path)

            for time_str, qty in parsed_total.items():
                total_data[time_str] = qty

    if not sources_complete:
        if existing_psr_types:
            # Read existing CSV and merge new PSR type columns in
            existing_data = {}
            existing_header = []
            with open(output_path, 'r', newline='') as f:
                reader = csv.reader(f)
                existing_header = next(reader)
                for row in reader:
                    existing_data[row[0]] = dict(zip(existing_header, row))

            existing_psr_cols = existing_header[1:]
            all_times = sorted(set(existing_data.keys()) | set(new_data.keys()))
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['time'] + existing_psr_cols + missing_psr_types)
                for t in all_times:
                    row = [t]
                    for psr in existing_psr_cols:
                        row.append(existing_data.get(t, {}).get(psr, ''))
                    for psr in missing_psr_types:
                        row.append(new_data.get(t, {}).get(psr, ''))
                    writer.writerow(row)
            print(f'Updated {output_path} with {len(missing_psr_types)} new PSR type(s): {missing_psr_types}')
        else:
            all_times = sorted(new_data.keys())
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['time'] + list(psr_types))
                for t in all_times:
                    row = [t] + [new_data[t].get(psr, '') for psr in psr_types]
                    writer.writerow(row)
            print(f'Wrote {len(all_times)} rows to {output_path}')

    if not total_exists:
        all_times_total = sorted(total_data.keys())
        with open(total_output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['time', 'total_generation'])
            for t in all_times_total:
                writer.writerow([t, total_data[t]])
        print(f'Wrote {len(all_times_total)} rows to {total_output_path}')
