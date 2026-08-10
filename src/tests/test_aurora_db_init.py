"""
Unit tests for Aurora database initialization script.

These tests verify the script's logic without making actual AWS API calls.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
from uuid import uuid4

# Add the workforce_db directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / 'workforce_db'))

from init_aurora_db import AuroraDBInitializer


def create_test_arn(service: str, resource: str) -> str:
    return f"arn:aws:{service}:us-east-1:{uuid4().int % 10**12:012d}:{resource}-{uuid4().hex}"


class TestAuroraDBInitializer:
    """Test the AuroraDBInitializer class."""
    
    @pytest.fixture
    def initializer(self):
        """Create an initializer instance with mock boto3 client."""
        with patch('init_aurora_db.boto3.client') as mock_client:
            mock_rds = Mock()
            mock_client.return_value = mock_rds
            
            init = AuroraDBInitializer(
                cluster_arn=create_test_arn('rds', 'cluster'),
                secret_arn=create_test_arn('secretsmanager', 'secret'),
                database_name='workforce_db',
                region='us-east-1'
            )
            init.rds_client = mock_rds
            return init
    
    def test_initialization(self, initializer):
        """Test that initializer is created with correct parameters."""
        assert initializer.cluster_arn.startswith('arn:aws:rds:us-east-1:')
        assert initializer.secret_arn.startswith('arn:aws:secretsmanager:us-east-1:')
        assert initializer.database_name == 'workforce_db'
        assert initializer.region == 'us-east-1'
    
    def test_execute_sql_success(self, initializer):
        """Test successful SQL execution."""
        # Mock successful response
        initializer.rds_client.execute_statement.return_value = {
            'numberOfRecordsUpdated': 1
        }
        
        result = initializer.execute_sql("SELECT 1", "Test query")
        
        assert result['numberOfRecordsUpdated'] == 1
        initializer.rds_client.execute_statement.assert_called_once()
    
    def test_execute_sql_failure(self, initializer):
        """Test SQL execution failure."""
        # Mock failure
        initializer.rds_client.execute_statement.side_effect = Exception("Database error")
        
        with pytest.raises(Exception) as exc_info:
            initializer.execute_sql("SELECT 1", "Test query")
        
        assert "Database error" in str(exc_info.value)
    
    def test_parse_data_api_response_with_data(self, initializer):
        """Test parsing Data API response with actual data."""
        response = {
            'records': [
                [
                    {'stringValue': 'available'},
                    {'longValue': 15}
                ],
                [
                    {'stringValue': 'on-job'},
                    {'longValue': 8}
                ]
            ],
            'columnMetadata': [
                {'name': 'availability_status'},
                {'name': 'count'}
            ]
        }
        
        results = initializer.parse_data_api_response(response)
        
        assert len(results) == 2
        assert results[0]['availability_status'] == 'available'
        assert results[0]['count'] == 15
        assert results[1]['availability_status'] == 'on-job'
        assert results[1]['count'] == 8
    
    def test_parse_data_api_response_empty(self, initializer):
        """Test parsing empty Data API response."""
        response = {}
        
        results = initializer.parse_data_api_response(response)
        
        assert results == []
    
    def test_parse_data_api_response_with_null(self, initializer):
        """Test parsing Data API response with null values."""
        response = {
            'records': [
                [
                    {'stringValue': 'ENG001'},
                    {'isNull': True}
                ]
            ],
            'columnMetadata': [
                {'name': 'employee_id'},
                {'name': 'location'}
            ]
        }
        
        results = initializer.parse_data_api_response(response)
        
        assert len(results) == 1
        assert results[0]['employee_id'] == 'ENG001'
        assert results[0]['location'] is None
    
    def test_execute_sql_file_not_found(self, initializer):
        """Test executing SQL file that doesn't exist."""
        non_existent_file = Path('/tmp/nonexistent.sql')
        
        with pytest.raises(FileNotFoundError):
            initializer.execute_sql_file(non_existent_file, "Test file")
    
    def test_execute_sql_file_filters_psql_commands(self, initializer, tmp_path):
        """Test that psql meta-commands are filtered out and statements are split."""
        # Create a temporary SQL file with psql commands and multiple statements
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("""
\\echo 'Starting...'
SELECT 1;
\\i other_file.sql
SELECT 2;
--
SELECT 3;
        """)
        
        # Mock successful execution
        initializer.rds_client.execute_statement.return_value = {'numberOfRecordsUpdated': 0}
        
        results = initializer.execute_sql_file(sql_file, "Test file")
        
        # Verify multiple statements were executed (3 SELECT statements)
        assert initializer.rds_client.execute_statement.call_count == 3
        
        # Verify each statement was executed separately
        calls = initializer.rds_client.execute_statement.call_args_list
        
        # Check that SELECT statements were executed
        executed_sqls = [call[1]['sql'] for call in calls]
        assert any('SELECT 1' in sql for sql in executed_sqls)
        assert any('SELECT 2' in sql for sql in executed_sqls)
        assert any('SELECT 3' in sql for sql in executed_sqls)
        
        # Verify psql commands were not executed
        for sql in executed_sqls:
            assert '\\echo' not in sql
            assert '\\i' not in sql
    
    def test_split_sql_statements(self, initializer):
        """Test splitting SQL into individual statements."""
        sql = """
        -- Comment
        SELECT 1;
        SELECT 2;
        
        -- Another comment
        SELECT 3;
        """
        
        statements = initializer.split_sql_statements(sql)
        
        assert len(statements) == 3
        assert 'SELECT 1' in statements[0]
        assert 'SELECT 2' in statements[1]
        assert 'SELECT 3' in statements[2]
    
    def test_split_sql_statements_with_strings(self, initializer):
        """Test splitting SQL with semicolons inside strings."""
        sql = """
        INSERT INTO test VALUES ('value; with semicolon');
        SELECT 'another; semicolon';
        """
        
        statements = initializer.split_sql_statements(sql)
        
        assert len(statements) == 2
        assert "value; with semicolon" in statements[0]
        assert "another; semicolon" in statements[1]
    
    def test_split_sql_statements_with_multi_row_insert(self, initializer):
        """Test splitting SQL with multi-row INSERT statements."""
        sql = """
        INSERT INTO engineers (employee_id, name) VALUES
        ('ENG001', 'John Smith'),
        ('ENG002', 'Jane Doe'),
        ('ENG003', 'Bob Johnson');
        
        SELECT * FROM engineers;
        """
        
        statements = initializer.split_sql_statements(sql)
        
        assert len(statements) == 2
        # First statement should be the complete INSERT with all rows
        assert 'INSERT INTO engineers' in statements[0]
        assert 'ENG001' in statements[0]
        assert 'ENG002' in statements[0]
        assert 'ENG003' in statements[0]
        # Second statement should be the SELECT
        assert 'SELECT * FROM engineers' in statements[1]


