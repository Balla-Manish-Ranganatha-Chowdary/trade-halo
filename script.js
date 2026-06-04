// Initialize Map
const map = L.map('map', {
    zoomControl: false // Move to bottom right later if needed
}).setView([12.9716, 77.5946], 11); // Center on Bengaluru

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap'
}).addTo(map);

// Data Globals
let rankedStores = [];
let markersLayer = L.featureGroup().addTo(map);
let dynamicCatchmentLayers = L.featureGroup().addTo(map);

// New Visualization Layers
let heatmapLayer = L.heatLayer([], {radius: 20, blur: 15, maxZoom: 13, gradient: {0.4: 'blue', 0.6: 'cyan', 0.8: 'yellow', 1.0: 'red'}}).addTo(map);
let competitorsLayer = L.featureGroup().addTo(map);
let existingStoresLayer = L.featureGroup().addTo(map);
let whiteSpaceLayer = L.featureGroup().addTo(map);

const RADIUS_METERS = 3000; // 3km default
let currentMode = 'standard'; // standard, shap, lisa
let paretoChartInstance = null;

// DOM Elements
const tbody = document.querySelector('#ranked-table tbody');
const detailsPanel = document.getElementById('details-panel');
const dName = document.getElementById('detail-name');
const dScore = document.getElementById('detail-score');
const dDemand = document.getElementById('detail-demand');
const dComp = document.getElementById('detail-comp');
const dOverlap = document.getElementById('detail-overlap');

// PapaParse config
const papaConfig = {
    header: true,
    dynamicTyping: true,
    skipEmptyLines: true
};

// Load Data
async function loadData() {
    try {
        const ts = Date.now();
        const [candReq, demandReq, compReq, storeReq, wsReq] = await Promise.all([
            fetch(`data/ranked_stores.csv?v=${ts}`),
            fetch(`data/demand_points.csv?v=${ts}`),
            fetch(`data/competitors.csv?v=${ts}`),
            fetch(`data/stores.csv?v=${ts}`),
            fetch(`data/white_space_clusters.csv?v=${ts}`)
        ]);
        
        // Candidates
        Papa.parse(await candReq.text(), {
            ...papaConfig,
            complete: function(results) {
                rankedStores = results.data;
                renderTable();
                plotStores();
                initParetoChart();
            }
        });
        
        // Demand Heatmap
        Papa.parse(await demandReq.text(), {
            ...papaConfig,
            complete: function(res) {
                const heatData = res.data.filter(r => r.lat && r.lng).map(r => [r.lat, r.lng, Math.min(r.weight / 200, 1.0)]);
                heatmapLayer.setLatLngs(heatData);
            }
        });
        
        // Competitors
        Papa.parse(await compReq.text(), {
            ...papaConfig,
            complete: function(res) {
                res.data.filter(r => r.lat && r.lng).forEach(r => {
                    L.circleMarker([r.lat, r.lng], { radius: 4, color: '#f43f5e', fillColor: '#f43f5e', fillOpacity: 0.8, weight: 1 })
                     .bindTooltip(`Competitor (${r.tier})`)
                     .addTo(competitorsLayer);
                });
            }
        });
        
        // Existing Stores
        Papa.parse(await storeReq.text(), {
            ...papaConfig,
            complete: function(res) {
                res.data.filter(r => r.lat && r.lng).forEach(r => {
                    L.marker([r.lat, r.lng], { icon: createIcon('#10b981', '#047857', 18) })
                     .bindTooltip("Existing TradeHalo Store")
                     .addTo(existingStoresLayer);
                });
            }
        });
        
        // White Spaces
        Papa.parse(await wsReq.text(), {
            ...papaConfig,
            complete: function(res) {
                if(res.data) {
                    res.data.filter(r => r.center_lat && r.center_lng).forEach(r => {
                        L.circle([r.center_lat, r.center_lng], {
                            color: '#eab308',
                            fillColor: '#fef08a',
                            fillOpacity: 0.3,
                            radius: 1500, // 1.5km
                            weight: 2,
                            dashArray: '5, 5'
                        }).bindTooltip(`<b>DBSCAN White-Space</b><br>Nodes: ${r.point_count}<br>Demand: ${r.total_weight.toFixed(0)}`)
                        .addTo(whiteSpaceLayer);
                    });
                }
            }
        });
        
    } catch (e) {
        console.error("Failed to load CSVs:", e);
    }
}

