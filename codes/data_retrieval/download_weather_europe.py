import cdsapi
import os
import json
import csv
import zipfile
from dotenv import load_dotenv
from shapely.geometry import shape, Point
from tenacity import sleep

# Get environment variables
load_dotenv()
DATA_DIR = os.getenv('DATA_DIR')
WEATHER_EUROPE_DATA_DIR = os.getenv('WEATHER_EUROPE_DATA_DIR')
CONSTANTS_DIR = os.getenv('CONSTANTS_DIR')
SLEEP_TIME = float(os.getenv('SLEEP_TIME', 0.3))
GRID_STEP_KM = float(os.getenv('GRID_STEP_KM', 100))
GRID_STEP_EUROPE_KM = float(os.getenv('GRID_STEP_EUROPE_KM', 300))

# Countries to download weather data for
COUNTRIES = [
    {"name": "germany",     "geojson": "DE.geojson"},
    {"name": "france",      "geojson": "FR.geojson"},
    {"name": "italy",       "geojson": "italy.geojson"},
    {"name": "netherlands", "geojson": "NL.geojson"},
]

# Convert km to approximate degrees (1 degree ≈ 111 km)
grid_step = GRID_STEP_EUROPE_KM / 111.0

# Build grid points per country
country_grid_points = {}
for country in COUNTRIES:
    geojson_path = os.path.join(DATA_DIR, CONSTANTS_DIR, country["geojson"])
    with open(geojson_path, 'r') as f:
        geojson_data = json.load(f)
    polygon = shape(geojson_data['features'][0]['geometry'])
    bounds = polygon.bounds
    min_lon, min_lat, max_lon, max_lat = bounds

    grid_points = []
    lon = min_lon
    while lon <= max_lon:
        lat = min_lat
        while lat <= max_lat:
            point = Point(lon, lat)
            if polygon.contains(point):
                grid_points.append((lon, lat))
            lat += grid_step
        lon += grid_step

    country_grid_points[country["name"]] = grid_points

total_points = sum(len(pts) for pts in country_grid_points.values())

print(f"\n{'='*60}")
for country_name, pts in country_grid_points.items():
    print(f"  {country_name.capitalize()}: {len(pts)} grid points")
print(f"{'='*60}")
print(f"Total: {total_points} weather files (~{total_points*0.5:.1f} MB estimated)")
print(f"Estimated time: ~{total_points * SLEEP_TIME / 60:.1f} minutes (with {SLEEP_TIME}s delay between requests)\n")

# Ask for confirmation
response = input("Proceed with downloads? (yes/no): ").strip().lower()
if response != 'yes':
    print("Cancelled.")
    exit()

# Prepare variables for request
dataset = "reanalysis-era5-single-levels-timeseries"
variables = [
    "surface_solar_radiation_downwards",
    "2m_temperature",
    "total_precipitation",
    "100m_u_component_of_wind",
    "100m_v_component_of_wind"
]

# Download weather data for each country and point
client = cdsapi.Client()

weather_output_dir = os.path.join(DATA_DIR, WEATHER_EUROPE_DATA_DIR)
os.makedirs(weather_output_dir, exist_ok=True)

for country_name, grid_points in country_grid_points.items():
    print(f"\n{'='*60}")
    print(f"Downloading data for {country_name.capitalize()} ({len(grid_points)} points)")
    print(f"{'='*60}")

    country_output_dir = os.path.join(weather_output_dir, country_name)
    os.makedirs(country_output_dir, exist_ok=True)

    locations_data = []

    for idx, (lon, lat) in enumerate(grid_points):
        print(f"  [{country_name}] Point {idx+1}/{len(grid_points)}: ({lon:.4f}, {lat:.4f})")

        request = {
            "variable": variables,
            "location": {"longitude": lon, "latitude": lat},
            "date": ["2020-01-01/2026-03-11"],
            "data_format": "csv"
        }

        point_filename = f"weather_data_{country_name}_{idx:04d}_{lon:.4f}_{lat:.4f}.zip"
        target = os.path.join(country_output_dir, point_filename)

        try:
            result = client.retrieve(dataset, request, target)

            extract_dir = os.path.join(country_output_dir, f"point_{country_name}_{idx:04d}")
            with zipfile.ZipFile(target, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            os.remove(target)

            locations_data.append({
                'country': country_name,
                'point_id': idx,
                'longitude': lon,
                'latitude': lat,
                'data_directory': extract_dir,
                'data_file': point_filename
            })

            sleep(SLEEP_TIME)
        except Exception as e:
            print(f"  Error downloading data for point ({lon:.4f}, {lat:.4f}): {e}")

    # Save locations CSV per country
    locations_csv_path = os.path.join(country_output_dir, "weather_locations.csv")
    with open(locations_csv_path, 'w', newline='') as csvfile:
        fieldnames = ['country', 'point_id', 'longitude', 'latitude', 'data_directory', 'data_file']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in locations_data:
            writer.writerow(row)

    print(f"  Locations saved to {locations_csv_path} ({len(locations_data)} points processed)")

print(f"\nAll countries completed!")