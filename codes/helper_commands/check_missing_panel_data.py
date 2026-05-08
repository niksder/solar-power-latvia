import os
import csv
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'panel_data')

# (display label, folder name)
FOLDERS = [
    ('S', 'energy_sources'),
    ('P', 'energy_prices'),
    ('T', 'total_production'),
    ('W', 'weather'),
]

TIME_COLS = {'time', 'valid_time'}

GREEN  = '\033[32m'
RED    = '\033[31m'
DIM    = '\033[90m'
BOLD   = '\033[1m'
RESET  = '\033[0m'

BLOCK  = '█'
DOT    = '·'

COL_WIDTH = 8  # visible chars per year column


def load_folder(folder_name):
    """Return {bzone: {year: bool}} — True = has at least one non-null non-zero value."""
    folder_path = os.path.join(BASE_DIR, folder_name)
    result = {}

    if not os.path.isdir(folder_path):
        return result

    for filename in sorted(os.listdir(folder_path)):
        if not filename.endswith('.csv'):
            continue

        bzone = filename.replace(f'{folder_name}_', '').replace('.csv', '')
        filepath = os.path.join(folder_path, filename)

        year_has_data = defaultdict(bool)  # default False

        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            value_cols = [c for c in reader.fieldnames if c not in TIME_COLS]

            for row in reader:
                time_val = row.get('time') or row.get('valid_time', '')
                year = time_val[:4]
                if not year.isdigit():
                    continue

                if year_has_data[year]:
                    continue  # already confirmed, skip remaining rows

                for col in value_cols:
                    val = row.get(col, '')
                    if val is None or val.strip() == '':
                        continue
                    try:
                        if float(val) != 0.0:
                            year_has_data[year] = True
                            break
                    except ValueError:
                        pass

        result[bzone] = dict(year_has_data)

    return result


def colored_block(has_data):
    if has_data is None:
        return DIM + DOT + RESET
    return (GREEN if has_data else RED) + BLOCK + RESET


def main():
    folder_data = {}  # folder_name -> {bzone: {year: bool}}
    for _label, folder_name in FOLDERS:
        folder_data[folder_name] = load_folder(folder_name)

    # Collect all bzones and years
    all_bzones = set()
    all_years = set()
    for fd in folder_data.values():
        for bzone, years in fd.items():
            all_bzones.add(bzone)
            all_years.update(years.keys())

    all_bzones = sorted(all_bzones)
    all_years = sorted(all_years)
    labels = [lbl for lbl, _ in FOLDERS]
    folder_names = [fn for _, fn in FOLDERS]

    bzone_width = max(len(b) for b in all_bzones) + 3
    table_width = bzone_width + COL_WIDTH * len(all_years)

    for label, fn in zip(labels, folder_names):
        fd = folder_data[fn]

        print()
        print(BOLD + f'  {fn}  ' + RESET)
        print(DIM + '─' * table_width + RESET)

        # Header: years
        header = ' ' * bzone_width
        for year in all_years:
            header += BOLD + year.center(COL_WIDTH) + RESET
        print(header)

        print(DIM + '─' * table_width + RESET)

        for bzone in all_bzones:
            row = bzone.ljust(bzone_width)
            bzone_data = fd.get(bzone, {})
            for year in all_years:
                has = bzone_data.get(year, None)
                row += '   ' + colored_block(has) + '    '
            print(row)

        print(DIM + '─' * table_width + RESET)

    # ── Legend ────────────────────────────────────────────────────────────────
    print()
    print(f'{GREEN}{BLOCK}{RESET} has data   {RED}{BLOCK}{RESET} all null/zero   {DIM}{DOT}{RESET} year not in file')


if __name__ == '__main__':
    main()
