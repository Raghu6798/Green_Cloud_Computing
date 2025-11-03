import sys
import datetime
import pandas as pd
import numpy as np
import torch
from loguru import logger
from flask import Flask, request, jsonify

from tsfm_public.toolkit.get_model import get_model
from tsfm_public.toolkit.time_series_preprocessor import TimeSeriesPreprocessor

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time} {level} {message}")
app = Flask(__name__)

# --- Model and Preprocessing Configuration ---
TTM_MODEL_PATH = "ibm-granite/granite-timeseries-ttm-r1"
CONTEXT_LENGTH = 1024
PREDICTION_LENGTH = 96 

# --- Load Model and Preprocessor ONCE at Startup ---
logger.info(f"Loading TTM model: {TTM_MODEL_PATH}...")
try:
    model = get_model(
        TTM_MODEL_PATH,
        context_length=CONTEXT_LENGTH,
        prediction_length=PREDICTION_LENGTH,
        freq_prefix_tuning=False,
        prefer_l1_loss=False,
    )
    
    logger.info("Model and TimeSeriesPreprocessor loaded successfully.")
except Exception as e:
    logger.error(f"FATAL: Could not load model or preprocessor. Error: {e}")
    model = None

# --- 2. Core Forecasting and Scheduling Logic ---

def get_carbon_forecast_for_one_region(hours_to_forecast):
    """Generates a forecast for a single region."""
    
    # 1. Simulate fetching the last CONTEXT_LENGTH hours of data
    historical_dates = pd.to_datetime(pd.date_range(end=pd.Timestamp.now(tz='UTC'), periods=CONTEXT_LENGTH, freq='h'))
    logger.info(f"Historical dates: {historical_dates}")
    historical_values = torch.randn(CONTEXT_LENGTH).numpy() * 50 + 150
    logger.info(f"Historical values: {historical_values}")
    historical_df = pd.DataFrame({"date": historical_dates, "value": historical_values})
    logger.info(f"Historical DataFrame: {historical_df}")
    # 2. Build raw past_values for the model (let model handle scaling)
    values_np = historical_df["value"].to_numpy(dtype=np.float32).reshape(-1, 1)
    values_np = np.nan_to_num(values_np, nan=0.0, posinf=0.0, neginf=0.0)
    context_tensor = torch.from_numpy(values_np).unsqueeze(0)
    logger.info(f"Context tensor: {context_tensor}")
    # 5. Generate the forecast using forward pass
    with torch.no_grad():
        outputs = model(past_values=context_tensor.cpu())
    logger.info(f"Outputs: {outputs}")
    # 6. Extract and truncate to requested horizon
    # outputs.prediction_outputs: [batch_size, prediction_length, num_input_channels]
    forecast_np = outputs.prediction_outputs.squeeze(0).cpu().numpy()
    truncated = forecast_np[:hours_to_forecast, 0]
    # 7. Clamp to non-negative intensities
    truncated = np.clip(truncated, a_min=0.0, a_max=None)
    return truncated.tolist()

def find_optimal_schedule(forecasts, vm_duration_hours, deadline_hours):
    """This optimization logic remains unchanged."""
    best_region, best_start_hour, lowest_avg_intensity = None, -1, float('inf')
    logger.info(f"Finding optimal schedule for {forecasts} with VM duration {vm_duration_hours} and deadline {deadline_hours}")
    for region, intensity_data in forecasts.items():
        for start_hour in range(deadline_hours - vm_duration_hours + 1):
            window = intensity_data[start_hour : start_hour + vm_duration_hours]
            if not window: continue
            avg_intensity = sum(window) / len(window)
            if avg_intensity < lowest_avg_intensity:
                lowest_avg_intensity = avg_intensity
                best_region = region
                best_start_hour = start_hour
    logger.info(f"Best region: {best_region}, Best start hour: {best_start_hour}, Lowest average intensity: {lowest_avg_intensity}")
    if best_start_hour == -1: return None
    schedule_time = datetime.datetime.utcnow() + datetime.timedelta(hours=best_start_hour)
    logger.info(f"Schedule time: {schedule_time}")
    return {
        "region": best_region,
        "startTimeUTC": schedule_time.isoformat() + "Z",
        "estimatedAvgIntensity": lowest_avg_intensity
    }
    logger.info(f"Optimal schedule: {optimal_schedule}")
# --- 3. The API Endpoint ---
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for debugging."""
    return jsonify({"status": "healthy", "model_loaded": model is not None}), 200

@app.route('/schedule', methods=['POST'])
def schedule():
    """The main API endpoint that OPA calls."""
    # (This function is identical to the previous correct version)
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    data = request.json
    logger.info(f"Received scheduling request: {data}")
    vm_spec = data.get('vm_spec', {})
    constraints = data.get('constraints', {})
    eligible_regions = constraints.get('eligible_regions', ['eu-west-1', 'us-east-2', 'ap-northeast-1'])
    vm_duration = vm_spec.get('duration_hours', 4)
    deadline = min(constraints.get('deadline_hours', 24), PREDICTION_LENGTH)
    try:
        all_forecasts = {}
        for region in eligible_regions:
            logger.info(f"  - Generating forecast for region: {region}")
            all_forecasts[region] = get_carbon_forecast_for_one_region(hours_to_forecast=deadline)
        optimal_schedule = find_optimal_schedule(all_forecasts, vm_duration, deadline)
    except Exception as e:
        logger.error(f"An error occurred during scheduling: {e}")
        return jsonify({"error": "Failed to process schedule due to an internal error."}), 500
    if optimal_schedule is None:
        return jsonify({"error": "Could not determine an optimal schedule."}), 500
    logger.success(f"Determined optimal schedule: {optimal_schedule}")
    return jsonify(optimal_schedule)

# --- 4. Run the Application ---
if __name__ == '__main__':
    if model:
        app.run(host='127.0.0.1', port=5000)
    else:
        logger.error("Application startup failed: TTM model could not be loaded.")