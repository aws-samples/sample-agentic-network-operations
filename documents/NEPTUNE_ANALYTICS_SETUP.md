# Neptune Analytics Setup Guide

## Overview

This guide walks through setting up Amazon Neptune Analytics for the North West England electricity distribution network graph database.

## Prerequisites

- AWS CLI configured with credentials
- Python 3.13 virtual environment
- Generated network data (`network_data.json`)
- Exported CSV files (`neptune_csv/` directory)

## Step 1: Generate and Export Data

```bash
# Activate Python environment
source .venv/bin/activate

# Generate network data
python src/generate_network_data.py

# Export to Neptune Analytics CSV format
python src/export_network_to_csv.py --input network_data.json --output-dir neptune_csv
```

This creates CSV files in the `neptune_csv/` directory:
- Node files: `gridsupplypoint_nodes.csv`, `primarysubstation_nodes.csv`, etc.
- Edge files: `feeds_edges.csv`, `supplies_edges.csv`, etc.

## Step 2: Upload CSV Files to S3

```bash
# Create S3 bucket (choose a unique name)
BUCKET_NAME="your-neptune-analytics-network-$(date +%s)"
aws s3 mb s3://${BUCKET_NAME} --region us-east-1

# Upload CSV files
aws s3 sync neptune_csv/ s3://${BUCKET_NAME}/network/ --region us-east-1

# Verify upload
aws s3 ls s3://${BUCKET_NAME}/network/
```

## Step 3: Create Neptune Analytics Graph

### Option A: Using AWS Console

1. Navigate to Neptune Analytics in AWS Console
2. Click "Create graph"
3. Configure:
   - **Graph name**: `nw-england-electricity-network`
   - **Description**: North West England electricity distribution network
   - **Provisioned memory**: Start with 128 GB (adjust based on needs)
   - **Replica count**: 0 (for development)
   - **Public connectivity**: Disabled (recommended)
   - **VPC**: Select your VPC or use default
   - **Subnet group**: Select private subnets
   - **Security group**: Create or select one allowing port 8182
4. Click "Create graph"

### Option B: Using AWS CLI

```bash
# Create Neptune Analytics graph
aws neptune-graph create-graph \
  --graph-name nw-england-electricity-network \
  --provisioned-memory 128 \
  --replica-count 0 \
  --public-connectivity false \
  --region us-east-1

# Wait for graph to be available
aws neptune-graph wait graph-available \
  --graph-identifier nw-england-electricity-network \
  --region us-east-1
```

## Step 4: Import CSV Data

### Using AWS Console

1. Go to your Neptune Analytics graph
2. Click "Import data"
3. Configure import:
   - **Source**: S3
   - **S3 URI**: `s3://${BUCKET_NAME}/network/`
   - **Format**: CSV
   - **IAM role**: Create or select role with S3 read access
4. Click "Start import"
5. Monitor import progress in the console

### Using AWS CLI

```bash
# Create IAM role for Neptune Analytics (if not exists)
# See IAM role creation section below

# Start import job
aws neptune-graph create-graph-using-import-task \
  --graph-name nw-england-electricity-network \
  --source s3://${BUCKET_NAME}/network/ \
  --format CSV \
  --role-arn arn:aws:iam::YOUR_ACCOUNT_ID:role/NeptuneAnalyticsImportRole \
  --region us-east-1

# Check import status
aws neptune-graph get-import-task \
  --task-identifier TASK_ID \
  --region us-east-1
```

## Step 5: Get Graph Endpoint

```bash
# Get graph details
aws neptune-graph get-graph \
  --graph-identifier nw-england-electricity-network \
  --region us-east-1 \
  --query 'endpoint' \
  --output text
```

Save this endpoint - you'll need it for querying.

## Step 6: Query the Graph

### Using AWS Console

1. Go to your Neptune Analytics graph
2. Click "Query" tab
3. Select "openCypher" as query language
4. Run test query:

```cypher
MATCH (p:Property)
WHERE p.address_city = 'Manchester'
RETURN COUNT(p) AS manchester_properties
```

### Using Python

