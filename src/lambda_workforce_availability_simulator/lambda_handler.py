"""
Workforce Availability Simulator Lambda Function

This Lambda function simulates engineer availability changes for demo purposes.
It runs on an hourly schedule (triggered by EventBridge) and randomly changes the 
availability status of 20-40% of engineers.

The simulator is completely isolated from the Workforce Router - both components only
interact through the Aurora PostgreSQL database.

Design Philosophy:
- Demo complexity: Makes the system more realistic by simulating engineers going on/off duty
- Testing scenarios: Creates situations where engineers become unavailable between queries
- Isolated component: Completely separate from workforce router - no shared code
"""

import os
import json
import logging
import random
from typing import Dict, List, Any, Optional

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

# Availability status options
AVAILABILITY_STATUSES = ['available', 'on-job', 'off-duty']


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


def execute_sql(sql: str, parameters: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Execute SQL statement using RDS Data API.
    
    Args:
        sql: SQL statement to execute
        parameters: Optional list of named parameters
        
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
        
        response = rds_client.execute_statement(**params)
        return response
        
    except ClientError as e:
        logger.error(f"Database error executing SQL: {e}", exc_info=True)
        raise


def simulate_availability_changes() -> Dict[str, Any]:
    """
    Randomly change availability status of 20-40% of engineers.
    
    Algorithm:
    1. Query all engineers from database
    2. Randomly select 20-40% of engineers
    3. For each selected engineer, randomly assign new status (different from current)
    4. Update database with new statuses using batch operations
    5. Log changes for observability
    
    Returns:
        Dictionary with simulation results including:
        - total_engineers: Total number of engineers in database
        - engineers_updated: Number of engineers whose status was changed
        - percentage_updated: Percentage of engineers updated
        - changes: List of changes made (engineer_id, employee_id, old_status, new_status)
    """
    try:
        # Step 1: Get all engineers
        query = """
            SELECT engineer_id, employee_id, name, availability_status
            FROM engineers
            ORDER BY engineer_id;
        """
        
        response = execute_sql(query)
        all_engineers = parse_data_api_response(response)
        
        if not all_engineers:
            logger.warning("No engineers found in database")
            return {
                'total_engineers': 0,
                'engineers_updated': 0,
                'percentage_updated': 0.0,
                'changes': []
            }
        
        # Step 2: Randomly select 20-40%
        percentage = random.uniform(0.20, 0.40)  # Random between 20% and 40%
        sample_size = max(1, int(len(all_engineers) * percentage))  # At least 1 engineer
        selected_engineers = random.sample(all_engineers, sample_size)
        
        logger.info(f"Selected {sample_size} engineers ({percentage:.1%}) for status update")
        
        # Step 3: Assign random new statuses
        changes = []
        
        for engineer in selected_engineers:
            current_status = engineer['availability_status']
            
            # Don't change to same status - choose from other options
            possible_statuses = [s for s in AVAILABILITY_STATUSES if s != current_status]
            new_status = random.choice(possible_statuses)
            
            changes.append({
                'engineer_id': engineer['engineer_id'],
                'employee_id': engineer['employee_id'],
                'name': engineer['name'],
                'old_status': current_status,
                'new_status': new_status
            })
        
        # Step 4: Update database (batch update using individual statements)
        # Note: RDS Data API batch_execute_statement requires all parameters to be the same type
        # For simplicity, we'll use individual updates
        for change in changes:
            update_query = """
                UPDATE engineers
                SET availability_status = :new_status,
                    status_updated_at = CURRENT_TIMESTAMP
                WHERE engineer_id = :engineer_id;
            """
            
            update_params = [
                {
                    'name': 'new_status',
                    'value': {'stringValue': change['new_status']}
                },
                {
                    'name': 'engineer_id',
                    'value': {'longValue': change['engineer_id']}
                }
            ]
            
            execute_sql(update_query, update_params)
        
        # Step 5: Log changes
        logger.info(f"Availability simulation: Updated {len(changes)} engineers ({percentage:.1%} of total)")
        
        return {
            'total_engineers': len(all_engineers),
            'engineers_updated': len(changes),
            'percentage_updated': percentage,
            'changes': changes
        }
        
    except ClientError as e:
        logger.error(f"Database error in simulate_availability_changes: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in simulate_availability_changes: {e}", exc_info=True)
        raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for EventBridge scheduled trigger.
    
    This function is invoked hourly by EventBridge to simulate engineer availability changes.
    
    Args:
        event: Lambda event (from EventBridge scheduled rule)
        context: Lambda context object
        
    Returns:
        Response dictionary with simulation results
    """
    logger.info("Workforce Availability Simulator triggered")
    logger.info(
        "Workforce availability simulation request_id=%s",
        getattr(context, 'aws_request_id', 'unknown'),
    )
    
    # Validate environment variables
    if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
        logger.error("Missing required environment variables: DB_CLUSTER_ARN or DB_SECRET_ARN")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'message': 'Lambda function not properly configured'
            })
        }
    
    try:
        # Call simulation algorithm
        result = simulate_availability_changes()
        
        logger.info(f"Simulation completed successfully: {result['engineers_updated']} engineers updated")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'success',
                'message': f"Updated {result['engineers_updated']} of {result['total_engineers']} engineers",
                'total_engineers': result['total_engineers'],
                'engineers_updated': result['engineers_updated'],
                'percentage_updated': result['percentage_updated'],
                'changes': result['changes']
            })
        }
        
    except Exception as e:
        logger.error(f"Simulation failed: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'message': f'Simulation failed: {str(e)}'
            })
        }
