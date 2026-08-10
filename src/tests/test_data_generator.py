#!/usr/bin/env python3
"""
Test script for North West England Electricity Distribution Network Data Generator

Validates:
- Property type distribution
- UPRN/MPAN uniqueness
- Network topology (all properties connected)
- Demand values are realistic
- North West England postcodes are valid
- Company branding (Unicorn Energy Networks for network assets, Unicorn Power for property supplier)
"""

import json
import sys
import re
from typing import Dict, List, Tuple
from collections import Counter


# ============================================================================
# TEST CONFIGURATION
# ============================================================================

# Expected values
EXPECTED_PROPERTIES = 10000
EXPECTED_PROPERTY_TYPE_DISTRIBUTION = {
    'residential': 0.75,  # 75%
    'commercial': 0.20,   # 20%
    'industrial': 0.05    # 5%
}

# Valid North West England postcode prefixes
VALID_NW_ENGLAND_POSTCODES = ['M', 'L', 'PR', 'CH', 'CA', 'FY', 'BL', 'WA']

# Company names
DNO_OPERATOR = "Unicorn Energy Networks"
ELECTRICITY_SUPPLIER = "Unicorn Power"

# Demand ranges by property type (kW)
DEMAND_RANGES = {
    'residential': {'house': (3.0, 12.0), 'flat': (2.0, 7.0)},
    'commercial': {'shop': (8.0, 25.0), 'office': (12.0, 35.0)},
    'industrial': {'factory': (40.0, 220.0), 'warehouse': (25.0, 110.0)}
}

# Tolerance for distribution checks (±5%)
DISTRIBUTION_TOLERANCE = 0.05


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def load_network_data(filename: str = "network_data.json") -> Dict:
    """Load network data from JSON file"""
    print(f"Loading data from {filename}...")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✓ Data loaded successfully")
        return data
    except Exception as e:
        print(f"✗ Failed to load data: {e}")
        sys.exit(1)


def test_property_count(data: Dict) -> bool:
    """Test that exactly 10,000 properties were generated"""
    print("\n" + "=" * 80)
    print("TEST 1: Property Count")
    print("=" * 80)
    
    properties = data['vertices']['properties']
    count = len(properties)
    
    print(f"Expected: {EXPECTED_PROPERTIES:,} properties")
    print(f"Actual:   {count:,} properties")
    
    if count == EXPECTED_PROPERTIES:
        print("✓ PASS: Correct number of properties generated")
        return True
    else:
        print(f"✗ FAIL: Expected {EXPECTED_PROPERTIES:,} properties, got {count:,}")
        return False


def test_property_type_distribution(data: Dict) -> bool:
    """Test property type distribution matches requirements"""
    print("\n" + "=" * 80)
    print("TEST 2: Property Type Distribution")
    print("=" * 80)
    
    properties = data['vertices']['properties']
    total = len(properties)
    
    # Count property types
    type_counts = Counter(p['property_type'] for p in properties)
    
    # Count property subtypes
    subtype_counts = Counter(p['property_subtype'] for p in properties)
    
    print(f"\nProperty Type Distribution:")
    print(f"  Total properties: {total:,}")
    
    all_passed = True
    
    for prop_type, expected_ratio in EXPECTED_PROPERTY_TYPE_DISTRIBUTION.items():
        actual_count = type_counts[prop_type]
        actual_ratio = actual_count / total
        expected_count = int(total * expected_ratio)
        
        # Calculate tolerance range
        min_count = int(total * (expected_ratio - DISTRIBUTION_TOLERANCE))
        max_count = int(total * (expected_ratio + DISTRIBUTION_TOLERANCE))
        
        within_tolerance = min_count <= actual_count <= max_count
        status = "✓" if within_tolerance else "✗"
        
        print(f"  {status} {prop_type.capitalize()}: {actual_count:,} ({actual_ratio:.1%}) - Expected: {expected_ratio:.0%} ± {DISTRIBUTION_TOLERANCE:.0%}")
        
        if not within_tolerance:
            all_passed = False
    
    print(f"\nProperty Subtype Distribution:")
    for subtype, count in subtype_counts.most_common():
        ratio = count / total
        print(f"  - {subtype.capitalize()}: {count:,} ({ratio:.1%})")
    
    # Verify specific subtype distributions
    residential_count = type_counts['residential']
    houses = subtype_counts['house']
    flats = subtype_counts['flat']
    
    print(f"\nResidential Breakdown:")
    print(f"  - Houses: {houses:,} ({houses/residential_count:.1%} of residential)")
    print(f"  - Flats:  {flats:,} ({flats/residential_count:.1%} of residential)")
    
    commercial_count = type_counts['commercial']
    shops = subtype_counts['shop']
    offices = subtype_counts['office']
    
    print(f"\nCommercial Breakdown:")
    print(f"  - Shops:   {shops:,} ({shops/commercial_count:.1%} of commercial)")
    print(f"  - Offices: {offices:,} ({offices/commercial_count:.1%} of commercial)")
    
    industrial_count = type_counts['industrial']
    factories = subtype_counts['factory']
    warehouses = subtype_counts['warehouse']
    
    print(f"\nIndustrial Breakdown:")
    print(f"  - Factories:  {factories:,} ({factories/industrial_count:.1%} of industrial)")
    print(f"  - Warehouses: {warehouses:,} ({warehouses/industrial_count:.1%} of industrial)")
    
    if all_passed:
        print("\n✓ PASS: Property type distribution is within tolerance")
    else:
        print("\n✗ FAIL: Property type distribution is outside tolerance")
    
    return all_passed


