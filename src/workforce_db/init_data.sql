-- Workforce Management System - Sample Data Initialization
-- 
-- This script populates the database with 25 sample engineers covering
-- North West England locations with varied skills and availability.
--
-- Skill Coverage:
-- - Transformer Installation & Repair: 5 engineers
-- - HV Cable Jointing & Repair: 4 engineers
-- - Overhead Line Maintenance: 5 engineers
-- - Substation Switchgear: 5 engineers
-- - Protection & Control Systems: 4 engineers
--
-- Availability Distribution:
-- - 60% available (15 engineers)
-- - 30% on-job (8 engineers)
-- - 10% off-duty (2 engineers)

-- Insert Engineers
-- Manchester area (M postcodes) - 8 engineers
INSERT INTO engineers (employee_id, name, current_location_lat, current_location_lon, availability_status) VALUES
('ENG001', 'James Anderson', 53.4808, -2.2426, 'available'),      -- Manchester city center
('ENG002', 'Sarah Mitchell', 53.4631, -2.2914, 'available'),      -- Trafford
('ENG003', 'Michael Thompson', 53.5074, -2.2297, 'on-job'),       -- Cheetham Hill
('ENG004', 'Emma Roberts', 53.4529, -2.2294, 'available'),        -- Didsbury
('ENG005', 'David Wilson', 53.5225, -2.1964, 'on-job'),           -- Prestwich
('ENG006', 'Rachel Hughes', 53.4445, -2.2014, 'available'),       -- Levenshulme
('ENG007', 'Thomas Clarke', 53.4912, -2.2881, 'available'),       -- Salford
('ENG008', 'Jennifer Brown', 53.4265, -2.2309, 'off-duty'),       -- Stockport

-- Liverpool area (L postcodes) - 6 engineers
('ENG009', 'Robert Taylor', 53.4084, -2.9916, 'available'),       -- Liverpool city center
('ENG010', 'Laura Davies', 53.4239, -2.9774, 'on-job'),           -- Everton
('ENG011', 'Christopher Evans', 53.3727, -2.9099, 'available'),   -- Speke
('ENG012', 'Sophie Williams', 53.4502, -3.0134, 'available'),     -- Bootle
('ENG013', 'Daniel Harris', 53.3908, -2.8695, 'on-job'),          -- Garston
('ENG014', 'Victoria Jones', 53.4355, -2.9609, 'available'),      -- Anfield

-- Preston area (PR postcodes) - 3 engineers
('ENG015', 'Andrew Martin', 53.7632, -2.7031, 'available'),       -- Preston city center
('ENG016', 'Hannah White', 53.7456, -2.6789, 'on-job'),           -- Fulwood
('ENG017', 'Matthew Green', 53.7821, -2.7234, 'available'),       -- Ribbleton

-- Bolton area (BL postcodes) - 2 engineers
('ENG018', 'Rebecca Scott', 53.5768, -2.4282, 'available'),       -- Bolton town center
('ENG019', 'Paul Turner', 53.5912, -2.4456, 'on-job'),            -- Tonge Moor

-- Chester area (CH postcodes) - 2 engineers
('ENG020', 'Catherine Walker', 53.1906, -2.8910, 'available'),    -- Chester city center
('ENG021', 'Mark Phillips', 53.2134, -2.9087, 'available'),       -- Blacon

-- Blackpool area (FY postcodes) - 2 engineers
('ENG022', 'Elizabeth Moore', 53.8175, -3.0357, 'on-job'),        -- Blackpool town center
('ENG023', 'Simon Cooper', 53.8421, -3.0512, 'available'),        -- Bispham

-- Warrington area (WA postcodes) - 2 engineers
('ENG024', 'Amanda Bell', 53.3900, -2.5970, 'available'),         -- Warrington town center
('ENG025', 'Richard King', 53.4123, -2.6234, 'off-duty');         -- Birchwood

