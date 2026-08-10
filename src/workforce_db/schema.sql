-- Workforce Management System Database Schema
-- Aurora PostgreSQL Serverless v2
-- 
-- This schema defines the engineer profiles and skills tables for the
-- workforce management system that supports engineer dispatch for
-- electricity distribution network operations.

-- Drop tables if they exist (for clean re-initialization)
DROP TABLE IF EXISTS engineer_skills CASCADE;
DROP TABLE IF EXISTS engineers CASCADE;

-- Engineers Table
-- Stores engineer profiles with availability status and location
CREATE TABLE engineers (
    engineer_id SERIAL PRIMARY KEY,
    employee_id VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    current_location_lat DECIMAL(10, 8),
    current_location_lon DECIMAL(11, 8),
    availability_status VARCHAR(20) NOT NULL DEFAULT 'available',
    status_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraint: availability_status must be one of the valid enum values
    CONSTRAINT chk_availability CHECK (
        availability_status IN ('available', 'on-job', 'off-duty')
    )
);

-- Create index on availability_status for faster queries
CREATE INDEX idx_engineers_availability ON engineers(availability_status);

-- Create index on employee_id for lookups
CREATE INDEX idx_engineers_employee_id ON engineers(employee_id);

-- Engineer Skills Table
-- Stores multiple skills per engineer with proficiency levels
CREATE TABLE engineer_skills (
    skill_id SERIAL PRIMARY KEY,
    engineer_id INTEGER NOT NULL REFERENCES engineers(engineer_id) ON DELETE CASCADE,
    skill_name VARCHAR(100) NOT NULL,
    proficiency_level VARCHAR(20) NOT NULL,
    certified_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraint: proficiency_level must be one of the valid enum values
    CONSTRAINT chk_proficiency CHECK (
        proficiency_level IN ('lead engineer', 'certified', 'trainee')
    ),
    
    -- Constraint: prevent duplicate skills for same engineer
    UNIQUE (engineer_id, skill_name)
);

-- Create index on engineer_id for faster joins
CREATE INDEX idx_engineer_skills_engineer_id ON engineer_skills(engineer_id);

-- Create index on skill_name for faster skill-based queries
CREATE INDEX idx_engineer_skills_skill_name ON engineer_skills(skill_name);

-- Create composite index for skill + proficiency queries
CREATE INDEX idx_engineer_skills_skill_proficiency ON engineer_skills(skill_name, proficiency_level);

-- Comments for documentation
COMMENT ON TABLE engineers IS 'Engineer profiles with availability status and location';
COMMENT ON TABLE engineer_skills IS 'Skills and proficiency levels for each engineer';

COMMENT ON COLUMN engineers.engineer_id IS 'Primary key, auto-incrementing';
COMMENT ON COLUMN engineers.employee_id IS 'Unique employee identifier (e.g., ENG001)';
COMMENT ON COLUMN engineers.name IS 'Full name of the engineer';
COMMENT ON COLUMN engineers.current_location_lat IS 'Current latitude coordinate';
COMMENT ON COLUMN engineers.current_location_lon IS 'Current longitude coordinate';
COMMENT ON COLUMN engineers.availability_status IS 'Current availability: available, on-job, or off-duty';
COMMENT ON COLUMN engineers.status_updated_at IS 'Timestamp of last status change';
COMMENT ON COLUMN engineers.created_at IS 'Timestamp when profile was created';

COMMENT ON COLUMN engineer_skills.skill_id IS 'Primary key, auto-incrementing';
COMMENT ON COLUMN engineer_skills.engineer_id IS 'Foreign key to engineers table';
COMMENT ON COLUMN engineer_skills.skill_name IS 'Name of the skill (e.g., Transformer Installation & Repair)';
COMMENT ON COLUMN engineer_skills.proficiency_level IS 'Proficiency: lead engineer, certified, or trainee';
COMMENT ON COLUMN engineer_skills.certified_date IS 'Date when engineer was certified for this skill';
COMMENT ON COLUMN engineer_skills.created_at IS 'Timestamp when skill was added';
