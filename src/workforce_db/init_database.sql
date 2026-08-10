-- Workforce Management System - Complete Database Initialization
-- 
-- This script initializes the complete workforce management database
-- by running both schema creation and sample data population.
--
-- Usage:
--   For local PostgreSQL testing:
--     psql -U postgres -d workforce_db -f init_database.sql
--
--   For Aurora PostgreSQL via RDS Data API:
--     Use the AWS CLI or boto3 to execute this script
--
-- Note: This script will DROP existing tables if they exist.

\echo 'Starting workforce management database initialization...'
\echo ''

-- Step 1: Create schema
\echo 'Step 1: Creating database schema...'
\i schema.sql
\echo 'Schema created successfully.'
\echo ''

-- Step 2: Load sample data
\echo 'Step 2: Loading sample data...'
\i init_data.sql
\echo 'Sample data loaded successfully.'
\echo ''

-- Step 3: Verify data
\echo 'Step 3: Verifying data...'
\echo ''

\echo 'Engineer count by availability status:'
SELECT availability_status, COUNT(*) as count 
FROM engineers 
GROUP BY availability_status 
ORDER BY availability_status;

\echo ''
\echo 'Engineer count by skill:'
SELECT skill_name, COUNT(DISTINCT engineer_id) as engineer_count 
FROM engineer_skills 
GROUP BY skill_name 
ORDER BY skill_name;

\echo ''
\echo 'Skill count by proficiency level:'
SELECT proficiency_level, COUNT(*) as count 
FROM engineer_skills 
GROUP BY proficiency_level 
ORDER BY proficiency_level;

\echo ''
\echo 'Total engineers:'
SELECT COUNT(*) as total_engineers FROM engineers;

\echo ''
\echo 'Total skills assigned:'
SELECT COUNT(*) as total_skills FROM engineer_skills;

\echo ''
\echo 'Database initialization complete!'
