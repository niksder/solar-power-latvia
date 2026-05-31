
from download_energy_prices import download_energy_prices
from download_sources import download_sources
from download_weather import download_weather
from merge_panel import merge_panel
from process_merged_data import process_merged_data

# A table with bidding zone codes, names, countries, geojson filenames

# https://github.com/datons/python-entsoe/blob/main/src/entsoe/_mappings.py
# https://github.com/EnergieID/entsoe-py/tree/master/entsoe/geo/geojson

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
    },
    {
        "code": "10YBE----------2",
        "name": "Belgium",
        "countries": ["Belgium"],
        "geojson": "BE.geojson",
    },
    {
        "code": "10YSK-SEPS-----K",
        "name": "Slovakia",
        "countries": ["Slovakia"],
        "geojson": "SK.geojson",
    },
    {
        "code": "10Y1001A1001A82H",
        "name": "Germany",
        "countries": ["Germany", "Luxembourg"],
        "geojson": "DE_LU.geojson",
    },
    {
        "code": "10YCA-BULGARIA-R",
        "name": "Bulgaria",
        "countries": ["Bulgaria"],
        "geojson": "BG.geojson",
    },
    {
        "code": "10Y1001A1001A39I",
        "name": "Estonia",
        "countries": ["Estonia"],
        "geojson": "EE.geojson",
    },
    {
        "code": "10YLT-1001A0008Q",
        "name": "Lithuania",
        "countries": ["Lithuania"],
        "geojson": "LT.geojson",
    },
    {
        "code": "10YDK-1--------W",
        "name": "DK1",
        "countries": ["Denmark"],
        "geojson": "DK_1.geojson",
    },
    {
        "code": "10YDK-2--------M",
        "name": "DK2",
        "countries": ["Denmark"],
        "geojson": "DK_2.geojson",
    },
    {
        "code": "10YNL----------L",
        "name": "Netherlands",
        "countries": ["Netherlands"],
        "geojson": "NL.geojson",
    },
    {
        "code": "10YGR-HTSO-----Y",
        "name": "Greece",
        "countries": ["Greece"],
        "geojson": "GR.geojson",
    },
    {
        "code": "10YHU-MAVIR----U",
        "name": "Hungary",
        "countries": ["Hungary"],
        "geojson": "HU.geojson",
    },
    {
        "code": "10YPT-REN------W",
        "name": "Portugal",
        "countries": ["Portugal"],
        "geojson": "PT.geojson",
    },
    {
        "code": "10YES-REE------0",
        "name": "Spain",
        "countries": ["Spain"],
        "geojson": "ES.geojson",
    },
    {
        "code": "10Y1001A1001A73I",
        "name": "IT_NORTH",
        "countries": ["Italy"],
        "geojson": "IT_NORD.geojson",
    },
    {
        "code": "10Y1001A1001A70O",
        "name": "IT_CNOR",
        "countries": ["Italy"],
        "geojson": "IT_CNOR.geojson",
    },
    {
        "code": "10Y1001A1001A71M",
        "name": "IT_CSUD",
        "countries": ["Italy"],
        "geojson": "IT_CSUD.geojson",
    },
    {
        "code": "10Y1001A1001A788",
        "name": "IT_SUD",
        "countries": ["Italy"],
        "geojson": "IT_SUD.geojson",
    },
    {
        "code": "10Y1001C--00096J",
        "name": "IT_CALA",
        "countries": ["Italy"],
        "geojson": "IT_CALA.geojson",
    },
    {
        "code": "10Y1001A1001A75E",
        "name": "IT_SICI",
        "countries": ["Italy"],
        "geojson": "IT_SICI.geojson",
    },
    {
        "code": "10Y1001A1001A74G",
        "name": "IT_SARD",
        "countries": ["Italy"],
        "geojson": "IT_SARD.geojson",
    },
    {
        "code": "10Y1001A1001A885",
        "name": "IT_SACOAC",
        "countries": ["Italy"],
        "geojson": "IT_SARD.geojson",
    },
    {
        "code": "10Y1001A1001A893",
        "name": "IT_SACODC",
        "countries": ["Italy"],
        "geojson": "IT_SARD.geojson",
    },
    {
        "code": "10YCY-1001A0003J",
        "name" : "Cyprus",
        "countries": ["Cyprus"],
        "geojson": "CY.geojson",
    },
    {
        "code": "10Y1001A1001A59C",
        "name": "Ireland",
        "countries": ["Ireland"],
        "geojson": "IE.geojson",
    },
]

if __name__ == '__main__':
    for zone in BIDDING_ZONES:
        print(f"{zone['code']}: {zone['name']} ({', '.join(zone['countries'])}) - {zone['geojson']}")
        download_energy_prices(zone)
        download_sources(zone)
        download_weather(zone)

    merge_panel(BIDDING_ZONES)
    process_merged_data()