def test_uprn_mpan_uniqueness(data: Dict) -> bool:
    """Test UPRN and MPAN uniqueness"""
    print("\n" + "=" * 80)
    print("TEST 3: UPRN and MPAN Uniqueness")
    print("=" * 80)
    
    properties = data['vertices']['properties']
    
    # Check UPRNs
    uprns = [p['uprn'] for p in properties]
    unique_uprns = set(uprns)
    
    print(f"\nUPRN Check:")
    print(f"  Total UPRNs:  {len(uprns):,}")
    print(f"  Unique UPRNs: {len(unique_uprns):,}")
    
    uprn_passed = len(uprns) == len(unique_uprns)
    if uprn_passed:
        print(f"  ✓ All UPRNs are unique")
    else:
        duplicates = len(uprns) - len(unique_uprns)
        print(f"  ✗ Found {duplicates} duplicate UPRNs")
    
    # Verify UPRN format (12 digits)
    invalid_uprns = [u for u in uprns if not (len(u) == 12 and u.isdigit())]
    if invalid_uprns:
        print(f"  ✗ Found {len(invalid_uprns)} invalid UPRN formats")
        uprn_passed = False
    else:
        print(f"  ✓ All UPRNs have valid format (12 digits)")
    
    # Check MPANs
    mpans = [p['mpan'] for p in properties]
    unique_mpans = set(mpans)
    
    print(f"\nMPAN Check:")
    print(f"  Total MPANs:  {len(mpans):,}")
    print(f"  Unique MPANs: {len(unique_mpans):,}")
    
    mpan_passed = len(mpans) == len(unique_mpans)
    if mpan_passed:
        print(f"  ✓ All MPANs are unique")
    else:
        duplicates = len(mpans) - len(unique_mpans)
        print(f"  ✗ Found {duplicates} duplicate MPANs")
    
    # Verify MPAN format (21 digits)
    invalid_mpans = [m for m in mpans if not (len(m) == 21 and m.isdigit())]
    if invalid_mpans:
        print(f"  ✗ Found {len(invalid_mpans)} invalid MPAN formats")
        mpan_passed = False
    else:
        print(f"  ✓ All MPANs have valid format (21 digits)")
    
    passed = uprn_passed and mpan_passed
    
    if passed:
        print("\n✓ PASS: All UPRNs and MPANs are unique and valid")
    else:
        print("\n✗ FAIL: UPRN or MPAN uniqueness/validity check failed")
    
    return passed


