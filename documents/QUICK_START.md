# Quick Start Guide

## 5-Minute Setup

### Prerequisites
- AWS CLI configured
- SAM CLI installed
- Python 3.13 virtual environment with the project dependencies installed
- AWS account with Neptune Analytics permissions

### Step 1: Deploy Infrastructure (2 minutes)

```bash
sam build
sam deploy --guided
# Accept defaults, note the bucket name and role ARN from outputs
```

**Output**: S3 bucket and IAM role created

### Step 2: Generate Data (2 minutes)

```bash
source .venv/bin/activate
python src/generate_network_data.py
python src/export_network_to_csv.py
```

**Output**: `neptune_csv/` directory with 10 CSV files

### Step 3: Upload to S3 (1 minute)

```bash
# Get bucket name from SAM outputs
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name nw-england-network \
  --query 'Stacks[0].Outputs[?OutputKey==`NeptuneDataBucketName`].OutputValue' \
  --output text)

aws s3 sync neptune_csv/ s3://${BUCKET}/network/
```

### Step 4: Create Graph and Import Data (5-10 minutes)

```bash
# Get IAM role ARN from SAM outputs
ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name nw-england-network \
  --query 'Stacks[0].Outputs[?OutputKey==`NeptuneAnalyticsImportRoleArn`].OutputValue' \
  --output text)

# Create graph and import data (takes 5-10 minutes)
aws neptune-graph create-graph-using-import-task \
  --graph-name nw-england-electricity-distribution-network \
  --source s3://${BUCKET}/network/ \
  --format CSV \
  --role-arn ${ROLE_ARN} \
  --min-provisioned-memory 32 \
  --max-provisioned-memory 32 \
  --no-public-connectivity \
  --deletion-protection \
  --region us-east-1 \
  --replica-count 0

# Set this to the graph identifier returned by the create command.
export NEPTUNE_GRAPH_ID="<your-neptune-graph-id>"

# Monitor import progress
aws neptune-graph get-import-task \
  --task-identifier <task-id-from-above-output> \
  --region us-east-1

```

**Note**: The import task returns immediately with a task ID. The actual import takes 5-10 minutes. Graph status must be "AVAILABLE" before querying.

For graph decommissioning, follow the approved data-retention and change-management process. The graph is created with deletion protection enabled.

### Step 5: Verify Graph Status

```bash
# Check if graph is ready
aws neptune-graph get-graph \
  --graph-identifier ${NEPTUNE_GRAPH_ID} \
  --region us-east-1 \
  --query '[status,endpoint]' \
  --output table
```

Wait until status shows "AVAILABLE" before querying.

### Step 6: Query (once available)

Get your graph endpoint:
```bash
aws neptune-graph get-graph \
  --graph-identifier ${NEPTUNE_GRAPH_ID} \
  --region us-east-1 \
  --query 'endpoint' \
  --output text
```

### Step 7: Test queries

Set up a graph notebook and attempt to connect....

```cypher
%%graph_notebook_config
{
  "host": "<your-neptune-graph-endpoint>",
  "neptune_service": "neptune-graph",
  "port": 443,
  "auth_mode": "IAM",
  "ssl": true,
  "ssl_verify": true,
  "aws_region": "us-east-1",
  "load_from_s3_arn": ""
}
```

Run a test query in the AWS Console (Neptune Analytics → Graphs → Query editor):
```cypher
%%oc

MATCH (p:Property)
WHERE p.address_city = 'Manchester'
RETURN COUNT(p) AS manchester_properties
```

## Common Queries

### Count properties by city
```cypher
%%oc

MATCH (p:Property)
RETURN p.address_city AS city, COUNT(p) AS count
ORDER BY count DESC
```

### Find properties with smart meters
```cypher
%%oc

MATCH (p:Property)
WHERE p.has_smart_meter = true
RETURN p.address_city AS city, COUNT(p) AS smart_meter_count
ORDER BY smart_meter_count DESC
```

### Calculate substation load
```cypher
%%oc

MATCH (ss:SecondarySubstation)-[:CONNECTS]->(p:Property)
RETURN ss.name, 
       SUM(p.peak_demand_kw) AS total_load_kw,
       COUNT(p) AS property_count
ORDER BY total_load_kw DESC
LIMIT 10
```

### Find properties impacted by substation outage
```cypher
%%oc

MATCH (ss:SecondarySubstation {name: 'Standish Substation'})-[:CONNECTS]->(p:Property)
RETURN DISTINCT p.postcode AS postcode
ORDER BY postcode
```

### Count properties impacted by substation outage
```cypher
%%oc

MATCH (ss:SecondarySubstation {name: 'Standish Substation'})-[:CONNECTS]->(p:Property)
RETURN ss.name, 
       COUNT(p) AS properties_affected,
       COLLECT(DISTINCT p.address_city)[0] AS city
```

### Find properties impacted by primary substation outage
```cypher
%%oc

MATCH (ps:PrimarySubstation {name: 'Wigan Primary'})-[:SUPPLIES]->(ss:SecondarySubstation)-[:CONNECTS]->(p:Property)
RETURN DISTINCT p.postcode AS postcode
ORDER BY postcode
```

### Find alternative supply routes via ring topology
```cypher
%%oc

MATCH (ps:PrimarySubstation {name: 'Wigan Primary'})-[:RING_TOPOLOGY]-(neighbor:PrimarySubstation)
RETURN neighbor.name AS alternative_primary,
       neighbor.location AS location,
       neighbor.capacity_mva AS capacity_mva
ORDER BY neighbor.name
```

### Trace supply path
```cypher
%%oc

MATCH path = (gsp:GridSupplyPoint)-[*]->(p:Property {uprn: '100012345678'})
RETURN path
LIMIT 1
```

## Cost Management

**Delete graph when done:**
```bash
aws neptune-graph delete-graph \
  --graph-identifier nw-england-electricity-distribution-network \
  --skip-snapshot \
  --region us-east-1
```

**Take snapshot first (optional):**
```bash
aws neptune-graph create-graph-snapshot \
  --graph-identifier nw-england-electricity-distribution-network \
  --snapshot-name network-snapshot-$(date +%Y%m%d) \
  --region us-east-1
```

## Next Steps

- **AI Agent Integration**: See [AI_AGENT_INTEGRATION.md](documents/AI_AGENT_INTEGRATION.md)
- **Detailed Setup**: See [NEPTUNE_ANALYTICS_SETUP.md](NEPTUNE_ANALYTICS_SETUP.md)
- **Query Examples**: See [query_examples.py](src/query_examples.py)

## Troubleshooting

**Import fails?**
- Check IAM role has S3 read permissions
- Verify CSV format (headers: `~id`, `~label`, `~from`, `~to`)

**Query timeout?**
- Increase provisioned memory
- Add filters to narrow results

**Can't connect?**
- Verify graph status is "available"
- Check security group allows port 8182

## Estimated Costs

- **Storage**: ~$0.10-0.50/month
- **Queries**: ~$0.01-1.00/month
- **Total**: ~$1-10/month for demo usage

**Delete graph when not in use to avoid charges!**
