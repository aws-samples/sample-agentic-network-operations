#!/bin/bash
# Validate SQL syntax using PostgreSQL (if available)
#
# This script checks if PostgreSQL is installed and validates the SQL files.
# If PostgreSQL is not available, it performs basic syntax checks.

set -e

echo "=================================================="
echo "SQL Validation for Workforce Management Database"
echo "=================================================="
echo ""

# Check if psql is available
if command -v psql &> /dev/null; then
    echo "✓ PostgreSQL client found"
    echo ""
    
    # Check if we can connect to a local PostgreSQL instance
    if psql -U postgres -c "SELECT version();" &> /dev/null; then
        echo "✓ Local PostgreSQL instance available"
        echo ""
        
        # Create temporary test database
        echo "Creating temporary test database..."
        psql -U postgres -c "DROP DATABASE IF EXISTS workforce_db_test;" &> /dev/null || true
        psql -U postgres -c "CREATE DATABASE workforce_db_test;" &> /dev/null
        
        # Test schema.sql
        echo "Validating schema.sql..."
        if psql -U postgres -d workforce_db_test -f schema.sql &> /dev/null; then
            echo "✓ schema.sql is valid"
        else
            echo "✗ schema.sql has errors"
            psql -U postgres -d workforce_db_test -f schema.sql
            exit 1
        fi
        
        # Test init_data.sql
        echo "Validating init_data.sql..."
        if psql -U postgres -d workforce_db_test -f init_data.sql &> /dev/null; then
            echo "✓ init_data.sql is valid"
        else
            echo "✗ init_data.sql has errors"
            psql -U postgres -d workforce_db_test -f init_data.sql
            exit 1
        fi
        
        # Run verification queries
        echo ""
        echo "Running verification queries..."
        echo ""
        
        echo "Total engineers:"
        psql -U postgres -d workforce_db_test -c "SELECT COUNT(*) FROM engineers;"
        
        echo ""
        echo "Total skills:"
        psql -U postgres -d workforce_db_test -c "SELECT COUNT(*) FROM engineer_skills;"
        
        echo ""
        echo "Availability distribution:"
        psql -U postgres -d workforce_db_test -c "SELECT availability_status, COUNT(*) FROM engineers GROUP BY availability_status ORDER BY availability_status;"
        
        echo ""
        echo "Skill coverage:"
        psql -U postgres -d workforce_db_test -c "SELECT skill_name, COUNT(DISTINCT engineer_id) FROM engineer_skills GROUP BY skill_name ORDER BY skill_name;"
        
        # Clean up
        echo ""
        echo "Cleaning up test database..."
        psql -U postgres -c "DROP DATABASE workforce_db_test;" &> /dev/null
        
        echo ""
        echo "=================================================="
        echo "✓ ALL SQL FILES ARE VALID"
        echo "=================================================="
        
    else
        echo "⚠ Cannot connect to local PostgreSQL instance"
        echo "  Skipping full validation"
        echo ""
        echo "Performing basic syntax checks..."
        
        # Basic syntax checks
        if grep -q "CREATE TABLE" schema.sql && grep -q "INSERT INTO" init_data.sql; then
            echo "✓ Basic syntax checks passed"
        else
            echo "✗ Basic syntax checks failed"
            exit 1
        fi
    fi
else
    echo "⚠ PostgreSQL client not found"
    echo "  Skipping validation"
    echo ""
    echo "To install PostgreSQL:"
    echo "  macOS: brew install postgresql"
    echo "  Ubuntu: sudo apt-get install postgresql-client"
    echo ""
    echo "Performing basic file checks..."
    
    # Check files exist
    if [ -f "schema.sql" ] && [ -f "init_data.sql" ]; then
        echo "✓ All SQL files present"
    else
        echo "✗ Missing SQL files"
        exit 1
    fi
fi
