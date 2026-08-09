# Command Line Weather Dashboard

#### Video Demo: <URL HERE>

## Description

Command Line Weather Dashboard is a Python CLI application. It turns
the terminal into a small, self-contained weather app: you can search for
any city on Earth, check current conditions, pull a multi-day forecast,
look at recent historical temperatures, save favorite cities for quick
access later, and export whatever you looked up to a CSV, JSON or PDF file.

All weather and location data comes from [Open-Meteo](https://open-meteo.com),
a free weather API that requires no API key or sign-up, which keeps the
project easy for anyone to run.

## Features

- **City search / geocoding** — type a city name and the app resolves it
  to coordinates and a country using Open-Meteo's geocoding endpoint.
- **Current weather** — temperature (with a Celsius→Fahrenheit
  conversion), "feels like" temperature, humidity, wind speed, a
  plain-English description translated from the raw WMO weather code,
  and the location's local date, local time, and timezone (e.g.
  `Asia/Kolkata` / `IST`).
- **Forecast** — a configurable multi-day forecast with daily highs,
  lows, and conditions, plus quick average/min/max statistics.
- **Alerts** — the app scans the current conditions for extreme heat,
  extreme cold, high wind, and heavy precipitation and prints warnings.
- **Historical statistics** — pulls the last N days of daily
  temperatures for a city from Open-Meteo's archive API and summarizes
  them.
- **Favorites** — save cities you check often to a local `favorites.json`
  file so you don't have to retype them.
- **Export** — dump the most recent lookup to `weather_export.csv`,
  `weather_export.json`, or a tabular `weather_export.pdf` report
  (built with `reportlab`). The PDF includes:
  - Location, local date/time, and timezone
  - A "Details" table listing **every** field from the lookup — name,
    country, coordinates, timezone info, and all measurements — each
    labeled with its unit where known (°C, %, mm, km/h); nothing is
    filtered out
  - A 5-day forecast table (date, high, low, precipitation, wind,
    condition), automatically fetched if the export wasn't already a
    forecast lookup
- **Map link** — every current-weather lookup prints a ready-to-click
  OpenStreetMap link centered on that city.

## Project structure

```
project.py         # main() plus all application logic
test_project.py     # pytest tests for the pure/testable functions
requirements.txt    # pip dependencies (requests, pytest, reportlab, pypdf)
favorites.json       # created automatically the first time you save a favorite
weather_export.csv/json/pdf  # created when you use the export feature
README.md
```

## How it works

`project.py` is organized into a few clear layers:

1. **Interactive menu (`main`)** — a simple numbered menu loop that
   dispatches to handler functions (`handle_current_weather`,
   `handle_forecast`, `handle_history`, `handle_export`). Keeping these
   handlers separate from `main` itself made the control flow much
   easier to reason about and test around.
2. **API functions** (`geocode_city`, `get_current_weather`,
   `get_forecast`, `get_historical_weather`) — each wraps a single
   Open-Meteo endpoint, handles network errors with `try/except`, and
   returns either a clean dictionary or `None` so the rest of the app
   never has to deal with raw API responses or exceptions directly.
3. **Pure helper functions** — the heart of the project for grading
   purposes, since these are the ones covered by `test_project.py`:
   - `weather_code_to_description` maps Open-Meteo's numeric WMO
     weather codes to readable text.
   - `celsius_to_fahrenheit` does the temperature conversion.
   - `split_datetime` splits Open-Meteo's local ISO 8601 timestamp
     (e.g. `2026-08-09T18:45`) into a separate date and time string.
   - `calculate_statistics` computes average/min/max over a list of
     temperatures (used for both forecasts and historical data) and
     raises `ValueError` on empty input rather than silently failing.
   - `check_alerts` inspects a current-weather dictionary and returns a
     list of human-readable warnings.
   - `get_map_url` builds an OpenStreetMap link from coordinates.
   - `load_favorites` / `save_favorite` handle reading and writing
     `favorites.json`, including de-duplication.
   - `export_weather_data` writes a dictionary to CSV or JSON and
     raises `ValueError` for unsupported formats.
   - `export_weather_report_pdf` writes a dictionary to a formatted,
     tabular PDF report — title, timestamp, location/local
     date-time/timezone, a unit-labeled "Details" table covering every
     field with no omissions, and a 5-day forecast table — using
     `reportlab`, and raises `ValueError` if given empty data.
4. **Display helpers** (`display_current_weather`, `display_forecast`)
   — keep all the `print` formatting out of the logic functions, which
   is what made the logic functions easy to unit test in the first
   place.

## Design decisions

I split API calls, pure calculations, and display/printing into
separate functions on purpose. Functions that touch the network are
inherently hard (and slow/unreliable) to unit test, so I made sure
every function with real logic worth testing — statistics, alert
rules, unit conversion, file I/O, string building, PDF generation —
has zero dependency on the network. That's also why `test_project.py`
never calls the real API: all eight tests target pure/file-I/O
functions and use `tmp_path` for anything touching the filesystem
(including the generated PDF and CSV/JSON exports), so the whole
suite runs in well under a second and never depends on internet
access or external state.

I chose Open-Meteo over alternatives like OpenWeatherMap specifically
because it needs no API key, which means anyone grading or reusing this
project can run it immediately with just `pip install -r requirements.txt`.

## How to run it

```
pip3 install -r requirements.txt
python3 project.py
```
## Running the tests

```
pytest test_project.py
```

Then follow the on-screen menu.

## Possible future improvements

- Support looking up multiple cities at once for side-by-side
  comparison.
- Cache API responses locally to reduce repeated calls for the same
  city within a short window.
- Add a `--city` command-line flag (via `argparse`) for a non-interactive,
  scriptable mode alongside the interactive menu.
