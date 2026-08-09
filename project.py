"""
Weather CLI Dashboard
CS50's Introduction to Programming with Python - Final Project

A command-line weather dashboard that lets users:
  - Search for any city in the world
  - View current weather conditions, including local date, time, and timezone
  - View a multi-day forecast
  - See weather-based alerts (high wind, extreme heat/cold, heavy rain)
  - Save and manage favorite cities
  - View historical weather statistics for a city
  - Export weather data to CSV, JSON, or a tabular PDF report (with units
    and a 5-day forecast table)
  - Get a quick map link for a location

Weather and geocoding data are provided free of charge (no API key
required) by Open-Meteo: https://open-meteo.com
"""

import csv
import json
import os
import sys
from datetime import datetime, timedelta

import requests
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FAVORITES_FILE = "favorites.json"

# WMO Weather interpretation codes -> human readable description
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def main():
    print("=" * 50)
    print("        COMMAND LINE WEATHER DASHBOARD")
    print("=" * 50)

    while True:
        print(
            "\nMenu:\n"
            "  1. Search for a city and view current weather\n"
            "  2. View forecast for a city\n"
            "  3. View historical statistics for a city\n"
            "  4. Save a favorite city\n"
            "  5. View favorite cities\n"
            "  6. Export last weather data\n"
            "  7. Quit"
        )
        choice = input("Choose an option (1-7): ").strip()

        if choice == "1":
            handle_current_weather()
        elif choice == "2":
            handle_forecast()
        elif choice == "3":
            handle_history()
        elif choice == "4":
            city = input("City name to save as favorite: ").strip()
            save_favorite(city, FAVORITES_FILE)
            print(f"Saved '{city}' to favorites.")
        elif choice == "5":
            favorites = load_favorites(FAVORITES_FILE)
            if not favorites:
                print("You have no favorite cities saved yet.")
            else:
                print("\nFavorite cities:")
                for i, fav in enumerate(favorites, start=1):
                    print(f"  {i}. {fav}")
        elif choice == "6":
            handle_export()
        elif choice == "7":
            print("Goodbye!")
            sys.exit(0)
        else:
            print("Invalid choice, please try again.")


# ---------------------------------------------------------------------------
# Interactive handlers (tie the menu options to the core functions below)
# ---------------------------------------------------------------------------

def handle_current_weather():
    city = input("Enter a city name: ").strip()
    location = geocode_city(city)
    if not location:
        print(f"Could not find a location named '{city}'.")
        return

    weather = get_current_weather(location["latitude"], location["longitude"])
    if not weather:
        print("Could not retrieve weather data right now.")
        return

    display_current_weather(location, weather)

    alerts = check_alerts(weather)
    if alerts:
        print("\n⚠ ALERTS:")
        for alert in alerts:
            print(f"  - {alert}")

    print(f"\nMap: {get_map_url(location['latitude'], location['longitude'])}")

    _LAST_DATA["type"] = "current"
    _LAST_DATA["data"] = {**location, **weather}
    _LAST_DATA["forecast"] = None


def handle_forecast():
    city = input("Enter a city name: ").strip()
    location = geocode_city(city)
    if not location:
        print(f"Could not find a location named '{city}'.")
        return

    forecast = get_forecast(location["latitude"], location["longitude"])
    if not forecast:
        print("Could not retrieve forecast data right now.")
        return

    display_forecast(location, forecast)

    stats = calculate_statistics(forecast["max_temps"])
    print(
        f"\nForecast stats -> avg high: {stats['average']}°C, "
        f"min: {stats['minimum']}°C, max: {stats['maximum']}°C"
    )

    _LAST_DATA["type"] = "forecast"
    _LAST_DATA["data"] = forecast
    _LAST_DATA["forecast"] = forecast


def handle_history():
    city = input("Enter a city name: ").strip()
    location = geocode_city(city)
    if not location:
        print(f"Could not find a location named '{city}'.")
        return

    try:
        days = int(input("How many past days? (e.g. 7): ").strip())
    except ValueError:
        days = 7

    history = get_historical_weather(location["latitude"], location["longitude"], days)
    if not history:
        print("Could not retrieve historical data right now.")
        return

    stats = calculate_statistics(history["max_temps"])
    print(f"\nOver the last {days} days in {location['name']}:")
    print(f"  Average high: {stats['average']}°C")
    print(f"  Hottest day:  {stats['maximum']}°C")
    print(f"  Coldest high: {stats['minimum']}°C")

    _LAST_DATA["type"] = "history"
    _LAST_DATA["data"] = history
    _LAST_DATA["forecast"] = None