function renderTable() {
    tbody.innerHTML = '';
    const topStores = rankedStores.slice(0, 50);
    
    topStores.forEach((store, index) => {
        const tr = document.createElement('tr');
        const paretoStar = store.is_pareto ? '⭐' : '';
        
        tr.innerHTML = `
            <td><span class="rank-badge">#${index + 1}</span></td>
            <td><strong>${store.name}</strong> ${paretoStar}</td>
            <td><span class="score-badge">${parseFloat(store.opportunity_score).toFixed(2)}</span></td>
        `;
        
        tr.addEventListener('click', () => {
            document.querySelectorAll('#ranked-table tr').forEach(row => row.classList.remove('active'));
            tr.classList.add('active');
            focusStore(store);
        });
        
        tbody.appendChild(tr);
    });
}

function createIcon(color, border='white', size=16) {
    return L.divIcon({
        className: 'custom-icon',
        html: `<div style="background-color: ${color}; width: ${size}px; height: ${size}px; border-radius: 50%; border: 2px solid ${border}; box-shadow: 0 0 10px ${color};"></div>`,
        iconSize: [size, size],
        iconAnchor: [size/2, size/2]
    });
}

function plotStores() {
    markersLayer.clearLayers();
    
    // Dynamically calculate thresholds to guarantee visual variety
    const demands = rankedStores.map(s => s.demand_reached).sort((a,b) => a - b);
    const lisaHigh = demands[Math.floor(demands.length * 0.80)] || 0; // Top 20%
    const lisaLow = demands[Math.floor(demands.length * 0.30)] || 0; // Bottom 30%
    const maxShap = Math.max(...rankedStores.map(s => s.shap_demand || 0.1));
    
    rankedStores.forEach((store, idx) => {
        if (!store.lat || !store.lng) return;
        
        let icon;
        if (currentMode === 'standard') {
            if (idx < 10) icon = createIcon('#38bdf8', 'white', 18); // Top 10 blue
            else if (idx < 30) icon = createIcon('#f59e0b', 'white', 16); // Mid orange
            else icon = createIcon('#64748b', 'white', 12); // Rest gray
        } else if (currentMode === 'shap') {
            // Distinct colors and sizes for SHAP intensity
            const intensity = (store.shap_demand || 0) / maxShap;
            if (intensity > 0.7) {
                icon = createIcon('#f43f5e', '#be123c', 22); // High Impact (Red, Large)
            } else if (intensity > 0.4) {
                icon = createIcon('#c084fc', '#7e22ce', 16); // Medium Impact (Purple)
            } else {
                icon = createIcon('#38bdf8', '#0369a1', 12); // Low Impact (Blue, Small)
            }
        } else if (currentMode === 'lisa') {
            // Distinct colors for spatial clusters
            if (store.demand_reached >= lisaHigh) {
                icon = createIcon('#10b981', '#059669', 22); // High-High Cluster (Green, Large)
            } else if (store.demand_reached <= lisaLow) {
                icon = createIcon('#f59e0b', '#b45309', 12); // Low-Low Cluster (Orange, Small)
            } else {
                icon = createIcon('#64748b', '#334155', 14); // Neutral (Gray)
            }
        }
        
        const marker = L.marker([store.lat, store.lng], { icon: icon }).addTo(markersLayer);
        marker.on('click', () => focusStore(store));
    });
}

function initParetoChart() {
    const ctx = document.getElementById('paretoChart').getContext('2d');
    
    const scatterData = rankedStores.map(store => ({
        x: store.demand_reached,
        y: store.self_overlap_demand,
        store: store,
        is_pareto: store.is_pareto
    }));
    
    const paretoPoints = scatterData.filter(d => d.is_pareto);
    const nonParetoPoints = scatterData.filter(d => !d.is_pareto);
    
    paretoPoints.sort((a,b) => a.x - b.x);

    paretoChartInstance = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [
                {
                    label: 'Pareto Optimal',
                    data: paretoPoints,
                    backgroundColor: '#10b981',
                    pointRadius: 6,
                    showLine: true, 
                    borderColor: 'rgba(16, 185, 129, 0.4)',
                    borderDash: [5, 5]
                },
                {
                    label: 'Dominated Locations',
                    data: nonParetoPoints,
                    backgroundColor: '#64748b',
                    pointRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: { label: ctx => ctx.raw.store.name }
                }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Demand Reached', color: '#94a3b8' },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#94a3b8' }
                },
                y: {
                    title: { display: true, text: 'Cannibalization Demand', color: '#94a3b8' },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#94a3b8' }
                }
            },
            onClick: (e, activeElements) => {
                if (activeElements.length > 0) {
                    const el = activeElements[0];
                    const data = paretoChartInstance.data.datasets[el.datasetIndex].data[el.index];
                    focusStore(data.store);
                }
            }
        }
    });
}