class TestDataAPIResponseParsing:
    """Test Data API response parsing with various data types."""
    
    @pytest.fixture
    def initializer(self):
        """Create an initializer instance."""
        with patch('init_aurora_db.boto3.client'):
            return AuroraDBInitializer(
                cluster_arn=create_test_arn('rds', 'cluster'),
                secret_arn=create_test_arn('secretsmanager', 'secret'),
                database_name='test_db',
                region='us-east-1'
            )
    
    def test_parse_string_values(self, initializer):
        """Test parsing string values."""
        response = {
            'records': [[{'stringValue': 'test'}]],
            'columnMetadata': [{'name': 'col1'}]
        }
        
        results = initializer.parse_data_api_response(response)
        assert results[0]['col1'] == 'test'
    
    def test_parse_long_values(self, initializer):
        """Test parsing long integer values."""
        response = {
            'records': [[{'longValue': 12345}]],
            'columnMetadata': [{'name': 'col1'}]
        }
        
        results = initializer.parse_data_api_response(response)
        assert results[0]['col1'] == 12345
    
    def test_parse_double_values(self, initializer):
        """Test parsing double/float values."""
        response = {
            'records': [[{'doubleValue': 123.45}]],
            'columnMetadata': [{'name': 'col1'}]
        }
        
        results = initializer.parse_data_api_response(response)
        assert results[0]['col1'] == 123.45
    
    def test_parse_boolean_values(self, initializer):
        """Test parsing boolean values."""
        response = {
            'records': [[{'booleanValue': True}]],
            'columnMetadata': [{'name': 'col1'}]
        }
        
        results = initializer.parse_data_api_response(response)
        assert results[0]['col1'] is True
    
    def test_parse_mixed_types(self, initializer):
        """Test parsing mixed data types in one row."""
        response = {
            'records': [[
                {'stringValue': 'test'},
                {'longValue': 123},
                {'doubleValue': 45.67},
                {'booleanValue': False},
                {'isNull': True}
            ]],
            'columnMetadata': [
                {'name': 'str_col'},
                {'name': 'int_col'},
                {'name': 'float_col'},
                {'name': 'bool_col'},
                {'name': 'null_col'}
            ]
        }
        
        results = initializer.parse_data_api_response(response)
        assert results[0]['str_col'] == 'test'
        assert results[0]['int_col'] == 123
        assert results[0]['float_col'] == 45.67
        assert results[0]['bool_col'] is False
        assert results[0]['null_col'] is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
