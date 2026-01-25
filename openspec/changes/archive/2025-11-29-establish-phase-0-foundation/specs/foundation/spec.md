# Spec: Foundation

## ADDED Requirements

### Requirement: Project Structure
The project MUST adhere to the defined layered architecture to ensure separation of concerns.

#### Scenario: Directory Structure Verification
Given a fresh clone of the repository
When I list the `app` directory
Then I should see `api`, `services`, `interfaces`, `infrastructure`, and `core` directories
And `interfaces` should contain abstract base classes
And `infrastructure` should contain concrete implementations

### Requirement: Development Environment
A containerized development environment MUST be provided for consistent setup.

#### Scenario: Docker Compose Startup
Given I have Docker installed
When I run `docker-compose -f docker-compose.dev.yml up -d`
Then Postgres, Redis, and MinIO containers should be running
And I should be able to connect to Postgres on port 5432
And I should be able to access MinIO console on port 9001

### Requirement: Database Management
Database schema changes MUST be managed via migration scripts.

#### Scenario: Apply Initial Migration
Given the Postgres database is running
When I run `alembic upgrade head`
Then the `post_analytics` table should be created in the database
And the table should have the correct columns and indexes