def test_network_topology(data: Dict) -> bool:
    """Test that all properties are connected to the network"""
    print("\n" + "=" * 80)
    print("TEST 4: Network Topology (All Properties Connected)")
    print("=" * 80)
    
    properties = data['vertices']['properties']
    secondary_substations = data['vertices']['secondary_substations']
    primary_substations = data['vertices']['primary_substations']
    gsps = data['vertices']['grid_supply_points']
    
    connects_edges = data['edges']['connects']
    secondary_supplies_edges = data['edges']['secondary_supplies']
    feeds_edges = data['edges']['feeds']
    
    print(f"\nNetwork Components:")
    print(f"  Grid Supply Points:      {len(gsps)}")
    print(f"  Primary Substations:     {len(primary_substations)}")
    print(f"  Secondary Substations:   {len(secondary_substations)}")
    print(f"  Properties:              {len(properties):,}")
    
    print(f"\nConnections:")
    print(f"  FEEDS (GSP → Primary):        {len(feeds_edges)}")
    print(f"  SUPPLIES (Primary → Secondary): {len(secondary_supplies_edges)}")
    print(f"  CONNECTS (Secondary → Property): {len(connects_edges):,}")
    
    # Check all properties are connected
    property_uprns = set(p['uprn'] for p in properties)
    connected_uprns = set(edge['to_id'] for edge in connects_edges)
    
    print(f"\nProperty Connectivity:")
    print(f"  Total properties:     {len(property_uprns):,}")
    print(f"  Connected properties: {len(connected_uprns):,}")
    
    properties_passed = property_uprns == connected_uprns
    
    if properties_passed:
        print(f"  ✓ All properties are connected to secondary substations")
    else:
        unconnected = property_uprns - connected_uprns
        print(f"  ✗ {len(unconnected)} properties are not connected")
    
    # Check all secondary substations are connected
    secondary_ids = set(s['id'] for s in secondary_substations)
    connected_secondary_ids = set(edge['to_id'] for edge in secondary_supplies_edges)
    
    print(f"\nSecondary Substation Connectivity:")
    print(f"  Total secondary substations:     {len(secondary_ids)}")
    print(f"  Connected secondary substations: {len(connected_secondary_ids)}")
    
    secondaries_passed = connected_secondary_ids.issubset(secondary_ids)
    
    if secondaries_passed:
        print(f"  ✓ All secondary substations have valid connections")
    else:
        print(f"  ✗ Some secondary substations have invalid connections")
    
    # Check redundancy (each secondary should have 2 feeders)
    secondary_feeder_counts = Counter(edge['to_id'] for edge in secondary_supplies_edges)
    secondaries_with_dual_feeders = sum(1 for count in secondary_feeder_counts.values() if count >= 2)
    
    print(f"\nRedundancy Check:")
    print(f"  Secondaries with 2+ feeders: {secondaries_with_dual_feeders} / {len(secondary_ids)}")
    
    redundancy_ratio = secondaries_with_dual_feeders / len(secondary_ids)
    if redundancy_ratio >= 0.95:  # At least 95% should have dual feeders
        print(f"  ✓ Most secondary substations have redundant supply ({redundancy_ratio:.1%})")
    else:
        print(f"  ⚠ Only {redundancy_ratio:.1%} of secondaries have redundant supply")
    
    # Check all primary substations are connected to GSPs
    primary_ids = set(p['id'] for p in primary_substations)
    connected_primary_ids = set(edge['to_id'] for edge in feeds_edges)
    
    print(f"\nPrimary Substation Connectivity:")
    print(f"  Total primary substations:     {len(primary_ids)}")
    print(f"  Connected primary substations: {len(connected_primary_ids)}")
    
    primaries_passed = connected_primary_ids.issubset(primary_ids)
    
    if primaries_passed:
        print(f"  ✓ All primary substations are connected to GSPs")
    else:
        print(f"  ✗ Some primary substations have invalid connections")
    
    passed = properties_passed and secondaries_passed and primaries_passed
    
    if passed:
        print("\n✓ PASS: Network topology is valid - all components are connected")
    else:
        print("\n✗ FAIL: Network topology validation failed")
    
    return passed


