"""
Workforce Router Lambda Function

This Lambda function provides engineer dispatch recommendations based on fault types.
It integrates with AgentCore Gateway as a tool with two actions:
1. recommend_engineers - Get engineer recommendations for a fault type
2. assign_engineer - Assign an engineer to a fault (updates status to "on-job")

The function uses RDS Data API to query Aurora PostgreSQL without VPC configuration.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize RDS Data API client
rds_client = boto3.client('rds-data')

# Environment variables
DB_CLUSTER_ARN = os.environ.get('DB_CLUSTER_ARN')
DB_SECRET_ARN = os.environ.get('DB_SECRET_ARN')
DB_NAME = os.environ.get('DB_NAME', 'workforce_db')

# Fault-to-Skill Mapping
# Maps fault types to required primary skills and optional secondary skills
FAULT_SKILL_MAPPING = {
    "transformer_failure": {
        "primary_skill": "Transformer Installation & Repair",
        "secondary_skills": ["Substation Switchgear"]
    },
    "cable_fault": {
        "primary_skill": "HV Cable Jointing & Repair",
        "secondary_skills": []
    },
    "overhead_line_fault": {
        "primary_skill": "Overhead Line Maintenance",
        "secondary_skills": []
    },
    "circuit_breaker_fault": {
        "primary_skill": "Substation Switchgear",
        "secondary_skills": ["Protection & Control Systems"]
    },
    "protection_device_fault": {
        "primary_skill": "Protection & Control Systems",
        "secondary_skills": []
    },
    "insulator_failure": {
        "primary_skill": "Overhead Line Maintenance",
        "secondary_skills": []
    },
    "substation_equipment_fault": {
        "primary_skill": "Substation Switchgear",
        "secondary_skills": ["Protection & Control Systems"]
    }
}


# Error Response Helper Functions

def error_invalid_fault_type(fault_type: str) -> Dict[str, Any]:
    """Return error response for invalid fault type."""
    valid_types = ', '.join(FAULT_SKILL_MAPPING.keys())
    return {
        'status': 'error',
        'error_type': 'invalid_fault_type',
        'message': f"Invalid fault type '{fault_type}'. Valid types: {valid_types}"
    }


def error_engineer_not_found(engineer_id: int) -> Dict[str, Any]:
    """Return error response for engineer not found."""
    return {
        'status': 'error',
        'error_type': 'engineer_not_found',
        'message': f'Engineer ID {engineer_id} not found'
    }


def error_engineer_not_available(employee_id: str, current_status: str) -> Dict[str, Any]:
    """Return error response for engineer not available."""
    return {
        'status': 'error',
        'error_type': 'engineer_not_available',
        'message': f"Engineer {employee_id} is currently {current_status} and cannot be assigned"
    }


def error_database_unavailable() -> Dict[str, Any]:
    """Return error response for database connection failure."""
    return {
        'status': 'error',
        'error_type': 'database_unavailable',
        'message': 'Unable to connect to engineer database'
    }


def error_invalid_request(field: str, message: str) -> Dict[str, Any]:
    """Return error response for invalid request."""
    return {
        'status': 'error',
        'error_type': 'invalid_request',
        'field': field,
        'message': message
    }


def error_internal() -> Dict[str, Any]:
    """Return error response for internal errors."""
    return {
        'status': 'error',
        'error_type': 'internal_error',
        'message': 'An unexpected error occurred'
    }


def parse_data_api_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse RDS Data API response format into a list of dictionaries.
    
    The Data API returns records as a list of lists with separate column metadata.
    This function converts it to a more usable format.
    
    Args:
        response: Response from rds_client.execute_statement()
        
    Returns:
        List of dictionaries where keys are column names and values are the data
        
    Example:
        Input: {
            'columnMetadata': [{'name': 'id'}, {'name': 'name'}],
            'records': [[{'longValue': 1}, {'stringValue': 'John'}]]
        }
        Output: [{'id': 1, 'name': 'John'}]
    """
    if 'records' not in response or not response['records']:
        return []
    
    records = response['records']
    column_metadata = response.get('columnMetadata', [])
    
    # If no column metadata, return empty list
    if not column_metadata:
        return []
    
    # Parse each record
    results = []
    for record in records:
        row = {}
        for i, column in enumerate(column_metadata):
            # Handle both 'name' and 'label' fields for column names
            column_name = column.get('name') or column.get('label', f'column_{i}')
            
            # Make sure we don't go out of bounds
            if i >= len(record):
                row[column_name] = None
                continue
            
            field = record[i]
            
            # Extract value based on type
            if 'stringValue' in field:
                row[column_name] = field['stringValue']
            elif 'longValue' in field:
                row[column_name] = field['longValue']
            elif 'doubleValue' in field:
                row[column_name] = field['doubleValue']
            elif 'booleanValue' in field:
                row[column_name] = field['booleanValue']
            elif 'isNull' in field and field['isNull']:
                row[column_name] = None
            else:
                row[column_name] = None
        
        results.append(row)
    
    return results


