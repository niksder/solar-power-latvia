
from download_energy_prices import download_energy_prices
from download_sources import download_sources
from download_weather import download_weather
from merge_panel import merge_panel

# A table with bidding zone codes, names, countries, geojson filenames

BIDDING_ZONES = [
    {
        "code": "10YLV-1001A00074",
        "name": "Latvia",
        "countries": ["Latvia"],
        "geojson": "LV.geojson",
    },
    {
        "code": "10YAT-APG------L",
        "name": "Austria",
        "countries": ["Austria"],
        "geojson": "AT.geojson",
    },
    {
        "code": "10YFI-1--------U",
        "name": "Finland",
        "countries": ["Finland"],
        "geojson": "FI.geojson",
    },
    {
        "code": "10YPL-AREA-----S",
        "name": "Poland",
        "countries": ["Poland"],
        "geojson": "PL.geojson",
    },
    {
        "code": "10YRO-TEL------P",
        "name": "Romania",
        "countries": ["Romania"],
        "geojson": "RO.geojson",
    },
    {
        "code": "10YCZ-CEPS-----N",
        "name": "Czechia",
        "countries": ["Czechia"],
        "geojson": "CZ.geojson",
    },
    {
        "code": "10YFR-RTE------C",
        "name": "France",
        "countries": ["France"],
        "geojson": "FR.geojson",
    },
    {
        "code": "10YSI-ELES-----O",
        "name": "Slovenia",
        "countries": ["Slovenia"],
        "geojson": "SI.geojson",
    },
    {
        "code": "10YCH-SWISSGRIDZ",
        "name": "Switzerland",
        "countries": ["Switzerland"],
        "geojson": "CH.geojson",
    },
    {
        "code": "10YHR-HEP------M",
        "name": "Croatia",
        "countries": ["Croatia"],
        "geojson": "HR.geojson",
    },
    {
        "code": "10Y1001A1001A44P",
        "name": "SE1",
        "countries": ["Sweden"],
        "geojson": "SE_1.geojson",
    },
    {
        "code": "10Y1001A1001A45N",
        "name": "SE2",
        "countries": ["Sweden"],
        "geojson": "SE_2.geojson",
    },
    {
        "code": "10Y1001A1001A46L",
        "name": "SE3",
        "countries": ["Sweden"],
        "geojson": "SE_3.geojson",
    },
    {
        "code": "10Y1001A1001A47J",
        "name": "SE4",
        "countries": ["Sweden"],
        "geojson": "SE_4.geojson",
    }
]

for zone in BIDDING_ZONES:
    print(f"{zone['code']}: {zone['name']} ({', '.join(zone['countries'])}) - {zone['geojson']}")
    download_energy_prices(zone)
    download_sources(zone)
    download_weather(zone)

merge_panel(BIDDING_ZONES)

