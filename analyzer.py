import pandas as pd
import numpy as np
import os
import xgboost as xgb
from scipy.spatial import cKDTree
from sklearn.cluster import DBSCAN

# --- HIGH PERFORMANCE SPATIAL MATH (O(log N) Stretch Goal) ---
EARTH_RADIUS = 6371.0

def latlon_to_cartesian(lat, lon):
    """Convert Lat/Lng to 3D Cartesian coordinates for cKDTree."""
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)
    x = EARTH_RADIUS * np.cos(lat_rad) * np.cos(lon_rad)
    y = EARTH_RADIUS * np.cos(lat_rad) * np.sin(lon_rad)
    z = EARTH_RADIUS * np.sin(lat_rad)
    return np.column_stack((x, y, z))

def build_tree(df):
    """Build a cKDTree from a DataFrame containing 'lat' and 'lng'."""
    coords = latlon_to_cartesian(df['lat'].values, df['lng'].values)
    return cKDTree(coords), coords

def min_max_scale(series, invert=False):
    mi, ma = series.min(), series.max()
    if ma == mi: return np.zeros(len(series)) + 0.5
    scaled = (series - mi) / (ma - mi)
    return 1.0 - scaled if invert else scaled

if __name__ == "__main__":
    print("Starting 58-Feature Analysis with cKDTree Optimization...")
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    
    demand_df = pd.read_csv(os.path.join(data_dir, 'demand_points.csv'))
    comp_df = pd.read_csv(os.path.join(data_dir, 'competitors.csv'))
    stores_df = pd.read_csv(os.path.join(data_dir, 'stores.csv'))
    cands_df = pd.read_csv(os.path.join(data_dir, 'candidates.csv'))
    
    RADIUS = 3.0
    AREA = np.pi * (RADIUS**2)
    
    # Build Spatial Indices
    print("Building cKDTree Spatial Indices...")
    d_tree, d_coords = build_tree(demand_df)
    c_tree, c_coords = build_tree(comp_df)
    s_tree, s_coords = build_tree(stores_df)
    cand_coords = latlon_to_cartesian(cands_df['lat'].values, cands_df['lng'].values)
    
    # Query all points within RADIUS at once (O(log N))
    d_indices = d_tree.query_ball_point(cand_coords, r=RADIUS)
    c_indices = c_tree.query_ball_point(cand_coords, r=RADIUS)
    s_indices = s_tree.query_ball_point(cand_coords, r=RADIUS)
    
    # Query nearest neighbor distance (k=1)
    d_nearest_dist, _ = d_tree.query(cand_coords, k=1)
    c_nearest_dist, _ = c_tree.query(cand_coords, k=1)
    s_nearest_dist, _ = s_tree.query(cand_coords, k=1)
    
    # Query exact distances for all competitors to calculate proximity pressure
    # To save memory, we'll just query the k-nearest up to a limit or use all since competitors N=350 is small
    c_all_dist, _ = c_tree.query(cand_coords, k=len(comp_df))

    results = []
    
    print("Processing Catchments...")
    for i, cand in cands_df.iterrows():
        d_idx = d_indices[i]
        c_idx = c_indices[i]
        
        d_in = demand_df.iloc[d_idx]
        c_in = comp_df.iloc[c_idx]
        
        # Hard Filters
        nearest_own = s_nearest_dist[i] if not np.isinf(s_nearest_dist[i]) else 10.0
        own_store_blocked = nearest_own <= RADIUS
        
        if len(d_in) == 0:
            continue
            
        # A. Demand (7)
        d_wt = d_in['weight'].sum()
        d_count = len(d_in)
        d_dens = d_wt / AREA
        d_offset = np.sqrt((cand['lat'] - np.average(d_in['lat'], weights=d_in['weight']))**2 + 
                           (cand['lng'] - np.average(d_in['lng'], weights=d_in['weight']))**2) * 111.0 if d_count > 0 else 0
        d_var = d_in['weight'].var() if d_count > 1 else 0
        min_d_dist = d_nearest_dist[i]
        freq_score = (d_in['weight'] * d_in['freq_index']).sum() / d_count
        
        # B. Competition (9)
        c_count = len(c_in)
        c_dens = c_count / AREA
        min_c_dist = c_nearest_dist[i] if not np.isinf(c_nearest_dist[i]) else 10.0
        c_dist_array = c_all_dist[i]
        c_pressure = np.sum(1 / np.where(c_dist_array < 0.1, 0.1, c_dist_array))
        saturation = c_count / max(d_wt, 1)
        unmet = max(0, d_wt - c_in['capacity'].sum())
        c_cluster = c_in['lat'].std() + c_in['lng'].std() if c_count > 1 else 0
        tier_gap = 2 - c_in['brand_tier'].mean() if c_count > 0 else 0
        avg_age = c_in['years_operating'].mean() if c_count > 0 else 0
        
        # C. Cannibalization (5)
        overlap_frac = np.exp(-nearest_own / RADIUS) if nearest_own < (2 * RADIUS) else 0
        overlap_demand = d_wt * overlap_frac
        risk_rev = overlap_demand * cand['avg_spend']
        net_new = d_wt - overlap_demand
        
        # D. Operating Cost (5)
        rent_adj = d_wt / cand['rent_index']
        ppi = cand['property_val_local'] / cand['city_avg_prop']
        labour = cand['avg_wage_local'] / cand['avg_wage_city']
        infra = 1 - cand['outage_rate']
        payback = cand['setup_cost'] / cand['monthly_margin']
        
        # E. Forward-Looking (8)
        future_pop = cand['units_approved'] * cand['avg_hh_size']
        footfall_g = cand['footfall_gain']
        eff_rad = RADIUS * cand['metro_multiplier']
        access_scr = cand['width_future'] / max(cand['width_current'], 1)
        zoning = cand['zoning_flag']
        pop_2027 = d_count * (1 + cand['pop_growth'])**3
        student_d = cand['student_demand']
        hosp_f = cand['hosp_footfall']
        
        # F. Customer Profile (7)
        demo_match = d_in['target_pop'].sum() / max(d_in['total_pop'].sum(), 1)
        affluence = (cand['property_val_local'] + d_in['car_density'].mean() * 1000) / 2
        working_rt = d_in['employed'].sum() / max(d_in['total_pop'].sum(), 1)
        student_dens = cand['student_demand'] / max(d_in['total_pop'].sum(), 1)
        commuter_rt = cand['footfall_gain'] / max(d_in['total_pop'].sum(), 1)
        event_foot = cand['event_footfall']
        transit = 1 / max(cand['dist_to_transit_hub'], 0.1)
        
        # G. Spatial & Accessibility (7)
        access = cand['width_current'] * cand['connectivity']
        pub_transit = 1 / max(cand['dist_to_transit_hub'], 0.1)
        parking = cand['parking_spots_200m'] / max(cand['expected_car_cust'], 1)
        traffic = cand['pedestrian_count'] + cand['vehicle_count']
        vis = cand['road_frontage'] * cand['max_signage_ht']
        boundary = 1.0
        flood_pen = cand['flood_days'] * cand['daily_rev_lost']
        
        # Hard filter viability
        viable = net_new * cand['avg_spend'] > cand['monthly_opex']
        
        res = {
            "location_id": cand['location_id'],
            "name": cand['name'],
            "lat": cand['lat'],
            "lng": cand['lng'],
            "own_store_blocked": own_store_blocked,
            "break_even_viable": viable,
            
            # Export raw vars for scoring
            "d_wt": d_wt, "d_count": d_count, "d_dens": d_dens, "d_offset": d_offset, "d_var": d_var, "min_d_dist": min_d_dist, "freq_score": freq_score,
            "c_count": c_count, "c_dens": c_dens, "min_c_dist": min_c_dist, "c_pressure": c_pressure, "saturation": saturation, "unmet": unmet, "c_cluster": c_cluster, "tier_gap": tier_gap, "avg_age": avg_age,
            "nearest_own": nearest_own, "overlap_frac": overlap_frac, "overlap_demand": overlap_demand, "risk_rev": risk_rev, "net_new": net_new,
            "rent_adj": rent_adj, "ppi": ppi, "labour": labour, "infra": infra, "payback": payback,
            "future_pop": future_pop, "footfall_g": footfall_g, "eff_rad": eff_rad, "access_scr": access_scr, "zoning": zoning, "pop_2027": pop_2027, "student_d": student_d, "hosp_f": hosp_f,
            "demo_match": demo_match, "affluence": affluence, "working_rt": working_rt, "student_dens": student_dens, "commuter_rt": commuter_rt, "event_foot": event_foot, "transit": transit,
            "access": access, "pub_transit": pub_transit, "parking": parking, "traffic": traffic, "vis": vis, "boundary": boundary, "flood_pen": flood_pen
        }
        results.append(res)
        
    df = pd.DataFrame(results)
    
    # Filter non-viable
    df = df[~df['own_store_blocked']]
    df = df[df['break_even_viable']]
    
    # Min-Max Normalization (Step 2 & 3)
    d_score = (min_max_scale(df['d_wt']) + min_max_scale(df['d_count']) + min_max_scale(df['d_dens']) + min_max_scale(df['d_offset'], True) + min_max_scale(df['d_var'], True) + min_max_scale(df['min_d_dist'], True) + min_max_scale(df['freq_score'])) / 7
    c_score = (min_max_scale(df['c_count'], True) + min_max_scale(df['c_dens'], True) + min_max_scale(df['min_c_dist']) + min_max_scale(df['c_pressure'], True) + min_max_scale(df['saturation'], True) + min_max_scale(df['unmet']) + min_max_scale(df['c_cluster']) + min_max_scale(df['tier_gap']) + min_max_scale(df['avg_age'], True)) / 9
    k_score = (min_max_scale(df['nearest_own']) + min_max_scale(df['overlap_frac'], True) + min_max_scale(df['overlap_demand'], True) + min_max_scale(df['risk_rev'], True) + min_max_scale(df['net_new'])) / 5
    cost_score = (min_max_scale(df['rent_adj']) + min_max_scale(df['ppi'], True) + min_max_scale(df['labour'], True) + min_max_scale(df['infra']) + min_max_scale(df['payback'], True)) / 5
    f_score = (min_max_scale(df['future_pop']) + min_max_scale(df['footfall_g']) + min_max_scale(df['eff_rad']) + min_max_scale(df['access_scr']) + min_max_scale(df['zoning']) + min_max_scale(df['pop_2027']) + min_max_scale(df['student_d']) + min_max_scale(df['hosp_f'])) / 8
    p_score = (min_max_scale(df['demo_match']) + min_max_scale(df['affluence']) + min_max_scale(df['working_rt']) + min_max_scale(df['student_dens']) + min_max_scale(df['commuter_rt']) + min_max_scale(df['event_foot']) + min_max_scale(df['transit'])) / 7
    a_score = (min_max_scale(df['access']) + min_max_scale(df['pub_transit']) + min_max_scale(df['parking']) + min_max_scale(df['traffic']) + min_max_scale(df['vis']) + min_max_scale(df['boundary']) + min_max_scale(df['flood_pen'], True)) / 7

    df['demand_score'] = d_score
    df['competition_score'] = c_score
    df['cannibalization_score'] = k_score
    df['cost_score'] = cost_score
    df['forward_score'] = f_score
    df['customer_profile_score'] = p_score
    df['accessibility_score'] = a_score
    
    raw_final = (0.25 * d_score + 0.20 * c_score + 0.20 * k_score + 0.15 * f_score + 0.10 * p_score + 0.10 * a_score) / np.clip(2.0 - cost_score, 0.5, 2.0)
    df['final_score'] = min_max_scale(raw_final)
    
    df['huff_capture_prob'] = min_max_scale(df['net_new'] / np.clip(df['d_wt'] + df['c_pressure']*100, 1, None))
    df['net_opportunity_index'] = raw_final
    
    df['opportunity_score'] = df['final_score']
    df['demand_reached'] = df['d_wt']
    df['unmet_demand'] = df['unmet']
    df['saturation_ratio'] = df['saturation']
    df['comp_pressure'] = df['c_pressure']
    df['self_overlap_count'] = np.where(df['overlap_demand'] > 0, 1, 0)
    df['self_overlap_demand'] = df['overlap_demand']
    df['net_new_demand'] = df['net_new']
    df['rent_adj_demand'] = df['rent_adj']
    df['competitor_density'] = df['c_dens']
    df['comp_count'] = df['c_count']
    df['nearest_sister_dist'] = df['nearest_own']
    
    # ML Prediction
    ml_features = df[['d_wt', 'c_pressure', 'net_new', 'rent_adj', 'future_pop', 'demo_match', 'access']].copy()
    model_path = os.path.join(os.path.dirname(__file__), 'xgb_model.json')
    if os.path.exists(model_path):
        model = xgb.XGBRegressor()
        model.load_model(model_path)
        raw_ml_preds = model.predict(ml_features)
        df['ml_score'] = min_max_scale(pd.Series(raw_ml_preds))
        df['final_score'] = (df['final_score'] * 0.8) + (df['ml_score'] * 0.2)
        
        booster = model.get_booster()
        shap_vals = booster.predict(xgb.DMatrix(ml_features), pred_contribs=True)
        df['shap_demand'] = min_max_scale(shap_vals[:, 0])
        df['shap_comp'] = shap_vals[:, 1]
    else:
        df['ml_score'] = 0.5
        df['shap_demand'] = df['opportunity_score'] * 0.5
    
    df['is_pareto'] = [True] * len(df)
    df['lisa_cluster'] = "Neutral"

    df = df.sort_values(by='final_score', ascending=False).reset_index(drop=True)
    df['rank'] = df.index + 1
    
    df.to_csv(os.path.join(data_dir, "opportunity_scores.csv"), index=False)
    df.to_csv(os.path.join(data_dir, "ranked_stores.csv"), index=False)
    print("Scoring complete.")
    
    # --- WHITE SPACE DETECTION (DBSCAN Stretch Goal) ---
    print("Executing DBSCAN White-Space Detection...")
    
    # 1. Filter out all demand points within 3km of an existing store
    d_to_s_dist, _ = s_tree.query(d_coords, k=1)
    uncontested_mask = d_to_s_dist > RADIUS
    white_space_demand = demand_df[uncontested_mask].copy()
    
    if not white_space_demand.empty:
        # 2. Cluster the uncontested demand points
        # eps is in Cartesian degrees approx (3km ~ 0.027 degrees). 
        # Using simple lat/lng Euclidean for DBSCAN is sufficient at city-scale
        coords_for_clustering = white_space_demand[['lat', 'lng']].values
        
        dbscan = DBSCAN(eps=0.015, min_samples=10) # roughly 1.5km radius, min 10 points
        clusters = dbscan.fit_predict(coords_for_clustering)
        
        white_space_demand['cluster_id'] = clusters
        # Exclude noise (-1)
        valid_clusters = white_space_demand[white_space_demand['cluster_id'] != -1]
        
        # 3. Aggregate clusters
        cluster_summary = valid_clusters.groupby('cluster_id').agg(
            center_lat=('lat', 'mean'),
            center_lng=('lng', 'mean'),
            total_weight=('weight', 'sum'),
            point_count=('weight', 'count')
        ).reset_index()
        
        # Rank by total weight to find the best white-spaces
        cluster_summary = cluster_summary.sort_values(by='total_weight', ascending=False).head(20)
        
        cluster_summary.to_csv(os.path.join(data_dir, "white_space_clusters.csv"), index=False)
        print(f"Found {len(cluster_summary)} viable uncontested market clusters!")
    else:
        print("No uncontested white space found.")
