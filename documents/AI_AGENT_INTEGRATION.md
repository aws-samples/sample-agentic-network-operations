# AI Agent Integration Guide: North West England Electricity Distribution Network

## Overview

This guide provides comprehensive documentation for integrating Large Language Models (LLMs) and AI agents with the North West England electricity distribution network graph database. The network is operated by **Unicorn Energy Networks** (DNO) and serves customers supplied by **Unicorn Power**.

## Table of Contents

1. [Graph Schema for LLM Context](#graph-schema-for-llm-context)
2. [Query Language Selection](#query-language-selection)
3. [Natural Language Query Examples](#natural-language-query-examples)
4. [Query Patterns for AI Agents](#query-patterns-for-ai-agents)
5. [Prompt Templates](#prompt-templates)
6. [Company Context](#company-context)
7. [Geography Context](#geography-context)
8. [Best Practices](#best-practices)

---

## Graph Schema for LLM Context

### Concise Schema Summary

When providing context to an LLM, use this condensed schema representation:

```
VERTEX TYPES:
- GridSupplyPoint: {id, name, voltage_kv, capacity_mva, location, operator}
- PrimarySubstation: {id, name, voltage_in_kv, voltage_out_kv, capacity_mva, location, operator}
- SecondarySubstation: {id, name, transformer_capacity_kva, voltage_out_v, location, operator}
- Property: {uprn, mpan, address_city, postcode, property_type, peak_demand_kw, has_smart_meter, supplier}
- ProtectionDevice: {id, device_type, rating_amps, voltage_kv, operator}

EDGE TYPES:
- FEEDS: GridSupplyPoint → PrimarySubstation
- SUPPLIES: PrimarySubstation → SecondarySubstation (also Primary → Primary for ring topology)
- CONNECTS: SecondarySubstation → Property
- PROTECTS: ProtectionDevice → Substation

COMPANIES:
- Unicorn Energy Networks: Distribution Network Operator (owns network assets)
- Unicorn Power: Electricity Retailer (supplies customers)

GEOGRAPHY:
- Region: North West England
- Cities: Manchester, Liverpool, Preston, Chester, Carlisle, Blackpool, Bolton, Warrington
- Postcodes: M (Manchester), L (Liverpool), PR (Preston), CH (Chester), CA (Carlisle), 
             FY (Blackpool), BL (Bolton), WA (Warrington)
```

### Detailed Property Reference

For more complex queries, provide this detailed property list:

**Property Vertex - Complete Properties:**
- `uprn`: 12-digit Unique Property Reference Number
- `mpan`: 21-digit Meter Point Administration Number
- `address_number`, `address_street`, `address_city`, `address_area`: Address components
- `postcode`: UK postcode (M, L, PR, CH, CA, FY, BL, WA formats)
- `property_type`: residential, commercial, industrial
- `property_subtype`: house, flat, shop, office, factory, warehouse
- `num_bedrooms`: Number of bedrooms (residential only, 0 for others)
- `connection_type`: single-phase, three-phase
- `peak_demand_kw`: Peak demand in kilowatts
- `has_smart_meter`: Boolean flag
- `latitude`, `longitude`: Geographic coordinates
- `supplier`: "Unicorn Power"

---

## Query Language Selection

### Why openCypher for AI Agents

**Primary Query Language**: openCypher (Cypher)

**Rationale for openCypher:**

1. **LLM Training Data**: LLMs have extensive training on SQL-like declarative syntax
2. **Pattern Matching**: Visual patterns `(a)-[r]->(b)` are self-documenting and intuitive
3. **Declarative Nature**: Easier for LLMs to generate "what to find" vs "how to traverse"
4. **Error Recovery**: Syntax errors are easier to detect and correct
5. **Industry Adoption**: Growing standard (Neo4j, Memgraph, Amazon Neptune)

The sample's query examples use parameterized openCypher calls through the
Neptune Analytics API. They do not expose a direct graph endpoint or accept
arbitrary query text from the command line.

---

## Natural Language Query Examples

### Basic Property Queries

**Natural Language**: "Show me all houses in Manchester"
```cypher
MATCH (p:Property)
WHERE p.address_city = 'Manchester' 
  AND p.property_subtype = 'house'
RETURN p
```

**Natural Language**: "Find properties with smart meters in Liverpool"
```cypher
MATCH (p:Property)
WHERE p.address_city = 'Liverpool' 
  AND p.has_smart_meter = true
RETURN p
```

**Natural Language**: "List all commercial properties in the M1 postcode area"
```cypher
MATCH (p:Property)
WHERE p.postcode STARTS WITH 'M1' 
  AND p.property_type = 'commercial'
RETURN p
```

**Natural Language**: "Find three-phase connections in Preston"
```cypher
MATCH (p:Property)
WHERE p.address_city = 'Preston' 
  AND p.connection_type = 'three-phase'
RETURN p
```

### Network Topology Queries

**Natural Language**: "Show me all properties connected to Deansgate Substation"
```cypher
MATCH (ss:SecondarySubstation {name: 'Deansgate Substation'})<-[:CONNECTS]-(p:Property)
RETURN p
```

**Natural Language**: "Find the path from the grid to property with UPRN 100012345678"
```cypher
MATCH path = (gsp:GridSupplyPoint)-[*]->(p:Property {uprn: '100012345678'})
RETURN path
LIMIT 1
```

**Natural Language**: "Show alternative supply routes for a property"
```cypher
MATCH path = (gsp:GridSupplyPoint)-[:FEEDS*1..5]->(p:Property {uprn: '100012345678'})
RETURN path
```

**Natural Language**: "List all substations that feed properties in Carlisle"
```cypher
MATCH (ss:SecondarySubstation)<-[:CONNECTS]-(p:Property)
WHERE p.address_city = 'Carlisle'
RETURN DISTINCT ss
```

### Load and Capacity Queries

**Natural Language**: "What's the total electricity demand on Salford Quays Primary substation?"
```cypher
MATCH (ps:PrimarySubstation {name: 'Salford Quays Primary'})-[:SUPPLIES*1..2]->(ss:SecondarySubstation)
      <-[:CONNECTS]-(p:Property)
RETURN ps.name AS substation, 
       SUM(p.peak_demand_kw) AS total_load_kw,
       ps.capacity_mva * 1000 AS capacity_kw
```

**Natural Language**: "Find secondary substations with load over 500 kW"
```cypher
MATCH (ss:SecondarySubstation)<-[:CONNECTS]-(p:Property)
WITH ss, SUM(p.peak_demand_kw) AS total_load
WHERE total_load > 500
RETURN ss.name, ss.location, total_load
ORDER BY total_load DESC
```

**Natural Language**: "Calculate the average demand for residential properties in Manchester"
```cypher
MATCH (p:Property)
WHERE p.address_city = 'Manchester' 
  AND p.property_type = 'residential'
RETURN AVG(p.peak_demand_kw) AS avg_demand_kw
```

### Company-Specific Queries

**Natural Language**: "Show all network assets owned by Unicorn Energy Networks in Bolton"
```cypher
MATCH (n)
WHERE n.operator = 'Unicorn Energy Networks' 
  AND n.location CONTAINS 'Bolton'
RETURN n
```

**Natural Language**: "Find all properties supplied by Unicorn Power with demand over 10 kW"
```cypher
MATCH (p:Property)
WHERE p.supplier = 'Unicorn Power' 
  AND p.peak_demand_kw > 10
RETURN p
```

**Natural Language**: "Count properties by supplier in each city"
```cypher
MATCH (p:Property)
RETURN p.address_city AS city, 
       p.supplier AS supplier, 
       COUNT(p) AS property_count
ORDER BY city, supplier
```

### Geographic Queries

**Natural Language**: "Find all substations in Greater Manchester"
```cypher
MATCH (ss:SecondarySubstation)
WHERE ss.location CONTAINS 'Greater Manchester'
RETURN ss
```

**Natural Language**: "List properties in Blackpool postcode area (FY)"
```cypher
MATCH (p:Property)
WHERE p.postcode STARTS WITH 'FY'
RETURN p
```

**Natural Language**: "Show distribution of property types across North West England cities"
```cypher
MATCH (p:Property)
RETURN p.address_city AS city, 
       p.property_type AS type, 
       COUNT(p) AS count
ORDER BY city, type
```

### Smart Meter Queries

**Natural Language**: "What percentage of properties in Liverpool have smart meters?"
```cypher
MATCH (p:Property)
WHERE p.address_city = 'Liverpool'
WITH COUNT(p) AS total,
     SUM(CASE WHEN p.has_smart_meter THEN 1 ELSE 0 END) AS smart_meter_count
RETURN smart_meter_count, 
       total, 
       (smart_meter_count * 100.0 / total) AS percentage
```

**Natural Language**: "Find industrial properties without smart meters"
```cypher
MATCH (p:Property)
WHERE p.property_type = 'industrial' 
  AND p.has_smart_meter = false
RETURN p
```

---

## Query Patterns for AI Agents

### Pattern 1: Simple Property Filter

**Template:**
```cypher
MATCH (p:Property)
WHERE p.{property_name} = '{value}'
RETURN p
```

**Use Cases:**
- Find properties by city, postcode, type
- Filter by supplier, connection type
- Boolean flags (smart meters)

**Example Variations:**
```cypher
-- Exact match
WHERE p.address_city = 'Manchester'

-- Starts with (postcodes)
WHERE p.postcode STARTS WITH 'M1'

-- Contains (partial match)
WHERE p.address_street CONTAINS 'High Street'

-- Comparison
WHERE p.peak_demand_kw > 10

-- Boolean
WHERE p.has_smart_meter = true
```

### Pattern 2: Relationship Traversal

**Template:**
```cypher
MATCH (start:StartLabel {property: 'value'})-[relationship*min..max]->(end:EndLabel)
RETURN end
```

**Use Cases:**
- Find connected components
- Trace supply paths
- Discover network topology

**Example Variations:**
```cypher
-- Direct connection
MATCH (ss:SecondarySubstation)<-[:CONNECTS]-(p:Property)

-- Multi-hop traversal
MATCH (gsp:GridSupplyPoint)-[:FEEDS|SUPPLIES*1..3]->(p:Property)

-- Bidirectional
MATCH (a)-[r]-(b)

-- With relationship properties
MATCH (a)-[r:SUPPLIES {is_backup: false}]->(b)
```

### Pattern 3: Aggregation

**Template:**
```cypher
MATCH (node:Label)
WHERE {filter_conditions}
RETURN {aggregation_function}(node.property) AS result
```

**Use Cases:**
- Calculate totals, averages, counts
- Group by categories
- Statistical analysis

**Example Variations:**
```cypher
-- Count
RETURN COUNT(p) AS total_properties

-- Sum
RETURN SUM(p.peak_demand_kw) AS total_demand

-- Average
RETURN AVG(p.peak_demand_kw) AS avg_demand

-- Group by
RETURN p.property_type, COUNT(p) AS count
GROUP BY p.property_type
```

### Pattern 4: Path Finding

**Template:**
```cypher
MATCH path = (start:StartLabel)-[*]->(end:EndLabel {property: 'value'})
RETURN path
LIMIT {n}
```

**Use Cases:**
- Trace supply routes
- Find alternative paths
- Network connectivity analysis

**Example Variations:**
```cypher
-- Shortest path
MATCH path = shortestPath((a)-[*]-(b))

-- All paths with limit
MATCH path = (a)-[*1..5]->(b)
RETURN path
LIMIT 10

-- Path with conditions
MATCH path = (a)-[r:SUPPLIES*]->(b)
WHERE ALL(rel IN r WHERE rel.is_backup = false)
```

### Pattern 5: Complex Filtering with Multiple Conditions

**Template:**
```cypher
MATCH (node:Label)
WHERE condition1
  AND condition2
  OR condition3
RETURN node
```

**Use Cases:**
- Multi-criteria search
- Complex business logic
- Combining geographic and technical filters

**Example Variations:**
```cypher
-- AND conditions
WHERE p.address_city = 'Manchester' 
  AND p.property_type = 'residential'
  AND p.has_smart_meter = true

-- OR conditions
WHERE p.address_city IN ['Manchester', 'Liverpool', 'Preston']

-- NOT conditions
WHERE NOT p.property_type = 'industrial'

-- Range conditions
WHERE p.peak_demand_kw >= 5 AND p.peak_demand_kw <= 15
```

---

## Prompt Templates

### Template 1: Basic Query Generation

```
You are a graph database query assistant for an electricity distribution network.

GRAPH SCHEMA:
{insert concise schema from above}

USER REQUEST: {natural language query}

Generate an openCypher query to answer this request. Return only the query, no explanation.

QUERY:
```

**Example:**
```
USER REQUEST: Find all houses in Manchester with smart meters

QUERY:
MATCH (p:Property)
WHERE p.address_city = 'Manchester' 
  AND p.property_subtype = 'house'
  AND p.has_smart_meter = true
RETURN p
```

### Template 2: Query with Explanation

```
You are a graph database query assistant for the North West England electricity distribution network 
operated by Unicorn Energy Networks.

GRAPH SCHEMA:
{insert concise schema}

GEOGRAPHY CONTEXT:
- Cities: Manchester, Liverpool, Preston, Chester, Carlisle, Blackpool, Bolton, Warrington
- Postcodes: M (Manchester), L (Liverpool), PR (Preston), CH (Chester), CA (Carlisle), 
             FY (Blackpool), BL (Bolton), WA (Warrington)

USER REQUEST: {natural language query}

Generate an openCypher query and explain your approach.

QUERY:
{query here}

EXPLANATION:
{brief explanation of the query logic}
```

### Template 3: Query Validation and Correction

```
You are validating an openCypher query for an electricity distribution network graph database.

GRAPH SCHEMA:
{insert concise schema}

QUERY TO VALIDATE:
{user's query}

TASK:
1. Check if the query is syntactically correct
2. Verify node labels and property names match the schema
3. Ensure relationship types are correct
4. Suggest corrections if needed

VALIDATION RESULT:
```

### Template 4: Multi-Step Query Planning

```
You are planning a complex query for an electricity distribution network graph database.

GRAPH SCHEMA:
{insert concise schema}

USER REQUEST: {complex natural language query}

TASK:
1. Break down the request into logical steps
2. Identify which vertex and edge types are needed
3. Determine the query pattern (filter, traversal, aggregation, path)
4. Generate the openCypher query
5. Explain the query logic

QUERY PLAN:
```

### Template 5: Context-Aware Query Generation

```
You are a graph database assistant for Unicorn Energy Networks' distribution network in North West England.

FULL CONTEXT:
- Network Operator: Unicorn Energy Networks (owns infrastructure)
- Electricity Supplier: Unicorn Power (serves customers)
- Region: North West England (Greater Manchester, Merseyside, Lancashire, Cheshire, Cumbria)
- Major Cities: Manchester, Liverpool, Preston, Chester, Carlisle, Blackpool, Bolton, Warrington
- Postcode Areas: M, L, PR, CH, CA, FY, BL, WA

GRAPH SCHEMA:
{insert concise schema}

CONVERSATION HISTORY:
{previous queries and results if applicable}

USER REQUEST: {natural language query}

Generate an openCypher query considering the full context. If the request mentions:
- "network assets" or "infrastructure" → filter by operator = 'Unicorn Energy Networks'
- "customers" or "supply" → filter by supplier = 'Unicorn Power'
- City names → use address_city property
- Postcode areas → use postcode STARTS WITH pattern

QUERY:
```

---

## Company Context

### Unicorn Energy Networks (Distribution Network Operator)

**Role**: Owns and operates the physical electricity distribution network

**Responsibilities:**
- Network infrastructure (substations, cables, transformers)
- Network maintenance and upgrades
- Network capacity planning
- Protection equipment management

**Assets in Database:**
- GridSupplyPoint vertices (operator = "Unicorn Energy Networks")
- PrimarySubstation vertices (operator = "Unicorn Energy Networks")
- SecondarySubstation vertices (operator = "Unicorn Energy Networks")
- ProtectionDevice vertices (operator = "Unicorn Energy Networks")
- All FEEDS, SUPPLIES edges (infrastructure connections)

**Query Examples:**
```cypher
-- Find all Unicorn Energy Networks substations
MATCH (n)
WHERE n.operator = 'Unicorn Energy Networks'
RETURN n

-- Count network assets by type
MATCH (n)
WHERE n.operator = 'Unicorn Energy Networks'
RETURN labels(n)[0] AS asset_type, COUNT(n) AS count
```

### Unicorn Power (Electricity Retailer/Supplier)

**Role**: Provides retail electricity supply to end customers

**Responsibilities:**
- Customer billing and relationships
- Electricity procurement
- Customer service
- Smart meter deployment

**Assets in Database:**
- Property vertices (supplier = "Unicorn Power")
- Customer connection data

**Query Examples:**
```cypher
-- Find all Unicorn Power customers
MATCH (p:Property)
WHERE p.supplier = 'Unicorn Power'
RETURN p

-- Count customers by property type
MATCH (p:Property)
WHERE p.supplier = 'Unicorn Power'
RETURN p.property_type, COUNT(p) AS customer_count
```

### Distinguishing Between Companies in Queries

**When to filter by operator (Unicorn Energy Networks):**
- Queries about network infrastructure
- Substation capacity and locations
- Protection equipment
- Network topology and connections

**When to filter by supplier (Unicorn Power):**
- Queries about customers and properties
- Demand analysis
- Smart meter deployment
- Customer segmentation

---

## Geography Context

### North West England Region

**Coverage Areas:**
- Greater Manchester
- Merseyside
- Lancashire
- Cheshire
- Cumbria

### Major Cities and Towns

| City | Postcode Area | Population Context | Key Characteristics |
|------|---------------|-------------------|---------------------|
| Manchester | M | Largest city | Commercial hub, high density |
| Liverpool | L | Major port city | Mixed residential/commercial |
| Preston | PR | County town | Regional center |
| Chester | CH | Historic city | Tourist destination |
| Carlisle | CA | Northern city | Border city, lower density |
| Blackpool | FY | Coastal resort | Seasonal demand variation |
| Bolton | BL | Industrial town | Manufacturing heritage |
| Warrington | WA | New town | Mixed development |

### Postcode Area Reference

**Format**: UK postcodes follow pattern: `AREA DISTRICT SECTOR UNIT`
- Example: `M1 1AA` (Manchester city center)
- Example: `L1 1AA` (Liverpool city center)

**Postcode Areas in Network:**
- **M**: Manchester (M1-M99)
- **L**: Liverpool (L1-L40)
- **PR**: Preston (PR1-PR9)
- **CH**: Chester (CH1-CH8)
- **CA**: Carlisle (CA1-CA8)
- **FY**: Blackpool (FY1-FY8)
- **BL**: Bolton (BL1-BL9)
- **WA**: Warrington (WA1-WA5)

### Geographic Query Patterns

**By City:**
```cypher
MATCH (p:Property)
WHERE p.address_city = 'Manchester'
RETURN p
```

**By Postcode Area:**
```cypher
MATCH (p:Property)
WHERE p.postcode STARTS WITH 'M1'
RETURN p
```

**By Region:**
```cypher
MATCH (p:Property)
WHERE p.address_area = 'Greater Manchester'
RETURN p
```

**Multiple Cities:**
```cypher
MATCH (p:Property)
WHERE p.address_city IN ['Manchester', 'Liverpool', 'Preston']
RETURN p
```

### Real-World Context for AI Agents

When generating queries, AI agents should understand:

1. **Urban vs Rural**: Manchester and Liverpool are high-density urban areas; Carlisle is more rural
2. **Postcode Density**: M and L postcodes have more properties than CA postcodes
3. **Property Types**: City centers (M1, L1) have more commercial properties; suburbs have more residential
4. **Industrial Areas**: Bolton (BL) and Warrington (WA) have higher industrial property concentration
5. **Coastal**: Blackpool (FY) is a coastal resort with seasonal characteristics

---

## Best Practices

### For AI Agents Generating Queries

1. **Always Specify Node Labels**
   ```cypher
   -- Good
   MATCH (p:Property)
   
   -- Avoid
   MATCH (p)
   ```

2. **Use Property Filters in Node Patterns**
   ```cypher
   -- Good
   MATCH (p:Property {address_city: 'Manchester'})
   
   -- Less efficient
   MATCH (p:Property)
   WHERE p.address_city = 'Manchester'
   ```

3. **Specify Relationship Types**
   ```cypher
   -- Good
   MATCH (ss:SecondarySubstation)<-[:CONNECTS]-(p:Property)
   
   -- Avoid
   MATCH (ss:SecondarySubstation)<-[]-(p:Property)
   ```

4. **Add LIMIT Clauses for Large Result Sets**
   ```cypher
   MATCH (p:Property)
   RETURN p
   LIMIT 100
   ```

5. **Use Explicit Return Columns**
   ```cypher
   -- Good
   RETURN p.uprn, p.address_city, p.peak_demand_kw
   
   -- Less clear
   RETURN p
   ```

6. **Validate Geographic References**
   - Check city names against the list: Manchester, Liverpool, Preston, Chester, Carlisle, Blackpool, Bolton, Warrington
   - Verify postcode areas: M, L, PR, CH, CA, FY, BL, WA

7. **Consider Company Context**
   - Use `operator = 'Unicorn Energy Networks'` for infrastructure queries
   - Use `supplier = 'Unicorn Power'` for customer queries

### Query Optimization Tips

1. **Filter Early**: Place restrictive filters at the start of the query
2. **Limit Traversal Depth**: Use specific hop counts `[*1..3]` instead of `[*]`
3. **Use Indexes**: Queries on `id`, `uprn`, `mpan` are indexed
4. **Avoid Cartesian Products**: Always connect patterns with relationships

### Error Handling

**Common Errors and Solutions:**

1. **Invalid Node Label**
   ```
   Error: Unknown label 'Substation'
   Solution: Use 'SecondarySubstation' or 'PrimarySubstation'
   ```

2. **Invalid Property Name**
   ```
   Error: Property 'city' does not exist
   Solution: Use 'address_city' instead
   ```

3. **Invalid Relationship Type**
   ```
   Error: Unknown relationship 'CONNECTED_TO'
   Solution: Use 'CONNECTS', 'SUPPLIES', or 'FEEDS'
   ```

4. **Type Mismatch**
   ```
   Error: Cannot compare string to integer
   Solution: Ensure property types match (e.g., voltage_kv is int, not string)
   ```

### Testing Generated Queries

Before executing a generated query, validate:

1. ✓ Node labels match schema (GridSupplyPoint, PrimarySubstation, SecondarySubstation, Property, ProtectionDevice)
2. ✓ Property names are correct (address_city not city, peak_demand_kw not demand)
3. ✓ Relationship types are valid (FEEDS, SUPPLIES, CONNECTS, PROTECTS)
4. ✓ Geographic references are accurate (Manchester not London)
5. ✓ Company names are exact (Unicorn Energy Networks, Unicorn Power)
6. ✓ Query has LIMIT clause if returning many results

---

## Example AI Agent Conversation

**User**: "How many houses in Manchester have smart meters?"

**AI Agent Internal Process**:
1. Identify entities: houses (property_subtype), Manchester (address_city), smart meters (has_smart_meter)
2. Select pattern: Simple property filter with aggregation
3. Generate query

**AI Agent Response**:
```cypher
MATCH (p:Property)
WHERE p.address_city = 'Manchester' 
  AND p.property_subtype = 'house'
  AND p.has_smart_meter = true
RETURN COUNT(p) AS smart_meter_houses
```

**User**: "What's the total load on substations in Liverpool?"

**AI Agent Internal Process**:
1. Identify entities: substations (SecondarySubstation), Liverpool (address_city), load (peak_demand_kw)
2. Select pattern: Relationship traversal with aggregation
3. Generate query

**AI Agent Response**:
```cypher
MATCH (ss:SecondarySubstation)<-[:CONNECTS]-(p:Property)
WHERE p.address_city = 'Liverpool'
RETURN ss.name AS substation, 
       SUM(p.peak_demand_kw) AS total_load_kw
ORDER BY total_load_kw DESC
```

**User**: "Show me the path from the grid to my property, UPRN 100012345678"

**AI Agent Internal Process**:
1. Identify entities: grid (GridSupplyPoint), property (Property with uprn)
2. Select pattern: Path finding
3. Generate query

**AI Agent Response**:
```cypher
MATCH path = (gsp:GridSupplyPoint)-[*]->(p:Property {uprn: '100012345678'})
RETURN path
LIMIT 1
```

---

## Appendix: Quick Reference

### Essential Node Labels
- `GridSupplyPoint`, `PrimarySubstation`, `SecondarySubstation`, `Property`, `ProtectionDevice`

### Essential Relationship Types
- `FEEDS`, `SUPPLIES`, `CONNECTS`, `PROTECTS`

### Essential Properties
- Property: `uprn`, `mpan`, `address_city`, `postcode`, `property_type`, `peak_demand_kw`, `has_smart_meter`, `supplier`
- Substation: `id`, `name`, `location`, `operator`

### Essential Companies
- `Unicorn Energy Networks` (network operator)
- `Unicorn Power` (electricity supplier)

### Essential Cities
- Manchester, Liverpool, Preston, Chester, Carlisle, Blackpool, Bolton, Warrington

### Essential Postcode Areas
- M, L, PR, CH, CA, FY, BL, WA

---

## Additional Resources

- **Graph Schema**: See `graph_schema.md` for complete vertex and edge definitions
- **Query Examples**: See `src/query_examples.py` for working code examples
- **Design Document**: See `.kiro/specs/electricity-distribution-network/design.md` for system architecture

---

**Document Version**: 1.0  
**Last Updated**: February 2026  
**Maintained By**: Unicorn Energy Networks Data Team
