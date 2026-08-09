import json
import os

import pytest
from pypdf import PdfReader

from project import (
    calculate_statistics,
    celsius_to_fahrenheit,
    check_alerts,
    export_weather_data,
    export_weather_report_pdf,
    get_map_url,
    load_favorites,
    save_favorite,
    split_datetime,
    weather_code_to_description,
)


def test_weather_code_to_description():
    assert weather_code_to_description(0) == "Clear sky"
    assert weather_code_to_description(95) == "Thunderstorm"
    # Unknown codes should not raise an error
    assert weather_code_to_description(-1) == "Unknown conditions"


def test_celsius_to_fahrenheit():
    assert celsius_to_fahrenheit(0) == 32.0
    assert celsius_to_fahrenheit(100) == 212.0
    assert celsius_to_fahrenheit(-40) == -40.0
    assert celsius_to_fahrenheit(37) == 98.6


def test_split_datetime():
    assert split_datetime("2026-08-09T14:30") == ("2026-08-09", "14:30")
    assert split_datetime("2026-01-01T00:00") == ("2026-01-01", "00:00")
    # Falsy / malformed input should not raise
    assert split_datetime(None) == (None, None)
    assert split_datetime("") == (None, None)
    assert split_datetime("no-time-here") == (None, None)


def test_calculate_statistics():
    stats = calculate_statistics([10, 20, 30])
    assert stats == {"average": 20.0, "minimum": 10, "maximum": 30}

    stats = calculate_statistics([5.5])
    assert stats == {"average": 5.5, "minimum": 5.5, "maximum": 5.5}

    with pytest.raises(ValueError):
        calculate_statistics([])


def test_check_alerts():
    # No dangerous conditions
    assert check_alerts({"temperature": 20, "wind_speed": 10, "precipitation": 0}) == []

    # Extreme heat
    assert "Extreme heat warning" in check_alerts(
        {"temperature": 40, "wind_speed": 5, "precipitation": 0}
    )

    # Extreme cold
    assert "Extreme cold warning" in check_alerts(
        {"temperature": -20, "wind_speed": 5, "precipitation": 0}
    )

    # High wind
    assert "High wind warning" in check_alerts(
        {"temperature": 20, "wind_speed": 60, "precipitation": 0}
    )

    # Heavy precipitation
    assert "Heavy precipitation warning" in check_alerts(
        {"temperature": 20, "wind_speed": 5, "precipitation": 15}
    )

    # Multiple alerts at once
    alerts = check_alerts({"temperature": 40, "wind_speed": 60, "precipitation": 20})
    assert len(alerts) == 3


def test_get_map_url():
    url = get_map_url(51.5074, -0.1278)
    assert url == "https://www.openstreetmap.org/#map=10/51.5074/-0.1278"
    assert "openstreetmap.org" in url


def test_save_and_load_favorites(tmp_path):
    filepath = tmp_path / "favorites.json"

    # No file yet -> empty list
    assert load_favorites(str(filepath)) == []

    save_favorite("Paris", str(filepath))
    save_favorite("Tokyo", str(filepath))
    favorites = load_favorites(str(filepath))
    assert favorites == ["Paris", "Tokyo"]

    # Saving a duplicate shouldn't add a second entry
    save_favorite("Paris", str(filepath))
    favorites = load_favorites(str(filepath))
    assert favorites.count("Paris") == 1
    assert len(favorites) == 2


def test_export_weather_data(tmp_path):
    data = {"temperature": 21.5, "humidity": 60}

    json_path = tmp_path / "weather.json"
    export_weather_data(data, str(json_path), "json")
    assert json_path.exists()
    with open(json_path) as f:
        loaded = json.load(f)
    assert loaded == data

    csv_path = tmp_path / "weather.csv"
    export_weather_data(data, str(csv_path), "csv")
    assert csv_path.exists()
    content = csv_path.read_text()
    assert "temperature" in content
    assert "21.5" in content

    with pytest.raises(ValueError):
        export_weather_data(data, str(tmp_path / "weather.txt"), "txt")