def test_demand_values(data: Dict) -> bool:
    """Test that demand values are realistic"""
    print("\n" + "=" * 80)
    print("TEST 5: Demand Values Are Realistic")
    print("=" * 80)
    
    properties = data['vertices']['properties']
    
    print(f"\nDemand Analysis:")
    
    all_passed = True
    
    for prop_type, subtypes in DEMAND_RANGES.items():
        print(f"\n{prop_type.capitalize()} Properties:")
        
        for subtype, (min_demand, max_demand) in subtypes.items():
            # Get properties of this type and subtype
            matching_props = [p for p in properties 
                            if p['property_type'] == prop_type and p['property_subtype'] == subtype]
            
            if not matching_props:
                continue
            
            demands = [p['peak_demand_kw'] for p in matching_props]
            avg_demand = sum(demands) / len(demands)
            actual_min = min(demands)
            actual_max = max(demands)
            
            # Check if all demands are within expected range
            out_of_range = [d for d in demands if d < min_demand or d > max_demand]
            
            status = "✓" if len(out_of_range) == 0 else "✗"
            
            print(f"  {status} {subtype.capitalize()}:")
            print(f"      Count: {len(matching_props):,}")
            print(f"      Expected range: {min_demand:.1f} - {max_demand:.1f} kW")
            print(f"      Actual range:   {actual_min:.2f} - {actual_max:.2f} kW")
            print(f"      Average:        {avg_demand:.2f} kW")
            
            if out_of_range:
                print(f"      ✗ {len(out_of_range)} properties outside expected range")
                all_passed = False
    
    # Overall statistics
    all_demands = [p['peak_demand_kw'] for p in properties]
    total_demand = sum(all_demands)
    avg_demand = total_demand / len(all_demands)
    
    print(f"\nOverall Demand Statistics:")
    print(f"  Total peak demand:   {total_demand:,.2f} kW ({total_demand/1000:.2f} MW)")
    print(f"  Average per property: {avg_demand:.2f} kW")
    print(f"  Minimum:             {min(all_demands):.2f} kW")
    print(f"  Maximum:             {max(all_demands):.2f} kW")
    
    if all_passed:
        print("\n✓ PASS: All demand values are within realistic ranges")
    else:
        print("\n✗ FAIL: Some demand values are outside expected ranges")
    
    return all_passed


def test_nw_england_postcodes(data: Dict) -> bool:
    """Test that all postcodes are valid North West England formats"""
    print("\n" + "=" * 80)
    print("TEST 6: North West England Postcodes")
    print("=" * 80)
    
    properties = data['vertices']['properties']
    
    # Extract postcode prefixes
    postcode_prefixes = Counter()
    invalid_postcodes = []
    
    for prop in properties:
        postcode = prop['postcode']
        
        # Extract prefix (letters before digits)
        match = re.match(r'^([A-Z]+)', postcode)
        if match:
            prefix = match.group(1)
            postcode_prefixes[prefix] += 1
            
            if prefix not in VALID_NW_ENGLAND_POSTCODES:
                invalid_postcodes.append(postcode)
        else:
            invalid_postcodes.append(postcode)
    
    print(f"\nPostcode Prefix Distribution:")
    for prefix in sorted(VALID_NW_ENGLAND_POSTCODES):
        count = postcode_prefixes[prefix]
        ratio = count / len(properties) if count > 0 else 0
        print(f"  {prefix:3s}: {count:,} ({ratio:.1%})")
    
    # Check for invalid prefixes
    invalid_prefixes = set(postcode_prefixes.keys()) - set(VALID_NW_ENGLAND_POSTCODES)
    
    if invalid_prefixes:
        print(f"\n✗ Found invalid postcode prefixes:")
        for prefix in invalid_prefixes:
            count = postcode_prefixes[prefix]
            print(f"    {prefix}: {count} properties")
    
    # Verify postcode format (e.g., "M1 1AA")
    postcode_pattern = re.compile(r'^[A-Z]{1,2}\d{1,2}\s\d[A-Z]{2}$')
    format_invalid = [p['postcode'] for p in properties if not postcode_pattern.match(p['postcode'])]
    
    print(f"\nPostcode Format Validation:")
    print(f"  Total postcodes:        {len(properties):,}")
    print(f"  Valid format:           {len(properties) - len(format_invalid):,}")
    print(f"  Invalid format:         {len(format_invalid)}")
    
    passed = len(invalid_postcodes) == 0 and len(format_invalid) == 0
    
    if passed:
        print("\n✓ PASS: All postcodes are valid North West England formats")
    else:
        print(f"\n✗ FAIL: Found {len(invalid_postcodes)} invalid postcodes")
        if format_invalid:
            print(f"  Examples of invalid formats: {format_invalid[:5]}")
    
    return passed


