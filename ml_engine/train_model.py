import numpy as np
import pandas as pd
import xgboost as xgb
import os
import json

def synthesize_training_data(n=1000):
    np.random.seed(42)
    # Generate synthetic analytical features (the same ones produced by analyzer.py)
    df = pd.DataFrame({
        'd_wt': np.random.normal(50000, 15000, n).clip(10000, 100000),
        'c_pressure': np.random.normal(10, 5, n).clip(0, 30),
        'net_new': np.random.normal(40000, 15000, n).clip(0, 80000),
        'rent_adj': np.random.normal(40000, 10000, n).clip(10000, 80000),
        'future_pop': np.random.normal(500, 200, n).clip(0, 1500),
        'demo_match': np.random.uniform(0.1, 0.8, n),
        'access': np.random.normal(40, 15, n).clip(10, 100)
    })
    
    # Target variable: historical_revenue (non-linear relationship)
    # High demand increases revenue, high comp pressure decreases it, net_new acts as a cap
    revenue = (
        df['d_wt'] * 10 
        - df['c_pressure'] * 5000 
        + df['net_new'] * 5
        + df['rent_adj'] * 2
        + df['future_pop'] * 100
        + df['demo_match'] * 50000
        + df['access'] * 1000
        + np.random.normal(0, 100000, n) # Noise
    ).clip(100000, 5000000)
    
    df['historical_revenue'] = revenue
    return df

def train_xgboost():
    print("Synthesizing historical training data...")
    df = synthesize_training_data(2000)
    
    X = df.drop(columns=['historical_revenue'])
    y = df['historical_revenue']
    
    print("Training XGBoost Regressor...")
    model = xgb.XGBRegressor(
        n_estimators=100, 
        max_depth=4, 
        learning_rate=0.1, 
        random_state=42
    )
    model.fit(X, y)
    
    score = model.score(X, y)
    print(f"Training R^2 Score: {score:.3f}")
    
    model_path = os.path.join(os.path.dirname(__file__), 'xgb_model.json')
    model.save_model(model_path)
    print(f"Model saved to {model_path}")

if __name__ == "__main__":
    train_xgboost()