def test_export_weather_report_pdf(tmp_path):
    data = {
        "name": "Paris",
        "country": "France",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "local_date": "2026-08-09",
        "local_time": "14:30",
        "timezone": "Europe/Paris",
        "timezone_abbreviation": "CEST",
        "temperature": 21.5,
        "humidity": 60,
        "weather_code": 0,
    }

    pdf_path = tmp_path / "weather.pdf"
    export_weather_report_pdf(data, str(pdf_path), report_type="current")
    assert pdf_path.exists()
    # A real PDF starts with the %PDF header
    assert pdf_path.read_bytes()[:4] == b"%PDF"

    # Works fine without a report_type
    pdf_path2 = tmp_path / "weather2.pdf"
    export_weather_report_pdf(data, str(pdf_path2), report_type=None)
    assert pdf_path2.exists()

    with pytest.raises(ValueError):
        export_weather_report_pdf({}, str(tmp_path / "empty.pdf"), report_type="current")


def test_export_weather_report_pdf_includes_5day_forecast(tmp_path):
    """A forecast dict passed in should produce a non-trivial PDF
    (bigger than a report with no forecast table)."""
    data = {"name": "Tokyo", "country": "Japan", "temperature": 25.0}
    forecast = {
        "dates": ["2026-08-09", "2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13"],
        "max_temps": [30, 31, 29, 28, 27],
        "min_temps": [22, 23, 21, 20, 19],
        "precipitation": [0, 2, 5, 0, 1],
        "wind_speeds": [10, 12, 15, 8, 9],
        "weather_codes": [0, 1, 61, 2, 3],
    }

    no_forecast_path = tmp_path / "no_forecast.pdf"
    export_weather_report_pdf(data, str(no_forecast_path))

    with_forecast_path = tmp_path / "with_forecast.pdf"
    export_weather_report_pdf(data, str(with_forecast_path), forecast=forecast)

    assert with_forecast_path.exists()
    assert with_forecast_path.read_bytes()[:4] == b"%PDF"
    # Including the forecast table should meaningfully increase file size
    assert with_forecast_path.stat().st_size > no_forecast_path.stat().st_size


def test_export_weather_report_pdf_forecast_data_self_contained(tmp_path):
    """When `data` itself is forecast-shaped (has 'dates'), the forecast
    table should be built from it without needing a separate `forecast`
    argument."""
    forecast = {
        "dates": ["2026-08-09", "2026-08-10"],
        "max_temps": [30, 31],
        "min_temps": [22, 23],
        "precipitation": [0, 2],
        "wind_speeds": [10, 12],
        "weather_codes": [0, 1],
    }
    pdf_path = tmp_path / "forecast_only.pdf"
    export_weather_report_pdf(forecast, str(pdf_path), report_type="forecast")
    assert pdf_path.exists()
    assert pdf_path.read_bytes()[:4] == b"%PDF"


def test_export_weather_report_pdf_no_fields_skipped(tmp_path):
    """Every field in `data` -- including location, coordinates, and
    timezone fields that used to be filtered out -- must show up as its
    own row in the Details table."""
    data = {
        "name": "Bhopal",
        "country": "India",
        "latitude": 23.2599,
        "longitude": 77.4126,
        "local_date": "2026-08-09",
        "local_time": "18:45",
        "timezone": "Asia/Kolkata",
        "timezone_abbreviation": "IST",
        "utc_offset_seconds": 19800,
        "temperature": 29.4,
        "feels_like": 32.1,
        "humidity": 78,
        "wind_speed": 14.2,
        "precipitation": 2.0,
        "weather_code": 61,
    }

    pdf_path = tmp_path / "all_fields.pdf"
    export_weather_report_pdf(data, str(pdf_path), report_type="current")

    reader = PdfReader(str(pdf_path))
    text = "\n".join(page.extract_text() for page in reader.pages)

    # Every field's label (and value) should be present somewhere in the
    # rendered PDF text -- nothing from `data` is silently dropped.
    expected_labels = [
        "Name", "Country", "Latitude", "Longitude", "Local date",
        "Local time", "Timezone", "Timezone abbreviation",
        "Utc offset seconds", "Temperature", "Feels like", "Humidity",
        "Wind speed", "Precipitation", "Weather code",
    ]
    for label in expected_labels:
        assert label in text, f"Expected field label '{label}' missing from PDF"

    for value in ["Bhopal", "India", "23.2599", "77.4126", "Asia/Kolkata", "IST", "19800"]:
        assert value in text, f"Expected value '{value}' missing from PDF"
