from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import os
import uvicorn
import json
import time
import webbrowser

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

app = FastAPI()
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# Define the Pydantic schema for the LLM output
class InsightResponse(BaseModel):
    executive_summary: str = Field(description="A one-sentence overview of whether this location is viable and why.")
    demand_and_competition_narrative: str = Field(description="A 2-3 sentence explanation of the market conditions, specifically explaining how the localized revenue leakage (demand) interacts with the current competitor density. Explain if the competitors represent a threat or a validated, lucrative market.")
    cannibalization_risk_assessment: str = Field(description="A 1-2 sentence plain-language explanation of the cannibalization penalty. If the penalty is high, clearly state that while demand exists, capturing it will simply shift revenue away from an existing TradeHalo node.")
    final_recommendation: str = Field(description="A definitive 'Approve', 'Review', or 'Reject' recommendation with a brief justification.")

@app.get("/api/insight")
def handle_insight_api(
    name: str = Query("Unknown"),
    score: float = Query(0.0),
    demand: float = Query(0.0),
    unmet_demand: float = Query(0.0),
    saturation: float = Query(0.0),
    comp_pressure: float = Query(0.0),
    overlap: float = Query(0.0),
    net_new_demand: float = Query(0.0),
    rent_adjusted: float = Query(0.0),
    _t: int = Query(0, description="Cache buster")
):
    metrics = {
        "location_name": name,
        "NOI_normalized_score_0_to_1": score,
        "total_demand_reached": demand,
        "unmet_demand_capacity": unmet_demand,
        "market_saturation_ratio": saturation,
        "competitor_proximity_pressure": comp_pressure,
        "cannibalization_overlap_nodes": overlap,
        "net_new_demand_added_to_network": net_new_demand,
        "rent_adjusted_opportunity": rent_adjusted,
        "top_driving_factors": []
    }
    
    if not genai or not os.environ.get("GEMINI_API_KEY"):
        return {
            "executive_summary": "Error: GEMINI_API_KEY is not set.",
            "demand_and_competition_narrative": "Please set your API key in the terminal before running the server.",
            "cannibalization_risk_assessment": "$env:GEMINI_API_KEY='your-key'",
            "final_recommendation": "Error"
        }
        
    try:
        client = genai.Client()
        system_prompt = """You are an expert Spatial Data Analyst and Retail Expansion Strategist for TradeHalo. Your role is to interpret raw geospatial machine learning outputs and translate them into clear, plain-language business narratives for executive stakeholders.
Your analysis must weigh the complex trade-offs between localized demand (revenue leakage from missed calls), competitor agglomeration, and the negative financial impact of cannibalizing existing TradeHalo territories.
You will receive a JSON payload containing the evaluation metrics for a proposed location. You must analyze these metrics and return your response STRICTLY adhering to the exact JSON schema provided."""
        
        user_prompt = f"Please analyze the following location metrics and generate the required JSON response:\n{json.dumps(metrics)}"
        
        max_retries = 4
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        response_schema=InsightResponse,
                        temperature=0.2,
                    ),
                )
                return json.loads(response.text)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                sleep_time = 2 ** attempt
                print(f"API busy or error encountered (503). Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
                
    except Exception as e:
        return {
            "executive_summary": "Failed to call LLM API.",
            "demand_and_competition_narrative": str(e),
            "cannibalization_risk_assessment": "Ensure dependencies are installed and network is connected.",
            "final_recommendation": "Error"
        }

# Mount static files (HTML, CSS, JS, CSVs)
# Note: we mount this last so the /api routes are hit first.
app.mount("/", StaticFiles(directory=DIRECTORY, html=True), name="static")

if __name__ == "__main__":
    url = "http://localhost:8002"
    print(f"\nStarting FastAPI TradeHalo Dashboard at {url}")
    print("Press Ctrl+C to stop.\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
