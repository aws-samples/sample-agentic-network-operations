#!/usr/bin/env python3
"""
Workforce Management System - Aurora PostgreSQL Database Initialization Script

This script initializes the Aurora PostgreSQL Serverless v2 database using the
RDS Data API. It executes the schema creation and sample data population scripts,
then runs verification queries to confirm the setup.

Usage:
    python init_aurora_db.py --cluster-arn <cluster-arn> --secret-arn <secret-arn> [--region <region>]

Requirements:
    - boto3
    - AWS credentials configured
    - Aurora cluster with Data API enabled
    - Secrets Manager secret with database credentials

Example:
    python init_aurora_db.py \
        --cluster-arn arn:aws:rds:us-east-1:123456789012:cluster:workforce-db \
        --secret-arn arn:aws:secretsmanager:us-east-1:123456789012:secret:workforce-db-secret \
        --region us-east-1
"""

import argparse
import boto3
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional


class AuroraDBInitializer:
    """Initialize Aurora PostgreSQL database using RDS Data API."""
    
    def __init__(self, cluster_arn: str, secret_arn: str, database_name: str = 'workforce_db', region: str = 'us-east-1'):
        """
        Initialize the database initializer.
        
        Args:
            cluster_arn: ARN of the Aurora cluster
            secret_arn: ARN of the Secrets Manager secret with credentials
            database_name: Name of the database to initialize
            region: AWS region
        """
        self.cluster_arn = cluster_arn
        self.secret_arn = secret_arn
        self.database_name = database_name
        self.region = region
        self.rds_client = boto3.client('rds-data', region_name=region)
        
    def execute_sql(self, sql: str, description: str = "SQL statement", include_metadata: bool = True) -> Dict[str, Any]:
        """
        Execute SQL statement using RDS Data API.
        
        Args:
            sql: SQL statement to execute
            description: Description of the SQL for logging
            include_metadata: Whether to include result metadata (column names)
            
        Returns:
            Response from RDS Data API
            
        Raises:
            Exception: If SQL execution fails
        """
        print(f"Executing: {description}...")
        
        try:
            response = self.rds_client.execute_statement(
                resourceArn=self.cluster_arn,
                secretArn=self.secret_arn,
                database=self.database_name,
                sql=sql,
                includeResultMetadata=include_metadata
            )
            
            # Debug: show what's in the response
            if 'numberOfRecordsUpdated' in response:
                print(f"✓ {description} completed successfully (updated {response['numberOfRecordsUpdated']} records)")
            else:
                print(f"✓ {description} completed successfully")
            
            return response
        except Exception as e:
            print(f"✗ {description} failed: {str(e)}")
            raise
    
    def split_sql_statements(self, sql: str) -> List[str]:
        """
        Split SQL file into individual statements.
        
        The RDS Data API doesn't support multi-statement execution,
        so we need to split on semicolons and execute each statement separately.
        
        This function properly handles:
        - String literals with semicolons
        - Multi-line statements
        - Comments (both -- and /* */ style)
        - Parentheses (for multi-row INSERTs)
        
        Args:
            sql: SQL content to split
            
        Returns:
            List of individual SQL statements
        """
        statements = []
        current_statement = []
        in_string = False
        paren_depth = 0
        escape_next = False
        
        lines = sql.split('\n')
        
        for line in lines:
            # Skip psql meta-commands entirely
            if line.strip().startswith('\\'):
                continue
            
            # Check if this is a comment-only line
            stripped = line.strip()
            if stripped.startswith('--') or not stripped:
                # If we're building a statement, add the comment/blank line to it
                if current_statement:
                    current_statement.append(line)
                    current_statement.append('\n')
                # Otherwise skip it (standalone comment/blank line between statements)
                continue
            
            # Process the line character by character
            i = 0
            found_semicolon = False
            while i < len(line):
                char = line[i]
                
                # Handle escape sequences
                if escape_next:
                    current_statement.append(char)
                    escape_next = False
                    i += 1
                    continue
                
                # Check for line comments (-- )
                if not in_string and i < len(line) - 1 and line[i:i+2] == '--':
                    # Add the rest of the line as a comment
                    current_statement.append(line[i:])
                    break
                
                # Handle backslash escapes
                if char == '\\':
                    escape_next = True
                    current_statement.append(char)
                    i += 1
                    continue
                
                # Handle string literals
                if char == "'":
                    in_string = not in_string
                    current_statement.append(char)
                    i += 1
                    continue
                
                # Track parentheses depth (only outside strings)
                if not in_string:
                    if char == '(':
                        paren_depth += 1
                    elif char == ')':
                        paren_depth -= 1
                
                # Check for statement terminator (semicolon outside strings and at paren depth 0)
                if char == ';' and not in_string and paren_depth == 0:
                    # End of statement - don't include the semicolon
                    stmt = ''.join(current_statement).strip()
                    if stmt and not stmt.startswith('--'):
                        statements.append(stmt)
                    current_statement = []
                    found_semicolon = True
                    # Break out of character loop - don't process rest of line (e.g. trailing comments)
                    break
                
                current_statement.append(char)
                i += 1
            
            # Add newline if we're building a statement and didn't just finish one
            if current_statement and not found_semicolon:
                current_statement.append('\n')
        
        # Add any remaining statement
        stmt = ''.join(current_statement).strip()
        if stmt and not stmt.startswith('--'):
            statements.append(stmt)
        
        return statements
    
    def execute_sql_file(self, file_path: Path, description: str = "SQL file", include_metadata: bool = False) -> List[Dict[str, Any]]:
        """
        Execute SQL from a file using RDS Data API.
        
        The RDS Data API doesn't support multi-statement execution,
        so this method splits the file into individual statements
        and executes them one at a time.
        
        Args:
            file_path: Path to SQL file
            description: Description of the file for logging
            include_metadata: Whether to include result metadata (for queries)
            
        Returns:
            List of responses from RDS Data API (one per statement)
            
        Raises:
            FileNotFoundError: If SQL file doesn't exist
            Exception: If SQL execution fails
        """
        if not file_path.exists():
            raise FileNotFoundError(f"SQL file not found: {file_path}")
        
        print(f"\nReading SQL file: {file_path}")
        sql = file_path.read_text()
        
        # Split into individual statements
        statements = self.split_sql_statements(sql)
        print(f"Found {len(statements)} SQL statements to execute")
        
        # Execute each statement
        responses = []
        for i, statement in enumerate(statements, 1):
            # Show first 60 chars of statement for logging
            preview = statement[:60].replace('\n', ' ')
            if len(statement) > 60:
                preview += '...'
            
            try:
                response = self.execute_sql(statement, f"Statement {i}/{len(statements)}: {preview}", include_metadata=include_metadata)
                responses.append(response)
            except Exception as e:
                print(f"\n✗ Failed on statement {i}:")
                print(f"  {preview}")
                raise
        
        print(f"\n✓ All {len(statements)} statements executed successfully")
        return responses
    
    def parse_data_api_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse RDS Data API response into list of dictionaries.
        
        Args:
            response: Response from RDS Data API
            
        Returns:
            List of row dictionaries
        """
        # Debug: print response keys
        print(f"   Debug: Response keys: {list(response.keys())}")
        
        if 'records' not in response or not response['records']:
            print(f"   Debug: No records in response or records is empty")
            return []
        
        records = response['records']
        column_metadata = response.get('columnMetadata', [])
        
        print(f"   Debug: Found {len(records)} records, {len(column_metadata)} columns")
        
        # If no column metadata, return empty list
        if not column_metadata:
            print(f"   Debug: No column metadata")
            return []
        
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
                
                value_dict = record[i]
                
                # Extract value from the Data API format
                if 'stringValue' in value_dict:
                    row[column_name] = value_dict['stringValue']
                elif 'longValue' in value_dict:
                    row[column_name] = value_dict['longValue']
                elif 'doubleValue' in value_dict:
                    row[column_name] = value_dict['doubleValue']
                elif 'booleanValue' in value_dict:
                    row[column_name] = value_dict['booleanValue']
                elif 'isNull' in value_dict and value_dict['isNull']:
                    row[column_name] = None
                else:
                    row[column_name] = None
            
            results.append(row)
        
        return results
    
    def run_verification_queries(self) -> bool:
        """
        Run verification queries to confirm database setup.
        
        Returns:
            True if all verifications pass, False otherwise
        """
        print("\n" + "="*70)
        print("VERIFICATION QUERIES")
        print("="*70)
        
        all_passed = True
        
        # Query 0: Check if tables exist and have data
        print("\n0. Checking tables exist:")
        try:
            response = self.execute_sql(
                """
                SELECT 
                    (SELECT COUNT(*) FROM engineers) as engineer_count,
                    (SELECT COUNT(*) FROM engineer_skills) as skill_count;
                """,
                "Table existence check"
            )
            
            print(f"   Debug: Response keys: {list(response.keys())}")
            
            results = self.parse_data_api_response(response)
            
            if results:
                row = results[0]
                eng_count = row.get('engineer_count', 0)
                skill_count = row.get('skill_count', 0)
                print(f"\n   Engineers table: {eng_count} rows")
                print(f"   Engineer_skills table: {skill_count} rows")
                
                if eng_count == 0:
                    print(f"   ✗ ERROR: Engineers table is empty!")
                    all_passed = False
                if skill_count == 0:
                    print(f"   ✗ ERROR: Engineer_skills table is empty!")
                    all_passed = False
            else:
                print("   ✗ No results returned from table check")
                all_passed = False
                
        except Exception as error:
            print(f"   ✗ Table check failed ({type(error).__name__})")
            all_passed = False
        
        # Query 1: Engineer count by availability status
        print("\n1. Engineer count by availability status:")
        try:
            response = self.execute_sql(
                """
                SELECT availability_status, COUNT(*) as count 
                FROM engineers 
                GROUP BY availability_status 
                ORDER BY availability_status;
                """,
                "Availability status query"
            )
            
            # Debug: print raw response structure
            if 'columnMetadata' in response:
                print(f"   Debug: Column names: {[col.get('name') or col.get('label') for col in response['columnMetadata']]}")
            
            results = self.parse_data_api_response(response)
            
            if results:
                print("\n   Status          | Count")
                print("   " + "-"*15 + " | " + "-"*5)
                for row in results:
                    status = row.get('availability_status', 'N/A')
                    count = row.get('count', 0)
                    print(f"   {status:<15} | {count}")
                
                # Verify we have engineers in each status
                statuses = {row.get('availability_status') for row in results if row.get('availability_status')}
                expected_statuses = {'available', 'on-job', 'off-duty'}
                if not expected_statuses.issubset(statuses):
                    print(f"   ⚠ Warning: Missing some availability statuses")
                    all_passed = False
            else:
                print("   ✗ No results returned")
                all_passed = False
                
        except Exception as error:
            print(f"   ✗ Query failed ({type(error).__name__})")
            all_passed = False
        
        # Query 2: Engineer count by skill
        print("\n2. Engineer count by skill:")
        try:
            response = self.execute_sql(
                """
                SELECT skill_name, COUNT(DISTINCT engineer_id) as engineer_count 
                FROM engineer_skills 
                GROUP BY skill_name 
                ORDER BY skill_name;
                """,
                "Skill coverage query"
            )
            results = self.parse_data_api_response(response)
            
            if results:
                print("\n   Skill Name                                    | Engineers")
                print("   " + "-"*45 + " | " + "-"*9)
                for row in results:
                    skill = row.get('skill_name', 'N/A')
                    count = row.get('engineer_count', 0)
                    print(f"   {skill:<45} | {count}")
                
                # Verify each skill has at least 2 engineers
                for row in results:
                    count = row.get('engineer_count', 0)
                    skill = row.get('skill_name', 'Unknown')
                    if count < 2:
                        print(f"   ⚠ Warning: {skill} has only {count} engineer(s)")
                        all_passed = False
            else:
                print("   ✗ No results returned")
                all_passed = False
                
        except Exception as e:
            print(f"   ✗ Query failed: {str(e)}")
            all_passed = False
        
        # Query 3: Skill count by proficiency level
        print("\n3. Skill count by proficiency level:")
        try:
            response = self.execute_sql(
                """
                SELECT proficiency_level, COUNT(*) as count 
                FROM engineer_skills 
                GROUP BY proficiency_level 
                ORDER BY 
                    CASE proficiency_level
                        WHEN 'lead engineer' THEN 1
                        WHEN 'certified' THEN 2
                        WHEN 'trainee' THEN 3
                    END;
                """,
                "Proficiency level query"
            )
            results = self.parse_data_api_response(response)
            
            if results:
                print("\n   Proficiency Level | Count")
                print("   " + "-"*17 + " | " + "-"*5)
                for row in results:
                    level = row.get('proficiency_level', 'N/A')
                    count = row.get('count', 0)
                    print(f"   {level:<17} | {count}")
            else:
                print("   ✗ No results returned")
                all_passed = False
                
        except Exception as e:
            print(f"   ✗ Query failed: {str(e)}")
            all_passed = False
        
        # Query 4: Total counts
        print("\n4. Total counts:")
        try:
            response = self.execute_sql(
                """
                SELECT 
                    (SELECT COUNT(*) FROM engineers) as total_engineers,
                    (SELECT COUNT(*) FROM engineer_skills) as total_skills;
                """,
                "Total counts query"
            )
            results = self.parse_data_api_response(response)
            
            if results:
                row = results[0]
                total_eng = row.get('total_engineers', 0)
                total_skills = row.get('total_skills', 0)
                print(f"\n   Total engineers: {total_eng}")
                print(f"   Total skills assigned: {total_skills}")
                
                # Verify we have expected number of engineers
                if total_eng < 20:
                    print(f"   ⚠ Warning: Expected at least 20 engineers, found {total_eng}")
                    all_passed = False
            else:
                print("   ✗ No results returned")
                all_passed = False
                
        except Exception as e:
            print(f"   ✗ Query failed: {str(e)}")
            all_passed = False
        
        # Query 5: Verify an engineer record has skills without printing identity data.
        print("\n5. Sample skill and availability check:")
        try:
            response = self.execute_sql(
                """
                SELECT 
                    e.availability_status,
                    es.skill_name,
                    es.proficiency_level
                FROM engineers e
                LEFT JOIN engineer_skills es ON e.engineer_id = es.engineer_id
                WHERE e.employee_id = 'ENG001'
                ORDER BY es.skill_name;
                """,
                "Sample engineer query"
            )
            results = self.parse_data_api_response(response)
            
            if results:
                first_row = results[0]
                status = first_row.get('availability_status', 'N/A')
                
                print(f"   Status: {status}")
                print(f"\n   Skills:")
                for row in results:
                    skill = row.get('skill_name')
                    level = row.get('proficiency_level')
                    if skill:
                        print(f"     - {skill} ({level})")
            else:
                print("   ✗ No results returned")
                all_passed = False
                
        except Exception as e:
            print(f"   ✗ Query failed: {str(e)}")
            all_passed = False
        
        return all_passed
    
    def initialize_database(self) -> bool:
        """
        Initialize the database with schema and sample data.
        
        Returns:
            True if initialization successful, False otherwise
        """
        print("="*70)
        print("WORKFORCE MANAGEMENT DATABASE INITIALIZATION")
        print("="*70)
        print(f"\nCluster ARN: {self.cluster_arn}")
        print(f"Secret ARN: {self.secret_arn}")
        print(f"Database: {self.database_name}")
        print(f"Region: {self.region}")
        
        # Get the directory containing this script
        script_dir = Path(__file__).parent
        
        try:
            # Step 1: Create schema
            print("\n" + "="*70)
            print("STEP 1: Creating Database Schema")
            print("="*70)
            schema_file = script_dir / 'schema.sql'
            self.execute_sql_file(schema_file, "Schema creation")
            
            # Step 2: Load sample data
            print("\n" + "="*70)
            print("STEP 2: Loading Sample Data")
            print("="*70)
            data_file = script_dir / 'init_data.sql'
            self.execute_sql_file(data_file, "Sample data loading")
            
            # Step 3: Verify data
            verification_passed = self.run_verification_queries()
            
            # Final summary
            print("\n" + "="*70)
            print("INITIALIZATION SUMMARY")
            print("="*70)
            
            if verification_passed:
                print("\n✓ Database initialization completed successfully!")
                print("✓ All verification checks passed")
                return True
            else:
                print("\n⚠ Database initialization completed with warnings")
                print("⚠ Some verification checks failed - please review output above")
                return False
                
        except Exception as e:
            print("\n" + "="*70)
            print("INITIALIZATION FAILED")
            print("="*70)
            print(f"\n✗ Error: {str(e)}")
            return False


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Initialize Aurora PostgreSQL database for Workforce Management System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize database using CloudFormation outputs
  python init_aurora_db.py \\
    --cluster-arn $(aws cloudformation describe-stacks \\
      --stack-name nw-england-electricity-network \\
      --query 'Stacks[0].Outputs[?OutputKey==`WorkforceDBClusterArn`].OutputValue' \\
      --output text) \\
    --secret-arn $(aws cloudformation describe-stacks \\
      --stack-name nw-england-electricity-network \\
      --query 'Stacks[0].Outputs[?OutputKey==`WorkforceDBSecretArn`].OutputValue' \\
      --output text)

  # Initialize database with explicit ARNs
  python init_aurora_db.py \\
    --cluster-arn arn:aws:rds:us-east-1:123456789012:cluster:workforce-db \\
    --secret-arn arn:aws:secretsmanager:us-east-1:123456789012:secret:workforce-db-secret \\
    --region us-east-1
        """
    )
    
    parser.add_argument(
        '--cluster-arn',
        required=True,
        help='ARN of the Aurora PostgreSQL cluster'
    )
    
    parser.add_argument(
        '--secret-arn',
        required=True,
        help='ARN of the Secrets Manager secret containing database credentials'
    )
    
    parser.add_argument(
        '--database',
        default='workforce_db',
        help='Database name (default: workforce_db)'
    )
    
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region (default: us-east-1)'
    )
    
    args = parser.parse_args()
    
    # Initialize database
    initializer = AuroraDBInitializer(
        cluster_arn=args.cluster_arn,
        secret_arn=args.secret_arn,
        database_name=args.database,
        region=args.region
    )
    
    success = initializer.initialize_database()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
