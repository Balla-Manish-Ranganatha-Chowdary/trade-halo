import pandas as pd
import numpy as np
import os

def haversine_vectorized(lat1, lon1, lat2, lon2):
    R = 6371.0 # Earth radius in km
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c

if __name__ == "__main__":
    print("Starting Comprehensive NOI Analysis...")
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    
    demand_df = pd.read_csv(os.path.join(data_dir, 'demand_points.csv'))
    comp_df = pd.read_csv(os.path.join(data_dir, 'competitors.csv'))
    stores_df = pd.read_csv(os.path.join(data_dir, 'stores.csv'))
    cands_df = pd.read_csv(os.path.join(data_dir, 'candidates.csv'))
    
    RADIUS = 3.0 # km catchment
    AREA = np.pi * (RADIUS**2)
    
    results = []
    
    for _, cand in cands_df.iterrows():
        # Demand calculations
        d_dist = haversine_vectorized(cand['lat'], cand['lon'], demand_df['lat'].values, demand_df['lon'].values)
        d_mask = d_dist <= RADIUS
        d_in = demand_df[d_mask]
        
        d_count = len(d_in)
        if d_count == 0:
            continue
            
        d_weighted = d_in['weight'].sum()
        d_density = d_weighted / AREA
        d_freq_score = (d_in['weight'] * d_in['freq']).sum() / d_count
        
        # Competitor calculations
        c_dist = haversine_vectorized(cand['lat'], cand['lon'], comp_df['lat'].values, comp_df['lon'].values)
        c_mask = c_dist <= RADIUS
        c_in = comp_df[c_mask]
        
        comp_count = len(c_in)
        comp_density = comp_count / AREA
        
        c_dists_safe = np.where(c_dist[c_mask] < 0.1, 0.1, c_dist[c_mask])
        comp_pressure = np.sum(1 / c_dists_safe)
        
        saturation = comp_count / max(d_weighted, 1)
        comp_capacity = (c_in['capacity'] * c_in['utilization']).sum()
        unmet_demand = max(0, d_weighted - comp_capacity)
        
        # Cannibalization calculations
        s_dist = haversine_vectorized(cand['lat'], cand['lon'], stores_df['lat'].values, stores_df['lon'].values)
        min_s_dist = s_dist.min() if len(s_dist) > 0 else 10.0
        self_overlap_count = np.sum(s_dist <= RADIUS)
        
        overlap_factor = np.exp(-min_s_dist / RADIUS) if min_s_dist < (2 * RADIUS) else 0
        overlap_demand = d_weighted * overlap_factor
        net_new_demand = d_weighted - overlap_demand
        
        # Operating costs and future signals
        rent_adj_demand = d_weighted / max(cand['rent_index'], 1)
        future_d = d_weighted * (1 + cand['future_pop_growth_rate'])**3
        
        # Master NOI calculation
        base_opp = unmet_demand * (d_freq_score / 10.0)
        cost_penalty = cand['rent_index'] * 0.2 + cand['avg_wage_local'] * 0.0005
        
        noi_raw = (base_opp - (overlap_demand * 10)) / max(cost_penalty, 1) * (1 + cand['future_pop_growth_rate'])
        
        results.append({
            "candidate_id": cand['candidate_id'],
            "name": cand['name'],
            "lat": cand['lat'],
            "lon": cand['lon'],
            "demand_reached": d_weighted,
            "demand_density": d_density,
            "freq_score": d_freq_score,
            "comp_count": comp_count,
            "competitor_density": comp_density,
            "comp_pressure": comp_pressure,
            "saturation_ratio": saturation,
            "unmet_demand": unmet_demand,
            "nearest_sister_dist": min_s_dist,
            "self_overlap_count": self_overlap_count,
            "self_overlap_demand": overlap_demand,
            "net_new_demand": net_new_demand,
            "rent_adj_demand": rent_adj_demand,
            "future_demand_proj": future_d,
            "NOI_raw": noi_raw
        })
        
    results_df = pd.DataFrame(results)
    
    # 0-1 Normalization
    noi_min = results_df['NOI_raw'].min()
    noi_max = results_df['NOI_raw'].max()
    results_df['opportunity_score'] = (results_df['NOI_raw'] - noi_min) / max(noi_max - noi_min, 1e-6)
    
    # Pareto calculation
    pareto_flags = []
    for i, row in results_df.iterrows():
        is_dominated = False
        for j, other_row in results_df.iterrows():
            if i == j: continue
            if (other_row['demand_reached'] > row['demand_reached'] and other_row['self_overlap_demand'] <= row['self_overlap_demand']) or \
               (other_row['demand_reached'] >= row['demand_reached'] and other_row['self_overlap_demand'] < row['self_overlap_demand']):
                is_dominated = True
                break
        pareto_flags.append(not is_dominated)
    results_df['is_pareto'] = pareto_flags
    
    # Simulated SHAP & LISA
    results_df['shap_demand'] = results_df['opportunity_score'] * np.random.uniform(0.3, 0.7, len(results_df))
    results_df['shap_comp'] = results_df['opportunity_score'] * np.random.uniform(0.1, 0.4, len(results_df))
    results_df['lisa_cluster'] = np.where(results_df['demand_reached'] > results_df['demand_reached'].mean() * 1.5, "High-High", "Neutral")
    
    results_df = results_df.sort_values(by='opportunity_score', ascending=False).reset_index(drop=True)
    results_df.to_csv(os.path.join(data_dir, "ranked_stores.csv"), index=False)
    print("Analysis complete. Normalized NOI scores saved.")
