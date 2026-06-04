-- ==============================================================================
-- TASK 1: MYSQL DATABASE SCHEMA FOR TRADEHALO (MULTI-TENANT SPATIAL DESIGN)
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS tradehalo;
USE tradehalo;

-- ------------------------------------------------------------------------------
-- 1. TENANTS TABLE (Handling Multiple Brands)
-- ------------------------------------------------------------------------------
-- Central table for SaaS architecture. Every other table relies on tenant_id
-- to strictly isolate data between competing brands (e.g., Starbucks vs Dunkin).
CREATE TABLE tenants (
    tenant_id BINARY(16) PRIMARY KEY, -- UUIDv4 stored as binary for fast indexing
    brand_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_brand_name (brand_name)
);

-- ------------------------------------------------------------------------------
-- 2. STORES TABLE
-- ------------------------------------------------------------------------------
-- Stores candidate locations and existing locations for a specific tenant.
CREATE TABLE stores (
    store_id BINARY(16) PRIMARY KEY,
    tenant_id BINARY(16) NOT NULL,
    is_existing_store BOOLEAN DEFAULT FALSE,
    name VARCHAR(255) NOT NULL,
    
    -- Spatial Data
    location POINT NOT NULL SRID 4326,
    
    -- Scores and Metrics (Compound Opportunity Score)
    compound_opportunity_score FLOAT,
    ml_attractiveness_score FLOAT,
    rent_index FLOAT,
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    
    -- Composite index to instantly query stores for a specific tenant
    INDEX idx_tenant_store (tenant_id, is_existing_store),
    
    -- SPATIAL INDEX for fast bounding-box geographic queries
    SPATIAL INDEX idx_store_location (location)
);

-- ------------------------------------------------------------------------------
-- 3. COMPETITOR DATA TABLE
-- ------------------------------------------------------------------------------
-- Stores rival locations. Notice tenant_id allows each brand to define who 
-- *their* specific competitors are (e.g. KFC's competitors differ from Zara's).
CREATE TABLE competitors (
    competitor_id BINARY(16) PRIMARY KEY,
    tenant_id BINARY(16) NOT NULL,
    brand_name VARCHAR(100) NOT NULL,
    brand_tier INT DEFAULT 2,
    location POINT NOT NULL SRID 4326,
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    
    -- Combined index to fetch a tenant's competitors instantly
    INDEX idx_tenant_competitor (tenant_id, brand_tier),
    SPATIAL INDEX idx_comp_location (location)
);

-- ------------------------------------------------------------------------------
-- 4. CATCHMENTS TABLE (Intersection Mapping)
-- ------------------------------------------------------------------------------
-- Because catchments can change dynamically, we store the aggregated catchment 
-- metrics directly linked to the store. For massive-scale mapping, linking 
-- individual demand nodes to a store is a Many-to-Many relationship.
CREATE TABLE store_catchments (
    catchment_id BINARY(16) PRIMARY KEY,
    store_id BINARY(16) NOT NULL,
    tenant_id BINARY(16) NOT NULL,
    
    radius_km FLOAT NOT NULL DEFAULT 3.0,
    total_demand_reached FLOAT NOT NULL,
    competitor_count INT NOT NULL,
    cannibalization_risk_demand FLOAT NOT NULL,
    
    -- Store the geographic polygon of the catchment for direct Map rendering
    catchment_polygon POLYGON NOT NULL SRID 4326,
    
    FOREIGN KEY (store_id) REFERENCES stores(store_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    
    INDEX idx_tenant_catchment (tenant_id, store_id),
    SPATIAL INDEX idx_catchment_poly (catchment_polygon)
);

-- ------------------------------------------------------------------------------
-- PRIMARY KEY & INDEXING STRATEGY NOTES:
-- ------------------------------------------------------------------------------
-- 1. Primary Keys: I used BINARY(16) instead of VARCHAR(36) for UUIDs. 
--    UUIDs are 128-bit. Storing them as BINARY(16) takes 16 bytes vs 36 bytes 
--    for a string, drastically reducing index memory size and improving JOIN speeds.
--
-- 2. Multi-Tenancy: Every table includes `tenant_id`. Queries MUST include 
--    `WHERE tenant_id = ?` to strictly isolate brand data. 
--    I added composite indexes like `(tenant_id, is_existing_store)` so the DB 
--    doesn't have to scan the entire table to find one brand's stores.
--
-- 3. Spatial Indexes: I utilized MySQL 8.0's `SRID 4326` (GPS Coordinates) and 
--    `SPATIAL INDEX`. This allows us to use `ST_Distance_Sphere` and `ST_Contains` 
--    to execute geospatial math entirely at the database layer in O(log N) time 
--    using an R-Tree, perfectly replacing the Python Haversine loops.
