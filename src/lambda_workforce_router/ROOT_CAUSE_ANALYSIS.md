# Root Cause Analysis: Lambda Returning 0 Engineers

## Issue Summary
Lambda was returning 0 engineers for all queries despite database being initialized with 25 engineers.

## Symptoms
```
Raw response records count: 4
Parsed engineers count: 0
```

The database query was returning records, but the parsing function was returning an empty list.

## Root Cause

**Missing `includeResultMetadata=True` in RDS Data API call**

The `execute_sql()` function was not requesting column metadata from the RDS Data API:

```python
# BROKEN CODE
response = rds_client.execute_statement(
    resourceArn=DB_CLUSTER_ARN,
    secretArn=DB_SECRET_ARN,
    database=DB_NAME,
    sql=sql
    # Missing: includeResultMetadata=True
)
```

Without `includeResultMetadata=True`, the RDS Data API response does not include the `columnMetadata` field, which contains the column names. The `parse_data_api_response()` function checks for this field and returns an empty list if it's missing:

```python
def parse_data_api_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    if 'records' not in response or not response['records']:
        return []
    
    records = response['records']
    column_metadata = response.get('columnMetadata', [])
    
    # If no column metadata, return empty list
    if not column_metadata:
        return []  # <-- This was being triggered
    
    # ... rest of parsing logic
```

## The Fix

Added `includeResultMetadata=True` to the RDS Data API call:

```python
# FIXED CODE
response = rds_client.execute_statement(
    resourceArn=DB_CLUSTER_ARN,
    secretArn=DB_SECRET_ARN,
    database=DB_NAME,
    sql=sql,
    includeResultMetadata=True  # <-- CRITICAL FIX
)
```

## Files Fixed

1. **src/lambda_workforce_router/lambda_handler.py**
   - Added `includeResultMetadata=True` to `execute_sql()` function
   - Added enhanced logging to show response structure

2. **src/lambda_workforce_availability_simulator/lambda_handler.py**
   - Added `includeResultMetadata=True` to `execute_sql()` function
   - Prevents same issue in simulator

## Why This Happened

The RDS Data API has two modes:
1. **Without metadata** (default): Returns just the raw values in arrays
2. **With metadata** (`includeResultMetadata=True`): Returns values + column names

The parsing function was written expecting mode 2, but the API call was using mode 1.

## Lessons Learned

1. **Always request metadata when parsing results**: The RDS Data API requires explicit opt-in for column metadata
2. **Test with real data early**: This issue would have been caught immediately with integration testing
3. **Add defensive logging**: The enhanced logging helped identify the exact failure point
4. **Check API documentation**: The boto3 RDS Data API docs clearly state that `includeResultMetadata` defaults to `False`

## Verification

After deploying the fix, the Lambda should return:

```json
{
  "statusCode": 200,
  "body": {
    "status": "success",
    "fault_type": "circuit_breaker_fault",
    "required_skill": "Substation Switchgear",
    "recommendations": [
      {
        "engineer_id": 9,
        "employee_id": "ENG009",
        "name": "Robert Taylor",
        "skills": [
          {
            "skill_name": "Substation Switchgear",
            "proficiency_level": "lead engineer"
          }
        ],
        "availability_status": "available",
        "location": {
          "latitude": 53.4084,
          "longitude": -2.9916
        }
      }
      // ... more engineers
    ],
    "total_available": 4
  }
}
```

## Deploy the Fix

```bash
# Rebuild both Lambda functions
sam build

# Deploy to AWS
sam deploy
```

## Related Issues Fixed

1. **SQL Query Error**: Fixed `SELECT DISTINCT` + `ORDER BY` PostgreSQL error (separate issue)
2. **Enhanced Logging**: Added debug logging to help troubleshoot future issues
3. **Better Error Messages**: Added debug_info to responses when no engineers found