```bash
# Set the Neptune Analytics graph identifier returned by the import task.
export NEPTUNE_GRAPH_ID="g-your-neptune-graph-id"

# Run a named, parameterized openCypher example.
python src/query_examples.py \
  --graph-id "${NEPTUNE_GRAPH_ID}" \
  --query high-load-substations \
  --limit 10
```

The executing identity requires `neptune-graph:ExecuteQuery` for the graph.
The script uses the Neptune Analytics data-plane API through boto3 rather than
a direct endpoint or Bolt connection.

## IAM Role for Import

Neptune Analytics needs an IAM role to read from S3. Create this role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "neptune-graph.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Attach this policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name/*",
        "arn:aws:s3:::your-bucket-name"
      ]
    }
  ]
}
```

## CSV Format Reference

### Node CSV Format

```csv
~id,~label,property1,property2,...
node-id-1,NodeType,value1,value2,...
node-id-2,NodeType,value1,value2,...
```

Example (`property_nodes.csv`):
```csv
~id,~label,uprn,mpan,address_city,postcode,property_type,peak_demand_kw,has_smart_meter,supplier
100012345678,Property,100012345678,21001234567890123456,Manchester,M1 1AA,residential,3.5,true,Unicorn Power
```

### Edge CSV Format

```csv
~id,~from,~to,~label,property1,property2,...
edge-id-1,source-node-id,target-node-id,EdgeType,value1,value2,...
```

Example (`connects_edges.csv`):
```csv
~id,~from,~to,~label,cable_type,length_meters,capacity_amps
CONNECTS-1,SS001,100012345678,CONNECTS,underground,45.5,100
```

## Monitoring and Management

### Check Graph Status

```bash
aws neptune-graph get-graph \
  --graph-identifier nw-england-electricity-network \
  --region us-east-1
```

### View Import Tasks

```bash
aws neptune-graph list-import-tasks \
  --region us-east-1
```

### Delete Graph (when done)

```bash
aws neptune-graph delete-graph \
  --graph-identifier nw-england-electricity-network \
  --skip-snapshot \
  --region us-east-1
```

## Cost Management

### Minimize Costs

1. **Delete when not in use**: No charges when graph is deleted
2. **Right-size memory**: Start with 128 GB, adjust based on query performance
3. **Use snapshots**: Take snapshot before deletion for quick restore
4. **Monitor queries**: Use CloudWatch to track query costs

### Estimated Costs

- **Graph storage**: ~$0.10/GB/month
- **Query compute**: ~$0.10 per million graph traversals
- **Snapshot storage**: ~$0.021/GB/month

For this demo dataset (~1-5 GB):
- Storage: ~$0.10-0.50/month
- Queries: ~$0.01-1.00/month (depending on usage)
- **Total**: ~$1-10/month

## Troubleshooting

### Import Fails

**Issue**: Import task fails with S3 access error

**Solution**: 
- Verify IAM role has S3 read permissions
- Check S3 bucket policy allows Neptune Analytics access
- Ensure CSV files are in correct format

### Query Timeout

**Issue**: Queries timeout or run slowly

**Solution**:
- Increase provisioned memory
- Add indexes on frequently queried properties
- Optimize query patterns (use filters early)

### Connection Refused

**Issue**: Cannot connect to graph endpoint

**Solution**:
- Verify security group allows port 8182
- Check VPC and subnet configuration
- Ensure graph status is "available"

### CSV Format Errors

**Issue**: Import fails with CSV parsing errors

**Solution**:
- Verify CSV headers match Neptune Analytics format (`~id`, `~label`, `~from`, `~to`)
- Check for special characters in data (escape quotes)
- Ensure consistent column count across all rows

## Next Steps

1. **Query the graph**: Use openCypher queries from `documents/AI_AGENT_INTEGRATION.md`
2. **Integrate with agents**: Connect AI agents to query the network
3. **Add external data**: Combine graph queries with weather data, etc.
4. **Optimize performance**: Add indexes, tune memory allocation

## Additional Resources

- [Neptune Analytics Documentation](https://docs.aws.amazon.com/neptune-analytics/)
- [openCypher Query Language](https://opencypher.org/)
- [AI Agent Integration Guide](documents/AI_AGENT_INTEGRATION.md)
- [CSV Import Format](https://docs.aws.amazon.com/neptune-analytics/latest/userguide/csv-format.html)
