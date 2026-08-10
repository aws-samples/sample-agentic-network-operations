# North West England Electricity Distribution Network - Graph Schema

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
