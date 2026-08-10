"""
Unit tests for PSR Lookup Lambda handler response formatting.

Tests cover:
- Response structure for found postcodes
- Response structure for not found postcodes
- Order preservation in results
"""

import json
import os
import sys
import tempfile
import pytest
from unittest.mock import MagicMock

# Add lambda function directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda_psr_lookup_tool'))

import lambda_handler


class TestResponseFormatting:
    """Test suite for Lambda handler response formatting."""
    
    def setup_method(self):
        """Set up test fixtures before each test."""
        # Reset module-level cache
        lambda_handler._psr_register_cache = None
        
        # Create temporary test data file
        self.test_data = [
            {"postcode": "M4 9CW", "on_psr": True},
            {"postcode": "L6 7SX", "on_psr": False},
            {"postcode": "WA1 6KW", "on_psr": False},
            {"postcode": "PR1 1KQ", "on_psr": False}
        ]
        
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(self.test_data, self.temp_file)
        self.temp_file.close()
        
        # Mock the PSR register file path
        original_join = os.path.join
        def mock_join(a, b):
            if b == "psr_register.json":
                return self.temp_file.name
            return original_join(a, b)
        
        self.patcher = pytest.MonkeyPatch()
        self.patcher.setattr('lambda_handler.os.path.join', mock_join)
        
        # Create mock context
        self.mock_context = MagicMock()
        self.mock_context.request_id = "test-request-123"
        self.mock_context.aws_request_id = "test-request-123"
    
    def teardown_method(self):
        """Clean up after each test."""
        self.patcher.undo()
        os.unlink(self.temp_file.name)
    
    def test_response_structure_for_found_postcodes(self):
        """Test that response has correct structure for postcodes found in register."""
        event = {
            "postcodes": ["M4 9CW", "L6 7SX"]
        }
        
        response = lambda_handler.lambda_handler(event, self.mock_context)
        
        # Verify response structure
        assert "statusCode" in response
        assert "body" in response
        assert response["statusCode"] == 200
        
        # Verify body structure
        body = response["body"]
        assert "results" in body
        assert isinstance(body["results"], list)
        assert len(body["results"]) == 2
        
        # Verify first result (on PSR)
        result1 = body["results"][0]
        assert "postcode" in result1
        assert "on_psr" in result1
        assert result1["postcode"] == "M4 9CW"
        assert result1["on_psr"] is True
        assert "found" not in result1  # Should not have redundant "found" field
        
        # Verify second result (not on PSR)
        result2 = body["results"][1]
        assert result2["postcode"] == "L6 7SX"
        assert result2["on_psr"] is False
        assert "found" not in result2
    
    def test_response_structure_for_not_found_postcodes(self):
        """Test that response has correct structure for postcodes not in register."""
        event = {
            "postcodes": ["INVALID1", "NOTFOUND"]
        }
        
        response = lambda_handler.lambda_handler(event, self.mock_context)
        
        # Verify response structure
        assert response["statusCode"] == 200
        assert "body" in response
        
        # Verify body structure
        body = response["body"]
        assert "results" in body
        assert len(body["results"]) == 2
        
        # Verify first result (not found = not on PSR)
        result1 = body["results"][0]
        assert result1["postcode"] == "INVALID1"
        assert result1["on_psr"] is False
        assert "found" not in result1
        
        # Verify second result (not found = not on PSR)
        result2 = body["results"][1]
        assert result2["postcode"] == "NOTFOUND"
        assert result2["on_psr"] is False
        assert "found" not in result2
    
    def test_response_structure_for_mixed_postcodes(self):
        """Test response structure with mix of found and not found postcodes."""
        event = {
            "postcodes": ["M4 9CW", "INVALID", "L6 7SX", "NOTFOUND"]
        }
        
        response = lambda_handler.lambda_handler(event, self.mock_context)
        
        # Verify response structure
        assert response["statusCode"] == 200
        body = response["body"]
        assert len(body["results"]) == 4
        
        # Verify found postcode (on PSR)
        assert body["results"][0]["postcode"] == "M4 9CW"
        assert body["results"][0]["on_psr"] is True
        
        # Verify not found postcode (not on PSR)
        assert body["results"][1]["postcode"] == "INVALID"
        assert body["results"][1]["on_psr"] is False
        
        # Verify another found postcode (not on PSR)
        assert body["results"][2]["postcode"] == "L6 7SX"
        assert body["results"][2]["on_psr"] is False
        
        # Verify another not found postcode (not on PSR)
        assert body["results"][3]["postcode"] == "NOTFOUND"
        assert body["results"][3]["on_psr"] is False
    
    def test_order_preservation_in_results(self):
        """Test that results maintain the same order as input postcodes."""
        # Test with specific order
        event = {
            "postcodes": ["WA1 6KW", "M4 9CW", "INVALID", "L6 7SX", "PR1 1KQ"]
        }
        
        response = lambda_handler.lambda_handler(event, self.mock_context)
        
        # Verify order is preserved
        body = response["body"]
        assert len(body["results"]) == 5
        
        # Check each postcode appears in the same position
        assert body["results"][0]["postcode"] == "WA1 6KW"
        assert body["results"][1]["postcode"] == "M4 9CW"
        assert body["results"][2]["postcode"] == "INVALID"
        assert body["results"][3]["postcode"] == "L6 7SX"
        assert body["results"][4]["postcode"] == "PR1 1KQ"
    
    def test_order_preservation_with_duplicates(self):
        """Test that order is preserved even with duplicate postcodes."""
        event = {
            "postcodes": ["M4 9CW", "L6 7SX", "M4 9CW", "L6 7SX"]
        }
        
        response = lambda_handler.lambda_handler(event, self.mock_context)
        
        # Verify each postcode gets its own result in order
        body = response["body"]
        assert len(body["results"]) == 4
        
        assert body["results"][0]["postcode"] == "M4 9CW"
        assert body["results"][1]["postcode"] == "L6 7SX"
        assert body["results"][2]["postcode"] == "M4 9CW"
        assert body["results"][3]["postcode"] == "L6 7SX"
    
    def test_empty_postcodes_array(self):
        """Test that empty postcodes array returns empty results."""
        event = {
            "postcodes": []
        }
        
        response = lambda_handler.lambda_handler(event, self.mock_context)
        
        # Verify response structure
        assert response["statusCode"] == 200
        body = response["body"]
        assert "results" in body
        assert body["results"] == []
    
    def test_original_postcode_format_preserved(self):
        """Test that original postcode format is preserved in response."""
        # Test with various formats
        event = {
            "postcodes": ["m4 9cw", "  L6 7SX  ", "WA1   6KW"]
        }
        
        response = lambda_handler.lambda_handler(event, self.mock_context)
        
        # Verify original formats are preserved in response
        body = response["body"]
        assert body["results"][0]["postcode"] == "m4 9cw"
        assert body["results"][1]["postcode"] == "  L6 7SX  "
        assert body["results"][2]["postcode"] == "WA1   6KW"
        
        # But lookups should still work (normalization happens internally)
        assert body["results"][0]["on_psr"] is True
        assert body["results"][1]["on_psr"] is False
        assert body["results"][2]["on_psr"] is False


