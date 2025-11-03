package kubernetes.admission

# Import the 'apply_gdpr' function from our other policy file.
import data.kubernetes.admission.constraints.apply_gdpr

main = { "allowed": false, "reason": "Default deny." }

main = { "allowed": true, "patch": patch } {
    input.request.kind.kind == "VmTemplate"
    input.request.operation == "CREATE"

    # --- Start with a hard-coded list of all possible regions ---
    all_possible_regions := [
        "eu-central-1", "us-east-1", "ap-south-1",
        "eu-west-1", "us-west-2"
    ]

    # --- Apply Constraint Policies ---
    # 1. Apply the GDPR filter. The result is 'regions_after_gdpr'.
    regions_after_gdpr := apply_gdpr(all_possible_regions)

    # (You could chain more filters here, e.g., for latency)
    # final_eligible_regions := apply_latency(regions_after_gdpr)
    final_eligible_regions := regions_after_gdpr
    
    # --- Call the Scheduler ---
    scheduler_request_body := {
        "vm_spec": input.request.object.spec,
        "constraints": {
            # Pass the dynamically filtered list of regions to the scheduler.
            "eligible_regions": final_eligible_regions,
            "deadline_hours": 48
        }
    }

    response := http.send({
        "method": "POST",
        "url": "http://scheduler-service.default.svc.cluster.local/schedule",
        "body": scheduler_request_body
    })

    response.status_code == 200

    # --- Create the Patch (this part remains the same) ---
    patch := base64.encode(json.marshal([
        {"op": "add", "path": "/spec/schedulingLocation", "value": response.body.region},
        {"op": "add", "path": "/spec/schedulingTime", "value": response.body.startTimeUTC}
    ]))
}