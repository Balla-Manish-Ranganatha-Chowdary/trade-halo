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
    noise = np.zeros_like(lat_array)
    for i in range(octaves):
        freq = 2 ** i
        amp = scale ** i
        noise += np.sin(lat_array * freq * 100) * np.cos(lon_array * freq * 100) * amp
    return noise

def generate_demand_points(n=10000):
    print("Generating demand points...")
    lats = np.random.uniform(LAT_MIN, LAT_MAX, n)
    lons = np.random.uniform(LON_MIN, LON_MAX, n)
    base_weight = np.abs(generate_noise(lats, lons)) * 100
    
    df = pd.DataFrame({
        'point_id': [str(uuid.uuid4()) for _ in range(n)],
        'lat': lats,
        'lng': lons,
        'weight': np.clip(base_weight + np.random.normal(10, 5, n), 1, 200),
        'freq_index': np.random.choice([0.5, 1.0, 1.5, 2.0], size=n, p=[0.2, 0.4, 0.3, 0.1]),
        'ward': np.random.choice([f"Ward_{i}" for i in range(1, 200)], size=n),
        'target_pop': np.random.normal(500, 150, n).clip(100, 1000),
        'total_pop': np.random.normal(2000, 500, n).clip(500, 5000),
        'car_density': np.random.uniform(0.1, 0.8, n),
        'employed': np.random.normal(1000, 300, n).clip(200, 3000),
        'seasonality_index': np.random.uniform(0.8, 1.2, n)
    })
    return df

def generate_competitors(n=350):
    print("Generating competitors...")
    lats = np.random.uniform(LAT_MIN, LAT_MAX, n)
    lons = np.random.uniform(LON_MIN, LON_MAX, n)
    competitor_brands = ["Starbucks", "Third Wave Coffee", "Blue Tokai", "Costa Coffee", "Cafe Coffee Day"]
    
    df = pd.DataFrame({
        'competitor_id': [str(uuid.uuid4()) for _ in range(n)],
        'brand_name': np.random.choice(competitor_brands, size=n),
        'lat': lats,
        'lng': lons,
        'brand_tier': np.random.choice([1, 2, 3], size=n, p=[0.5, 0.3, 0.2]),
        'capacity': np.random.normal(500, 150, n).clip(100, 1500),
        'utilization': np.random.uniform(0.5, 1.0, n),
        'years_operating': np.random.exponential(scale=3, size=n).clip(0.1, 20)
    })
    return df

def generate_own_stores(n=15):
    print("Generating existing own stores...")
    lats = np.random.uniform(LAT_MIN, LAT_MAX, n)
    lons = np.random.uniform(LON_MIN, LON_MAX, n)
    neighborhoods = ["Indiranagar", "Koramangala", "Whitefield", "Jayanagar", "HSR Layout", "Malleshwaram", "JP Nagar", "Marathahalli", "Electronic City", "BTM Layout", "Banashankari", "Rajajinagar", "Bellandur", "Hebbal", "Yelahanka", "MG Road"]
    
    df = pd.DataFrame({
        'store_id': [str(uuid.uuid4()) for _ in range(n)],
        'name': [f"TradeHalo {np.random.choice(neighborhoods)}" for _ in range(n)],
        'lat': lats,
        'lng': lons,
        'city': 'Bengaluru',
        'monthly_revenue': np.random.normal(2000000, 500000, n).clip(500000, None)
    })
    return df

