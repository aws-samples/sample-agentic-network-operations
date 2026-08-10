"""
Lambda function to convert UK postcodes to latitude/longitude coordinates.
Uses the postcodes.io API for geocoding.

See here for full schema of returnable parameters https://postcodes.io/docs/postcode/schema
"""

import json
import logging
from typing import Dict, Any
from urllib.parse import quote
import requests


POSTCODES_API_URL = 'https://api.postcodes.io/postcodes'
HTTP_TIMEOUT_SECONDS = (3.05, 10)
logger = logging.getLogger(__name__)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Convert a UK postcode to latitude and longitude coordinates.
    
    Args:
        event: Lambda event containing 'postcode' parameter
        context: Lambda context object
        
    Returns:
        Dict containing statusCode, body with latitude, longitude, and postcode info
    """
    try:
        # Extract postcode from event
        postcode = event.get('postcode', '').strip()
        
        if not postcode:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required parameter: postcode'
                })
            }
        
        # The API requires the postcode in the path; quote it before constructing
        # a URL from the fixed service endpoint.
        response = requests.get(
            f'{POSTCODES_API_URL}/{quote(postcode, safe="")}',
            timeout=HTTP_TIMEOUT_SECONDS,
            verify=True,
            allow_redirects=False,
        )

        if response.is_redirect:
            raise requests.HTTPError('Unexpected redirect from postcode API')
        if response.status_code == 404:
            return {
                'statusCode': 404,
                'body': json.dumps({
                    'error': 'Invalid postcode format or postcode not found'
                })
            }
        response.raise_for_status()
        data = response.json()

        if data.get('status') == 200 and data.get('result'):
            result = data['result']

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'postcode': result.get('postcode'),
                    'latitude': result.get('latitude'),
                    'longitude': result.get('longitude'),
                    'region': result.get('region'),
                    'country': result.get('country'),
                    'admin_district': result.get('admin_district')
                })
            }

        return {
            'statusCode': 404,
            'body': json.dumps({
                'error': 'Postcode not found'
            })
        }

    except requests.HTTPError:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Postcode service returned an unexpected response'
            })
        }

    except requests.RequestException:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Unable to retrieve postcode information'
            })
        }
        
    except Exception:
        logger.exception('Unexpected postcode processing failure')
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Unable to process postcode information'
            })
        }
