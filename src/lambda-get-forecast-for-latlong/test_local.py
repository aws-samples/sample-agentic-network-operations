#!/usr/bin/env python3
"""
Local test script for the weather forecast Lambda function.
"""

import json
from lambda_handler import lambda_handler


def test_valid_coordinates():
    """Test with valid London coordinates."""
    print("Test 1: Valid coordinates (London)")
    print("-" * 50)
    
    event = {
        'latitude': 51.5074,
        'longitude': -0.1278
    }
    
    result = lambda_handler(event, None)
    print(f"Status Code: {result['statusCode']}")
    
    if result['statusCode'] == 200:
        body = json.loads(result['body'])
        print(f"Location: {body['latitude']}, {body['longitude']}")
        print(f"Timezone: {body['timezone']}")
        print(f"\nForecast Summary:")
        summary = body['forecast_summary']
        print(f"  Precipitation events: {summary['total_precipitation_events']}")
        print(f"  High wind events: {summary['total_high_wind_events']}")
        print(f"\nDaily Summary:")
        for day in summary['daily_summary']:
            print(f"  {day['date']}: {day['total_precipitation_mm']}mm rain, "
                  f"max wind {day['max_wind_speed_kmh']} km/h")
        
        print(f"\nFull Response (formatted):")
        print(json.dumps(body, indent=2))
    else:
        error_body = json.loads(result['body'])
        print(f"Error: {json.dumps(error_body, indent=2)}")
    
    print()


def test_missing_parameters():
    """Test with missing parameters."""
    print("Test 2: Missing parameters")
    print("-" * 50)
    
    event = {'latitude': 51.5074}
    result = lambda_handler(event, None)
    print(f"Status Code: {result['statusCode']}")
    error_body = json.loads(result['body'])
    print(f"Response: {json.dumps(error_body, indent=2)}")
    print()


def test_invalid_coordinates():
    """Test with invalid coordinates."""
    print("Test 3: Invalid coordinates")
    print("-" * 50)
    
    event = {
        'latitude': 999,
        'longitude': -0.1278
    }
    
    result = lambda_handler(event, None)
    print(f"Status Code: {result['statusCode']}")
    error_body = json.loads(result['body'])
    print(f"Response: {json.dumps(error_body, indent=2)}")
    print()


def test_multiple_uk_locations():
    """Test multiple UK locations."""
    print("Test 4: Multiple UK locations")
    print("-" * 50)
    
    locations = [
        {'name': 'London', 'latitude': 51.5074, 'longitude': -0.1278},
        {'name': 'Manchester', 'latitude': 53.4808, 'longitude': -2.2426},
        {'name': 'Edinburgh', 'latitude': 55.9533, 'longitude': -3.1883},
    ]
    
    for location in locations:
        event = {
            'latitude': location['latitude'],
            'longitude': location['longitude']
        }
        
        result = lambda_handler(event, None)
        if result['statusCode'] == 200:
            body = json.loads(result['body'])
            summary = body['forecast_summary']
            print(f"{location['name']}: "
                  f"{summary['total_precipitation_events']} precip events, "
                  f"{summary['total_high_wind_events']} wind events")
        else:
            print(f"{location['name']}: Error - {result['body']}")
    
    print()


if __name__ == '__main__':
    test_valid_coordinates()
    test_missing_parameters()
    test_invalid_coordinates()
    test_multiple_uk_locations()
    
    print("All tests completed!")
