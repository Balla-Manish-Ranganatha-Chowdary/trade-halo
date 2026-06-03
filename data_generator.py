import pandas as pd
import numpy as np
import uuid
import os

# Set random seed for reproducibility
np.random.seed(42)

# Bounding box for Bengaluru, India
LAT_MIN, LAT_MAX = 12.85, 13.15
LON_MIN, LON_MAX = 77.45, 77.75

def generate_noise(lat_array, lon_array, scale=0.1, octaves=4):
    """Simple pseudo-perlin noise alternative using sine waves for spatial clustering"""
    noise = np.zeros_like(lat_array)
    for i in range(octaves):
        freq = 2 ** i
        amp = scale ** i
        noise += np.sin(lat_array * freq * 100) * np.cos(lon_array * freq * 100) * amp
    return noise

def generate_demand_points(n=8000):
    print("Generating demand points...")
    lats = np.random.uniform(LAT_MIN, LAT_MAX, n)
    lons = np.random.uniform(LON_MIN, LON_MAX, n)
    
    # Base weight using spatial clustering (noise)
    base_weight = np.abs(generate_noise(lats, lons)) * 100
    
    df = pd.DataFrame({
        'demand_id': [str(uuid.uuid4()) for _ in range(n)],
        'lat': lats,
        'lon': lons,
        'weight': np.clip(base_weight + np.random.normal(10, 5, n), 1, 200),
        'freq': np.random.choice([1, 2, 4, 12, 52], size=n, p=[0.4, 0.3, 0.15, 0.1, 0.05]), # 1 to 52 times a year
        'target_pop_ratio': np.random.uniform(0.1, 0.6, n), # % of local pop that is target demo
        'affluence_index': np.clip(np.abs(generate_noise(lats, lons, scale=0.2)) + np.random.uniform(0, 0.5, n), 0, 1),
        'working_ratio': np.random.uniform(0.3, 0.8, n),
        'student_density': np.random.exponential(scale=0.1, size=n).clip(0, 0.5)
    })
    return df

def generate_competitors(n=300):
    print("Generating competitors...")
    lats = np.random.uniform(LAT_MIN, LAT_MAX, n)
    lons = np.random.uniform(LON_MIN, LON_MAX, n)
    
    df = pd.DataFrame({
        'competitor_id': [str(uuid.uuid4()) for _ in range(n)],
        'lat': lats,
        'lon': lons,
        'capacity': np.random.normal(500, 150, n).clip(100, 1500), # Customers served per month
        'utilization': np.random.uniform(0.5, 1.0, n),
        'tier': np.random.choice(['budget', 'mid', 'premium'], size=n, p=[0.5, 0.3, 0.2]),
        'years_operating': np.random.exponential(scale=3, size=n).clip(0, 20)
    })
    return df

def generate_own_stores(n=10):
    print("Generating existing own stores...")
    lats = np.random.uniform(LAT_MIN, LAT_MAX, n)
    lons = np.random.uniform(LON_MIN, LON_MAX, n)
    
    df = pd.DataFrame({
        'store_id': [str(uuid.uuid4()) for _ in range(n)],
        'lat': lats,
        'lon': lons,
        'monthly_revenue': np.random.normal(2000000, 500000, n).clip(500000, None)
    })
    return df

def generate_candidate_locations(n=200):
    print("Generating candidate nodes...")
    lats = np.random.uniform(LAT_MIN, LAT_MAX, n)
    lons = np.random.uniform(LON_MIN, LON_MAX, n)
    
    df = pd.DataFrame({
        'candidate_id': [str(uuid.uuid4()) for _ in range(n)],
        'name': [f"TradeHalo Node {i+1}" for i in range(n)],
        'lat': lats,
        'lon': lons,
        'rent_index': np.clip(np.abs(generate_noise(lats, lons, scale=0.3)) * 50 + 50, 20, 200), # Rent per sqft
        'property_price_local': np.random.normal(8000, 2000, n).clip(3000, 20000), # per sqft
        'avg_wage_local': np.random.normal(20000, 3000, n).clip(12000, 35000),
        'outage_rate': np.random.beta(2, 10, n), # power outage freq
        'setup_cost': np.random.normal(1500000, 300000, n).clip(500000, 3000000),
        'future_pop_growth_rate': np.random.normal(0.05, 0.03, n).clip(-0.02, 0.15),
        'planned_sqft_office': np.random.exponential(scale=500000, size=n).clip(0, 3000000),
        'dist_to_metro': np.random.exponential(scale=2, size=n).clip(0, 10), # km
        'road_width_current': np.random.choice([10, 20, 30, 40, 60], size=n), # ft
        'flood_days_per_year': np.random.poisson(lam=1, size=n).clip(0, 10),
        'parking_spots_200m': np.random.poisson(lam=20, size=n).clip(0, 100),
        'daily_pedestrian_count': np.random.normal(5000, 2000, n).clip(500, 20000)
    })
    return df

if __name__ == "__main__":
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    demand_df = generate_demand_points(10000)
    comp_df = generate_competitors(350)
    stores_df = generate_own_stores(15)
    candidates_df = generate_candidate_locations(250)
    
    demand_df.to_csv(os.path.join(data_dir, 'demand_points.csv'), index=False)
    comp_df.to_csv(os.path.join(data_dir, 'competitors.csv'), index=False)
    stores_df.to_csv(os.path.join(data_dir, 'stores.csv'), index=False)
    candidates_df.to_csv(os.path.join(data_dir, 'candidates.csv'), index=False)
    
    print("Bengaluru synthetic data generation complete!")
