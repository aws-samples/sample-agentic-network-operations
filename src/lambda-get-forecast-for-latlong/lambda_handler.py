"""
Lambda function to get weather forecast for a given latitude/longitude.
Uses the Open-Meteo API to retrieve precipitation and wind speed forecasts.

NOTE Only for non-commercial use and less than 10.000 daily API calls, otherwise a commercial license must be obtained.
"""

import json
import logging
from typing import Dict, Any, List
from datetime import datetime
import requests


OPEN_METEO_FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
HTTP_TIMEOUT_SECONDS = (3.05, 10)
logger = logging.getLogger(__name__)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Get 7-day weather forecast for a UK location.
    
    Args:
        event: Lambda event containing 'latitude' and 'longitude' parameters
        context: Lambda context object
        
    Returns:
        Dict containing statusCode and body with forecast data
    """
    try:
        # Extract coordinates from event
        latitude = event.get('latitude')
        longitude = event.get('longitude')
        
        if latitude is None or longitude is None:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required parameters: latitude and longitude'
                })
            }
        
        # Validate coordinates
        try:
            lat = float(latitude)
            lon = float(longitude)
            
            if not (-90 <= lat <= 90):
                raise ValueError('Latitude must be between -90 and 90')
            if not (-180 <= lon <= 180):
                raise ValueError('Longitude must be between -180 and 180')
                
        except (ValueError, TypeError) as e:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': f'Invalid coordinates: {str(e)}'
                })
            }
        
        # Keep the host fixed and let requests safely encode query parameters.
        response = requests.get(
            OPEN_METEO_FORECAST_URL,
            params={
                'latitude': lat,
                'longitude': lon,
                'hourly': 'precipitation,wind_speed_10m',
                'forecast_days': 7,
                'timezone': 'Europe/London',
            },
            timeout=HTTP_TIMEOUT_SECONDS,
            verify=True,
            allow_redirects=False,
        )

        if response.is_redirect:
            raise requests.HTTPError('Unexpected redirect from weather API')
        response.raise_for_status()
        data = response.json()

        # Process the hourly data
        hourly = data.get('hourly', {})
        times = hourly.get('time', [])
        precipitation = hourly.get('precipitation', [])
        wind_speed = hourly.get('wind_speed_10m', [])

        # Analyze forecast for significant weather events
        forecast_summary = analyze_forecast(times, precipitation, wind_speed)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'latitude': lat,
                'longitude': lon,
                'timezone': data.get('timezone'),
                'forecast_summary': forecast_summary,
                # Returning all the hourly data makes the response far too verbose
                # 'hourly_data': {
                #     'time': times,
                #     'precipitation_mm': precipitation,
                #     'wind_speed_kmh': wind_speed
                # }
            })
        }

    except requests.HTTPError:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Weather service returned an unexpected response'
            })
        }

    except requests.RequestException:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Unable to retrieve the weather forecast'
            })
        }
        
    except Exception:
        logger.exception('Unexpected weather forecast processing failure')
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Unable to process the weather forecast'
            })
        }


def analyze_forecast(times: List[str], precipitation: List[float], 
                     wind_speed: List[float]) -> Dict[str, Any]:
    """
    Analyze forecast data to identify significant weather events.
    
    Args:
        times: List of timestamp strings
        precipitation: List of precipitation values in mm
        wind_speed: List of wind speed values in km/h
        
    Returns:
        Dict with summary of significant weather events
    """
    HIGH_WIND_THRESHOLD = 40  # km/h (approximately 25 mph)
    SIGNIFICANT_PRECIPITATION_THRESHOLD = 2.0  # mm per hour
    
    high_precipitation_events = []
    high_wind_events = []
    
    for i, time_str in enumerate(times):
        precip = precipitation[i] if i < len(precipitation) else 0
        wind = wind_speed[i] if i < len(wind_speed) else 0
        
        # Check for significant precipitation
        if precip >= SIGNIFICANT_PRECIPITATION_THRESHOLD:
            high_precipitation_events.append({
                'time': time_str,
                'precipitation_mm': round(precip, 2)
            })
        
        # Check for high winds
        if wind >= HIGH_WIND_THRESHOLD:
            high_wind_events.append({
                'time': time_str,
                'wind_speed_kmh': round(wind, 2)
            })
    
    # Calculate daily totals
    daily_totals = calculate_daily_totals(times, precipitation, wind_speed)
    
    return {
        'total_high_precipitation_events': len(high_precipitation_events),
        'total_high_wind_events': len(high_wind_events),
        'high_precipitation_events': high_precipitation_events[:20],  # Limit to first 20
        'high_wind_events': high_wind_events[:20],  # Limit to first 20
        'daily_summary': daily_totals,
        'thresholds': {
            'high_wind_kmh': HIGH_WIND_THRESHOLD,
            'significant_precipitation_mm': SIGNIFICANT_PRECIPITATION_THRESHOLD
        }
    }


def calculate_daily_totals(times: List[str], precipitation: List[float], 
                           wind_speed: List[float]) -> List[Dict[str, Any]]:
    """
    Calculate daily totals and maximums.
    
    Args:
        times: List of timestamp strings
        precipitation: List of precipitation values
        wind_speed: List of wind speed values
        
    Returns:
        List of daily summaries
    """
    daily_data = {}
    
    for i, time_str in enumerate(times):
        date = time_str.split('T')[0]
        
        if date not in daily_data:
            daily_data[date] = {
                'date': date,
                'total_precipitation_mm': 0,
                'max_wind_speed_kmh': 0
            }
        
        if i < len(precipitation):
            daily_data[date]['total_precipitation_mm'] += precipitation[i]
        
        if i < len(wind_speed):
            daily_data[date]['max_wind_speed_kmh'] = max(
                daily_data[date]['max_wind_speed_kmh'], 
                wind_speed[i]
            )
    
    # Round values and sort by date
    result = []
    for date in sorted(daily_data.keys()):
        data = daily_data[date]
        result.append({
            'date': date,
            'total_precipitation_mm': round(data['total_precipitation_mm'], 2),
            'max_wind_speed_kmh': round(data['max_wind_speed_kmh'], 2)
        })
    
    return result
