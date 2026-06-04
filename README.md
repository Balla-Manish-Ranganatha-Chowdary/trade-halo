# TradeHalo Spatial Intelligence Engine

![Dashboard Screenshot Placeholder](<!-- Insert path/to/dashboard_screenshot.png here -->)

## 1. The Opportunity-Score Model
TradeHalo uses a **Hybrid Architecture** (Rule-Based + XGBoost Machine Learning) to score and rank potential store locations. 

The core philosophy of the engine is that retail success is a function of **Unmet Demand Capacity**. We evaluate 250 candidate locations across 58 variables split into 7 macro categories (Demand, Competition, Cannibalization, Forward-Looking, Customer Profile, Accessibility, and Cost). 

Each metric is isolated, geographically filtered (using a parameterized 3km catchment), and normalized to a strict `[0, 1]` scale. Positive signals (like high demand or future transit development) push the score toward 1.0. Negative signals (like high competitor density or high operating costs) apply mathematical penalties.

### Scoring Logic & Task 3 Trade-Offs
To build the Opportunity Score, we had to mathematically fuse radically different signals (e.g., foot traffic vs. rent prices). Here are the key analytical trade-offs made during Task 3:

* **Normalization Choice (Min-Max vs. Z-Score):** We chose Min-Max scaling to compress every metric strictly into a `[0, 1]` range. While Z-scores (standard deviations) handle outliers better, they can produce unbounded negative/positive values. In a composite formula, a single unbounded metric could entirely hijack the final score. Min-Max ensures every metric stays strictly within its assigned weight bracket.
* **Operating Cost as a Divisor Penalty:** Instead of subtracting high operating costs (Rent, Labor) from the score, we applied Cost as a mathematical divisor. *Trade-off:* If you subtract costs, a hyper-premium location (like a luxury mall) might score near zero. By dividing, we treat costs as an ROI compressor—the location remains highly lucrative, but the margin of error for success is compressed.
* **Weighting Justifications:** The macro-weights were aggressively biased toward immediate spatial fundamentals: **Demand (25%), Competition (20%), and Cannibalization (20%)** account for 65% of the total score. *Trade-off:* We deliberately deprioritized Forward-Looking signals (15%) and Customer Profiling (10%). Why? Because speculative future population growth or vague demographic matches cannot mathematically save a store if it is immediately suffocated by 11 competitors on opening day. 

### The XGBoost Machine Learning Layer
While the Rule-Based engine relies on deterministic math (Huff Gravity logic) to calculate theoretical market share, retail economics are rarely perfectly linear. To capture nonlinear interactions, we introduced an `xgboost.XGBRegressor` machine learning model.

* **What We Did:** We synthesized a historical dataset simulating 2,000 previous retail locations and their known historical outcomes. We then trained the XGBoost algorithm on this dataset so it could learn the hidden relationships between geography and profit.
* **The Training Features:** The ML model specifically analyzes the 7 most critical nonlinear variables for each candidate:
    1. `d_wt` (Raw Demand Weight)
    2. `c_pressure` (Competitor Proximity/Pressure)
    3. `net_new` (Net New Demand after cannibalization)
    4. `rent_adj` (Rent Adjusted Demand)
    5. `future_pop` (Future Population Growth)
    6. `demo_match` (Demographic Target Match)
    7. `access` (Street Connectivity/Visibility)
* **What Exactly is it Predicting?** The target variable (`y`) the tree predicts is a localized **Historical Revenue Coefficient**. It tries to predict if a location with these exact traits historically overperformed or underperformed the raw theoretical math.
* **How It Predicts the Opportunity Score:** The model parses the 7 features down its decision trees. If it notices a pattern—like "High rent + High future pop = Good" but "High rent + Low future pop + Medium competition = Catastrophic failure"—it outputs a raw prediction value. We normalize this value back onto a `[0, 1]` scale to create the `ml_attractiveness_score`.

### Why the 80% / 20% Blending Weight?
The final Opportunity Score is calculated as: `(Rule-Based Final * 0.8) + (ML Score * 0.2)`. 

We purposefully weighted the Rule-Based (Huff Gravity) model at 80% because it relies on strict, auditable, and immutable physics (geospatial decay, capacity, hard costs). Executives generally distrust "black-box" AI algorithms when allocating millions of dollars for real estate. By keeping the ML weight at a strict 20%, the AI acts as an **"Intuition Modifier"**. It nudges a location up or down based on hidden data patterns without completely overwriting the fundamental, undeniable physics of the 80% Huff Gravity engine.

## 2. Trade-Offs & Assumptions
* **Assumption (Circular Catchment):** We assume a perfect 3km circular catchment using the Haversine formula (and later `cKDTree` in 3D Cartesian space). In reality, rivers, highways, and travel-time (isochrones) warp catchments. A trade-off was made for extreme $O(\log N)$ computational speed over routing-engine accuracy.
* **Assumption (Cannibalization):** We assume an exponential decay model for self-cannibalization. If a candidate is directly on top of an existing store, cannibalization is 100%. At 6km (2x radius), it decays to 0%.
* **Trade-Off (Memory vs Speed):** During the Stretch Goals, we discarded the NumPy vectorized distance matrices (which are memory-heavy and crash at 1M points) in favor of building a `scipy.spatial.cKDTree`. While the tree takes a few milliseconds to build upfront, it allows for infinite scalability.

## 3. The Dashboard & Visualizations
The frontend is built using Leaflet.js and Chart.js, designed to answer the core executive question: *"Why did the model pick this location?"*

* **Demand Heatmap:** Shows the raw distribution of customer weight. We visualize this so executives can verify that the AI isn't recommending stores in "dead zones."
* **Competitor & Existing Store Pins:** Displays the exact location of rivals and our own fleet. This is critical to visually validate the cannibalization and saturation scores shown in the sidebar.
* **SHAP Impacts Layer:** We extracted exact `pred_contribs` (SHAP values) from the XGBoost decision trees. The map pins change color and size based on *how much* demand/competition mathematically warped the prediction, turning a "black box" AI into an explainable model.
* **Pareto Optimality Chart:** A scatter plot comparing *Demand Reached* (Y-Axis) vs *Cannibalization Risk* (X-Axis). The glowing green dotted line connects the "Pareto Optimal" stores—meaning you cannot find a store with higher demand without accepting exponentially more cannibalization risk.
* **DBSCAN White-Space Polygons:** Large glowing yellow circles generated by our clustering algorithm. This visualization explicitly highlights massive pockets of demand that are >3km away from *any* existing store, instantly revealing uncontested market territory.
