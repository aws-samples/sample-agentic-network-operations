import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock, patch


MODULE_PATH = Path(__file__).with_name('lambda_handler.py')
SPEC = importlib.util.spec_from_file_location('postcode_lambda_handler', MODULE_PATH)
postcode = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(postcode)


def test_postcode_request_uses_fixed_endpoint_and_safe_request_options():
    response = Mock()
    response.is_redirect = False
    response.status_code = 200
    response.json.return_value = {
        'status': 200,
        'result': {
            'postcode': 'SW1A 1AA',
            'latitude': 51.501,
            'longitude': -0.141,
            'region': 'London',
            'country': 'England',
            'admin_district': 'Westminster',
        },
    }

    with patch.object(postcode.requests, 'get', return_value=response) as get:
        result = postcode.lambda_handler({'postcode': 'SW1A 1AA'}, None)

    assert result['statusCode'] == 200
    assert json.loads(result['body'])['postcode'] == 'SW1A 1AA'
    get.assert_called_once_with(
        f'{postcode.POSTCODES_API_URL}/SW1A%201AA',
        timeout=postcode.HTTP_TIMEOUT_SECONDS,
        verify=True,
        allow_redirects=False,
    )


def test_postcode_rejects_missing_input_without_http_request():
    with patch.object(postcode.requests, 'get') as get:
        result = postcode.lambda_handler({}, None)

    assert result['statusCode'] == 400
    get.assert_not_called()


def test_postcode_rejects_redirects():
    response = Mock()
    response.is_redirect = True
    response.status_code = 302

    with patch.object(postcode.requests, 'get', return_value=response):
        result = postcode.lambda_handler({'postcode': 'SW1A 1AA'}, None)

    assert result['statusCode'] == 500
    assert json.loads(result['body'])['error'] == 'Postcode service returned an unexpected response'


def test_postcode_hides_unexpected_exception_details():
    response = Mock()
    response.is_redirect = False
    response.status_code = 200
    response.json.side_effect = RuntimeError('internal postcode parser detail')

    with patch.object(postcode.requests, 'get', return_value=response):
        result = postcode.lambda_handler({'postcode': 'SW1A 1AA'}, None)

    assert result['statusCode'] == 500
    body = json.loads(result['body'])
    assert body['error'] == 'Unable to process postcode information'
    assert 'internal postcode parser detail' not in body['error']
