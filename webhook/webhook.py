import sys
import json
import base64
import requests
from loguru import logger
from flask import Flask, request, jsonify

# --- Basic Setup ---
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time} {level} {message}")
app = Flask(__name__)

# --- Configuration ---
SCHEDULER_URL = "http://scheduler-service.default.svc.cluster.local/schedule"


GPU_AVAILABILITY = {
    "nvidia-tesla-t4": ["us-east-1", "us-west-2", "eu-central-1"],
    "nvidia-a100": ["us-east-1"],
}

LATENCY_ZONES = {
    "from_ap-southeast-1": {
        "ap-south-1", # Mumbai
        "ap-northeast-1", # Tokyo
        "ap-southeast-2", # Sydney
    }
}

# --- Webhook Logic ---
@app.route('/mutate', methods=['POST'])
def mutate():
    admission_review_request = request.json
    uid = admission_review_request["request"]["uid"]
    
    try:
        logger.info(f"Received AdmissionReview request [UID: {uid}]")
        vm_template = admission_review_request["request"]["object"]
        vm_spec = vm_template.get("spec", {})
        
        # --- (Policy and Scheduling logic remains the same) ---
        eligible_regions = {
            "us-east-1", "us-east-2", "us-west-2",
            "eu-central-1", "eu-west-1", "eu-west-2",
            "ap-south-1", "ap-northeast-1", "ap-southeast-2"
        }
        gpu_spec = vm_spec.get("gpu")
        if gpu_spec:
            gpu_type = gpu_spec.get("type")
            logger.info(f"[UID: {uid}] GPU constraint detected: {gpu_type}")
            if gpu_type in GPU_AVAILABILITY:
                gpu_regions = set(GPU_AVAILABILITY[gpu_type])
                eligible_regions.intersection_update(gpu_regions) # Keep only regions that have the GPU
            else:
                raise Exception(f"No regions available for GPU type: {gpu_type}")
            logger.info(f"[UID: {uid}] Regions after GPU filter: {eligible_regions}")

        # 2. Filter by Data Residency
        labels = vm_template.get("metadata", {}).get("labels", {})
        data_residency = labels.get("data_residency")
        if data_residency == "gdpr":
            logger.info(f"[UID: {uid}] GDPR constraint detected.")
            gdpr_regions = {r for r in eligible_regions if r.startswith("eu-")}
            eligible_regions = gdpr_regions
            logger.info(f"[UID: {uid}] Regions after GDPR filter: {eligible_regions}")
        elif data_residency == "usa":
            logger.info(f"[UID: {uid}] USA data residency constraint detected.")
            usa_regions = {r for r in eligible_regions if r.startswith("us-")}
            eligible_regions = usa_regions
            logger.info(f"[UID: {uid}] Regions after USA filter: {eligible_regions}")

        # 3. Filter by Latency
        latency_spec = vm_spec.get("latency")
        if latency_spec:
            origin = latency_spec.get("from_region")
            logger.info(f"[UID: {uid}] Latency constraint detected from origin: {origin}")
            latency_key = f"from_{origin}"
            if latency_key in LATENCY_ZONES:
                latency_regions = LATENCY_ZONES[latency_key]
                eligible_regions.intersection_update(latency_regions)
            else:
                # In a real system, you might have a dynamic ping test here.
                logger.warning(f"[UID: {uid}] No pre-defined latency zone for origin {origin}. Skipping filter.")
            logger.info(f"[UID: {uid}] Regions after Latency filter: {eligible_regions}")


        # --- Final Check and Call to Scheduler ---
        if not eligible_regions:
            raise Exception("No eligible regions found after applying all constraints.")
        
        logger.info(f"[UID: {uid}] Final eligible regions for scheduling: {list(eligible_regions)}")

        scheduler_request_body = {
            "vm_spec": vm_spec,
            "constraints": {
                "eligible_regions": list(eligible_regions),
                "deadline_hours": 48
            }
        }
        
        logger.info(f"[UID: {uid}] Calling scheduler at {SCHEDULER_URL}...")
        response = requests.post(SCHEDULER_URL, json=scheduler_request_body, timeout=5)
        response.raise_for_status()
        optimal_schedule = response.json()
        logger.info(f"[UID: {uid}] Received optimal schedule: {optimal_schedule}")

        patch = [
            {"op": "add", "path": "/spec/schedulingLocation", "value": optimal_schedule["region"]},
            {"op": "add", "path": "/spec/schedulingTime", "value": optimal_schedule["startTimeUTC"]}
        ]
        
        patch_str = base64.b64encode(json.dumps(patch).encode()).decode()
        
        # --- THIS IS THE FIX ---
        # The entire response must be wrapped in a top-level JSON object
        # that mirrors the AdmissionReview structure.
        admission_response = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": uid,
                "allowed": True,
                "patchType": "JSONPatch",
                "patch": patch_str,
            }
        }
        logger.success(f"[UID: {uid}] Mutation successful. Sending patch.")
        return jsonify(admission_response) # Return the full AdmissionReview object

    except Exception as e:
        logger.error(f"Webhook failed: {e}")
        # --- THIS IS ALSO FIXED ---
        # The error response must also be a valid AdmissionReview object.
        return jsonify({
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": uid,
                "allowed": False,
                "status": {"message": str(e)}
            }
        })

if __name__ == '__main__':
    # (This part remains the same)
    app.run(
        host='0.0.0.0',
        port=8443,
        ssl_context=('/etc/webhook/certs/tls.crt', '/etc/webhook/certs/tls.key')
    )