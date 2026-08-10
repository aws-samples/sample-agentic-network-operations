#!/usr/bin/env python3
"""
North West England Electricity Distribution Network Data Generator

Generates realistic mock data for an electricity distribution network operated by
Unicorn Energy Networks (DNO) with retail supply by Unicorn Power.

Geographic Scope: North West England (Greater Manchester, Merseyside, Lancashire, 
Cheshire, and Cumbria)
"""

import json
import logging
import random
import sys
from datetime import datetime
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass, asdict


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Configure logging for the data generator.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Console handler with formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger


# Initialize logger
logger = setup_logging()


# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

# Company Information
DNO_OPERATOR = "Unicorn Energy Networks"
ELECTRICITY_SUPPLIER = "Unicorn Power"

# Network Scale
NUM_GSPS = 3
NUM_PRIMARY_SUBSTATIONS = 20
NUM_SECONDARY_SUBSTATIONS = 150
NUM_PROPERTIES = 10000
NUM_PROTECTION_DEVICES_PER_PRIMARY = 2

# Voltage Standards (UK)
TRANSMISSION_VOLTAGES_KV = [132, 275]
PRIMARY_DISTRIBUTION_VOLTAGES_KV = [11, 33]
SECONDARY_VOLTAGE_SINGLE_PHASE_V = 230
SECONDARY_VOLTAGE_THREE_PHASE_V = 400

# Property Type Distribution
PROPERTY_TYPE_DISTRIBUTION = {
    'residential': 0.75,  # 75%
    'commercial': 0.20,   # 20%
    'industrial': 0.05    # 5%
}

# Property Subtype Distribution
RESIDENTIAL_SUBTYPES = {
    'house': 0.67,  # 50% of total (67% of residential)
    'flat': 0.33    # 25% of total (33% of residential)
}

COMMERCIAL_SUBTYPES = {
    'shop': 0.50,   # 10% of total (50% of commercial)
    'office': 0.50  # 10% of total (50% of commercial)
}

INDUSTRIAL_SUBTYPES = {
    'factory': 0.60,    # 3% of total (60% of industrial)
    'warehouse': 0.40   # 2% of total (40% of industrial)
}

# North West England Cities and Postcodes
NW_ENGLAND_CITIES = {
    'Manchester': {'postcode_prefix': 'M', 'area': 'Greater Manchester'},
    'Liverpool': {'postcode_prefix': 'L', 'area': 'Merseyside'},
    'Preston': {'postcode_prefix': 'PR', 'area': 'Lancashire'},
    'Chester': {'postcode_prefix': 'CH', 'area': 'Cheshire'},
    'Carlisle': {'postcode_prefix': 'CA', 'area': 'Cumbria'},
    'Blackpool': {'postcode_prefix': 'FY', 'area': 'Lancashire'},
    'Bolton': {'postcode_prefix': 'BL', 'area': 'Greater Manchester'},
    'Warrington': {'postcode_prefix': 'WA', 'area': 'Cheshire'}
}

# Geographic Boundaries for North West England
NW_ENGLAND_BOUNDS = {
    'lat_min': 53.0,
    'lat_max': 55.0,
    'lon_min': -3.5,
    'lon_max': -2.0
}

# Cable Types
CABLE_TYPES = ['overhead', 'underground']
CONDUCTOR_MATERIALS = ['copper', 'aluminum']

# Protection Device Types
PROTECTION_DEVICE_TYPES = ['circuit_breaker', 'fuse', 'recloser']

# Substation Types
SECONDARY_SUBSTATION_TYPES = ['pole-mounted', 'ground-mounted', 'kiosk']


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class GridSupplyPoint:
    """Grid Supply Point - connection to transmission system"""
    id: str
    name: str
    voltage_kv: int
    capacity_mva: float
    location: str
    latitude: float
    longitude: float
    operator: str


@dataclass
class PrimarySubstation:
    """Primary Substation - steps down from transmission to primary distribution"""
    id: str
    name: str
    voltage_in_kv: int
    voltage_out_kv: int
    capacity_mva: float
    location: str
    latitude: float
    longitude: float
    num_transformers: int
    has_circuit_breaker: bool
    has_switchgear: bool
    operator: str


@dataclass
class SecondarySubstation:
    """Secondary Substation - steps down to low voltage for consumers"""
    id: str
    name: str
    transformer_capacity_kva: float
    voltage_in_kv: int
    voltage_out_v: int
    num_phases: int
    location: str
    latitude: float
    longitude: float
    substation_type: str
    installation_year: int
    operator: str


@dataclass
class Property:
    """Property - electricity consumer (residential, commercial, industrial)"""
    uprn: str
    mpan: str
    address_number: str
    address_street: str
    address_city: str
    address_area: str
    postcode: str
    property_type: str
    property_subtype: str
    num_bedrooms: int  # residential only, 0 for others
    connection_type: str
    peak_demand_kw: float
    has_smart_meter: bool
    latitude: float
    longitude: float
    supplier: str


@dataclass
class ProtectionDevice:
    """Protection Device - circuit breakers, fuses, reclosers"""
    id: str
    device_type: str
    rating_amps: int
    voltage_kv: float
    location: str
    installation_year: int
    operator: str


@dataclass
class FeedsEdge:
    """FEEDS edge - GSP to Primary Substation"""
    from_id: str
    to_id: str
    feeder_id: str
    voltage_kv: int
    cable_type: str
    conductor_material: str
    length_meters: float
    capacity_amps: int


@dataclass
class SuppliesEdge:
    """SUPPLIES edge - Primary to Secondary Substation"""
    from_id: str
    to_id: str
    feeder_id: str
    voltage_kv: int
    cable_type: str
    conductor_material: str
    length_meters: float
    capacity_amps: int
    circuit_number: int
    is_backup: bool


@dataclass
class ConnectsEdge:
    """CONNECTS edge - Secondary Substation to Property"""
    from_id: str
    to_id: str
    cable_type: str
    conductor_size_mm2: float
    length_meters: float
    capacity_amps: int
    num_phases: int
    installation_year: int


@dataclass
class ProtectsEdge:
    """PROTECTS edge - Protection Device to Substation"""
    from_id: str
    to_id: str
    protection_type: str
    trip_time_ms: int


# ============================================================================
# GLOBAL STATE FOR UNIQUENESS TRACKING
# ============================================================================

# Track generated identifiers to ensure uniqueness
generated_uprns: Set[str] = set()
generated_mpans: Set[str] = set()


# ============================================================================
# DATA GENERATION FUNCTIONS
# ============================================================================

def generate_gsps(count: int = NUM_GSPS) -> List[GridSupplyPoint]:
    """
    Generate Grid Supply Points for North West England.
    
    GSPs are the connection points between the transmission system (National Grid)
    and the distribution network operated by Unicorn Energy Networks.
    
    Args:
        count: Number of GSPs to generate (default: 3)
        
    Returns:
        List of GridSupplyPoint objects
    """
    logger.info(f"Generating {count} Grid Supply Points for North West England...")
    
    # Real GSP locations in North West England with realistic coordinates
    gsp_locations = [
        {
            'name': 'Manchester North GSP',
            'location': 'Greater Manchester',
            'latitude': 53.5074,  # North Manchester area
            'longitude': -2.2426,
            'voltage_kv': 275,
            'capacity_mva': 500.0
        },
        {
            'name': 'Liverpool GSP',
            'location': 'Merseyside',
            'latitude': 53.4084,
            'longitude': -2.9916,
            'voltage_kv': 132,
            'capacity_mva': 350.0
        },
        {
            'name': 'Carlisle GSP',
            'location': 'Cumbria',
            'latitude': 54.8951,
            'longitude': -2.9382,
            'voltage_kv': 132,
            'capacity_mva': 250.0
        }
    ]
    
    gsps = []
    for i, location_data in enumerate(gsp_locations[:count], start=1):
        gsp = GridSupplyPoint(
            id=f"GSP{i:03d}",
            name=location_data['name'],
            voltage_kv=location_data['voltage_kv'],
            capacity_mva=location_data['capacity_mva'],
            location=location_data['location'],
            latitude=location_data['latitude'],
            longitude=location_data['longitude'],
            operator=DNO_OPERATOR
        )
        gsps.append(gsp)
        logger.debug(f"Created GSP: {gsp.name} ({gsp.voltage_kv}kV, {gsp.capacity_mva}MVA)")
    
    logger.info(f"Generated {len(gsps)} Grid Supply Points")
    return gsps


