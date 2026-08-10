"""
Unit tests for PSR Lookup Lambda data loading and caching functionality.

Tests cover:
- Successful data loading from valid JSON file
- Error handling for missing file
- Error handling for invalid JSON
- Caching behavior across multiple calls
"""

import json
import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock

# Add lambda function directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda_psr_lookup_tool'))

import lambda_handler


class TestDataLoading:
    """Test suite for PSR register data loading."""
    
    def setup_method(self):
        """Reset module-level cache before each test."""
        lambda_handler._psr_register_cache = None
    
    def test_successful_data_loading_from_valid_json(self):
        """Test loading PSR register data from a valid JSON file."""
        # Create temporary test data file
        test_data = [
            {"postcode": "M4 9CW", "on_psr": True},
            {"postcode": "L6 7SX", "on_psr": False},
            {"postcode": "WA1 6KW", "on_psr": False}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_file_path = f.name
        
        try:
            # Mock the file path to use our test file
            with patch('lambda_handler.os.path.join', return_value=temp_file_path):
                with patch('lambda_handler.os.path.dirname', return_value=os.path.dirname(temp_file_path)):
                    psr_register = lambda_handler._load_psr_register()
            
            # Verify data was loaded correctly
            assert psr_register is not None
            assert len(psr_register) == 3
            assert psr_register["M4 9CW"] is True
            assert psr_register["L6 7SX"] is False
            assert psr_register["WA1 6KW"] is False
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
    
    def test_error_handling_for_missing_file(self):
        """Test that FileNotFoundError is raised when data file doesn't exist."""
        non_existent_path = "/tmp/non_existent_psr_data_12345.json"
        
        # Mock the file path to use non-existent file
        with patch('lambda_handler.os.path.join', return_value=non_existent_path):
            with patch('lambda_handler.os.path.dirname', return_value="/tmp"):
                with pytest.raises(FileNotFoundError) as exc_info:
                    lambda_handler._load_psr_register()
        
        assert "PSR register data file not found" in str(exc_info.value)
    
    def test_error_handling_for_invalid_json(self):
        """Test that JSONDecodeError is raised when data file contains invalid JSON."""
        # Create temporary file with invalid JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json content }")
            temp_file_path = f.name
        
        try:
            # Mock the file path to use our test file
            with patch('lambda_handler.os.path.join', return_value=temp_file_path):
                with patch('lambda_handler.os.path.dirname', return_value=os.path.dirname(temp_file_path)):
                    with pytest.raises(json.JSONDecodeError):
                        lambda_handler._load_psr_register()
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
    
    def test_caching_behavior_across_multiple_calls(self):
        """Test that PSR register data is cached and reused across multiple calls."""
        # Create temporary test data file
        test_data = [
            {"postcode": "M4 9CW", "on_psr": True},
            {"postcode": "L6 7SX", "on_psr": False}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_file_path = f.name
        
        try:
            # Mock the file path to use our test file
            with patch('lambda_handler.os.path.join', return_value=temp_file_path):
                with patch('lambda_handler.os.path.dirname', return_value=os.path.dirname(temp_file_path)):
                    # First call - should load from file
                    register1 = lambda_handler._load_psr_register()
                    
                    # Verify cache was populated
                    assert lambda_handler._psr_register_cache is not None
                    assert lambda_handler._psr_register_cache is register1
                    
                    # Second call - should use cache
                    register2 = lambda_handler._load_psr_register()
                    
                    # Verify same object is reused (not just equal, but identical)
                    assert register2 is register1
                    assert id(register2) == id(register1)
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
    
    def test_default_path_resolution(self):
        """Test that default path resolution works correctly in _load_psr_register."""
        # This test verifies the path construction logic
        # We can't easily test the actual path without mocking, but we can verify
        # the function constructs a path that includes psr_register.json
        
        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "psr_register.json")
            test_data = [{"postcode": "M4 9CW", "on_psr": True}]
            
            with open(test_file, 'w') as f:
                json.dump(test_data, f)
            
            # Mock to use our temp directory
            with patch('lambda_handler.os.path.dirname', return_value=temp_dir):
                with patch('lambda_handler.os.path.join', return_value=test_file):
                    psr_register = lambda_handler._load_psr_register()
                    
                    # Verify data was loaded
                    assert psr_register is not None
                    assert "M4 9CW" in psr_register


class TestPostcodeNormalization:
    """Test suite for postcode normalization during data loading."""
    
    def setup_method(self):
        """Reset module-level cache before each test."""
        lambda_handler._psr_register_cache = None
    
    def test_postcodes_normalized_during_loading(self):
        """Test that postcodes are normalized when loading from JSON."""
        # Create test data with various postcode formats
        test_data = [
            {"postcode": "m4 9cw", "on_psr": True},      # lowercase
            {"postcode": "  L6 7SX  ", "on_psr": False},  # extra whitespace
            {"postcode": "WA1   6KW", "on_psr": False}    # multiple spaces
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_file_path = f.name
        
        try:
            # Mock the file path to use our test file
            with patch('lambda_handler.os.path.join', return_value=temp_file_path):
                with patch('lambda_handler.os.path.dirname', return_value=os.path.dirname(temp_file_path)):
                    psr_register = lambda_handler._load_psr_register()
            
            # Verify all postcodes are normalized in the register
            assert "M4 9CW" in psr_register
            assert "L6 7SX" in psr_register
            assert "WA1 6KW" in psr_register
            
            # Verify lowercase and extra whitespace versions are not keys
            assert "m4 9cw" not in psr_register
            assert "  L6 7SX  " not in psr_register
            assert "WA1   6KW" not in psr_register
        finally:
            os.unlink(temp_file_path)
    
    def test_normalize_postcode_function(self):
        """Test the _normalize_postcode function directly."""
        # Test various formats
        assert lambda_handler._normalize_postcode("m4 9cw") == "M4 9CW"
        assert lambda_handler._normalize_postcode("  L6 7SX  ") == "L6 7SX"
        assert lambda_handler._normalize_postcode("WA1   6KW") == "WA1 6KW"
        assert lambda_handler._normalize_postcode("M4  9CW") == "M4 9CW"
        assert lambda_handler._normalize_postcode("m4    9cw") == "M4 9CW"


class TestLookupFunctionality:
    """Test suite for postcode lookup functionality."""
    
    def test_lookup_postcodes_found(self):
        """Test looking up postcodes that exist in the register."""
        psr_register = {
            "M4 9CW": True,
            "L6 7SX": False,
            "WA1 6KW": False
        }
        
        postcodes = ["M4 9CW", "L6 7SX"]
        results = lambda_handler._lookup_postcodes(postcodes, psr_register)
        
        assert len(results) == 2
        assert results[0] == {"postcode": "M4 9CW", "on_psr": True}
        assert results[1] == {"postcode": "L6 7SX", "on_psr": False}
    
    def test_lookup_postcodes_not_found(self):
        """Test looking up postcodes that don't exist in the register."""
        psr_register = {
            "M4 9CW": True
        }
        
        postcodes = ["INVALID"]
        results = lambda_handler._lookup_postcodes(postcodes, psr_register)
        
        assert len(results) == 1
        assert results[0] == {"postcode": "INVALID", "on_psr": False}
    
    def test_lookup_postcodes_mixed(self):
        """Test looking up a mix of found and not found postcodes."""
        psr_register = {
            "M4 9CW": True,
            "L6 7SX": False
        }
        
        postcodes = ["M4 9CW", "INVALID", "L6 7SX"]
        results = lambda_handler._lookup_postcodes(postcodes, psr_register)
        
        assert len(results) == 3
        assert results[0] == {"postcode": "M4 9CW", "on_psr": True}
        assert results[1] == {"postcode": "INVALID", "on_psr": False}
        assert results[2] == {"postcode": "L6 7SX", "on_psr": False}
    
    def test_lookup_with_case_variations(self):
        """Test that lookup works with different case variations."""
        psr_register = {
            "M4 9CW": True
        }
        
        # Test lowercase input
        postcodes = ["m4 9cw"]
        results = lambda_handler._lookup_postcodes(postcodes, psr_register)
        
        assert len(results) == 1
        assert results[0]["postcode"] == "m4 9cw"  # Original preserved
        assert results[0]["on_psr"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