def generate_candidates(n=250):
    print("Generating candidate locations...")
    lats = np.random.uniform(LAT_MIN, LAT_MAX, n)
    lons = np.random.uniform(LON_MIN, LON_MAX, n)
    neighborhoods = ["Indiranagar", "Koramangala", "Whitefield", "Jayanagar", "HSR Layout", "Malleshwaram", "JP Nagar", "Marathahalli", "Electronic City", "BTM Layout", "Banashankari", "Rajajinagar", "Bellandur", "Hebbal", "Yelahanka", "MG Road", "Frazer Town", "Sadashivanagar", "Basavanagudi", "Ulsoor"]
    
    df = pd.DataFrame({
        'location_id': [str(uuid.uuid4()) for _ in range(n)],
        'name': [f"TradeHalo {np.random.choice(neighborhoods)} Candidate" for _ in range(n)],
        'lat': lats,
        'lng': lons,
        # Operating Costs
        'rent_index': np.random.normal(1.0, 0.2, n).clip(0.5, 2.0),
        'property_val_local': np.random.normal(12000, 3000, n).clip(5000, 25000),
        'city_avg_prop': 10000,
        'avg_wage_local': np.random.normal(22000, 2000, n).clip(15000, 35000),
        'avg_wage_city': 20000,
        'outage_rate': np.random.beta(2, 10, n),
        'setup_cost': np.random.normal(1500000, 300000, n).clip(500000, 3000000),
        'monthly_margin': np.random.normal(300000, 50000, n).clip(100000, 800000),
        'monthly_opex': np.random.normal(500000, 100000, n).clip(200000, 1500000),
        'avg_spend': 500,
        # Forward Looking
        'units_approved': np.random.poisson(lam=100, size=n).clip(0, 500),
        'avg_hh_size': 3.5,
        'footfall_gain': np.random.exponential(scale=5000, size=n).clip(0, 30000),
        'metro_multiplier': np.random.choice([1.0, 1.2, 1.5], size=n, p=[0.7, 0.2, 0.1]),
        'pop_growth': np.random.normal(0.05, 0.03, n).clip(-0.02, 0.15),
        'student_demand': np.random.exponential(scale=500, size=n).clip(0, 5000),
        'hosp_footfall': np.random.exponential(scale=300, size=n).clip(0, 2000),
        'zoning_flag': np.random.choice([0, 1], size=n, p=[0.9, 0.1]),
        # Spatial & Accessibility
        'width_future': np.random.choice([20, 40, 60], size=n),
        'width_current': np.random.choice([20, 40, 60], size=n),
        'dist_to_transit_hub': np.random.exponential(scale=3, size=n).clip(0.1, 15),
        'connectivity': np.random.uniform(0.5, 1.5, n),
        'expected_car_cust': np.random.poisson(lam=50, size=n).clip(10, 200),
        'pedestrian_count': np.random.normal(5000, 2000, n).clip(500, 20000),
        'vehicle_count': np.random.normal(10000, 3000, n).clip(1000, 30000),
        'road_frontage': np.random.normal(30, 10, n).clip(10, 100),
        'max_signage_ht': np.random.choice([10, 20, 30], size=n),
        'flood_days': np.random.poisson(lam=1, size=n).clip(0, 10),
        'daily_rev_lost': np.random.normal(10000, 2000, n).clip(5000, 30000),
        'event_footfall': np.random.exponential(scale=1000, size=n).clip(0, 10000),
        'parking_spots_200m': np.random.poisson(lam=20, size=n).clip(0, 100),
        # Business logic
        'store_fmt': np.random.uniform(0, 1, n)
    })
    return df

if __name__ == "__main__":
    data_dir = os.path.join(os.path.dirname(__file__), '../data')
    os.makedirs(data_dir, exist_ok=True)
    
    demand_df = generate_demand_points(10000)
    comp_df = generate_competitors(350)
    stores_df = generate_own_stores(15)
    candidates_df = generate_candidates(250)
    
    demand_df.to_csv(os.path.join(data_dir, 'demand_points.csv'), index=False)
    comp_df.to_csv(os.path.join(data_dir, 'competitors.csv'), index=False)
    stores_df.to_csv(os.path.join(data_dir, 'stores.csv'), index=False)
    candidates_df.to_csv(os.path.join(data_dir, 'candidates.csv'), index=False)
    
    print("Bengaluru synthetic data generation complete for all 58 features!")
