#!/usr/bin/env python3
"""
Neptune Analytics CSV Exporter

Exports the generated electricity distribution network data to CSV format
for import into Amazon Neptune Analytics.

Neptune Analytics supports CSV import with separate files for nodes and edges.

Usage:
    python src/export_network_to_csv.py --input network_data.json --output-dir neptune_csv
"""

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Any


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure logging for the CSV exporter."""
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger


logger = setup_logging()


# ============================================================================
# CSV EXPORT FUNCTIONS
# ============================================================================

def export_nodes_to_csv(
    nodes: List[Dict[str, Any]],
    node_type: str,
    output_dir: Path
) -> str:
    """
    Export nodes to CSV format for Neptune Analytics.
    
    Neptune Analytics CSV format for nodes:
    - First column: ~id (unique identifier)
    - Second column: ~label (node type)
    - Remaining columns: properties with type suffixes
    
    Type suffixes:
    - :Int for integers
    - :Double for floats
    - :Bool for booleans
    - No suffix for strings
    
    Args:
        nodes: List of node dictionaries
        node_type: Type of node (e.g., 'GridSupplyPoint')
        output_dir: Directory to write CSV files
        
    Returns:
        Path to created CSV file
    """
    if not nodes:
        logger.warning(f"No {node_type} nodes to export")
        return None
    
    filename = f"{node_type.lower()}_nodes.csv"
    filepath = output_dir / filename
    
    logger.info(f"Exporting {len(nodes)} {node_type} nodes to {filepath}")
    
    # Get all unique property keys from all nodes
    all_keys = set()
    for node in nodes:
        all_keys.update(node.keys())
    
    # Remove 'id' as it will be mapped to ~id
    all_keys.discard('id')
    
    # Sort keys for consistent column order
    property_keys = sorted(all_keys)
    
    # Infer types from first node with each property
    property_types = {}
    for key in property_keys:
        for node in nodes:
            if key in node and node[key] is not None and node[key] != '':
                value = node[key]
                if isinstance(value, bool):
                    property_types[key] = ':Bool'
                elif isinstance(value, int):
                    property_types[key] = ':Int'
                elif isinstance(value, float):
                    property_types[key] = ':Double'
                else:
                    property_types[key] = ''  # String (no suffix)
                break
    
    # Neptune Analytics CSV header format with type suffixes
    headers = ['~id', '~label'] + [f"{key}{property_types.get(key, '')}" for key in property_keys]
    
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        
        for node in nodes:
            row = {
                '~id': node.get('id', node.get('uprn', '')),  # Use id or uprn for Property
                '~label': node_type
            }
            
            # Add all properties with typed header keys
            for key in property_keys:
                value = node.get(key, '')
                # Convert boolean to string
                if isinstance(value, bool):
                    value = str(value).lower()
                # Use the typed header key
                typed_key = f"{key}{property_types.get(key, '')}"
                row[typed_key] = value
            
            writer.writerow(row)
    
    logger.info(f"✓ Exported {len(nodes)} {node_type} nodes")
    return str(filepath)


def export_edges_to_csv(
    edges: List[Dict[str, Any]],
    edge_type: str,
    output_dir: Path
) -> str:
    """
    Export edges to CSV format for Neptune Analytics.
    
    Neptune Analytics CSV format for edges:
    - ~id: unique edge identifier
    - ~from: source node ID
    - ~to: target node ID
    - ~label: edge type
    - Remaining columns: edge properties with type suffixes
    
    Type suffixes:
    - :Int for integers
    - :Double for floats
    - :Bool for booleans
    - No suffix for strings
    
    Args:
        edges: List of edge dictionaries
        edge_type: Type of edge (e.g., 'FEEDS')
        output_dir: Directory to write CSV files
        
    Returns:
        Path to created CSV file
    """
    if not edges:
        logger.warning(f"No {edge_type} edges to export")
        return None
    
    filename = f"{edge_type.lower()}_edges.csv"
    filepath = output_dir / filename
    
    logger.info(f"Exporting {len(edges)} {edge_type} edges to {filepath}")
    
    # Get all unique property keys
    all_keys = set()
    for edge in edges:
        all_keys.update(edge.keys())
    
    # Remove standard edge keys
    all_keys.discard('from_id')
    all_keys.discard('to_id')
    
    # Sort keys for consistent column order
    property_keys = sorted(all_keys)
    
    # Infer types from first edge with each property
    property_types = {}
    for key in property_keys:
        for edge in edges:
            if key in edge and edge[key] is not None and edge[key] != '':
                value = edge[key]
                if isinstance(value, bool):
                    property_types[key] = ':Bool'
                elif isinstance(value, int):
                    property_types[key] = ':Int'
                elif isinstance(value, float):
                    property_types[key] = ':Double'
                else:
                    property_types[key] = ''  # String (no suffix)
                break
    
    # Neptune Analytics CSV header format with type suffixes
    headers = ['~id', '~from', '~to', '~label'] + [f"{key}{property_types.get(key, '')}" for key in property_keys]
    
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        
        for i, edge in enumerate(edges, start=1):
            row = {
                '~id': f"{edge_type}-{i}",
                '~from': edge['from_id'],
                '~to': edge['to_id'],
                '~label': edge_type
            }
            
            # Add all properties with typed header keys
            for key in property_keys:
                value = edge.get(key, '')
                # Convert boolean to string
                if isinstance(value, bool):
                    value = str(value).lower()
                # Use the typed header key
                typed_key = f"{key}{property_types.get(key, '')}"
                row[typed_key] = value
            
            writer.writerow(row)
    
    logger.info(f"✓ Exported {len(edges)} {edge_type} edges")
    return str(filepath)


def export_network_to_neptune_csv(
    data_file: str,
    output_dir: str
) -> Dict[str, List[str]]:
    """
    Export network data to Neptune Analytics CSV format.
    
    Creates separate CSV files for each node type and edge type.
    
    Args:
        data_file: Path to JSON data file
        output_dir: Directory to write CSV files
        
    Returns:
        Dictionary with lists of created node and edge CSV files
    """
    logger.info(f"Loading network data from {data_file}")
    
    # Load JSON data
    with open(data_file, 'r') as f:
        data = json.load(f)
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Output directory: {output_path}")
    
    # Track created files
    node_files = []
    edge_files = []
    
    # Export nodes
    logger.info("=" * 80)
    logger.info("EXPORTING NODES")
    logger.info("=" * 80)
    
    node_types = [
        ('grid_supply_points', 'GridSupplyPoint'),
        ('primary_substations', 'PrimarySubstation'),
        ('secondary_substations', 'SecondarySubstation'),
        ('properties', 'Property'),
        ('protection_devices', 'ProtectionDevice')
    ]
    
    for data_key, node_type in node_types:
        if 'vertices' in data and data_key in data['vertices']:
            filepath = export_nodes_to_csv(
                data['vertices'][data_key],
                node_type,
                output_path
            )
            if filepath:
                node_files.append(filepath)
    
    # Export edges
    logger.info("=" * 80)
    logger.info("EXPORTING EDGES")
    logger.info("=" * 80)
    
    edge_types = [
        ('feeds', 'FEEDS'),
        ('ring_topology', 'RING_TOPOLOGY'),
        ('secondary_supplies', 'SUPPLIES'),
        ('connects', 'CONNECTS'),
        ('protects', 'PROTECTS')
    ]
    
    for data_key, edge_type in edge_types:
        if 'edges' in data and data_key in data['edges']:
            filepath = export_edges_to_csv(
                data['edges'][data_key],
                edge_type,
                output_path
            )
            if filepath:
                edge_files.append(filepath)
    
    # Summary
    logger.info("=" * 80)
    logger.info("EXPORT SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Node CSV files: {len(node_files)}")
    for f in node_files:
        logger.info(f"  - {f}")
    logger.info(f"Edge CSV files: {len(edge_files)}")
    for f in edge_files:
        logger.info(f"  - {f}")
    
    return {
        'node_files': node_files,
        'edge_files': edge_files
    }


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point for CSV export."""
    parser = argparse.ArgumentParser(
        description='Export network data to Neptune Analytics CSV format'
    )
    parser.add_argument(
        '--input',
        type=str,
        default='network_data.json',
        help='Input JSON data file (default: network_data.json)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='neptune_csv',
        help='Output directory for CSV files (default: neptune_csv)'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )
    
    args = parser.parse_args()
    
    # Update logger level
    global logger
    logger = setup_logging(args.log_level)
    
    try:
        # Export to CSV
        result = export_network_to_neptune_csv(
            args.input,
            args.output_dir
        )
        
        logger.info("=" * 80)
        logger.info("✓ CSV EXPORT COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total files created: {len(result['node_files']) + len(result['edge_files'])}")
        logger.info(f"Output directory: {args.output_dir}")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Create a Neptune Analytics graph")
        logger.info("2. Upload CSV files to S3")
        logger.info("3. Import CSV files into Neptune Analytics")
        logger.info("4. Query the graph using openCypher")
        
        return 0
        
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
