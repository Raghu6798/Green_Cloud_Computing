package kubernetes.admission.constraints

# This rule defines a set of regions that are compliant with GDPR.
gdpr_compliant_regions = {
    "eu-central-1",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "eu-north-1",
    "eu-south-1",
    "eu-south-2",
}

# This function checks if a given list of regions should be filtered for GDPR.
# It returns the filtered list if GDPR applies, otherwise it returns the original list.
apply_gdpr(regions) = filtered_regions {
    # Check if the user's request has a specific label indicating GDPR data.
    input.request.object.metadata.labels.data_residency == "gdpr"
    
    # Filter the incoming list of regions, keeping only those that are in our compliant set.
    filtered_regions := { region |
        region := regions[_]
        gdpr_compliant_regions[region]
    }
} else = regions {
    # If the label is not present, do not apply any filtering.
    not input.request.object.metadata.labels.data_residency == "gdpr"
}