"""
PSR Lookup Lambda Handler

This Lambda function provides Priority Services Register (PSR) lookup functionality
for UK postcodes in the North West England electricity distribution network.
"""

import json
import logging
import os

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level cache for PSR register (persists across warm Lambda invocations)
_psr_register_cache = None


def _load_psr_register():
    """Load PSR register from JSON file into dictionary for O(1) lookups."""
    global _psr_register_cache
    
    if _psr_register_cache is not None:
        return _psr_register_cache
    
    # Get path to PSR register file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_file = os.path.join(current_dir, "psr_register.json")
    
    if not os.path.exists(data_file):
        raise FileNotFoundError(f"PSR register data file not found: {data_file}")
    
    # Load and parse JSON
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Convert to dictionary: normalized postcode -> on_psr boolean
    _psr_register_cache = {
        _normalize_postcode(entry['postcode']): entry['on_psr']
        for entry in data
    }
    
    logger.info(f"Loaded {len(_psr_register_cache)} postcodes into PSR register")
    return _psr_register_cache


def _normalize_postcode(postcode):
    """Normalize postcode: uppercase, trim, single space."""
    return ' '.join(postcode.upper().strip().split())


def _lookup_postcodes(postcodes, psr_register):
    """Look up PSR status for list of postcodes."""
    results = []
    for postcode in postcodes:
        normalized = _normalize_postcode(postcode)
        if normalized in psr_register:
            results.append({
                "postcode": postcode,
                "on_psr": psr_register[normalized]
            })
        else:
            results.append({
                "postcode": postcode,
                "on_psr": False
            })
    return results


def lambda_handler(event, context):
    """
    Lambda function handler for PSR lookup requests.
    
    Args:
        event: Lambda event containing postcodes to lookup
        context: Lambda context object
    
    Returns:
        dict: Response with status code and body containing results
    """
    try:
        # Load PSR register (uses cache for warm invocations)
        psr_register = _load_psr_register()
        
        # Extract postcodes from event
        if "postcodes" not in event:
            return {
                "statusCode": 400,
                "body": {
                    "error": "Missing required field: postcodes"
                }
            }
        
        postcodes = event["postcodes"]
        
        if not isinstance(postcodes, list):
            logger.info(
                "Rejected PSR lookup request request_id=%s reason=invalid_postcodes_type",
                getattr(context, "aws_request_id", "unknown"),
            )
            return {
                "statusCode": 400,
                "body": {
                    "error": "Invalid field type: postcodes must be an array"
                }
            }
        
        logger.info(
            "Processing PSR lookup request request_id=%s postcode_count=%d",
            getattr(context, "aws_request_id", "unknown"),
            len(postcodes),
        )

        # Perform lookups
        results = _lookup_postcodes(postcodes, psr_register)
        
        # Return successful response
        return {
            "statusCode": 200,
            "body": {
                "results": results
            }
        }
        
    except FileNotFoundError as e:
        logger.error(f"PSR register file not found: {str(e)}")
        return {
            "statusCode": 500,
            "body": {
                "error": "PSR register data file not found"
            }
        }
    
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in PSR register: {str(e)}")
        return {
            "statusCode": 500,
            "body": {
                "error": "Failed to parse PSR register data: invalid JSON"
            }
        }
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": {
                "error": "Internal server error"
            }
        }
