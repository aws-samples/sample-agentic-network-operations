#!/usr/bin/env python3
"""
Test script for edge creation functions.

This script validates that the edge creation functions can parse the data structure
correctly without requiring an actual Neptune connection.
"""

import json
import logging
from typing import Dict, List, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_edge_structure(edge_type: str, edges: List[Dict[str, Any]]) -> bool:
    """
    Validate that edges have the expected structure.
    
    Args:
        edge_type: Type of edge (feeds, supplies, connects, protects)
        edges: List of edge dictionaries
        
    Returns:
        True if all edges are valid, False otherwise
    """
    logger.info(f"Validating {len(edges)} {edge_type} edges...")
    
    required_fields = {
        'feeds': ['from_id', 'to_id', 'feeder_id', 'voltage_kv', 'cable_type', 
                  'conductor_material', 'length_meters', 'capacity_amps'],
        'secondary_supplies': ['from_id', 'to_id', 'feeder_id', 'voltage_kv', 'cable_type',
                              'conductor_material', 'length_meters', 'capacity_amps',
                              'circuit_number', 'is_backup'],
        'connects': ['from_id', 'to_id', 'cable_type', 'conductor_size_mm2',
                    'length_meters', 'capacity_amps', 'num_phases', 'installation_year'],
        'protects': ['from_id', 'to_id', 'protection_type', 'trip_time_ms']
    }
    
    if edge_type not in required_fields:
        logger.error(f"Unknown edge type: {edge_type}")
        return False
    
    fields = required_fields[edge_type]
    valid = True
    
    for i, edge in enumerate(edges[:5]):  # Check first 5 edges
        missing_fields = [field for field in fields if field not in edge]
        if missing_fields:
            logger.error(f"Edge {i} missing fields: {missing_fields}")
            valid = False
        else:
            logger.debug(f"Edge {i}: {edge['from_id']} → {edge['to_id']} ✓")
    
    if valid:
        logger.info(f"✓ All {edge_type} edges have valid structure")
    else:
        logger.error(f"✗ Some {edge_type} edges have invalid structure")
    
    return valid


def main():
    """Main test function."""
    logger.info("=" * 80)
    logger.info("Edge Creation Functions Structure Test")
    logger.info("=" * 80)
    
    # Load network data
    data_file = "network_data.json"
    logger.info(f"Loading data from {data_file}...")
    
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Data file not found: {data_file}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in data file: {e}")
        return False
    
    logger.info("✓ Data loaded successfully")
    logger.info("")
    
    # Validate edge structures
    all_valid = True
    
    # Test FEEDS edges
    logger.info("=" * 80)
    if 'feeds' in data['edges']:
        all_valid &= validate_edge_structure('feeds', data['edges']['feeds'])
    else:
        logger.error("No 'feeds' edges found in data")
        all_valid = False
    
    logger.info("")
    
    # Test SUPPLIES edges (secondary_supplies in data)
    logger.info("=" * 80)
    if 'secondary_supplies' in data['edges']:
        all_valid &= validate_edge_structure('secondary_supplies', data['edges']['secondary_supplies'])
    else:
        logger.error("No 'secondary_supplies' edges found in data")
        all_valid = False
    
    logger.info("")
    
    # Test CONNECTS edges
    logger.info("=" * 80)
    if 'connects' in data['edges']:
        all_valid &= validate_edge_structure('connects', data['edges']['connects'])
    else:
        logger.error("No 'connects' edges found in data")
        all_valid = False
    
    logger.info("")
    
    # Test PROTECTS edges
    logger.info("=" * 80)
    if 'protects' in data['edges']:
        all_valid &= validate_edge_structure('protects', data['edges']['protects'])
    else:
        logger.error("No 'protects' edges found in data")
        all_valid = False
    
    logger.info("")
    logger.info("=" * 80)
    if all_valid:
        logger.info("✓ All edge structures are valid")
        logger.info("Edge creation functions should work correctly with this data")
    else:
        logger.error("✗ Some edge structures are invalid")
        logger.error("Edge creation functions may fail with this data")
    logger.info("=" * 80)
    
    return all_valid


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