def handle_export():
    if not _LAST_DATA["data"]:
        print("No data to export yet. Look up a city first (options 1-3).")
        return
    fmt = input("Export as csv, json, or pdf? ").strip().lower()
    filename = f"weather_export.{fmt}"
    try:
        if fmt == "pdf":
            forecast = _LAST_DATA.get("forecast")
            # If the last lookup wasn't a forecast, and we have location
            # coordinates, fetch a fresh 5-day forecast to include in the
            # PDF's "5-Day Forecast" section.
            if forecast is None and "latitude" in _LAST_DATA["data"]:
                forecast = get_forecast(
                    _LAST_DATA["data"]["latitude"], _LAST_DATA["data"]["longitude"], days=5
                )
            export_weather_report_pdf(
                _LAST_DATA["data"], filename, _LAST_DATA["type"], forecast=forecast
            )
        else:
            export_weather_data(_LAST_DATA["data"], filename, fmt)
        print(f"Exported data to {filename}")
    except ValueError as e:
        print(f"Export failed: {e}")


# Simple in-memory holder so option 6 knows what to export
_LAST_DATA = {"type": None, "data": None, "forecast": None}


# ---------------------------------------------------------------------------
# API functions
# ---------------------------------------------------------------------------

def geocode_city(city_name):
    """Look up a city name and return its coordinates and metadata.

    Returns a dict like {"name", "country", "latitude", "longitude"}
    or None if the city could not be found / the request failed.
    """
    if not city_name:
        return None
    try:
        response = requests.get(
            GEOCODING_URL, params={"name": city_name, "count": 1}, timeout=10
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return None

    results = data.get("results")
    if not results:
        return None

    top = results[0]
    return {
        "name": top.get("name"),
        "country": top.get("country"),
        "latitude": top.get("latitude"),
        "longitude": top.get("longitude"),
        "timezone": top.get("timezone"),
    }


def get_current_weather(latitude, longitude):
    """Fetch current weather conditions for a coordinate pair."""
    try:
        response = requests.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "precipitation,weather_code,wind_speed_10m",
                "timezone": "auto",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return None

    current = data.get("current")
    if not current:
        return None

    local_dt = current.get("time")  # e.g. "2026-08-09T14:30"
    local_date, local_time = split_datetime(local_dt)

    return {
        "temperature": current.get("temperature_2m"),
        "feels_like": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "precipitation": current.get("precipitation"),
        "weather_code": current.get("weather_code"),
        "wind_speed": current.get("wind_speed_10m"),
        "local_date": local_date,
        "local_time": local_time,
        "timezone": data.get("timezone"),
        "timezone_abbreviation": data.get("timezone_abbreviation"),
        "utc_offset_seconds": data.get("utc_offset_seconds"),
    }


def get_forecast(latitude, longitude, days=5):
    """Fetch a multi-day forecast for a coordinate pair."""
    days = max(1, min(days, 16))
    try:
        response = requests.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_sum,wind_speed_10m_max",
                "forecast_days": days,
                "timezone": "auto",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return None

    daily = data.get("daily")
    if not daily:
        return None

    return {
        "dates": daily.get("time", []),
        "max_temps": daily.get("temperature_2m_max", []),
        "min_temps": daily.get("temperature_2m_min", []),
        "precipitation": daily.get("precipitation_sum", []),
        "wind_speeds": daily.get("wind_speed_10m_max", []),
        "weather_codes": daily.get("weather_code", []),
    }


def get_historical_weather(latitude, longitude, days_back=7):
    """Fetch historical daily max/min temperatures for the past N days."""
    end_date = datetime.now().date() - timedelta(days=1)
    start_date = end_date - timedelta(days=days_back - 1)
    try:
        response = requests.get(
            ARCHIVE_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "daily": "temperature_2m_max,temperature_2m_min",
                "timezone": "auto",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return None

    daily = data.get("daily")
    if not daily:
        return None

    return {
        "dates": daily.get("time", []),
        "max_temps": daily.get("temperature_2m_max", []),
        "min_temps": daily.get("temperature_2m_min", []),
    }


# ---------------------------------------------------------------------------
# Pure / testable helper functions
# ---------------------------------------------------------------------------

def weather_code_to_description(code):
    """Translate a WMO weather code into a human-readable description."""
    return WEATHER_CODES.get(code, "Unknown conditions")


def celsius_to_fahrenheit(celsius):
    """Convert a Celsius temperature to Fahrenheit, rounded to 1 decimal."""
    return round((celsius * 9 / 5) + 32, 1)


def split_datetime(iso_datetime):
    """Split an ISO 8601 'YYYY-MM-DDTHH:MM' string into (date, time).

    Returns (None, None) if given a falsy/invalid value.
    """
    if not iso_datetime or "T" not in iso_datetime:
        return None, None
    date_part, time_part = iso_datetime.split("T", 1)
    return date_part, time_part


def calculate_statistics(temperatures):
    """Given a list of temperatures, return average/min/max stats.

    Raises ValueError if the list is empty.
    """
    if not temperatures:
        raise ValueError("Cannot calculate statistics for an empty list")

    return {
        "average": round(sum(temperatures) / len(temperatures), 1),
        "minimum": round(min(temperatures), 1),
        "maximum": round(max(temperatures), 1),
    }


def check_alerts(weather):
    """Inspect a current-weather dict and return a list of alert strings.

    Looks at temperature, wind speed, and precipitation to flag
    potentially dangerous conditions.
    """
    alerts = []
    temp = weather.get("temperature")
    wind = weather.get("wind_speed")
    precip = weather.get("precipitation")

    if temp is not None:
        if temp >= 38:
            alerts.append("Extreme heat warning")
        elif temp <= -15:
            alerts.append("Extreme cold warning")

    if wind is not None and wind >= 50:
        alerts.append("High wind warning")

    if precip is not None and precip >= 10:
        alerts.append("Heavy precipitation warning")

    return alerts


def get_map_url(latitude, longitude):
    """Build an OpenStreetMap link for a set of coordinates."""
    return f"https://www.openstreetmap.org/#map=10/{latitude}/{longitude}"


def load_favorites(filepath):
    """Load the list of favorite city names from a JSON file.

    Returns an empty list if the file doesn't exist or is invalid.
    """
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except (json.JSONDecodeError, OSError):
        return []


def save_favorite(city_name, filepath):
    """Add a city name to the favorites JSON file (no duplicates)."""
    favorites = load_favorites(filepath)
    if city_name not in favorites:
        favorites.append(city_name)
    with open(filepath, "w") as f:
        json.dump(favorites, f, indent=2)
    return favorites


def export_weather_data(data, filename, file_format):
    """Export a dict of weather data to either CSV or JSON.

    Raises ValueError for an unsupported format.
    """
    file_format = file_format.lower()
    if file_format == "json":
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
    elif file_format == "csv":
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["field", "value"])
            for key, value in data.items():
                writer.writerow([key, value])
    else:
        raise ValueError(f"Unsupported export format: {file_format}")
    return True


# Units for each known field, used to label rows and forecast columns in
# the PDF report.
FIELD_UNITS = {
    "temperature": "°C",
    "feels_like": "°C",
    "humidity": "%",
    "precipitation": "mm",
    "wind_speed": "km/h",
    "max_temps": "°C",
    "min_temps": "°C",
    "precipitation_sum": "mm",
    "wind_speeds": "km/h",
}

# Fields that are list-shaped (e.g. multi-day forecast arrays) get their
# values joined into a single readable string in the Details table rather
# than being skipped — every field from the source data is shown.


def _field_label(key):
    """Turn a snake_case field name into a readable label with its unit."""
    label = key.replace("_", " ").capitalize()
    unit = FIELD_UNITS.get(key)
    return f"{label} ({unit})" if unit else label


def export_weather_report_pdf(data, filename, report_type=None, forecast=None):
    """Export weather data to a formatted, tabular PDF report.

    The report always includes:
      - A title and generation timestamp
      - Location, local date/time, and timezone (when present in `data`
        or `forecast`)
      - A "Details" table listing every field in `data`, each labeled
        with its unit where known (°C, %, mm, km/h, etc.) — nothing is
        omitted, including location name, country, coordinates, and
        timezone fields
      - A 5-day forecast table (date, high, low, precipitation, wind,
        condition) built from `forecast` if provided, or from `data`
        itself when `data` already looks like forecast data (i.e. has
        a "dates" list)

    `forecast` should be a dict shaped like the return value of
    `get_forecast` (keys: dates, max_temps, min_temps, precipitation,
    wind_speeds, weather_codes). Only the first 5 entries are used.

    Raises ValueError if `data` is empty/falsy.
    """
    if not data:
        raise ValueError("No data available to export")

    styles = getSampleStyleSheet()
    story = []

    title_text = "Weather Report"
    if report_type:
        title_text = f"Weather Report - {report_type.capitalize()}"
    story.append(Paragraph(title_text, styles["Title"]))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]
    ))

    # Location / local date-time / timezone summary line(s)
    if data.get("name"):
        location_line = data["name"]
        if data.get("country"):
            location_line += f", {data['country']}"
        story.append(Paragraph(f"Location: {location_line}", styles["Normal"]))
    if data.get("local_date") or data.get("local_time"):
        tz_label = data.get("timezone_abbreviation") or data.get("timezone") or ""
        story.append(Paragraph(
            f"Local date/time: {data.get('local_date', '')} "
            f"{data.get('local_time', '')} {tz_label}".strip(),
            styles["Normal"],
        ))
    elif data.get("timezone"):
        story.append(Paragraph(f"Timezone: {data['timezone']}", styles["Normal"]))

    story.append(Spacer(1, 12))

    # --- Details table: every field from `data` gets its own row,
    # nothing is skipped ---
    detail_rows = [["Field", "Value"]]
    for key, value in data.items():
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        detail_rows.append([_field_label(key), str(value)])

    if len(detail_rows) > 1:
        story.append(Paragraph("Details", styles["Heading2"]))
        detail_table = Table(detail_rows, colWidths=[180, 270])
        detail_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(detail_table)
        story.append(Spacer(1, 16))

    # --- 5-day forecast table ---
    forecast_source = forecast if forecast else (data if "dates" in data else None)
    if forecast_source and forecast_source.get("dates"):
        story.append(Paragraph("5-Day Forecast", styles["Heading2"]))

        forecast_rows = [["Date", "High (°C)", "Low (°C)", "Precip (mm)", "Wind (km/h)", "Condition"]]
        dates = forecast_source.get("dates", [])[:5]
        max_temps = forecast_source.get("max_temps", [])
        min_temps = forecast_source.get("min_temps", [])
        precip = forecast_source.get("precipitation", [])
        wind = forecast_source.get("wind_speeds", [])
        codes = forecast_source.get("weather_codes", [])

        for i, date in enumerate(dates):
            hi = max_temps[i] if i < len(max_temps) else ""
            lo = min_temps[i] if i < len(min_temps) else ""
            pr = precip[i] if i < len(precip) else ""
            wd = wind[i] if i < len(wind) else ""
            cond = weather_code_to_description(codes[i]) if i < len(codes) else ""
            forecast_rows.append([str(date), str(hi), str(lo), str(pr), str(wd), cond])

        forecast_table = Table(
            forecast_rows, colWidths=[75, 60, 55, 65, 65, 130]
        )
        forecast_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(forecast_table)

    doc = SimpleDocTemplate(filename, pagesize=letter)
    doc.build(story)
    return True


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def display_current_weather(location, weather):
    print(f"\nCurrent weather in {location['name']}, {location['country']}:")
    if weather.get("local_date") or weather.get("local_time"):
        tz_label = weather.get("timezone_abbreviation") or weather.get("timezone") or ""
        print(f"  Local date:   {weather.get('local_date')}")
        print(f"  Local time:   {weather.get('local_time')} {tz_label}".rstrip())
    if weather.get("timezone"):
        print(f"  Timezone:     {weather['timezone']}")
    print(f"  Condition:    {weather_code_to_description(weather['weather_code'])}")
    print(f"  Temperature:  {weather['temperature']}°C "
          f"({celsius_to_fahrenheit(weather['temperature'])}°F)")
    print(f"  Feels like:   {weather['feels_like']}°C")
    print(f"  Humidity:     {weather['humidity']}%")
    print(f"  Wind speed:   {weather['wind_speed']} km/h")
    print(f"  Precipitation: {weather['precipitation']} mm")


def display_forecast(location, forecast):
    print(f"\nForecast for {location['name']}, {location['country']}:")
    for date, hi, lo, code in zip(
        forecast["dates"], forecast["max_temps"], forecast["min_temps"],
        forecast["weather_codes"]
    ):
        print(f"  {date}: {hi}°C / {lo}°C - {weather_code_to_description(code)}")


if __name__ == "__main__":
    main()
