import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock, patch


MODULE_PATH = Path(__file__).with_name('lambda_handler.py')
SPEC = importlib.util.spec_from_file_location('weather_lambda_handler', MODULE_PATH)
weather = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(weather)


def test_weather_request_uses_fixed_endpoint_and_safe_request_options():
    response = Mock()
    response.is_redirect = False
    response.json.return_value = {
        'timezone': 'Europe/London',
        'hourly': {
            'time': ['2026-07-23T00:00'],
            'precipitation': [0],
            'wind_speed_10m': [10],
        },
    }

    with patch.object(weather.requests, 'get', return_value=response) as get:
        result = weather.lambda_handler({'latitude': '54.5', 'longitude': '-3.2'}, None)

    assert result['statusCode'] == 200
    assert json.loads(result['body'])['latitude'] == 54.5
    get.assert_called_once_with(
        weather.OPEN_METEO_FORECAST_URL,
        params={
            'latitude': 54.5,
            'longitude': -3.2,
            'hourly': 'precipitation,wind_speed_10m',
            'forecast_days': 7,
            'timezone': 'Europe/London',
        },
        timeout=weather.HTTP_TIMEOUT_SECONDS,
        verify=True,
        allow_redirects=False,
    )


def test_weather_rejects_invalid_coordinates_without_http_request():
    with patch.object(weather.requests, 'get') as get:
        result = weather.lambda_handler({'latitude': '91', 'longitude': '0'}, None)

    assert result['statusCode'] == 400
    get.assert_not_called()


def test_weather_rejects_redirects():
    response = Mock()
    response.is_redirect = True

    with patch.object(weather.requests, 'get', return_value=response):
        result = weather.lambda_handler({'latitude': '54.5', 'longitude': '-3.2'}, None)

    assert result['statusCode'] == 500
    assert json.loads(result['body'])['error'] == 'Weather service returned an unexpected response'


def test_weather_hides_unexpected_exception_details():
    response = Mock()
    response.is_redirect = False
    response.json.side_effect = RuntimeError('internal weather parser detail')

    with patch.object(weather.requests, 'get', return_value=response):
        result = weather.lambda_handler({'latitude': '54.5', 'longitude': '-3.2'}, None)

    assert result['statusCode'] == 500
    body = json.loads(result['body'])
    assert body['error'] == 'Unable to process the weather forecast'
    assert 'internal weather parser detail' not in body['error']