def generate_primary_substations(
    gsps: List[GridSupplyPoint], 
    count: int = NUM_PRIMARY_SUBSTATIONS
) -> Tuple[List[PrimarySubstation], List[FeedsEdge], List[SuppliesEdge]]:
    """
    Generate Primary Substations for North West England with ring topology.
    
    Primary substations step down voltage from transmission levels (132kV/275kV)
    to primary distribution levels (11kV/33kV). They are connected in a ring
    topology for redundancy.
    
    Args:
        gsps: List of Grid Supply Points to connect to
        count: Number of primary substations to generate (default: 20)
        
    Returns:
        Tuple of (primary_substations, feeds_edges, ring_topology_edges)
        - primary_substations: List of PrimarySubstation objects
        - feeds_edges: List of FeedsEdge objects (GSP → Primary)
        - ring_topology_edges: List of SuppliesEdge objects (Primary → Primary ring)
    """
    logger.info(f"Generating {count} Primary Substations for North West England...")
    
    # Real primary substation locations in North West England
    primary_locations = [
        # Greater Manchester area (8 substations)
        {'name': 'Salford Quays Primary', 'location': 'Salford, Greater Manchester', 
         'latitude': 53.4719, 'longitude': -2.2965, 'gsp_index': 0},
        {'name': 'Trafford Park Primary', 'location': 'Trafford, Greater Manchester',
         'latitude': 53.4675, 'longitude': -2.3089, 'gsp_index': 0},
        {'name': 'Stockport Primary', 'location': 'Stockport, Greater Manchester',
         'latitude': 53.4106, 'longitude': -2.1575, 'gsp_index': 0},
        {'name': 'Oldham Primary', 'location': 'Oldham, Greater Manchester',
         'latitude': 53.5444, 'longitude': -2.1169, 'gsp_index': 0},
        {'name': 'Rochdale Primary', 'location': 'Rochdale, Greater Manchester',
         'latitude': 53.6097, 'longitude': -2.1561, 'gsp_index': 0},
        {'name': 'Bolton Primary', 'location': 'Bolton, Greater Manchester',
         'latitude': 53.5768, 'longitude': -2.4282, 'gsp_index': 0},
        {'name': 'Wigan Primary', 'location': 'Wigan, Greater Manchester',
         'latitude': 53.5450, 'longitude': -2.6325, 'gsp_index': 0},
        {'name': 'Bury Primary', 'location': 'Bury, Greater Manchester',
         'latitude': 53.5933, 'longitude': -2.2966, 'gsp_index': 0},
        
        # Merseyside area (6 substations)
        {'name': 'Anfield Primary', 'location': 'Liverpool, Merseyside',
         'latitude': 53.4308, 'longitude': -2.9608, 'gsp_index': 1},
        {'name': 'Liverpool Docks Primary', 'location': 'Liverpool, Merseyside',
         'latitude': 53.4014, 'longitude': -2.9930, 'gsp_index': 1},
        {'name': 'Birkenhead Primary', 'location': 'Birkenhead, Merseyside',
         'latitude': 53.3932, 'longitude': -3.0145, 'gsp_index': 1},
        {'name': 'St Helens Primary', 'location': 'St Helens, Merseyside',
         'latitude': 53.4500, 'longitude': -2.7373, 'gsp_index': 1},
        {'name': 'Southport Primary', 'location': 'Southport, Merseyside',
         'latitude': 53.6476, 'longitude': -3.0052, 'gsp_index': 1},
        {'name': 'Bootle Primary', 'location': 'Bootle, Merseyside',
         'latitude': 53.4450, 'longitude': -2.9890, 'gsp_index': 1},
        
        # Lancashire, Cheshire, Cumbria (6 substations)
        {'name': 'Preston Docks Primary', 'location': 'Preston, Lancashire',
         'latitude': 53.7632, 'longitude': -2.7044, 'gsp_index': 2},
        {'name': 'Blackpool Primary', 'location': 'Blackpool, Lancashire',
         'latitude': 53.8175, 'longitude': -3.0357, 'gsp_index': 2},
        {'name': 'Chester Primary', 'location': 'Chester, Cheshire',
         'latitude': 53.1905, 'longitude': -2.8908, 'gsp_index': 1},
        {'name': 'Warrington Primary', 'location': 'Warrington, Cheshire',
         'latitude': 53.3900, 'longitude': -2.5970, 'gsp_index': 0},
        {'name': 'Carlisle North Primary', 'location': 'Carlisle, Cumbria',
         'latitude': 54.9026, 'longitude': -2.9382, 'gsp_index': 2},
        {'name': 'Barrow Primary', 'location': 'Barrow-in-Furness, Cumbria',
         'latitude': 54.1107, 'longitude': -3.2269, 'gsp_index': 2}
    ]
    
    primary_substations = []
    feeds_edges = []
    
    # Generate primary substations
    for i, location_data in enumerate(primary_locations[:count], start=1):
        # Get the GSP this primary connects to
        gsp = gsps[location_data['gsp_index']]
        
        # Determine voltage levels
        voltage_in_kv = gsp.voltage_kv
        voltage_out_kv = random.choice(PRIMARY_DISTRIBUTION_VOLTAGES_KV)
        
        # Create primary substation
        primary = PrimarySubstation(
            id=f"PS{i:03d}",
            name=location_data['name'],
            voltage_in_kv=voltage_in_kv,
            voltage_out_kv=voltage_out_kv,
            capacity_mva=random.uniform(30.0, 90.0),  # 30-90 MVA capacity
            location=location_data['location'],
            latitude=location_data['latitude'],
            longitude=location_data['longitude'],
            num_transformers=random.randint(2, 4),
            has_circuit_breaker=True,
            has_switchgear=True,
            operator=DNO_OPERATOR
        )
        primary_substations.append(primary)
        
        # Create FEEDS edge from GSP to Primary
        feeds_edge = FeedsEdge(
            from_id=gsp.id,
            to_id=primary.id,
            feeder_id=f"F-{gsp.id}-{primary.id}",
            voltage_kv=voltage_in_kv,
            cable_type=random.choice(CABLE_TYPES),
            conductor_material=random.choice(CONDUCTOR_MATERIALS),
            length_meters=random.uniform(5000, 25000),  # 5-25 km
            capacity_amps=random.randint(400, 1200)
        )
        feeds_edges.append(feeds_edge)
        
        logger.debug(f"Created Primary: {primary.name} ({primary.voltage_in_kv}kV → {primary.voltage_out_kv}kV, {primary.capacity_mva:.1f}MVA)")
    
    # Create ring topology connections between primary substations
    logger.info("Creating ring topology connections between primary substations...")
    ring_topology_edges = []
    
    # Group primaries by GSP for regional ring topology
    primaries_by_gsp = {}
    for primary in primary_substations:
        # Find which GSP this primary connects to by checking feeds_edges
        gsp_id = None
        for edge in feeds_edges:
            if edge.to_id == primary.id:
                gsp_id = edge.from_id
                break
        
        if gsp_id not in primaries_by_gsp:
            primaries_by_gsp[gsp_id] = []
        primaries_by_gsp[gsp_id].append(primary)
    
    # Create ring connections within each GSP region
    for gsp_id, primaries in primaries_by_gsp.items():
        if len(primaries) < 2:
            continue
            
        # Create ring: connect each primary to the next one, and last to first
        for i in range(len(primaries)):
            from_primary = primaries[i]
            to_primary = primaries[(i + 1) % len(primaries)]
            
            # Create bidirectional ring connection (normal direction)
            ring_edge = SuppliesEdge(
                from_id=from_primary.id,
                to_id=to_primary.id,
                feeder_id=f"RING-{from_primary.id}-{to_primary.id}",
                voltage_kv=from_primary.voltage_out_kv,
                cable_type=random.choice(CABLE_TYPES),
                conductor_material=random.choice(CONDUCTOR_MATERIALS),
                length_meters=random.uniform(3000, 15000),  # 3-15 km between primaries
                capacity_amps=random.randint(300, 800),
                circuit_number=1,
                is_backup=False
            )
            ring_topology_edges.append(ring_edge)
            
            logger.debug(f"Ring connection: {from_primary.name} → {to_primary.name}")
    
    # Add some cross-region connections for additional redundancy
    if len(primary_substations) >= 10:
        # Connect some primaries across GSP boundaries
        cross_connections = [
            (primary_substations[7], primary_substations[18]),  # Bolton to Warrington
            (primary_substations[6], primary_substations[11]),  # Wigan to St Helens
            (primary_substations[17], primary_substations[12])  # Chester to Southport
        ]
        
        for from_primary, to_primary in cross_connections:
            if from_primary and to_primary:
                cross_edge = SuppliesEdge(
                    from_id=from_primary.id,
                    to_id=to_primary.id,
                    feeder_id=f"CROSS-{from_primary.id}-{to_primary.id}",
                    voltage_kv=min(from_primary.voltage_out_kv, to_primary.voltage_out_kv),
                    cable_type='underground',  # Cross-region typically underground
                    conductor_material='aluminum',
                    length_meters=random.uniform(8000, 20000),  # 8-20 km
                    capacity_amps=random.randint(300, 600),
                    circuit_number=2,
                    is_backup=True
                )
                ring_topology_edges.append(cross_edge)
                logger.debug(f"Cross-region connection: {from_primary.name} → {to_primary.name}")
    
    logger.info(f"Generated {len(primary_substations)} Primary Substations")
    logger.info(f"Created {len(feeds_edges)} FEEDS connections (GSP → Primary)")
    logger.info(f"Created {len(ring_topology_edges)} ring topology connections (Primary ↔ Primary)")
    
    return primary_substations, feeds_edges, ring_topology_edges


