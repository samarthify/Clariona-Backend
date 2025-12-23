-- Initialize PostgreSQL database with required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create database user for application (optional)
-- CREATE USER govintel_user WITH PASSWORD 'govintel_password';
-- GRANT ALL PRIVILEGES ON DATABASE govintel TO govintel_user;