def test_company_branding(data: Dict) -> bool:
    """Test company branding (Unicorn Energy Networks for assets, Unicorn Power for supply)"""
    print("\n" + "=" * 80)
    print("TEST 7: Company Branding")
    print("=" * 80)
    
    gsps = data['vertices']['grid_supply_points']
    primary_substations = data['vertices']['primary_substations']
    secondary_substations = data['vertices']['secondary_substations']
    properties = data['vertices']['properties']
    protection_devices = data['vertices']['protection_devices']
    
    all_passed = True
    
    # Check GSPs
    print(f"\nGrid Supply Points ({len(gsps)}):")
    gsp_operators = Counter(g['operator'] for g in gsps)
    for operator, count in gsp_operators.items():
        status = "✓" if operator == DNO_OPERATOR else "✗"
        print(f"  {status} {operator}: {count}")
        if operator != DNO_OPERATOR:
            all_passed = False
    
    # Check Primary Substations
    print(f"\nPrimary Substations ({len(primary_substations)}):")
    primary_operators = Counter(p['operator'] for p in primary_substations)
    for operator, count in primary_operators.items():
        status = "✓" if operator == DNO_OPERATOR else "✗"
        print(f"  {status} {operator}: {count}")
        if operator != DNO_OPERATOR:
            all_passed = False
    
    # Check Secondary Substations
    print(f"\nSecondary Substations ({len(secondary_substations)}):")
    secondary_operators = Counter(s['operator'] for s in secondary_substations)
    for operator, count in secondary_operators.items():
        status = "✓" if operator == DNO_OPERATOR else "✗"
        print(f"  {status} {operator}: {count}")
        if operator != DNO_OPERATOR:
            all_passed = False
    
    # Check Protection Devices
    print(f"\nProtection Devices ({len(protection_devices)}):")
    device_operators = Counter(d['operator'] for d in protection_devices)
    for operator, count in device_operators.items():
        status = "✓" if operator == DNO_OPERATOR else "✗"
        print(f"  {status} {operator}: {count}")
        if operator != DNO_OPERATOR:
            all_passed = False
    
    # Check Properties
    print(f"\nProperties ({len(properties):,}):")
    property_suppliers = Counter(p['supplier'] for p in properties)
    for supplier, count in property_suppliers.items():
        status = "✓" if supplier == ELECTRICITY_SUPPLIER else "✗"
        print(f"  {status} {supplier}: {count:,}")
        if supplier != ELECTRICITY_SUPPLIER:
            all_passed = False
    
    if all_passed:
        print(f"\n✓ PASS: All network assets owned by {DNO_OPERATOR}")
        print(f"         All properties supplied by {ELECTRICITY_SUPPLIER}")
    else:
        print(f"\n✗ FAIL: Company branding is incorrect")
    
    return all_passed


def print_summary(results: Dict[str, bool]):
    """Print test summary"""
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    total_tests = len(results)
    passed_tests = sum(1 for passed in results.values() if passed)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print("=" * 80)
    print(f"Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("✓ ALL TESTS PASSED")
        return 0
    else:
        print(f"✗ {total_tests - passed_tests} TEST(S) FAILED")
        return 1


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main test execution"""
    print("=" * 80)
    print("North West England Electricity Distribution Network")
    print("Data Generator Test Suite")
    print("=" * 80)
    
    # Load data
    data = load_network_data()
    
    # Run tests
    results = {
        "Property Count": test_property_count(data),
        "Property Type Distribution": test_property_type_distribution(data),
        "UPRN/MPAN Uniqueness": test_uprn_mpan_uniqueness(data),
        "Network Topology": test_network_topology(data),
        "Demand Values": test_demand_values(data),
        "North West England Postcodes": test_nw_england_postcodes(data),
        "Company Branding": test_company_branding(data)
    }
    
    # Print summary
    exit_code = print_summary(results)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
