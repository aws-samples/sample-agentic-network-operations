"""Manual aggregate-only diagnostic for the workforce database."""

import os
import boto3
from typing import Dict, List, Any

# Initialize RDS Data API client
rds_client = boto3.client('rds-data')

# Environment variables - set these before running
DB_CLUSTER_ARN = os.environ.get('DB_CLUSTER_ARN')
DB_SECRET_ARN = os.environ.get('DB_SECRET_ARN')
DB_NAME = os.environ.get('DB_NAME', 'workforce_db')


def parse_data_api_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse RDS Data API response format into a list of dictionaries."""
    if 'records' not in response or not response['records']:
        return []
    
    records = response['records']
    column_metadata = response.get('columnMetadata', [])
    
    if not column_metadata:
        return []
    
    results = []
    for record in records:
        row = {}
        for i, column in enumerate(column_metadata):
            column_name = column.get('name') or column.get('label', f'column_{i}')
            
            if i >= len(record):
                row[column_name] = None
                continue
            
            field = record[i]
            
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


def execute_sql(sql: str, parameters=None):
    """Execute SQL statement using RDS Data API."""
    params = {
        'resourceArn': DB_CLUSTER_ARN,
        'secretArn': DB_SECRET_ARN,
        'database': DB_NAME,
        'sql': sql
    }
    
    if parameters:
        params['parameters'] = parameters
    
    response = rds_client.execute_statement(**params)
    return response


def run_database_diagnostics():
    """Run aggregate-only queries without printing engineer identifiers."""
    
    print("=" * 80)
    print("DATABASE STATE DIAGNOSTICS")
    print("=" * 80)
    
    # Test 1: Count total engineers
    print("\n1. Total Engineers:")
    response = execute_sql("SELECT COUNT(*) as total FROM engineers;")
    result = parse_data_api_response(response)
    print(f"   Total: {result[0]['total']}")
    
    # Test 2: Count by availability status
    print("\n2. Engineers by Availability Status:")
    response = execute_sql("""
        SELECT availability_status, COUNT(*) as count
        FROM engineers
        GROUP BY availability_status
        ORDER BY availability_status;
    """)
    results = parse_data_api_response(response)
    for row in results:
        print(f"   {row['availability_status']}: {row['count']}")
    
    # Test 3: Count skills
    print("\n3. Skills Distribution:")
    response = execute_sql("""
        SELECT skill_name, COUNT(DISTINCT engineer_id) as engineer_count
        FROM engineer_skills
        GROUP BY skill_name
        ORDER BY skill_name;
    """)
    results = parse_data_api_response(response)
    for row in results:
        print(f"   {row['skill_name']}: {row['engineer_count']} engineers")
    
    # Keep manual diagnostics safe to use with a non-demo database.
    print("\n4. Available engineers with 'Substation Switchgear' by proficiency:")
    response = execute_sql("""
        SELECT
            es.proficiency_level,
            COUNT(DISTINCT e.engineer_id) AS engineer_count
        FROM engineers e
        INNER JOIN engineer_skills es ON e.engineer_id = es.engineer_id
        WHERE e.availability_status = 'available'
          AND es.skill_name = 'Substation Switchgear'
        GROUP BY es.proficiency_level
        ORDER BY es.proficiency_level;
    """)
    results = parse_data_api_response(response)
    print(f"   Found {sum(row['engineer_count'] for row in results)} engineers")
    for row in results:
        print(f"   - {row['proficiency_level']}: {row['engineer_count']}")
    
    # Test 5: Validate the recommendation ranking with aggregate output.
    print("\n5. Recommendation ranking summary:")
    skill_name = 'Substation Switchgear'
    parameters = [
        {
            'name': 'skill_name',
            'value': {'stringValue': skill_name}
        }
    ]
    
    response = execute_sql("""
        SELECT
            es.skill_name,
            es.proficiency_level,
            CASE es.proficiency_level
                WHEN 'lead engineer' THEN 1
                WHEN 'certified' THEN 2
                WHEN 'trainee' THEN 3
            END AS proficiency_rank,
            COUNT(DISTINCT e.engineer_id) AS engineer_count
        FROM engineers e
        INNER JOIN engineer_skills es ON e.engineer_id = es.engineer_id
        WHERE e.availability_status = 'available'
          AND es.skill_name = :skill_name
        GROUP BY es.skill_name, es.proficiency_level
        ORDER BY proficiency_rank;
    """, parameters)
    
    results = parse_data_api_response(response)
    print(f"   Found {sum(row['engineer_count'] for row in results)} engineers")
    for row in results:
        print(
            f"   - rank {row['proficiency_rank']}: "
            f"{row['proficiency_level']} ({row['engineer_count']} engineers)"
        )
    
    # Test 6: Check if database is actually initialized
    print("\n6. Checking if database tables exist:")
    response = execute_sql("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    results = parse_data_api_response(response)
    print(f"   Found {len(results)} tables:")
    for row in results:
        print(f"   - {row['table_name']}")
    
    print("\n" + "=" * 80)
    print("DIAGNOSTICS COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    if not DB_CLUSTER_ARN or not DB_SECRET_ARN:
        print("ERROR: Please set DB_CLUSTER_ARN and DB_SECRET_ARN environment variables")
        print("\nExample:")
        print("export DB_CLUSTER_ARN='arn:aws:rds:us-east-1:123456789012:cluster:workforce-db'")
        print("export DB_SECRET_ARN='arn:aws:secretsmanager:us-east-1:123456789012:secret:workforce-db-secret-abc123'")
        exit(1)
    
    run_database_diagnostics()
