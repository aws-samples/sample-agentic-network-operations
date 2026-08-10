# Workforce Management Database

This directory contains the database schema and initialization scripts for the Workforce Management System.

## Files

- `schema.sql` - Database schema definition (tables, constraints, indexes)
- `init_data.sql` - Sample data for 25 engineers with skills and availability
- `init_database.sql` - Combined script that runs both schema and data initialization

## Database Schema

### Engineers Table

Stores engineer profiles with availability status and location.

**Columns:**
- `engineer_id` - Primary key (auto-increment)
- `employee_id` - Unique employee identifier (e.g., ENG001)
- `name` - Full name of the engineer
- `current_location_lat` - Current latitude coordinate
- `current_location_lon` - Current longitude coordinate
- `availability_status` - Current availability: `available`, `on-job`, or `off-duty`
- `status_updated_at` - Timestamp of last status change
- `created_at` - Timestamp when profile was created

**Constraints:**
- `UNIQUE` constraint on `employee_id`
- `CHECK` constraint on `availability_status` (must be one of: available, on-job, off-duty)

### Engineer Skills Table

Stores multiple skills per engineer with proficiency levels.

**Columns:**
- `skill_id` - Primary key (auto-increment)
- `engineer_id` - Foreign key to engineers table
- `skill_name` - Name of the skill (e.g., "Transformer Installation & Repair")
- `proficiency_level` - Proficiency: `lead engineer`, `certified`, or `trainee`
- `certified_date` - Date when engineer was certified for this skill
- `created_at` - Timestamp when skill was added

**Constraints:**
- `FOREIGN KEY` to engineers table with `ON DELETE CASCADE`
- `CHECK` constraint on `proficiency_level` (must be one of: lead engineer, certified, trainee)
- `UNIQUE` constraint on `(engineer_id, skill_name)` to prevent duplicate skills per engineer

## Sample Data

The initialization script creates 25 engineers covering North West England:

### Geographic Distribution
- Manchester area (M postcodes): 8 engineers
- Liverpool area (L postcodes): 6 engineers
- Preston area (PR postcodes): 3 engineers
- Bolton area (BL postcodes): 2 engineers
- Chester area (CH postcodes): 2 engineers
- Blackpool area (FY postcodes): 2 engineers
- Warrington area (WA postcodes): 2 engineers

### Skill Coverage
Each skill type has at least 2 engineers to ensure fault coverage:
- Transformer Installation & Repair: 5 engineers
- HV Cable Jointing & Repair: 4 engineers
- Overhead Line Maintenance: 5 engineers
- Substation Switchgear: 5 engineers
- Protection & Control Systems: 4 engineers

### Availability Distribution
- 60% available (15 engineers)
- 30% on-job (8 engineers)
- 10% off-duty (2 engineers)

### Skills per Engineer
Each engineer has 2-4 skills with varied proficiency levels to create realistic scenarios.

## Usage

### Local PostgreSQL Testing

```bash
# Create database
createdb workforce_db

# Initialize schema and data
psql -U postgres -d workforce_db -f init_database.sql
```

### Aurora PostgreSQL Serverless v2 (Recommended)

Use the provided Python initialization script for Aurora PostgreSQL with RDS Data API:

```bash
# Using CloudFormation stack outputs (recommended)
python init_aurora_db.py \
  --cluster-arn $(aws cloudformation describe-stacks \
    --stack-name nw-england-electricity-network \
    --query 'Stacks[0].Outputs[?OutputKey==`WorkforceDBClusterArn`].OutputValue' \
    --output text) \
  --secret-arn $(aws cloudformation describe-stacks \
    --stack-name nw-england-electricity-network \
    --query 'Stacks[0].Outputs[?OutputKey==`WorkforceDBSecretArn`].OutputValue' \
    --output text)

# Or with explicit ARNs
python init_aurora_db.py \
  --cluster-arn arn:aws:rds:us-east-1:ACCOUNT:cluster:workforce-db \
  --secret-arn arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:workforce-db-secret \
  --region us-east-1
```

The script will:
1. Create the database schema (tables, constraints, indexes)
2. Load 25 sample engineers with skills and availability
3. Run verification queries to confirm setup
4. Display a summary of the initialization

### Manual AWS CLI Method

If you prefer to use the AWS CLI directly:

```bash
# Execute schema
aws rds-data execute-statement \
  --resource-arn "arn:aws:rds:us-east-1:ACCOUNT:cluster:workforce-db" \
  --secret-arn "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:workforce-db-secret" \
  --database "workforce_db" \
  --sql "$(cat schema.sql)"

# Execute data initialization
aws rds-data execute-statement \
  --resource-arn "arn:aws:rds:us-east-1:ACCOUNT:cluster:workforce-db" \
  --secret-arn "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:workforce-db-secret" \
  --database "workforce_db" \
  --sql "$(cat init_data.sql)"
```

## Verification Queries

After initialization, verify the data:

```sql
-- Check availability distribution
SELECT availability_status, COUNT(*) as count 
FROM engineers 
GROUP BY availability_status 
ORDER BY availability_status;

-- Check skill coverage
SELECT skill_name, COUNT(DISTINCT engineer_id) as engineer_count 
FROM engineer_skills 
GROUP BY skill_name 
ORDER BY skill_name;

-- Check proficiency distribution
SELECT proficiency_level, COUNT(*) as count 
FROM engineer_skills 
GROUP BY proficiency_level 
ORDER BY proficiency_level;

-- List all engineers with their skills
SELECT 
    e.employee_id,
    e.name,
    e.availability_status,
    es.skill_name,
    es.proficiency_level
FROM engineers e
LEFT JOIN engineer_skills es ON e.engineer_id = es.engineer_id
ORDER BY e.employee_id, es.skill_name;
```

## Requirements Validation

This schema satisfies the following requirements:

- **Requirement 1.1**: Engineer profiles include name, employee ID, and current location
- **Requirement 1.2**: Database validates all required fields are present
- **Requirement 1.3**: Multiple skills per engineer with proficiency levels
- **Requirement 1.4**: Status changes update timestamp
- **Requirement 1.5**: Availability states maintained (available, on-job, off-duty)

## Notes

- The schema uses `SERIAL` for auto-incrementing primary keys
- Timestamps use `TIMESTAMP WITH TIME ZONE` for proper timezone handling
- Foreign key constraints use `ON DELETE CASCADE` to maintain referential integrity
- Indexes are created on frequently queried columns for performance
- Check constraints enforce valid enum values at the database level
- **RDS Data API Limitation**: The Data API doesn't support multi-statement execution, so the initialization script automatically splits SQL files into individual statements and executes them sequentially