def generate_secondary_substations(
    primary_substations: List[PrimarySubstation],
    count: int = NUM_SECONDARY_SUBSTATIONS
) -> Tuple[List[SecondarySubstation], List[SuppliesEdge]]:
    """
    Generate Secondary Substations for North West England with redundant supply.
    
    Secondary substations (distribution transformers) step down voltage from primary
    distribution levels (11kV/33kV) to low voltage (230V/400V) for end consumers.
    Each secondary has 2 primary feeders (normal + backup) for redundancy.
    
    Args:
        primary_substations: List of Primary Substations to connect to
        count: Number of secondary substations to generate (default: 150)
        
    Returns:
        Tuple of (secondary_substations, supplies_edges)
        - secondary_substations: List of SecondarySubstation objects
        - supplies_edges: List of SuppliesEdge objects (Primary → Secondary)
    """
    logger.info(f"Generating {count} Secondary Substations for North West England...")
    
    # Real secondary substation locations based on streets/areas in North West England
    # These are distributed across the major cities
    secondary_locations = [
        # Manchester area (40 substations)
        {'name': 'Deansgate Substation', 'location': 'Manchester City Centre', 'city': 'Manchester',
         'latitude': 53.4808, 'longitude': -2.2426},
        {'name': 'Piccadilly Gardens Substation', 'location': 'Manchester City Centre', 'city': 'Manchester',
         'latitude': 53.4808, 'longitude': -2.2369},
        {'name': 'Oxford Road Substation', 'location': 'Manchester', 'city': 'Manchester',
         'latitude': 53.4668, 'longitude': -2.2338},
        {'name': 'Curry Mile Substation', 'location': 'Rusholme, Manchester', 'city': 'Manchester',
         'latitude': 53.4547, 'longitude': -2.2206},
        {'name': 'Fallowfield Substation', 'location': 'Fallowfield, Manchester', 'city': 'Manchester',
         'latitude': 53.4447, 'longitude': -2.2206},
        {'name': 'Didsbury Village Substation', 'location': 'Didsbury, Manchester', 'city': 'Manchester',
         'latitude': 53.4119, 'longitude': -2.2322},
        {'name': 'Chorlton Substation', 'location': 'Chorlton, Manchester', 'city': 'Manchester',
         'latitude': 53.4419, 'longitude': -2.2722},
        {'name': 'Withington Substation', 'location': 'Withington, Manchester', 'city': 'Manchester',
         'latitude': 53.4319, 'longitude': -2.2222},
        {'name': 'Levenshulme Substation', 'location': 'Levenshulme, Manchester', 'city': 'Manchester',
         'latitude': 53.4519, 'longitude': -2.1922},
        {'name': 'Gorton Substation', 'location': 'Gorton, Manchester', 'city': 'Manchester',
         'latitude': 53.4619, 'longitude': -2.1622},
        {'name': 'Moss Side Substation', 'location': 'Moss Side, Manchester', 'city': 'Manchester',
         'latitude': 53.4619, 'longitude': -2.2522},
        {'name': 'Hulme Substation', 'location': 'Hulme, Manchester', 'city': 'Manchester',
         'latitude': 53.4669, 'longitude': -2.2522},
        {'name': 'Ardwick Substation', 'location': 'Ardwick, Manchester', 'city': 'Manchester',
         'latitude': 53.4719, 'longitude': -2.2222},
        {'name': 'Longsight Substation', 'location': 'Longsight, Manchester', 'city': 'Manchester',
         'latitude': 53.4569, 'longitude': -2.2022},
        {'name': 'Whalley Range Substation', 'location': 'Whalley Range, Manchester', 'city': 'Manchester',
         'latitude': 53.4469, 'longitude': -2.2622},
        
        # Salford area (10 substations)
        {'name': 'Salford Quays Substation', 'location': 'Salford Quays', 'city': 'Salford',
         'latitude': 53.4719, 'longitude': -2.2965},
        {'name': 'MediaCityUK Substation', 'location': 'Salford Quays', 'city': 'Salford',
         'latitude': 53.4719, 'longitude': -2.3015},
        {'name': 'Ordsall Substation', 'location': 'Ordsall, Salford', 'city': 'Salford',
         'latitude': 53.4669, 'longitude': -2.2815},
        {'name': 'Pendleton Substation', 'location': 'Pendleton, Salford', 'city': 'Salford',
         'latitude': 53.4919, 'longitude': -2.2915},
        {'name': 'Eccles Substation', 'location': 'Eccles, Salford', 'city': 'Salford',
         'latitude': 53.4819, 'longitude': -2.3365},
        {'name': 'Swinton Substation', 'location': 'Swinton, Salford', 'city': 'Salford',
         'latitude': 53.5119, 'longitude': -2.3415},
        {'name': 'Walkden Substation', 'location': 'Walkden, Salford', 'city': 'Salford',
         'latitude': 53.5219, 'longitude': -2.3965},
        {'name': 'Worsley Substation', 'location': 'Worsley, Salford', 'city': 'Salford',
         'latitude': 53.5019, 'longitude': -2.3765},
        {'name': 'Irlam Substation', 'location': 'Irlam, Salford', 'city': 'Salford',
         'latitude': 53.4419, 'longitude': -2.4265},
        {'name': 'Cadishead Substation', 'location': 'Cadishead, Salford', 'city': 'Salford',
         'latitude': 53.4319, 'longitude': -2.4465},
        
        # Liverpool area (30 substations)
        {'name': 'Penny Lane Substation', 'location': 'Liverpool', 'city': 'Liverpool',
         'latitude': 53.3747, 'longitude': -2.9175},
        {'name': 'Bold Street Substation', 'location': 'Liverpool City Centre', 'city': 'Liverpool',
         'latitude': 53.4042, 'longitude': -2.9798},
        {'name': 'Lime Street Substation', 'location': 'Liverpool City Centre', 'city': 'Liverpool',
         'latitude': 53.4075, 'longitude': -2.9781},
        {'name': 'Albert Dock Substation', 'location': 'Liverpool Waterfront', 'city': 'Liverpool',
         'latitude': 53.3981, 'longitude': -2.9930},
        {'name': 'Anfield Road Substation', 'location': 'Anfield, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4308, 'longitude': -2.9608},
        {'name': 'Everton Substation', 'location': 'Everton, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4208, 'longitude': -2.9708},
        {'name': 'Kirkdale Substation', 'location': 'Kirkdale, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4408, 'longitude': -2.9808},
        {'name': 'Walton Substation', 'location': 'Walton, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4508, 'longitude': -2.9608},
        {'name': 'Fazakerley Substation', 'location': 'Fazakerley, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4708, 'longitude': -2.9408},
        {'name': 'Croxteth Substation', 'location': 'Croxteth, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4508, 'longitude': -2.9208},
        {'name': 'Kensington Substation', 'location': 'Kensington, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4108, 'longitude': -2.9508},
        {'name': 'Toxteth Substation', 'location': 'Toxteth, Liverpool', 'city': 'Liverpool',
         'latitude': 53.3808, 'longitude': -2.9608},
        {'name': 'Aigburth Substation', 'location': 'Aigburth, Liverpool', 'city': 'Liverpool',
         'latitude': 53.3608, 'longitude': -2.9308},
        {'name': 'Allerton Substation', 'location': 'Allerton, Liverpool', 'city': 'Liverpool',
         'latitude': 53.3708, 'longitude': -2.9008},
        {'name': 'Woolton Substation', 'location': 'Woolton, Liverpool', 'city': 'Liverpool',
         'latitude': 53.3808, 'longitude': -2.8708},
        
        # Stockport area (10 substations)
        {'name': 'Stockport Town Substation', 'location': 'Stockport', 'city': 'Stockport',
         'latitude': 53.4106, 'longitude': -2.1575},
        {'name': 'Cheadle Substation', 'location': 'Cheadle, Stockport', 'city': 'Stockport',
         'latitude': 53.3906, 'longitude': -2.2175},
        {'name': 'Bramhall Substation', 'location': 'Bramhall, Stockport', 'city': 'Stockport',
         'latitude': 53.3606, 'longitude': -2.1675},
        {'name': 'Hazel Grove Substation', 'location': 'Hazel Grove, Stockport', 'city': 'Stockport',
         'latitude': 53.3706, 'longitude': -2.1175},
        {'name': 'Marple Substation', 'location': 'Marple, Stockport', 'city': 'Stockport',
         'latitude': 53.4006, 'longitude': -2.0575},
        {'name': 'Reddish Substation', 'location': 'Reddish, Stockport', 'city': 'Stockport',
         'latitude': 53.4406, 'longitude': -2.1675},
        {'name': 'Heaton Moor Substation', 'location': 'Heaton Moor, Stockport', 'city': 'Stockport',
         'latitude': 53.4206, 'longitude': -2.1875},
        {'name': 'Gatley Substation', 'location': 'Gatley, Stockport', 'city': 'Stockport',
         'latitude': 53.3806, 'longitude': -2.2375},
        {'name': 'Bredbury Substation', 'location': 'Bredbury, Stockport', 'city': 'Stockport',
         'latitude': 53.4306, 'longitude': -2.1075},
        {'name': 'Romiley Substation', 'location': 'Romiley, Stockport', 'city': 'Stockport',
         'latitude': 53.4106, 'longitude': -2.0875},
        
        # Bolton area (10 substations)
        {'name': 'Bolton Town Centre Substation', 'location': 'Bolton', 'city': 'Bolton',
         'latitude': 53.5768, 'longitude': -2.4282},
        {'name': 'Farnworth Substation', 'location': 'Farnworth, Bolton', 'city': 'Bolton',
         'latitude': 53.5468, 'longitude': -2.3982},
        {'name': 'Horwich Substation', 'location': 'Horwich, Bolton', 'city': 'Bolton',
         'latitude': 53.5968, 'longitude': -2.5382},
        {'name': 'Westhoughton Substation', 'location': 'Westhoughton, Bolton', 'city': 'Bolton',
         'latitude': 53.5468, 'longitude': -2.5282},
        {'name': 'Little Lever Substation', 'location': 'Little Lever, Bolton', 'city': 'Bolton',
         'latitude': 53.5668, 'longitude': -2.3682},
        {'name': 'Breightmet Substation', 'location': 'Breightmet, Bolton', 'city': 'Bolton',
         'latitude': 53.5968, 'longitude': -2.3982},
        {'name': 'Astley Bridge Substation', 'location': 'Astley Bridge, Bolton', 'city': 'Bolton',
         'latitude': 53.6068, 'longitude': -2.4282},
        {'name': 'Tonge Moor Substation', 'location': 'Tonge Moor, Bolton', 'city': 'Bolton',
         'latitude': 53.5868, 'longitude': -2.4082},
        {'name': 'Halliwell Substation', 'location': 'Halliwell, Bolton', 'city': 'Bolton',
         'latitude': 53.5968, 'longitude': -2.4482},
        {'name': 'Heaton Substation', 'location': 'Heaton, Bolton', 'city': 'Bolton',
         'latitude': 53.5868, 'longitude': -2.4682},
        
        # Preston area (10 substations)
        {'name': 'Fishergate Substation', 'location': 'Preston City Centre', 'city': 'Preston',
         'latitude': 53.7632, 'longitude': -2.7044},
        {'name': 'Deepdale Substation', 'location': 'Deepdale, Preston', 'city': 'Preston',
         'latitude': 53.7732, 'longitude': -2.6944},
        {'name': 'Ashton Substation', 'location': 'Ashton, Preston', 'city': 'Preston',
         'latitude': 53.7732, 'longitude': -2.7244},
        {'name': 'Fulwood Substation', 'location': 'Fulwood, Preston', 'city': 'Preston',
         'latitude': 53.7932, 'longitude': -2.7144},
        {'name': 'Ribbleton Substation', 'location': 'Ribbleton, Preston', 'city': 'Preston',
         'latitude': 53.7832, 'longitude': -2.6744},
        {'name': 'Penwortham Substation', 'location': 'Penwortham, Preston', 'city': 'Preston',
         'latitude': 53.7432, 'longitude': -2.7244},
        {'name': 'Lostock Hall Substation', 'location': 'Lostock Hall, Preston', 'city': 'Preston',
         'latitude': 53.7232, 'longitude': -2.6844},
        {'name': 'Bamber Bridge Substation', 'location': 'Bamber Bridge, Preston', 'city': 'Preston',
         'latitude': 53.7232, 'longitude': -2.6544},
        {'name': 'Lea Substation', 'location': 'Lea, Preston', 'city': 'Preston',
         'latitude': 53.7632, 'longitude': -2.6644},
        {'name': 'Ingol Substation', 'location': 'Ingol, Preston', 'city': 'Preston',
         'latitude': 53.7932, 'longitude': -2.7444},
        
        # Warrington area (8 substations)
        {'name': 'Warrington Town Centre Substation', 'location': 'Warrington', 'city': 'Warrington',
         'latitude': 53.3900, 'longitude': -2.5970},
        {'name': 'Birchwood Substation', 'location': 'Birchwood, Warrington', 'city': 'Warrington',
         'latitude': 53.4200, 'longitude': -2.5270},
        {'name': 'Padgate Substation', 'location': 'Padgate, Warrington', 'city': 'Warrington',
         'latitude': 53.4000, 'longitude': -2.5570},
        {'name': 'Stockton Heath Substation', 'location': 'Stockton Heath, Warrington', 'city': 'Warrington',
         'latitude': 53.3700, 'longitude': -2.5670},
        {'name': 'Latchford Substation', 'location': 'Latchford, Warrington', 'city': 'Warrington',
         'latitude': 53.3800, 'longitude': -2.5870},
        {'name': 'Orford Substation', 'location': 'Orford, Warrington', 'city': 'Warrington',
         'latitude': 53.3900, 'longitude': -2.6170},
        {'name': 'Woolston Substation', 'location': 'Woolston, Warrington', 'city': 'Warrington',
         'latitude': 53.4100, 'longitude': -2.5770},
        {'name': 'Culcheth Substation', 'location': 'Culcheth, Warrington', 'city': 'Warrington',
         'latitude': 53.4500, 'longitude': -2.5170},
        
        # Chester area (8 substations)
        {'name': 'Chester City Centre Substation', 'location': 'Chester', 'city': 'Chester',
         'latitude': 53.1905, 'longitude': -2.8908},
        {'name': 'Blacon Substation', 'location': 'Blacon, Chester', 'city': 'Chester',
         'latitude': 53.2005, 'longitude': -2.9208},
        {'name': 'Hoole Substation', 'location': 'Hoole, Chester', 'city': 'Chester',
         'latitude': 53.1905, 'longitude': -2.8708},
        {'name': 'Boughton Substation', 'location': 'Boughton, Chester', 'city': 'Chester',
         'latitude': 53.1805, 'longitude': -2.8808},
        {'name': 'Handbridge Substation', 'location': 'Handbridge, Chester', 'city': 'Chester',
         'latitude': 53.1805, 'longitude': -2.8908},
        {'name': 'Upton Substation', 'location': 'Upton, Chester', 'city': 'Chester',
         'latitude': 53.2105, 'longitude': -2.8708},
        {'name': 'Saughall Substation', 'location': 'Saughall, Chester', 'city': 'Chester',
         'latitude': 53.2305, 'longitude': -2.9508},
        {'name': 'Ellesmere Port Substation', 'location': 'Ellesmere Port, Chester', 'city': 'Chester',
         'latitude': 53.2805, 'longitude': -2.8908},
        
        # Blackpool area (8 substations)
        {'name': 'Blackpool Tower Substation', 'location': 'Blackpool', 'city': 'Blackpool',
         'latitude': 53.8175, 'longitude': -3.0357},
        {'name': 'North Shore Substation', 'location': 'North Shore, Blackpool', 'city': 'Blackpool',
         'latitude': 53.8375, 'longitude': -3.0457},
        {'name': 'South Shore Substation', 'location': 'South Shore, Blackpool', 'city': 'Blackpool',
         'latitude': 53.7975, 'longitude': -3.0257},
        {'name': 'Marton Substation', 'location': 'Marton, Blackpool', 'city': 'Blackpool',
         'latitude': 53.8075, 'longitude': -3.0057},
        {'name': 'Bispham Substation', 'location': 'Bispham, Blackpool', 'city': 'Blackpool',
         'latitude': 53.8575, 'longitude': -3.0457},
        {'name': 'Layton Substation', 'location': 'Layton, Blackpool', 'city': 'Blackpool',
         'latitude': 53.8275, 'longitude': -3.0157},
        {'name': 'Cleveleys Substation', 'location': 'Cleveleys, Blackpool', 'city': 'Blackpool',
         'latitude': 53.8775, 'longitude': -3.0457},
        {'name': 'Fleetwood Substation', 'location': 'Fleetwood, Blackpool', 'city': 'Blackpool',
         'latitude': 53.9175, 'longitude': -3.0157},
        
        # Carlisle area (8 substations)
        {'name': 'Carlisle City Centre Substation', 'location': 'Carlisle', 'city': 'Carlisle',
         'latitude': 54.8951, 'longitude': -2.9382},
        {'name': 'Stanwix Substation', 'location': 'Stanwix, Carlisle', 'city': 'Carlisle',
         'latitude': 54.9051, 'longitude': -2.9482},
        {'name': 'Botcherby Substation', 'location': 'Botcherby, Carlisle', 'city': 'Carlisle',
         'latitude': 54.8851, 'longitude': -2.9182},
        {'name': 'Harraby Substation', 'location': 'Harraby, Carlisle', 'city': 'Carlisle',
         'latitude': 54.8751, 'longitude': -2.9282},
        {'name': 'Denton Holme Substation', 'location': 'Denton Holme, Carlisle', 'city': 'Carlisle',
         'latitude': 54.8951, 'longitude': -2.9582},
        {'name': 'Upperby Substation', 'location': 'Upperby, Carlisle', 'city': 'Carlisle',
         'latitude': 54.8751, 'longitude': -2.9482},
        {'name': 'Belah Substation', 'location': 'Belah, Carlisle', 'city': 'Carlisle',
         'latitude': 54.9151, 'longitude': -2.9282},
        {'name': 'Morton Substation', 'location': 'Morton, Carlisle', 'city': 'Carlisle',
         'latitude': 54.9251, 'longitude': -2.9482},
        
        # Additional Manchester suburbs (15 substations)
        {'name': 'Cheetham Hill Substation', 'location': 'Cheetham Hill, Manchester', 'city': 'Manchester',
         'latitude': 53.5019, 'longitude': -2.2326},
        {'name': 'Crumpsall Substation', 'location': 'Crumpsall, Manchester', 'city': 'Manchester',
         'latitude': 53.5119, 'longitude': -2.2426},
        {'name': 'Blackley Substation', 'location': 'Blackley, Manchester', 'city': 'Manchester',
         'latitude': 53.5319, 'longitude': -2.2326},
        {'name': 'Moston Substation', 'location': 'Moston, Manchester', 'city': 'Manchester',
         'latitude': 53.5219, 'longitude': -2.1926},
        {'name': 'Newton Heath Substation', 'location': 'Newton Heath, Manchester', 'city': 'Manchester',
         'latitude': 53.5019, 'longitude': -2.1726},
        {'name': 'Clayton Substation', 'location': 'Clayton, Manchester', 'city': 'Manchester',
         'latitude': 53.4819, 'longitude': -2.1726},
        {'name': 'Openshaw Substation', 'location': 'Openshaw, Manchester', 'city': 'Manchester',
         'latitude': 53.4719, 'longitude': -2.1626},
        {'name': 'Belle Vue Substation', 'location': 'Belle Vue, Manchester', 'city': 'Manchester',
         'latitude': 53.4619, 'longitude': -2.1826},
        {'name': 'Rusholme Substation', 'location': 'Rusholme, Manchester', 'city': 'Manchester',
         'latitude': 53.4519, 'longitude': -2.2226},
        {'name': 'Victoria Park Substation', 'location': 'Victoria Park, Manchester', 'city': 'Manchester',
         'latitude': 53.4519, 'longitude': -2.2126},
        {'name': 'Burnage Substation', 'location': 'Burnage, Manchester', 'city': 'Manchester',
         'latitude': 53.4319, 'longitude': -2.2026},
        {'name': 'Northenden Substation', 'location': 'Northenden, Manchester', 'city': 'Manchester',
         'latitude': 53.4119, 'longitude': -2.2622},
        {'name': 'Wythenshawe Substation', 'location': 'Wythenshawe, Manchester', 'city': 'Manchester',
         'latitude': 53.3919, 'longitude': -2.2622},
        {'name': 'Baguley Substation', 'location': 'Baguley, Manchester', 'city': 'Manchester',
         'latitude': 53.4019, 'longitude': -2.2822},
        {'name': 'Sale Substation', 'location': 'Sale, Manchester', 'city': 'Manchester',
         'latitude': 53.4219, 'longitude': -2.3222},
        
        # Additional Liverpool suburbs (15 substations)
        {'name': 'West Derby Substation', 'location': 'West Derby, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4408, 'longitude': -2.9108},
        {'name': 'Norris Green Substation', 'location': 'Norris Green, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4608, 'longitude': -2.9208},
        {'name': 'Tuebrook Substation', 'location': 'Tuebrook, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4308, 'longitude': -2.9308},
        {'name': 'Old Swan Substation', 'location': 'Old Swan, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4208, 'longitude': -2.9208},
        {'name': 'Wavertree Substation', 'location': 'Wavertree, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4008, 'longitude': -2.9208},
        {'name': 'Childwall Substation', 'location': 'Childwall, Liverpool', 'city': 'Liverpool',
         'latitude': 53.3908, 'longitude': -2.8908},
        {'name': 'Garston Substation', 'location': 'Garston, Liverpool', 'city': 'Liverpool',
         'latitude': 53.3508, 'longitude': -2.9108},
        {'name': 'Speke Substation', 'location': 'Speke, Liverpool', 'city': 'Liverpool',
         'latitude': 53.3408, 'longitude': -2.8608},
        {'name': 'Halewood Substation', 'location': 'Halewood, Liverpool', 'city': 'Liverpool',
         'latitude': 53.3608, 'longitude': -2.8408},
        {'name': 'Huyton Substation', 'location': 'Huyton, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4108, 'longitude': -2.8408},
        {'name': 'Prescot Substation', 'location': 'Prescot, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4308, 'longitude': -2.8008},
        {'name': 'Maghull Substation', 'location': 'Maghull, Liverpool', 'city': 'Liverpool',
         'latitude': 53.5208, 'longitude': -2.9408},
        {'name': 'Formby Substation', 'location': 'Formby, Liverpool', 'city': 'Liverpool',
         'latitude': 53.5608, 'longitude': -3.0708},
        {'name': 'Litherland Substation', 'location': 'Litherland, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4708, 'longitude': -2.9908},
        {'name': 'Seaforth Substation', 'location': 'Seaforth, Liverpool', 'city': 'Liverpool',
         'latitude': 53.4608, 'longitude': -3.0008},
        
        # Oldham area (5 substations)
        {'name': 'Oldham Town Centre Substation', 'location': 'Oldham', 'city': 'Oldham',
         'latitude': 53.5444, 'longitude': -2.1169},
        {'name': 'Chadderton Substation', 'location': 'Chadderton, Oldham', 'city': 'Oldham',
         'latitude': 53.5544, 'longitude': -2.1469},
        {'name': 'Royton Substation', 'location': 'Royton, Oldham', 'city': 'Oldham',
         'latitude': 53.5644, 'longitude': -2.1269},
        {'name': 'Shaw Substation', 'location': 'Shaw, Oldham', 'city': 'Oldham',
         'latitude': 53.5744, 'longitude': -2.0969},
        {'name': 'Failsworth Substation', 'location': 'Failsworth, Oldham', 'city': 'Oldham',
         'latitude': 53.5144, 'longitude': -2.1569},
        
        # Rochdale area (5 substations)
        {'name': 'Rochdale Town Centre Substation', 'location': 'Rochdale', 'city': 'Rochdale',
         'latitude': 53.6097, 'longitude': -2.1561},
        {'name': 'Heywood Substation', 'location': 'Heywood, Rochdale', 'city': 'Rochdale',
         'latitude': 53.5897, 'longitude': -2.2161},
        {'name': 'Middleton Substation', 'location': 'Middleton, Rochdale', 'city': 'Rochdale',
         'latitude': 53.5497, 'longitude': -2.1961},
        {'name': 'Littleborough Substation', 'location': 'Littleborough, Rochdale', 'city': 'Rochdale',
         'latitude': 53.6397, 'longitude': -2.0961},
        {'name': 'Milnrow Substation', 'location': 'Milnrow, Rochdale', 'city': 'Rochdale',
         'latitude': 53.6097, 'longitude': -2.1161},
        
        # Wigan area (5 substations)
        {'name': 'Wigan Town Centre Substation', 'location': 'Wigan', 'city': 'Wigan',
         'latitude': 53.5450, 'longitude': -2.6325},
        {'name': 'Leigh Substation', 'location': 'Leigh, Wigan', 'city': 'Wigan',
         'latitude': 53.4950, 'longitude': -2.5125},
        {'name': 'Ashton-in-Makerfield Substation', 'location': 'Ashton-in-Makerfield, Wigan', 'city': 'Wigan',
         'latitude': 53.4850, 'longitude': -2.6425},
        {'name': 'Hindley Substation', 'location': 'Hindley, Wigan', 'city': 'Wigan',
         'latitude': 53.5350, 'longitude': -2.5725},
        {'name': 'Standish Substation', 'location': 'Standish, Wigan', 'city': 'Wigan',
         'latitude': 53.5850, 'longitude': -2.6625},
        
        # Bury area (3 substations)
        {'name': 'Bury Town Centre Substation', 'location': 'Bury', 'city': 'Bury',
         'latitude': 53.5933, 'longitude': -2.2966},
        {'name': 'Radcliffe Substation', 'location': 'Radcliffe, Bury', 'city': 'Bury',
         'latitude': 53.5633, 'longitude': -2.3266},
        {'name': 'Prestwich Substation', 'location': 'Prestwich, Bury', 'city': 'Bury',
         'latitude': 53.5333, 'longitude': -2.2866}
    ]
    
    # Ensure we have enough locations
    if count > len(secondary_locations):
        logger.warning(f"Requested {count} secondary substations but only {len(secondary_locations)} locations defined. Generating {len(secondary_locations)} substations.")
        count = len(secondary_locations)
    
    secondary_substations = []
    supplies_edges = []
    
    # Calculate how many secondaries per primary (roughly equal distribution)
    secondaries_per_primary = count // len(primary_substations)
    remainder = count % len(primary_substations)
    
    logger.info(f"Distributing ~{secondaries_per_primary} secondary substations per primary substation")
    
    # Generate secondary substations and assign to primaries
    secondary_index = 0
    for primary_idx, primary in enumerate(primary_substations):
        # Determine how many secondaries this primary gets
        num_secondaries = secondaries_per_primary
        if primary_idx < remainder:
            num_secondaries += 1
        
        # Create secondaries for this primary
        for _ in range(num_secondaries):
            if secondary_index >= count:
                break
                
            location_data = secondary_locations[secondary_index]
            
            # Create secondary substation
            secondary = SecondarySubstation(
                id=f"SS{secondary_index + 1:03d}",
                name=location_data['name'],
                transformer_capacity_kva=random.uniform(100.0, 1000.0),  # 100-1000 kVA
                voltage_in_kv=primary.voltage_out_kv,
                voltage_out_v=random.choice([SECONDARY_VOLTAGE_SINGLE_PHASE_V, SECONDARY_VOLTAGE_THREE_PHASE_V]),
                num_phases=random.choice([1, 3]),
                location=location_data['location'],
                latitude=location_data['latitude'],
                longitude=location_data['longitude'],
                substation_type=random.choice(SECONDARY_SUBSTATION_TYPES),
                installation_year=random.randint(1980, 2024),
                operator=DNO_OPERATOR
            )
            secondary_substations.append(secondary)
            
            # Create normal supply connection (Primary → Secondary)
            normal_supply = SuppliesEdge(
                from_id=primary.id,
                to_id=secondary.id,
                feeder_id=f"SF-{primary.id}-{secondary.id}-N",
                voltage_kv=primary.voltage_out_kv,
                cable_type=random.choice(CABLE_TYPES),
                conductor_material=random.choice(CONDUCTOR_MATERIALS),
                length_meters=random.uniform(500, 5000),  # 0.5-5 km
                capacity_amps=random.randint(200, 600),
                circuit_number=1,
                is_backup=False
            )
            supplies_edges.append(normal_supply)
            
            # Find a different primary for backup supply (preferably nearby)
            # Use ring topology - connect to next primary in the list
            backup_primary_idx = (primary_idx + 1) % len(primary_substations)
            backup_primary = primary_substations[backup_primary_idx]
            
            # Create backup supply connection (Different Primary → Secondary)
            backup_supply = SuppliesEdge(
                from_id=backup_primary.id,
                to_id=secondary.id,
                feeder_id=f"SF-{backup_primary.id}-{secondary.id}-B",
                voltage_kv=backup_primary.voltage_out_kv,
                cable_type=random.choice(CABLE_TYPES),
                conductor_material=random.choice(CONDUCTOR_MATERIALS),
                length_meters=random.uniform(1000, 8000),  # 1-8 km (backup typically longer)
                capacity_amps=random.randint(200, 600),
                circuit_number=2,
                is_backup=True
            )
            supplies_edges.append(backup_supply)
            
            logger.debug(f"Created Secondary: {secondary.name} (Normal: {primary.name}, Backup: {backup_primary.name})")
            
            secondary_index += 1
    
    logger.info(f"Generated {len(secondary_substations)} Secondary Substations")
    logger.info(f"Created {len(supplies_edges)} SUPPLIES connections (Primary → Secondary)")
    logger.info(f"Each secondary has 2 primary feeders (normal + backup) for redundancy")
    
    return secondary_substations, supplies_edges


def generate_uprn() -> str:
    """
    Generate a unique 12-digit UPRN (Unique Property Reference Number).
    
    Returns:
        12-digit UPRN as string
    """
    while True:
        uprn = ''.join([str(random.randint(0, 9)) for _ in range(12)])
        if uprn not in generated_uprns:
            generated_uprns.add(uprn)
            return uprn


def generate_mpan() -> str:
    """
    Generate a unique 21-digit MPAN (Meter Point Administration Number).
    
    Format: Profile Class (2) + MTC (3) + LLFC (3) + Distributor ID (2) + Unique ID (11)
    
    Returns:
        21-digit MPAN as string
    """
    while True:
        profile_class = str(random.randint(1, 8)).zfill(2)  # 01-08
        mtc = str(random.randint(1, 999)).zfill(3)  # Meter Timeswitch Code
        llfc = str(random.randint(1, 999)).zfill(3)  # Line Loss Factor Class
        distributor_id = '14'  # Unicorn Energy Networks distributor ID
        unique_id = ''.join([str(random.randint(0, 9)) for _ in range(11)])
        
        mpan = profile_class + mtc + llfc + distributor_id + unique_id
        
        if mpan not in generated_mpans:
            generated_mpans.add(mpan)
            return mpan


def calculate_demand(property_type: str, property_subtype: str, num_bedrooms: int) -> float:
    """
    Calculate realistic peak demand in kW based on property type.
    
    Args:
        property_type: Type of property (residential, commercial, industrial)
        property_subtype: Subtype (house, flat, shop, office, factory, warehouse)
        num_bedrooms: Number of bedrooms (residential only)
        
    Returns:
        Peak demand in kW
    """
    if property_type == 'residential':
        if property_subtype == 'house':
            # Houses: 5-8 kW for 3-bed, scale with bedrooms
            base_demand = 6.0
            return round(base_demand + (num_bedrooms - 3) * 1.5 + random.uniform(-1.0, 1.0), 2)
        else:  # flat
            # Flats: 3-5 kW for 2-bed, scale with bedrooms
            base_demand = 4.0
            return round(base_demand + (num_bedrooms - 2) * 1.0 + random.uniform(-0.5, 0.5), 2)
    
    elif property_type == 'commercial':
        if property_subtype == 'shop':
            # Shops: 10-20 kW
            return round(random.uniform(10.0, 20.0), 2)
        else:  # office
            # Offices: 15-30 kW
            return round(random.uniform(15.0, 30.0), 2)
    
    else:  # industrial
        if property_subtype == 'factory':
            # Factories: 50-200 kW
            return round(random.uniform(50.0, 200.0), 2)
        else:  # warehouse
            # Warehouses: 30-100 kW
            return round(random.uniform(30.0, 100.0), 2)


def generate_nw_england_address(city: str) -> Dict[str, any]:
    """
    Generate a realistic address in North West England with real street names and postcodes.
    
    Args:
        city: City name (Manchester, Liverpool, Preston, Chester, Carlisle, Blackpool, Bolton, Warrington)
        
    Returns:
        Dictionary with address components and coordinates
    """
    city_data = NW_ENGLAND_CITIES.get(city)
    if not city_data:
        # Default to Manchester if city not found
        city = 'Manchester'
        city_data = NW_ENGLAND_CITIES['Manchester']
    
    # Real street names for each city
    street_names = {
        'Manchester': ['Deansgate', 'Oxford Road', 'Wilmslow Road', 'Curry Mile', 'Portland Street', 
                      'Market Street', 'King Street', 'Princess Street', 'Oldham Street', 'Piccadilly',
                      'Whitworth Street', 'Quay Street', 'Chapel Street', 'Cross Street', 'Mosley Street'],
        'Liverpool': ['Bold Street', 'Penny Lane', 'Lime Street', 'Church Street', 'Lord Street',
                     'Dale Street', 'Castle Street', 'Water Street', 'Mathew Street', 'Hope Street',
                     'Rodney Street', 'Duke Street', 'Hanover Street', 'Paradise Street', 'Renshaw Street'],
        'Preston': ['Fishergate', 'Friargate', 'Church Street', 'Lancaster Road', 'Deepdale Road',
                   'Ribbleton Lane', 'Blackpool Road', 'Garstang Road', 'Watling Street Road', 'Strand Road'],
        'Chester': ['Eastgate Street', 'Bridge Street', 'Watergate Street', 'Northgate Street', 'Foregate Street',
                   'Grosvenor Street', 'City Road', 'Liverpool Road', 'Hoole Road', 'Boughton'],
        'Carlisle': ['English Street', 'Scotch Street', 'Castle Street', 'Botchergate', 'Warwick Road',
                    'London Road', 'Stanwix', 'Denton Holme', 'Upperby Road', 'Wigton Road'],
        'Blackpool': ['Promenade', 'Church Street', 'Talbot Road', 'Lytham Road', 'Central Drive',
                     'Waterloo Road', 'Whitegate Drive', 'Devonshire Road', 'Dickson Road', 'Newton Drive'],
        'Bolton': ['Deansgate', 'Bradshawgate', 'Newport Street', 'Blackburn Road', 'Manchester Road',
                  'Chorley New Road', 'St Helens Road', 'Bury Road', 'Wigan Road', 'Halliwell Road'],
        'Warrington': ['Bridge Street', 'Sankey Street', 'Buttermarket Street', 'Horsemarket Street', 'Church Street',
                      'Winwick Street', 'Manchester Road', 'Liverpool Road', 'Knutsford Road', 'Chester Road']
    }
    
    # Get street names for this city (default to Manchester if not found)
    streets = street_names.get(city, street_names['Manchester'])
    street = random.choice(streets)
    
    # Generate house/building number
    number = str(random.randint(1, 250))
    
    # Generate postcode with correct prefix for the city
    postcode_prefix = city_data['postcode_prefix']
    postcode_district = random.randint(1, 9)
    postcode_sector = random.randint(1, 9)
    postcode_unit = ''.join([random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(2)])
    postcode = f"{postcode_prefix}{postcode_district} {postcode_sector}{postcode_unit}"
    
    # Generate realistic coordinates within the city bounds
    # Add small random offset to city center coordinates
    lat_offset = random.uniform(-0.05, 0.05)
    lon_offset = random.uniform(-0.05, 0.05)
    
    # Get base coordinates from city data or use approximate city centers
    city_coords = {
        'Manchester': (53.4808, -2.2426),
        'Liverpool': (53.4084, -2.9916),
        'Preston': (53.7632, -2.7044),
        'Chester': (53.1905, -2.8908),
        'Carlisle': (54.8951, -2.9382),
        'Blackpool': (53.8175, -3.0357),
        'Bolton': (53.5768, -2.4282),
        'Warrington': (53.3900, -2.5970)
    }
    
    base_lat, base_lon = city_coords.get(city, (53.4808, -2.2426))
    latitude = round(base_lat + lat_offset, 6)
    longitude = round(base_lon + lon_offset, 6)
    
    return {
        'number': number,
        'street': street,
        'city': city,
        'area': city_data['area'],
        'postcode': postcode,
        'latitude': latitude,
        'longitude': longitude
    }


def generate_properties(
    secondary_substations: List[SecondarySubstation],
    count: int = NUM_PROPERTIES
) -> Tuple[List[Property], List[ConnectsEdge]]:
    """
    Generate properties (electricity consumers) for North West England.
    
    Properties are distributed across secondary substations with realistic type distribution:
    - 75% residential (50% houses, 25% flats)
    - 20% commercial (10% shops, 10% offices)
    - 5% industrial (3% factories, 2% warehouses)
    
    Args:
        secondary_substations: List of Secondary Substations to connect to
        count: Number of properties to generate (default: 10,000)
        
    Returns:
        Tuple of (properties, connects_edges)
        - properties: List of Property objects
        - connects_edges: List of ConnectsEdge objects (Secondary → Property)
    """
    logger.info(f"Generating {count:,} properties for North West England...")
    
    # Calculate property type distribution
    num_residential = int(count * PROPERTY_TYPE_DISTRIBUTION['residential'])
    num_commercial = int(count * PROPERTY_TYPE_DISTRIBUTION['commercial'])
    num_industrial = count - num_residential - num_commercial  # Remainder
    
    logger.info(f"Property distribution: {num_residential:,} residential, {num_commercial:,} commercial, {num_industrial:,} industrial")
    
    # Calculate subtype distribution
    num_houses = int(num_residential * RESIDENTIAL_SUBTYPES['house'])
    num_flats = num_residential - num_houses
    
    num_shops = int(num_commercial * COMMERCIAL_SUBTYPES['shop'])
    num_offices = num_commercial - num_shops
    
    num_factories = int(num_industrial * INDUSTRIAL_SUBTYPES['factory'])
    num_warehouses = num_industrial - num_factories
    
    logger.info(f"Residential: {num_houses:,} houses, {num_flats:,} flats")
    logger.info(f"Commercial: {num_shops:,} shops, {num_offices:,} offices")
    logger.info(f"Industrial: {num_factories:,} factories, {num_warehouses:,} warehouses")
    
    # Create property type list
    property_types = (
        [('residential', 'house') for _ in range(num_houses)] +
        [('residential', 'flat') for _ in range(num_flats)] +
        [('commercial', 'shop') for _ in range(num_shops)] +
        [('commercial', 'office') for _ in range(num_offices)] +
        [('industrial', 'factory') for _ in range(num_factories)] +
        [('industrial', 'warehouse') for _ in range(num_warehouses)]
    )
    
    # Shuffle to randomize distribution
    random.shuffle(property_types)
    
    # Calculate properties per secondary substation
    properties_per_secondary = count // len(secondary_substations)
    remainder = count % len(secondary_substations)
    
    logger.info(f"Distributing ~{properties_per_secondary} properties per secondary substation")
    
    # City distribution weights (based on population)
    city_weights = {
        'Manchester': 0.25,
        'Liverpool': 0.25,
        'Preston': 0.10,
        'Bolton': 0.10,
        'Warrington': 0.08,
        'Chester': 0.08,
        'Blackpool': 0.08,
        'Carlisle': 0.06
    }
    
    cities = list(city_weights.keys())
    weights = list(city_weights.values())
    
    properties = []
    connects_edges = []
    
    property_index = 0
    
    # Generate properties and assign to secondary substations
    for secondary_idx, secondary in enumerate(secondary_substations):
        # Determine how many properties this secondary gets
        num_properties = properties_per_secondary
        if secondary_idx < remainder:
            num_properties += 1
        
        # Create properties for this secondary
        for _ in range(num_properties):
            if property_index >= count:
                break
            
            # Get property type and subtype
            property_type, property_subtype = property_types[property_index]
            
            # Select city based on weights
            city = random.choices(cities, weights=weights)[0]
            
            # Generate address
            address = generate_nw_england_address(city)
            
            # Generate UPRN and MPAN
            uprn = generate_uprn()
            mpan = generate_mpan()
            
            # Determine number of bedrooms (residential only)
            if property_type == 'residential':
                if property_subtype == 'house':
                    num_bedrooms = random.choices([2, 3, 4, 5], weights=[0.15, 0.50, 0.25, 0.10])[0]
                else:  # flat
                    num_bedrooms = random.choices([1, 2, 3], weights=[0.30, 0.60, 0.10])[0]
            else:
                num_bedrooms = 0
            
            # Calculate demand
            peak_demand_kw = calculate_demand(property_type, property_subtype, num_bedrooms)
            
            # Determine connection type
            # Industrial and large commercial typically three-phase
            if property_type == 'industrial':
                connection_type = 'three-phase'
            elif property_type == 'commercial' and peak_demand_kw > 20:
                connection_type = 'three-phase'
            elif property_type == 'residential' and num_bedrooms >= 4:
                connection_type = random.choice(['single-phase', 'three-phase'])
            else:
                connection_type = 'single-phase'
            
            # Smart meter flag (60% have smart meters)
            has_smart_meter = random.random() < 0.60
            
            # Priority Services Register (PSR) determination
            # Track separately for export to PSR register file
            # Residential properties more likely to be on PSR
            # Higher bedroom count slightly increases probability (elderly homeowners)
            if property_type == 'residential':
                if num_bedrooms >= 4:
                    on_psr = random.random() < 0.15  # 15% for larger homes
                elif num_bedrooms >= 2:
                    on_psr = random.random() < 0.12  # 12% for medium homes
                else:
                    on_psr = random.random() < 0.10  # 10% for smaller homes
            elif property_type == 'commercial':
                on_psr = random.random() < 0.05  # 5% for commercial (care homes, medical facilities)
            else:
                on_psr = False  # Industrial properties not on PSR
            
            # Create property
            property_obj = Property(
                uprn=uprn,
                mpan=mpan,
                address_number=address['number'],
                address_street=address['street'],
                address_city=address['city'],
                address_area=address['area'],
                postcode=address['postcode'],
                property_type=property_type,
                property_subtype=property_subtype,
                num_bedrooms=num_bedrooms,
                connection_type=connection_type,
                peak_demand_kw=peak_demand_kw,
                has_smart_meter=has_smart_meter,
                latitude=address['latitude'],
                longitude=address['longitude'],
                supplier=ELECTRICITY_SUPPLIER
            )
            # Store PSR status as a tuple with property for later export
            properties.append((property_obj, on_psr))
            
            # Create CONNECTS edge (Secondary → Property)
            connects_edge = ConnectsEdge(
                from_id=secondary.id,
                to_id=uprn,  # Use UPRN as property ID
                cable_type=random.choice(CABLE_TYPES),
                conductor_size_mm2=random.choice([16.0, 25.0, 35.0, 50.0, 70.0, 95.0]),
                length_meters=random.uniform(10, 500),  # 10m to 500m service cable
                capacity_amps=random.choice([60, 80, 100]) if connection_type == 'single-phase' else random.choice([100, 125, 160]),
                num_phases=1 if connection_type == 'single-phase' else 3,
                installation_year=random.randint(1980, 2024)
            )
            connects_edges.append(connects_edge)
            
            if (property_index + 1) % 1000 == 0:
                logger.info(f"Generated {property_index + 1:,} / {count:,} properties...")
            
            property_index += 1
    
    logger.info(f"Generated {len(properties):,} properties")
    logger.info(f"Created {len(connects_edges):,} CONNECTS connections (Secondary → Property)")
    logger.info(f"Unique UPRNs: {len(generated_uprns):,}")
    logger.info(f"Unique MPANs: {len(generated_mpans):,}")
    
    # Verify uniqueness
    if len(generated_uprns) != len(properties):
        logger.error(f"UPRN uniqueness check failed! Generated {len(properties)} properties but only {len(generated_uprns)} unique UPRNs")
    else:
        logger.info("✓ UPRN uniqueness verified")
    
    if len(generated_mpans) != len(properties):
        logger.error(f"MPAN uniqueness check failed! Generated {len(properties)} properties but only {len(generated_mpans)} unique MPANs")
    else:
        logger.info("✓ MPAN uniqueness verified")
    
    # Separate properties and PSR status for return
    # properties is now a list of (Property, on_psr) tuples
    return properties, connects_edges


def generate_protection_devices(
    primary_substations: List[PrimarySubstation],
    secondary_substations: List[SecondarySubstation]
) -> Tuple[List[ProtectionDevice], List[ProtectsEdge]]:
    """
    Generate protection devices (circuit breakers and fuses) for the network.
    
    Protection devices are placed at:
    - Primary substations: Circuit breakers (2 per substation)
    - Secondary substations: Fuses (1 per substation)
    
    Args:
        primary_substations: List of Primary Substations
        secondary_substations: List of Secondary Substations
        
    Returns:
        Tuple of (protection_devices, protects_edges)
        - protection_devices: List of ProtectionDevice objects
        - protects_edges: List of ProtectsEdge objects (Device → Substation)
    """
    logger.info("Generating protection devices for network...")
    
    protection_devices = []
    protects_edges = []
    device_id_counter = 1
    
    # Generate circuit breakers for primary substations
    logger.info(f"Generating circuit breakers for {len(primary_substations)} primary substations...")
    
    for primary in primary_substations:
        # Each primary substation gets 2 circuit breakers
        # One for incoming feeder, one for outgoing feeder
        for i in range(NUM_PROTECTION_DEVICES_PER_PRIMARY):
            device_type = 'circuit_breaker'
            
            # Circuit breaker ratings based on primary voltage
            if primary.voltage_in_kv >= 132:
                rating_amps = random.randint(1000, 2000)  # High voltage breakers
            elif primary.voltage_in_kv >= 33:
                rating_amps = random.randint(600, 1200)   # Medium voltage breakers
            else:
                rating_amps = random.randint(400, 800)    # Lower voltage breakers
            
            # Create circuit breaker
            device = ProtectionDevice(
                id=f"CB{device_id_counter:03d}",
                device_type=device_type,
                rating_amps=rating_amps,
                voltage_kv=float(primary.voltage_in_kv),
                location=primary.location,
                installation_year=random.randint(1990, 2024),
                operator=DNO_OPERATOR
            )
            protection_devices.append(device)
            
            # Create PROTECTS edge (Device → Primary Substation)
            protection_type = 'overcurrent' if i == 0 else 'earth_fault'
            protects_edge = ProtectsEdge(
                from_id=device.id,
                to_id=primary.id,
                protection_type=protection_type,
                trip_time_ms=random.randint(50, 200)  # 50-200ms trip time
            )
            protects_edges.append(protects_edge)
            
            logger.debug(f"Created {device_type} {device.id} for {primary.name} ({protection_type}, {rating_amps}A)")
            
            device_id_counter += 1
    
    logger.info(f"Generated {len(protection_devices)} circuit breakers for primary substations")
    
    # Generate fuses for secondary substations
    logger.info(f"Generating fuses for {len(secondary_substations)} secondary substations...")
    
    for secondary in secondary_substations:
        # Each secondary substation gets 1 fuse
        device_type = 'fuse'
        
        # Fuse ratings based on secondary transformer capacity
        if secondary.transformer_capacity_kva >= 500:
            rating_amps = random.randint(200, 400)
        elif secondary.transformer_capacity_kva >= 250:
            rating_amps = random.randint(100, 200)
        else:
            rating_amps = random.randint(50, 100)
        
        # Create fuse
        device = ProtectionDevice(
            id=f"FUSE{device_id_counter:03d}",
            device_type=device_type,
            rating_amps=rating_amps,
            voltage_kv=float(secondary.voltage_in_kv),
            location=secondary.location,
            installation_year=secondary.installation_year,
            operator=DNO_OPERATOR
        )
        protection_devices.append(device)
        
        # Create PROTECTS edge (Device → Secondary Substation)
        protects_edge = ProtectsEdge(
            from_id=device.id,
            to_id=secondary.id,
            protection_type='overcurrent',
            trip_time_ms=random.randint(10, 50)  # 10-50ms trip time for fuses
        )
        protects_edges.append(protects_edge)
        
        if device_id_counter % 50 == 0:
            logger.debug(f"Generated {device_id_counter} protection devices...")
        
        device_id_counter += 1
    
    logger.info(f"Generated {len(protection_devices) - (len(primary_substations) * NUM_PROTECTION_DEVICES_PER_PRIMARY)} fuses for secondary substations")
    logger.info(f"Total protection devices: {len(protection_devices)}")
    logger.info(f"Created {len(protects_edges)} PROTECTS connections (Device → Substation)")
    
    return protection_devices, protects_edges


# ============================================================================
# DATA EXPORT AND VALIDATION
# ============================================================================

def validate_data_structure(
    gsps: List[GridSupplyPoint],
    primary_substations: List[PrimarySubstation],
    secondary_substations: List[SecondarySubstation],
    properties: List[Property],
    protection_devices: List[ProtectionDevice],
    feeds_edges: List[FeedsEdge],
    ring_topology_edges: List[SuppliesEdge],
    secondary_supplies_edges: List[SuppliesEdge],
    connects_edges: List[ConnectsEdge],
    protects_edges: List[ProtectsEdge]
) -> bool:
    """
    Validate the generated data structure before saving.
    
    Checks:
    - All required components are present
    - UPRN and MPAN uniqueness
    - All properties are connected to secondary substations
    - All secondary substations are connected to primary substations
    - All primary substations are connected to GSPs
    - Edge references point to valid vertices
    
    Args:
        All generated data structures
        
    Returns:
        True if validation passes, False otherwise
    """
    logger.info("Validating data structure...")
    
    validation_passed = True
    
    # Check component counts
    if len(gsps) == 0:
        logger.error("Validation failed: No GSPs generated")
        validation_passed = False
    
    if len(primary_substations) == 0:
        logger.error("Validation failed: No primary substations generated")
        validation_passed = False
    
    if len(secondary_substations) == 0:
        logger.error("Validation failed: No secondary substations generated")
        validation_passed = False
    
    if len(properties) == 0:
        logger.error("Validation failed: No properties generated")
        validation_passed = False
    
    # Check UPRN uniqueness
    uprns = [p.uprn for p in properties]
    if len(uprns) != len(set(uprns)):
        logger.error(f"Validation failed: Duplicate UPRNs found ({len(uprns)} total, {len(set(uprns))} unique)")
        validation_passed = False
    else:
        logger.info(f"✓ UPRN uniqueness validated: {len(uprns):,} unique UPRNs")
    
    # Check MPAN uniqueness
    mpans = [p.mpan for p in properties]
    if len(mpans) != len(set(mpans)):
        logger.error(f"Validation failed: Duplicate MPANs found ({len(mpans)} total, {len(set(mpans))} unique)")
        validation_passed = False
    else:
        logger.info(f"✓ MPAN uniqueness validated: {len(mpans):,} unique MPANs")
    
    # Check all properties are connected
    connected_property_ids = set(edge.to_id for edge in connects_edges)
    property_ids = set(p.uprn for p in properties)
    
    if connected_property_ids != property_ids:
        missing = property_ids - connected_property_ids
        logger.error(f"Validation failed: {len(missing)} properties not connected to secondary substations")
        validation_passed = False
    else:
        logger.info(f"✓ All {len(properties):,} properties are connected to secondary substations")
    
    # Check all secondary substations are connected
    secondary_ids = set(s.id for s in secondary_substations)
    connected_secondary_ids = set(edge.to_id for edge in secondary_supplies_edges)
    
    if not connected_secondary_ids.issubset(secondary_ids):
        logger.error("Validation failed: Some SUPPLIES edges reference non-existent secondary substations")
        validation_passed = False
    else:
        logger.info(f"✓ All {len(secondary_substations)} secondary substations have valid connections")
    
    # Check all primary substations are connected to GSPs
    primary_ids = set(p.id for p in primary_substations)
    connected_primary_ids = set(edge.to_id for edge in feeds_edges)
    
    if not connected_primary_ids.issubset(primary_ids):
        logger.error("Validation failed: Some FEEDS edges reference non-existent primary substations")
        validation_passed = False
    else:
        logger.info(f"✓ All {len(primary_substations)} primary substations are connected to GSPs")
    
    # Check edge references are valid
    gsp_ids = set(g.id for g in gsps)
    
    # Validate FEEDS edges
    for edge in feeds_edges:
        if edge.from_id not in gsp_ids:
            logger.error(f"Validation failed: FEEDS edge references non-existent GSP: {edge.from_id}")
            validation_passed = False
        if edge.to_id not in primary_ids:
            logger.error(f"Validation failed: FEEDS edge references non-existent primary: {edge.to_id}")
            validation_passed = False
    
    # Validate SUPPLIES edges (both ring topology and secondary supplies)
    all_supplies_edges = ring_topology_edges + secondary_supplies_edges
    for edge in all_supplies_edges:
        if edge.from_id not in primary_ids:
            logger.error(f"Validation failed: SUPPLIES edge references non-existent primary: {edge.from_id}")
            validation_passed = False
        if edge.to_id not in primary_ids and edge.to_id not in secondary_ids:
            logger.error(f"Validation failed: SUPPLIES edge references non-existent substation: {edge.to_id}")
            validation_passed = False
    
    # Validate CONNECTS edges
    for edge in connects_edges:
        if edge.from_id not in secondary_ids:
            logger.error(f"Validation failed: CONNECTS edge references non-existent secondary: {edge.from_id}")
            validation_passed = False
        if edge.to_id not in property_ids:
            logger.error(f"Validation failed: CONNECTS edge references non-existent property: {edge.to_id}")
            validation_passed = False
    
    # Validate PROTECTS edges
    device_ids = set(d.id for d in protection_devices)
    all_substation_ids = primary_ids | secondary_ids
    
    for edge in protects_edges:
        if edge.from_id not in device_ids:
            logger.error(f"Validation failed: PROTECTS edge references non-existent device: {edge.from_id}")
            validation_passed = False
        if edge.to_id not in all_substation_ids:
            logger.error(f"Validation failed: PROTECTS edge references non-existent substation: {edge.to_id}")
            validation_passed = False
    
    if validation_passed:
        logger.info("✓ Data structure validation passed")
    else:
        logger.error("✗ Data structure validation failed")
    
    return validation_passed


def generate_graph_schema_documentation() -> str:
    """
    Generate graph schema documentation for AI agent context.
    
    This documentation provides LLMs with the structure of the graph database,
    enabling them to generate accurate queries and understand the data model.
    
    Returns:
        Markdown-formatted schema documentation
    """
    schema_doc = """# North West England Electricity Distribution Network - Graph Schema

## Overview

This graph database models a realistic UK electricity distribution network for the North West England region,
operated by **Unicorn Energy Networks** (Distribution Network Operator) with retail supply by **Unicorn Power**.

**Geographic Coverage**: Greater Manchester, Merseyside, Lancashire, Cheshire, and Cumbria
**Major Cities**: Manchester, Liverpool, Preston, Chester, Carlisle, Blackpool, Bolton, Warrington

## Vertex Types

### GridSupplyPoint
Connection point between transmission system (National Grid) and distribution network.

**Properties**:
- `id` (string): Unique identifier (e.g., "GSP001")
- `name` (string): GSP name (e.g., "Manchester North GSP")
- `voltage_kv` (int): Voltage level in kV (132 or 275)
- `capacity_mva` (float): Capacity in MVA
- `location` (string): Geographic location
- `latitude` (float): Latitude coordinate
- `longitude` (float): Longitude coordinate
- `operator` (string): "Unicorn Energy Networks"

### PrimarySubstation
Steps down voltage from transmission to primary distribution levels.

**Properties**:
- `id` (string): Unique identifier (e.g., "PS001")
- `name` (string): Substation name (e.g., "Salford Quays Primary")
- `voltage_in_kv` (int): Input voltage in kV (132 or 275)
- `voltage_out_kv` (int): Output voltage in kV (11 or 33)
- `capacity_mva` (float): Capacity in MVA
- `location` (string): Geographic location
- `latitude` (float): Latitude coordinate
- `longitude` (float): Longitude coordinate
- `num_transformers` (int): Number of transformers
- `has_circuit_breaker` (boolean): Circuit breaker present
- `has_switchgear` (boolean): Switchgear present
- `operator` (string): "Unicorn Energy Networks"

### SecondarySubstation
Distribution transformer stepping down to low voltage for consumers.

**Properties**:
- `id` (string): Unique identifier (e.g., "SS001")
- `name` (string): Substation name (e.g., "Deansgate Substation")
- `transformer_capacity_kva` (float): Capacity in kVA (100-1000)
- `voltage_in_kv` (int): Input voltage in kV (11 or 33)
- `voltage_out_v` (int): Output voltage in V (230 or 400)
- `num_phases` (int): Number of phases (1 or 3)
- `location` (string): Geographic location
- `latitude` (float): Latitude coordinate
- `longitude` (float): Longitude coordinate
- `substation_type` (string): Type (pole-mounted, ground-mounted, kiosk)
- `installation_year` (int): Year installed
- `operator` (string): "Unicorn Energy Networks"

### Property
Electricity consumer (residential, commercial, or industrial premises).

**Properties**:
- `uprn` (string): 12-digit Unique Property Reference Number
- `mpan` (string): 21-digit Meter Point Administration Number
- `address_number` (string): Building number
- `address_street` (string): Street name
- `address_city` (string): City (Manchester, Liverpool, Preston, etc.)
- `address_area` (string): Area (Greater Manchester, Merseyside, etc.)
- `postcode` (string): UK postcode (M, L, PR, CH, CA, FY, BL, WA formats)
- `property_type` (string): Type (residential, commercial, industrial)
- `property_subtype` (string): Subtype (house, flat, shop, office, factory, warehouse)
- `num_bedrooms` (int): Number of bedrooms (residential only, 0 for others)
- `connection_type` (string): Connection type (single-phase, three-phase)
- `peak_demand_kw` (float): Peak demand in kW
- `has_smart_meter` (boolean): Smart meter installed
- `latitude` (float): Latitude coordinate
- `longitude` (float): Longitude coordinate
- `supplier` (string): "Unicorn Power"

### ProtectionDevice
Protection equipment (circuit breakers, fuses, reclosers).

**Properties**:
- `id` (string): Unique identifier (e.g., "CB001", "FUSE001")
- `device_type` (string): Type (circuit_breaker, fuse, recloser)
- `rating_amps` (int): Current rating in amperes
- `voltage_kv` (float): Voltage level in kV
- `location` (string): Geographic location
- `installation_year` (int): Year installed
- `operator` (string): "Unicorn Energy Networks"

## Edge Types

### FEEDS
Connection from Grid Supply Point to Primary Substation.

**Properties**:
- `feeder_id` (string): Unique feeder identifier
- `voltage_kv` (int): Voltage level in kV
- `cable_type` (string): Cable type (overhead, underground)
- `conductor_material` (string): Material (copper, aluminum)
- `length_meters` (float): Cable length in meters
- `capacity_amps` (int): Current capacity in amperes

**Direction**: GridSupplyPoint → PrimarySubstation

### SUPPLIES
Connection between substations (Primary to Primary for ring topology, or Primary to Secondary).

**Properties**:
- `feeder_id` (string): Unique feeder identifier
- `voltage_kv` (int): Voltage level in kV
- `cable_type` (string): Cable type (overhead, underground)
- `conductor_material` (string): Material (copper, aluminum)
- `length_meters` (float): Cable length in meters
- `capacity_amps` (int): Current capacity in amperes
- `circuit_number` (int): Circuit number
- `is_backup` (boolean): Backup/redundant connection flag

**Direction**: PrimarySubstation → PrimarySubstation (ring topology)
**Direction**: PrimarySubstation → SecondarySubstation

### CONNECTS
Low voltage connection from Secondary Substation to Property.

**Properties**:
- `cable_type` (string): Cable type (overhead, underground)
- `conductor_size_mm2` (float): Conductor size in mm²
- `length_meters` (float): Cable length in meters
- `capacity_amps` (int): Current capacity in amperes
- `num_phases` (int): Number of phases (1 or 3)
- `installation_year` (int): Year installed

**Direction**: SecondarySubstation → Property

### PROTECTS
Protection relationship from device to protected equipment.

**Properties**:
- `protection_type` (string): Type (overcurrent, earth_fault, etc.)
- `trip_time_ms` (int): Trip time in milliseconds

**Direction**: ProtectionDevice → Substation (Primary or Secondary)

## Network Topology

The network follows a hierarchical structure with redundancy:

1. **Transmission Level**: Grid Supply Points (3 GSPs)
2. **Primary Distribution**: Primary Substations (20) connected in ring topology
3. **Secondary Distribution**: Secondary Substations (~150) with dual feeders (normal + backup)
4. **Low Voltage**: Properties (10,000) connected to secondary substations

**Redundancy Features**:
- Ring topology at primary level provides alternative supply paths
- Each secondary substation has 2 primary feeders (normal + backup)
- Protection devices at all voltage levels

## Company Information

- **Unicorn Energy Networks**: Distribution Network Operator (DNO)
  - Owns and operates the physical distribution network
  - Responsible for network assets (substations, cables, transformers)
  
- **Unicorn Power**: Electricity Retailer/Supplier
  - Provides retail electricity supply to customers
  - Manages customer billing and relationships

## Query Examples

### Find all properties in Manchester
```
MATCH (p:Property)
WHERE p.address_city = 'Manchester'
RETURN p
```

### Find path from GSP to a specific property
```
MATCH path = (gsp:GridSupplyPoint)-[*]->(property:Property {uprn: '100012345678'})
RETURN path
LIMIT 1
```

### Calculate total load on a secondary substation
```
MATCH (ss:SecondarySubstation {id: 'SS001'})<-[:CONNECTS]-(property:Property)
RETURN ss.id AS substation, SUM(property.peak_demand_kw) AS total_load_kw
```

### Find properties with smart meters in a postcode area
```
MATCH (property:Property)
WHERE property.postcode STARTS WITH 'M1' AND property.has_smart_meter = true
RETURN property
```

### Find all properties supplied by Unicorn Power
```
MATCH (property:Property)
WHERE property.supplier = 'Unicorn Power'
RETURN property
```

## Data Statistics

- **Grid Supply Points**: 3
- **Primary Substations**: 20
- **Secondary Substations**: ~150
- **Properties**: 10,000
  - Residential: 75% (houses: 50%, flats: 25%)
  - Commercial: 20% (shops: 10%, offices: 10%)
  - Industrial: 5% (factories: 3%, warehouses: 2%)
- **Protection Devices**: ~190

## Voltage Levels (UK Standards)

- **Transmission**: 132kV, 275kV
- **Primary Distribution**: 11kV, 33kV
- **Secondary Distribution**: 230V (single-phase), 400V (three-phase)
"""
    
    return schema_doc


def save_to_json(
    gsps: List[GridSupplyPoint],
    primary_substations: List[PrimarySubstation],
    secondary_substations: List[SecondarySubstation],
    properties: List[Property],
    protection_devices: List[ProtectionDevice],
    feeds_edges: List[FeedsEdge],
    ring_topology_edges: List[SuppliesEdge],
    secondary_supplies_edges: List[SuppliesEdge],
    connects_edges: List[ConnectsEdge],
    protects_edges: List[ProtectsEdge],
    filename: str = "network_data.json"
) -> bool:
    """
    Save all generated data to JSON file with metadata.
    
    Args:
        All generated data structures
        filename: Output filename (default: "network_data.json")
        
    Returns:
        True if save successful, False otherwise
    """
    logger.info(f"Saving data to {filename}...")
    
    try:
        # Convert dataclass objects to dictionaries
        data = {
            "metadata": {
                "generated_at": datetime.now().astimezone().isoformat(),
                "generator_version": "1.0.0",
                "region": "North West England",
                "dno_operator": DNO_OPERATOR,
                "electricity_supplier": ELECTRICITY_SUPPLIER,
                "counts": {
                    "grid_supply_points": len(gsps),
                    "primary_substations": len(primary_substations),
                    "secondary_substations": len(secondary_substations),
                    "properties": len(properties),
                    "protection_devices": len(protection_devices),
                    "feeds_edges": len(feeds_edges),
                    "ring_topology_edges": len(ring_topology_edges),
                    "secondary_supplies_edges": len(secondary_supplies_edges),
                    "connects_edges": len(connects_edges),
                    "protects_edges": len(protects_edges),
                    "total_vertices": len(gsps) + len(primary_substations) + len(secondary_substations) + len(properties) + len(protection_devices),
                    "total_edges": len(feeds_edges) + len(ring_topology_edges) + len(secondary_supplies_edges) + len(connects_edges) + len(protects_edges)
                },
                "property_distribution": {
                    "residential": sum(1 for p in properties if p.property_type == 'residential'),
                    "commercial": sum(1 for p in properties if p.property_type == 'commercial'),
                    "industrial": sum(1 for p in properties if p.property_type == 'industrial'),
                    "houses": sum(1 for p in properties if p.property_subtype == 'house'),
                    "flats": sum(1 for p in properties if p.property_subtype == 'flat'),
                    "shops": sum(1 for p in properties if p.property_subtype == 'shop'),
                    "offices": sum(1 for p in properties if p.property_subtype == 'office'),
                    "factories": sum(1 for p in properties if p.property_subtype == 'factory'),
                    "warehouses": sum(1 for p in properties if p.property_subtype == 'warehouse')
                },
                "smart_meters": sum(1 for p in properties if p.has_smart_meter),
                "total_peak_demand_kw": round(sum(p.peak_demand_kw for p in properties), 2)
            },
            "vertices": {
                "grid_supply_points": [asdict(gsp) for gsp in gsps],
                "primary_substations": [asdict(ps) for ps in primary_substations],
                "secondary_substations": [asdict(ss) for ss in secondary_substations],
                "properties": [asdict(p) for p in properties],
                "protection_devices": [asdict(pd) for pd in protection_devices]
            },
            "edges": {
                "feeds": [asdict(edge) for edge in feeds_edges],
                "ring_topology": [asdict(edge) for edge in ring_topology_edges],
                "secondary_supplies": [asdict(edge) for edge in secondary_supplies_edges],
                "connects": [asdict(edge) for edge in connects_edges],
                "protects": [asdict(edge) for edge in protects_edges]
            }
        }
        
        # Write to JSON file with pretty formatting
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Get file size
        import os
        file_size_mb = os.path.getsize(filename) / (1024 * 1024)
        
        logger.info(f"✓ Data saved to {filename} ({file_size_mb:.2f} MB)")
        logger.info(f"  - Total vertices: {data['metadata']['counts']['total_vertices']:,}")
        logger.info(f"  - Total edges: {data['metadata']['counts']['total_edges']:,}")
        logger.info(f"  - Properties: {data['metadata']['counts']['properties']:,}")
        logger.info(f"  - Total peak demand: {data['metadata']['total_peak_demand_kw']:,.2f} kW")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to save data to {filename}: {e}")
        return False


def save_graph_schema(filename: str = "graph_schema.md") -> bool:
    """
    Save graph schema documentation to markdown file.
    
    Args:
        filename: Output filename (default: "graph_schema.md")
        
    Returns:
        True if save successful, False otherwise
    """
    logger.info(f"Generating graph schema documentation...")
    
    try:
        schema_doc = generate_graph_schema_documentation()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(schema_doc)
        
        logger.info(f"✓ Graph schema documentation saved to {filename}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save graph schema to {filename}: {e}")
        return False


# ============================================================================
# PSR REGISTER EXPORT
# ============================================================================

def export_psr_register(properties_with_psr: List[Tuple[Property, bool]], output_dir: str = "psr_register") -> bool:
    """
    Export Priority Services Register to JSON file.
    
    Creates a standalone JSON file mapping postcodes to PSR status.
    This data is kept separate from the graph database for privacy/security.
    
    Args:
        properties_with_psr: List of (Property, on_psr) tuples
        output_dir: Directory to save PSR register file
        
    Returns:
        True if export successful, False otherwise
    """
    from pathlib import Path
    
    try:
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Build PSR register - one entry per postcode
        psr_register = []
        psr_count = 0
        
        for property_obj, on_psr in properties_with_psr:
            psr_register.append({
                "postcode": property_obj.postcode,
                "on_psr": on_psr
            })
            if on_psr:
                psr_count += 1
        
        # Save to JSON
        output_file = output_path / "psr_register.json"
        with open(output_file, 'w') as f:
            json.dump(psr_register, f, indent=2)
        
        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        logger.info(f"✓ PSR register saved to {output_file} ({file_size_mb:.2f} MB)")
        logger.info(f"  - Total properties: {len(psr_register):,}")
        logger.info(f"  - Properties on PSR: {psr_count:,} ({psr_count/len(psr_register)*100:.1f}%)")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to export PSR register: {e}")
        return False


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function"""
    logger.info("=" * 80)
    logger.info("North West England Electricity Distribution Network Data Generator")
    logger.info("=" * 80)
    logger.info(f"Distribution Network Operator: {DNO_OPERATOR}")
    logger.info(f"Electricity Supplier: {ELECTRICITY_SUPPLIER}")
    logger.info(f"Target Properties: {NUM_PROPERTIES:,}")
    logger.info("=" * 80)
    
    # Generate Grid Supply Points
    gsps = generate_gsps()
    
    # Generate Primary Substations with ring topology
    primary_substations, feeds_edges, ring_topology_edges = generate_primary_substations(gsps)
    
    # Generate Secondary Substations with redundant supply
    secondary_substations, secondary_supplies_edges = generate_secondary_substations(primary_substations)
    
    # Generate Properties
    properties_with_psr, connects_edges = generate_properties(secondary_substations)
    
    # Separate properties from PSR status for graph export
    properties = [prop for prop, _ in properties_with_psr]
    
    # Generate Protection Devices
    protection_devices, protects_edges = generate_protection_devices(primary_substations, secondary_substations)
    
    logger.info("=" * 80)
    logger.info("Data generation complete")
    logger.info(f"Generated {len(gsps)} Grid Supply Points")
    logger.info(f"Generated {len(primary_substations)} Primary Substations")
    logger.info(f"Generated {len(secondary_substations)} Secondary Substations")
    logger.info(f"Generated {len(properties):,} Properties")
    logger.info(f"Generated {len(protection_devices)} Protection Devices")
    logger.info(f"Created {len(feeds_edges)} FEEDS connections (GSP → Primary)")
    logger.info(f"Created {len(ring_topology_edges)} ring topology connections (Primary ↔ Primary)")
    logger.info(f"Created {len(secondary_supplies_edges)} SUPPLIES connections (Primary → Secondary)")
    logger.info(f"Created {len(connects_edges):,} CONNECTS connections (Secondary → Property)")
    logger.info(f"Created {len(protects_edges)} PROTECTS connections (Device → Substation)")
    logger.info("=" * 80)
    
    # Validate data structure
    logger.info("")
    validation_passed = validate_data_structure(
        gsps, primary_substations, secondary_substations, properties, protection_devices,
        feeds_edges, ring_topology_edges, secondary_supplies_edges, connects_edges, protects_edges
    )
    
    if not validation_passed:
        logger.error("Data validation failed. Aborting export.")
        return 1
    
    # Save data to JSON
    logger.info("")
    json_saved = save_to_json(
        gsps, primary_substations, secondary_substations, properties, protection_devices,
        feeds_edges, ring_topology_edges, secondary_supplies_edges, connects_edges, protects_edges
    )
    
    if not json_saved:
        logger.error("Failed to save data to JSON")
        return 1
    
    # Save graph schema documentation
    schema_saved = save_graph_schema()
    
    if not schema_saved:
        logger.warning("Failed to save graph schema documentation (non-critical)")
    
    # Export PSR register to separate file
    logger.info("")
    psr_saved = export_psr_register(properties_with_psr)
    
    if not psr_saved:
        logger.warning("Failed to save PSR register (non-critical)")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("✓ Data export complete")
    logger.info("  - network_data.json: Network data with metadata")
    logger.info("  - graph_schema.md: Graph schema documentation for AI agents")
    logger.info("  - psr_register/psr_register.json: Priority Services Register (separate from graph)")
    logger.info("=" * 80)
    
    return 0


if __name__ == "__main__":
    main()
