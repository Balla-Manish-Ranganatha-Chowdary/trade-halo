# TradeHalo Location Opportunity Analysis

## Opportunity-Score Model (Task 3)

The Opportunity Score is calculated using a **Hybrid Huff Gravity Heuristic**. 

**1. Base Attractiveness (A):**
Instead of static proxies (like square footage), attractiveness is derived dynamically from **Demand Reached**. Demand itself is synthesized as a product of *Call Volume*, *Missed Call Rates*, and *Average Job Value*, creating a highly realistic quantification of local revenue leakage. 

**2. Competitor Density as a Non-Linear Multiplier:**
Following *Hotelling's Law of agglomeration*, a moderate competitor density acts as a **validation signal** (people are already buying similar services here). Therefore, if competitor density is slightly above average ($Z_{comp} > 0$), the base attractiveness receives a 10% multiplier. However, if density is extreme ($Z_{comp} > 2$), the market is saturated, resulting in a 20% penalty.

**3. Cannibalization Penalty (Negative Weighting):**
High self-overlap is mathematically catastrophic for net-new growth. The model applies a distance-decaying penalty factor ($\omega$). If a proposed node is within the radius ($R$) of an existing sister store, it receives a severe percentage penalty to its score, clamping near zero if the overlap is total. If the distance is greater than $2R$, the penalty decays to zero.

**Formula:**
`Opportunity Score = (Demand_Reached * Comp_Multiplier) * (1 - Cannibalization_Penalty)`

### Assumptions & Trade-offs
- **Prototype Simplification:** For this prototype, I bypassed the full XGBoost implementation mentioned in the blueprint in favor of a robust mathematical heuristic. Training an ML model without historical success data (ground truth) would just fit to noise.
- **Euclidean vs. Spherical:** We strictly use the Haversine formula to account for the Earth's curvature. Euclidean distances fail completely over large Indian territories.
- **Cannibalization Sensitivity:** The $\omega$ (omega) factor is set to 0.5. In a real-world scenario, this would be exposed as a dial on the dashboard allowing executives to choose between aggressive clustering vs. total territorial isolation.

---

## Stretch Goals (Task 4)

### 1. White-Space Detection
While not fully implemented in the UI to save scope, the algorithmic approach for white-space detection is:
1.  **Masking:** Delete any demand point falling within 3km of *any* existing store (ours or competitors).
2.  **Clustering:** Run DBSCAN (Density-Based Spatial Clustering of Applications with Noise) on the surviving points. DBSCAN is ideal because it ignores sparse noise and finds organic shapes of demand.
3.  **Centroid Extraction:** Compute the geographic centroid of the densest DBSCAN clusters to suggest entirely new coordinate nodes (True Whitespace).

### 2. MySQL Spatial Alternatives
If we executed this in MySQL 8 instead of Python:
Instead of Python arrays, we utilize `ST_Distance_Sphere(POINT(lon1, lat1), POINT(lon2, lat2))`.
The critical upgrade is utilizing the `SPATIAL INDEX` (R-tree). We first use `MBRContains` to draw a minimum bounding rectangle around the store. MySQL instantly discards 99% of demand points outside this box without doing any math. Only the remaining 1% are passed to `ST_Distance_Sphere` for exact circular boundary checking.

### 3. Performance Scaling (10,000 stores, 1M demand points)
**What breaks?**
Our current `numpy` broadcasting approach calculates a distance matrix of dimensions `[10,000 x 1,000,000]`. This requires computing 10 billion distinct trigonometric equations. Attempting to hold this matrix in RAM will cause an immediate Out-Of-Memory (OOM) crash (requiring ~80GB of RAM).

**How to fix it?**
1.  **Spatial Trees:** We abandon flat arrays and build a `scipy.spatial.cKDTree` or Ball Tree containing the 1M demand points. For each of the 10,000 stores, we run a `query_ball_point(radius)` search. This collapses the time complexity from $O(N \times M)$ to roughly $O(N \log M)$, running in seconds with minimal RAM.
2.  **FFI / Rust:** If the Python interpreter overhead in the hot loop evaluating the Hybrid Huff cannibalization penalty is still too slow, the mathematical core should be rewritten in Rust and exposed to Python via `PyO3`, achieving bare-metal execution speeds.