function focusStore(store) {
    const latlng = [store.lat, store.lng];
    map.flyTo(latlng, 13, { duration: 0.5 });
    
    dynamicCatchmentLayers.clearLayers();
    
    const isBadOverlap = store.self_overlap_count > 0 && store.nearest_sister_dist < 3;
    const color = isBadOverlap ? '#f43f5e' : '#38bdf8';
    
    L.circle(latlng, {
        color: color,
        fillColor: color,
        fillOpacity: 0.15,
        radius: RADIUS_METERS
    }).addTo(dynamicCatchmentLayers);
    
    if (store.self_overlap_count > 0) {
        const angle = Math.random() * Math.PI * 2;
        const sisterDistDeg = store.nearest_sister_dist / 111.32;
        const sisterLat = store.lat + (Math.sin(angle) * sisterDistDeg);
        const sisterLon = store.lng + (Math.cos(angle) * sisterDistDeg);
        
        L.circle([sisterLat, sisterLon], {
            color: '#10b981', // Existing store color
            fillColor: '#10b981',
            fillOpacity: 0.1,
            dashArray: '5, 10',
            radius: RADIUS_METERS
        }).addTo(dynamicCatchmentLayers);
        
        const midLat = (store.lat + sisterLat) / 2;
        const midLon = (store.lng + sisterLon) / 2;
        L.marker([midLat, midLon], { icon: createIcon('#f43f5e', '#ef4444', 10) }).addTo(dynamicCatchmentLayers);
    }
    
    dName.textContent = store.name;
    dScore.textContent = parseFloat(store.opportunity_score).toFixed(2);
    dDemand.textContent = parseFloat(store.demand_reached).toFixed(0);
    dComp.textContent = store.comp_count;
    
    if (store.self_overlap_count > 0) {
        dOverlap.textContent = `High (${parseFloat(store.self_overlap_demand).toFixed(0)} demand at risk)`;
        dOverlap.className = "value warning";
    } else {
        dOverlap.textContent = "Low (Clear territory)";
        dOverlap.className = "value highlight";
    }
    
    detailsPanel.classList.remove('hidden');
    fetchAIInsights(store);
}

async function fetchAIInsights(store) {
    const aiPanel = document.getElementById('ai-insights-panel');
    const aiLoading = document.getElementById('ai-loading');
    const aiContent = document.getElementById('ai-content');
    
    aiPanel.classList.remove('hidden');
    aiLoading.classList.remove('hidden');
    aiContent.classList.add('hidden');
    
    const params = new URLSearchParams({
        name: store.name,
        score: store.opportunity_score,
        demand: store.demand_reached,
        unmet_demand: store.unmet_demand,
        saturation: store.saturation_ratio,
        comp_pressure: store.comp_pressure,
        overlap: store.self_overlap_count,
        net_new_demand: store.net_new_demand,
        rent_adjusted: store.rent_adj_demand,
        _t: Date.now()
    });
    
    document.getElementById('ai-exec').textContent = 'Analyzing...';
    
    try {
        const response = await fetch(`/api/insight?${params.toString()}`, { cache: 'no-store' });
        const data = await response.json();
        
        document.getElementById('ai-exec').textContent = data.executive_summary || '';
        document.getElementById('ai-demand').textContent = data.demand_and_competition_narrative || '';
        document.getElementById('ai-risk').textContent = data.cannibalization_risk_assessment || '';
        document.getElementById('ai-rec').textContent = data.final_recommendation || '';
        
        aiLoading.classList.add('hidden');
        aiContent.classList.remove('hidden');
    } catch (e) {
        aiLoading.classList.add('hidden');
        document.getElementById('ai-exec').textContent = "Failed to load AI Insights.";
        aiContent.classList.remove('hidden');
    }
}

// Map Controls Logic
document.querySelectorAll('.layer-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        document.querySelectorAll('.layer-btn').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        currentMode = e.target.id.replace('btn-', '');
        plotStores();
    });
});

// Toggle Listeners
document.getElementById('toggle-demand').addEventListener('change', (e) => {
    if(e.target.checked) map.addLayer(heatmapLayer);
    else map.removeLayer(heatmapLayer);
});
document.getElementById('toggle-comps').addEventListener('change', (e) => {
    if(e.target.checked) map.addLayer(competitorsLayer);
    else map.removeLayer(competitorsLayer);
});
document.getElementById('toggle-stores').addEventListener('change', (e) => {
    if(e.target.checked) map.addLayer(existingStoresLayer);
    else map.removeLayer(existingStoresLayer);
});
document.getElementById('toggle-whitespace').addEventListener('change', (e) => {
    if(e.target.checked) map.addLayer(whiteSpaceLayer);
    else map.removeLayer(whiteSpaceLayer);
});

window.onload = loadData;
