-- Task 1: Data Model Design
-- This schema represents the multi-tenant database for the HashConnect RetailCX platform.
-- We use MySQL 8.0 features, specifically the SPATIAL INDEX on POINT columns.

-- 1. Brands (Tenants)
CREATE TABLE brands (
    brand_id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Stores (Deployment Nodes)
CREATE TABLE stores (
    store_id VARCHAR(36) PRIMARY KEY,
    brand_id VARCHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    coordinates POINT SRID 4326 NOT NULL,
    city VARCHAR(100),
    FOREIGN KEY (brand_id) REFERENCES brands(brand_id),
    SPATIAL INDEX idx_store_coords (coordinates),
    INDEX idx_store_city (city)
);

-- 3. Competitors
CREATE TABLE competitors (
    competitor_id VARCHAR(36) PRIMARY KEY,
    brand_id VARCHAR(36) NOT NULL,
    coordinates POINT SRID 4326 NOT NULL,
    FOREIGN KEY (brand_id) REFERENCES brands(brand_id),
    SPATIAL INDEX idx_comp_coords (coordinates)
);

-- 4. Demand Points (Granular populations/grids)
CREATE TABLE demand_points (
    point_id VARCHAR(36) PRIMARY KEY,
    brand_id VARCHAR(36) NOT NULL, -- Allows custom demand grids per tenant if needed
    coordinates POINT SRID 4326 NOT NULL,
    weight DECIMAL(10,4) NOT NULL COMMENT 'Magnitude of demand (e.g., revenue leakage proxy)',
    FOREIGN KEY (brand_id) REFERENCES brands(brand_id),
    SPATIAL INDEX idx_demand_coords (coordinates)
);

-- 5. Catchments & Opportunity Scores (Materialized view/Computed results)
CREATE TABLE catchments (
    catchment_id VARCHAR(36) PRIMARY KEY,
    store_id VARCHAR(36) NOT NULL,
    radius_km DECIMAL(6,2) DEFAULT 3.00,
    demand_reached DECIMAL(12,4) DEFAULT 0.0000,
    competitor_count INT DEFAULT 0,
    self_overlap_count INT DEFAULT 0, -- Overlap with sister stores
    opportunity_score DECIMAL(8,4),
    FOREIGN KEY (store_id) REFERENCES stores(store_id),
    INDEX idx_catchment_store (store_id),
    INDEX idx_opportunity_score (opportunity_score DESC) -- Useful for the ranked dashboard
);