class TestResponseFieldTypes:
    """Test suite for verifying correct data types in response fields."""
    
    def setup_method(self):
        """Set up test fixtures before each test."""
        lambda_handler._psr_register_cache = None
        
        self.test_data = [
            {"postcode": "M4 9CW", "on_psr": True},
            {"postcode": "L6 7SX", "on_psr": False}
        ]
        
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(self.test_data, self.temp_file)
        self.temp_file.close()
        
        original_join = os.path.join
        def mock_join(a, b):
            if b == "psr_register.json":
                return self.temp_file.name
            return original_join(a, b)
        
        self.patcher = pytest.MonkeyPatch()
        self.patcher.setattr('lambda_handler.os.path.join', mock_join)
        
        self.mock_context = MagicMock()
        self.mock_context.request_id = "test-request-123"
    
    def teardown_method(self):
        """Clean up after each test."""
        self.patcher.undo()
        os.unlink(self.temp_file.name)
    
    def test_field_types_for_found_postcode(self):
        """Test that all fields have correct types for found postcodes."""
        event = {"postcodes": ["M4 9CW"]}
        response = lambda_handler.lambda_handler(event, self.mock_context)
        
        result = response["body"]["results"][0]
        
        # Verify types
        assert isinstance(result["postcode"], str)
        assert isinstance(result["on_psr"], bool)
        assert "found" not in result
    
    def test_field_types_for_not_found_postcode(self):
        """Test that all fields have correct types for not found postcodes."""
        event = {"postcodes": ["INVALID"]}
        response = lambda_handler.lambda_handler(event, self.mock_context)
        
        result = response["body"]["results"][0]
        
        # Verify types
        assert isinstance(result["postcode"], str)
        assert isinstance(result["on_psr"], bool)
        assert result["on_psr"] is False  # False for not found
        assert "found" not in result
    
    def test_status_code_is_integer(self):
        """Test that statusCode is an integer."""
        event = {"postcodes": ["M4 9CW"]}
        response = lambda_handler.lambda_handler(event, self.mock_context)
        
        assert isinstance(response["statusCode"], int)
        assert response["statusCode"] == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