def execute_sql(sql: str, parameters: Optional[List[Dict[str, Any]]] = None, 
                transaction_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute SQL statement using RDS Data API.
    
    Args:
        sql: SQL statement to execute
        parameters: Optional list of named parameters
        transaction_id: Optional transaction ID for transactional queries
        
    Returns:
        Response from RDS Data API
        
    Raises:
        ClientError: If database operation fails
    """
    try:
        params = {
            'resourceArn': DB_CLUSTER_ARN,
            'secretArn': DB_SECRET_ARN,
            'database': DB_NAME,
            'sql': sql,
            'includeResultMetadata': True  # CRITICAL: Required for column names
        }
        
        if parameters:
            params['parameters'] = parameters
        
        if transaction_id:
            params['transactionId'] = transaction_id
        
        response = rds_client.execute_statement(**params)
        return response
        
    except ClientError as e:
        logger.error(f"Database error executing SQL: {e}", exc_info=True)
        raise


def recommend_engineers(fault_type: str) -> Dict[str, Any]:
    """
    Recommend engineers for a given fault type.
    
    Algorithm:
    1. Validate fault type
    2. Map fault type to required skill
    3. Query available engineers with required skill using RDS Data API
    4. Rank by proficiency level (lead engineer > certified > trainee)
    5. Return top 5 recommendations
    
    Args:
        fault_type: Type of fault requiring engineer dispatch
        
    Returns:
        Response dictionary with recommendations or error
    """
    # Step 1: Validate fault type
    if fault_type not in FAULT_SKILL_MAPPING:
        return error_invalid_fault_type(fault_type)
    
    # Step 2: Get required skill
    required_skill = FAULT_SKILL_MAPPING[fault_type]["primary_skill"]
    
    # Step 3: Query database using RDS Data API
    sql = """
        SELECT DISTINCT
            e.engineer_id,
            e.employee_id,
            e.name,
            e.current_location_lat,
            e.current_location_lon,
            e.availability_status,
            es.skill_name,
            es.proficiency_level,
            CASE es.proficiency_level
                WHEN 'lead engineer' THEN 1
                WHEN 'certified' THEN 2
                WHEN 'trainee' THEN 3
            END as proficiency_rank
        FROM engineers e
        INNER JOIN engineer_skills es ON e.engineer_id = es.engineer_id
        WHERE e.availability_status = 'available'
          AND es.skill_name = :skill_name
        ORDER BY proficiency_rank, e.engineer_id
        LIMIT 5;
    """
    
    parameters = [
        {
            'name': 'skill_name',
            'value': {'stringValue': required_skill}
        }
    ]
    
    try:
        # Execute query
        logger.info("Executing engineer recommendation query")
        response = execute_sql(sql, parameters)
        
        # Log raw response for debugging
        logger.info(f"Raw response keys: {list(response.keys())}")
        logger.info(f"Raw response records count: {len(response.get('records', []))}")
        logger.info(f"Has columnMetadata: {'columnMetadata' in response}")
        if 'columnMetadata' in response:
            logger.info(f"Column count: {len(response['columnMetadata'])}")
        
        # Step 4: Parse Data API response
        engineers = parse_data_api_response(response)
        logger.info(f"Parsed engineers count: {len(engineers)}")
        
        # Step 5: Return recommendations
        if not engineers:
            # Add debug info to help troubleshoot
            logger.warning("No available engineers found for the requested skill")
            return {
                'status': 'no_engineers_available',
                'fault_type': fault_type,
                'required_skill': required_skill,
                'recommendations': [],
                'total_available': 0,
                'message': f"No engineers with required skill '{required_skill}' are currently available",
                'debug_info': {
                    'query_executed': 'SELECT DISTINCT with proficiency_rank',
                    'skill_searched': required_skill,
                    'availability_filter': 'available'
                }
            }
        
        # Format engineer recommendations
        recommendations = []
        for eng in engineers:
            recommendation = {
                'engineer_id': eng['engineer_id'],
                'employee_id': eng['employee_id'],
                'name': eng['name'],
                'skills': [
                    {
                        'skill_name': eng['skill_name'],
                        'proficiency_level': eng['proficiency_level']
                    }
                ],
                'availability_status': eng['availability_status']
            }
            
            # Add location if available
            if eng.get('current_location_lat') is not None and eng.get('current_location_lon') is not None:
                recommendation['location'] = {
                    'latitude': eng['current_location_lat'],
                    'longitude': eng['current_location_lon']
                }
            
            recommendations.append(recommendation)
        
        return {
            'status': 'success',
            'fault_type': fault_type,
            'required_skill': required_skill,
            'recommendations': recommendations,
            'total_available': len(recommendations)
        }
        
    except ClientError as e:
        logger.error(f"Database error in recommend_engineers: {e}", exc_info=True)
        return error_database_unavailable()
    except Exception as e:
        logger.error(f"Unexpected error in recommend_engineers: {e}", exc_info=True)
        return error_internal()


def assign_engineer(engineer_id: int, fault_type: str) -> Dict[str, Any]:
    """
    Assign an engineer to a fault by updating their status to 'on-job'.
    
    Algorithm:
    1. Begin transaction
    2. Verify engineer exists and is available
    3. Update status to 'on-job' with timestamp
    4. Commit transaction on success, rollback on error
    5. Return confirmation
    
    Args:
        engineer_id: ID of the engineer to assign
        fault_type: Type of fault (for logging/context)
        
    Returns:
        Response dictionary with assignment confirmation or error
    """
    try:
        # Step 1: Begin transaction
        transaction_response = rds_client.begin_transaction(
            resourceArn=DB_CLUSTER_ARN,
            secretArn=DB_SECRET_ARN,
            database=DB_NAME
        )
        transaction_id = transaction_response['transactionId']
        
        try:
            # Step 2: Check current status
            check_sql = """
                SELECT engineer_id, employee_id, name, availability_status
                FROM engineers
                WHERE engineer_id = :engineer_id
            """
            
            check_params = [
                {
                    'name': 'engineer_id',
                    'value': {'longValue': engineer_id}
                }
            ]
            
            response = execute_sql(check_sql, check_params, transaction_id)
            engineers = parse_data_api_response(response)
            
            if not engineers:
                # Rollback transaction
                rds_client.rollback_transaction(
                    resourceArn=DB_CLUSTER_ARN,
                    secretArn=DB_SECRET_ARN,
                    transactionId=transaction_id
                )
                return error_engineer_not_found(engineer_id)
            
            engineer = engineers[0]
            if engineer['availability_status'] != 'available':
                # Rollback transaction
                rds_client.rollback_transaction(
                    resourceArn=DB_CLUSTER_ARN,
                    secretArn=DB_SECRET_ARN,
                    transactionId=transaction_id
                )
                return error_engineer_not_available(engineer['employee_id'], engineer['availability_status'])
            
            # Step 3: Update status
            update_sql = """
                UPDATE engineers
                SET availability_status = 'on-job',
                    status_updated_at = CURRENT_TIMESTAMP
                WHERE engineer_id = :engineer_id
                RETURNING engineer_id, employee_id, name, availability_status, status_updated_at;
            """
            
            update_params = [
                {
                    'name': 'engineer_id',
                    'value': {'longValue': engineer_id}
                }
            ]
            
            response = execute_sql(update_sql, update_params, transaction_id)
            
            # Step 4: Commit transaction
            rds_client.commit_transaction(
                resourceArn=DB_CLUSTER_ARN,
                secretArn=DB_SECRET_ARN,
                transactionId=transaction_id
            )
            
            updated = parse_data_api_response(response)[0]
            
            return {
                'status': 'success',
                'engineer_id': updated['engineer_id'],
                'employee_id': updated['employee_id'],
                'name': updated['name'],
                'previous_status': 'available',
                'new_status': updated['availability_status'],
                'updated_at': updated['status_updated_at']
            }
            
        except Exception as e:
            # Rollback on any error
            logger.error(f"Error during assignment, rolling back transaction: {e}", exc_info=True)
            rds_client.rollback_transaction(
                resourceArn=DB_CLUSTER_ARN,
                secretArn=DB_SECRET_ARN,
                transactionId=transaction_id
            )
            raise
            
    except ClientError as e:
        logger.error(f"Database error in assign_engineer: {e}", exc_info=True)
        return error_database_unavailable()
    except Exception as e:
        logger.error(f"Unexpected error in assign_engineer: {e}", exc_info=True)
        return error_internal()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for AgentCore Gateway integration.
    
    Routes requests to appropriate action handlers based on the 'action' parameter.
    
    Args:
        event: Lambda event containing action and parameters
        context: Lambda context object
        
    Returns:
        Response dictionary with status and data
    """
    # Validate environment variables
    if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
        logger.error("Missing required environment variables: DB_CLUSTER_ARN or DB_SECRET_ARN")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'error_type': 'configuration_error',
                'message': 'Lambda function not properly configured'
            })
        }
    
    # Extract action from event
    action = event.get('action')
    logged_action = (
        action
        if action in {'recommend_engineers', 'assign_engineer'}
        else 'missing_or_invalid'
    )
    logger.info(
        "Received workforce router request request_id=%s action=%s",
        getattr(context, 'aws_request_id', 'unknown'),
        logged_action,
    )
    
    if not action:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'status': 'error',
                'error_type': 'invalid_request',
                'message': 'Missing required parameter: action'
            })
        }
    
    # Route to appropriate handler
    if action == 'recommend_engineers':
        fault_type = event.get('fault_type')
        if not fault_type:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'status': 'error',
                    'error_type': 'invalid_request',
                    'message': 'Missing required parameter: fault_type'
                })
            }
        
        logger.info("Processing engineer recommendation request")
        
        # Call recommend_engineers function
        result = recommend_engineers(fault_type)
        
        # Log result summary
        if result['status'] == 'success':
            logger.info(
                "Successfully recommended %d engineers",
                result['total_available'],
            )
        elif result['status'] == 'no_engineers_available':
            logger.info("No engineers available for the requested skill")
        else:
            logger.warning(f"Error in recommend_engineers: {result.get('error_type')}")
        
        # Determine HTTP status code based on result
        if result['status'] == 'success' or result['status'] == 'no_engineers_available':
            status_code = 200
        elif result['status'] == 'error':
            if result['error_type'] == 'invalid_fault_type':
                status_code = 400
            elif result['error_type'] == 'database_unavailable':
                status_code = 503
            else:
                status_code = 500
        else:
            status_code = 500
        
        return {
            'statusCode': status_code,
            'body': json.dumps(result)
        }
    
    elif action == 'assign_engineer':
        engineer_id = event.get('engineer_id')
        fault_type = event.get('fault_type')
        
        if not engineer_id:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'status': 'error',
                    'error_type': 'invalid_request',
                    'message': 'Missing required parameter: engineer_id'
                })
            }
        
        logger.info("Processing engineer assignment request")
        
        # Call assign_engineer function
        result = assign_engineer(engineer_id, fault_type)
        
        # Log result summary
        if result['status'] == 'success':
            logger.info("Successfully assigned engineer")
        else:
            logger.warning(f"Error in assign_engineer: {result.get('error_type')}")
        
        # Determine HTTP status code based on result
        if result['status'] == 'success':
            status_code = 200
        elif result['status'] == 'error':
            if result['error_type'] == 'engineer_not_found':
                status_code = 404
            elif result['error_type'] == 'engineer_not_available':
                status_code = 409
            elif result['error_type'] == 'database_unavailable':
                status_code = 503
            else:
                status_code = 500
        else:
            status_code = 500
        
        return {
            'statusCode': status_code,
            'body': json.dumps(result)
        }
    
    else:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'status': 'error',
                'error_type': 'invalid_action',
                'message': f'Unknown action: {action}. Valid actions: recommend_engineers, assign_engineer'
            })
        }
