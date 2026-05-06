import os
import json
import zipfile
import pandas as pd
import cdsapi
from shapely.geometry import shape, Point
from tenacity import sleep
from dotenv import load_dotenv

load_dotenv()
DATA_DIR = os.getenv('DATA_DIR')
PANEL_DATA_DIR = os.getenv('PANEL_DATA_DIR')
WEATHER_DATA_DIR = os.getenv('WEATHER_DATA_DIR')
CONSTANTS_DIR = os.getenv('CONSTANTS_DIR')
SLEEP_TIME = float(os.getenv('SLEEP_TIME', 0.3))
GRID_STEP_KM = float(os.getenv('GRID_STEP_PANEL_KM', 150))

VARIABLES = [
    "surface_solar_radiation_downwards",
    "2m_temperature",
    "total_precipitation",
    "100m_u_component_of_wind",
    "100m_v_component_of_wind",
]

DATASET = "reanalysis-era5-single-levels-timeseries"
DATE_RANGE = "2020-01-01/2026-03-11"


def _grid_points_for_zone(zone):
    """Return a list of (lon, lat) grid points inside the zone's geojson polygon."""
    geojson_path = os.path.join(DATA_DIR, CONSTANTS_DIR, zone['geojson'])
    with open(geojson_path, 'r') as f:
        geojson_data = json.load(f)

    polygon = shape(geojson_data['features'][0]['geometry'])
    min_lon, min_lat, max_lon, max_lat = polygon.bounds
    grid_step = GRID_STEP_KM / 111.0

    points = []
    lon = min_lon
    while lon <= max_lon:
        lat = min_lat
        while lat <= max_lat:
            if polygon.contains(Point(lon, lat)):
                points.append((lon, lat))
            lat += grid_step
        lon += grid_step

    if not points:
        # Grid step too large for this zone — fall back to the polygon centroid
        centroid = polygon.centroid
        points = [(centroid.x, centroid.y)]

    return points


def download_weather(zone):
    """Download and merge weather data for one bidding zone.

    For each grid point inside the zone's geojson polygon, downloads ERA5
    weather data from the CDS API, extracts the CSV, then averages all points
    and writes a single output CSV to
    ``{PANEL_DATA_DIR}/{WEATHER_DATA_DIR}/weather_{zone_name}.csv``.

    Parameters
    ----------
    zone : dict
        A bidding zone dict with at least ``name`` and ``geojson`` keys.
    """
    weather_dir = os.path.join(PANEL_DATA_DIR, WEATHER_DATA_DIR)
    os.makedirs(weather_dir, exist_ok=True)

    output_path = os.path.join(weather_dir, f'weather_{zone["name"]}.csv')
    if os.path.exists(output_path):
        print(f'Skipping weather for {zone["name"]} (already exists)')
        return

    grid_points = _grid_points_for_zone(zone)
    print(f'{zone["name"]}: {len(grid_points)} grid points found')

    client = cdsapi.Client()
    point_dirs = []

    for idx, (lon, lat) in enumerate(grid_points):
        print(f'  [{zone["name"]}] Point {idx + 1}/{len(grid_points)}: ({lon:.4f}, {lat:.4f})')

        request = {
            "variable": VARIABLES,
            "location": {"longitude": lon, "latitude": lat},
            "date": [DATE_RANGE],
            "data_format": "csv",
        }

        zip_filename = f'weather_{zone["name"]}_{idx:04d}_{lon:.4f}_{lat:.4f}.zip'
        zip_path = os.path.join(weather_dir, zip_filename)

        try:
            client.retrieve(DATASET, request, zip_path)

            extract_dir = os.path.join(weather_dir, f'weather_{zone["name"]}_point_{idx:04d}')
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_dir)
            os.remove(zip_path)

            point_dirs.append(extract_dir)
            sleep(SLEEP_TIME)
        except Exception as e:
            print(f'  Error for ({lon:.4f}, {lat:.4f}): {e}')

    # Merge all point CSVs by averaging
    frames = []
    for d in point_dirs:
        csv_files = [os.path.join(d, fn) for fn in os.listdir(d) if fn.endswith('.csv')]
        for csv_path in csv_files:
            df = pd.read_csv(csv_path, parse_dates=["valid_time"])
            frames.append(df)

    if not frames:
        print(f'No data downloaded for {zone["name"]}, skipping merge.')
        return

    combined = pd.concat(frames, ignore_index=True)
    value_cols = [c for c in combined.columns if c not in ("valid_time", "latitude", "longitude")]
    averaged = (
        combined.groupby("valid_time", sort=True)[value_cols]
        .mean()
        .reset_index()
    )

    averaged.to_csv(output_path, index=False)
    print(f'Wrote {len(averaged)} rows to {output_path}')

    # Clean up extracted point directories
    for d in point_dirs:
        for fn in os.listdir(d):
            os.remove(os.path.join(d, fn))
        os.rmdir(d)