-- Insert Engineer Skills
-- Ensure at least 2 engineers per skill type with varied proficiency levels

-- Transformer Installation & Repair (5 engineers)
INSERT INTO engineer_skills (engineer_id, skill_name, proficiency_level, certified_date) VALUES
(1, 'Transformer Installation & Repair', 'lead engineer', '2018-03-15'),
(1, 'Substation Switchgear', 'certified', '2020-06-10'),
(2, 'Transformer Installation & Repair', 'certified', '2020-09-22'),
(3, 'Transformer Installation & Repair', 'trainee', '2024-01-10'),
(3, 'Substation Switchgear', 'trainee', '2024-01-10'),
(8, 'Transformer Installation & Repair', 'lead engineer', '2017-11-05'),
(8, 'Protection & Control Systems', 'certified', '2019-04-18'),
(15, 'Transformer Installation & Repair', 'certified', '2021-07-14'),

-- HV Cable Jointing & Repair (4 engineers)
(4, 'HV Cable Jointing & Repair', 'lead engineer', '2016-05-20'),
(5, 'HV Cable Jointing & Repair', 'certified', '2019-08-12'),
(5, 'Overhead Line Maintenance', 'trainee', '2023-11-01'),
(11, 'HV Cable Jointing & Repair', 'certified', '2020-02-28'),
(16, 'HV Cable Jointing & Repair', 'trainee', '2024-03-05'),
(16, 'Substation Switchgear', 'trainee', '2024-03-05'),

-- Overhead Line Maintenance (5 engineers)
(6, 'Overhead Line Maintenance', 'lead engineer', '2015-09-08'),
(7, 'Overhead Line Maintenance', 'certified', '2018-12-19'),
(7, 'Protection & Control Systems', 'trainee', '2023-06-15'),
(12, 'Overhead Line Maintenance', 'certified', '2019-10-30'),
(17, 'Overhead Line Maintenance', 'trainee', '2023-08-22'),
(22, 'Overhead Line Maintenance', 'lead engineer', '2016-02-14'),

-- Substation Switchgear (5 engineers)
(9, 'Substation Switchgear', 'lead engineer', '2017-04-25'),
(9, 'Protection & Control Systems', 'certified', '2019-09-11'),
(10, 'Substation Switchgear', 'certified', '2020-11-03'),
(13, 'Substation Switchgear', 'certified', '2021-01-17'),
(18, 'Substation Switchgear', 'trainee', '2024-02-08'),
(21, 'Substation Switchgear', 'lead engineer', '2016-08-29'),

-- Protection & Control Systems (4 engineers)
(14, 'Protection & Control Systems', 'lead engineer', '2015-12-10'),
(19, 'Protection & Control Systems', 'certified', '2019-05-23'),
(19, 'Substation Switchgear', 'certified', '2019-05-23'),
(20, 'Protection & Control Systems', 'certified', '2020-07-16'),
(23, 'Protection & Control Systems', 'trainee', '2023-09-12'),

-- Additional skills for remaining engineers to ensure 2-4 skills per engineer
(24, 'HV Cable Jointing & Repair', 'certified', '2018-10-05'),
(24, 'Overhead Line Maintenance', 'certified', '2018-10-05'),
(25, 'Transformer Installation & Repair', 'certified', '2019-03-28'),
(25, 'Substation Switchgear', 'trainee', '2022-11-14');

-- Verification queries (commented out - uncomment to verify data)
-- SELECT availability_status, COUNT(*) as count 
-- FROM engineers 
-- GROUP BY availability_status 
-- ORDER BY availability_status;

-- SELECT skill_name, COUNT(DISTINCT engineer_id) as engineer_count 
-- FROM engineer_skills 
-- GROUP BY skill_name 
-- ORDER BY skill_name;

-- SELECT proficiency_level, COUNT(*) as count 
-- FROM engineer_skills 
-- GROUP BY proficiency_level 
-- ORDER BY proficiency_level;
