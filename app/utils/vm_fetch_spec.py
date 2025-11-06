# AWS Instance Specs
import boto3
import pandas as pd
# Azure Instance Specs
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient

# GCP Compute Engine Instance Specs
from google.cloud import compute_v1

# DigitalOcean Droplet Specs
import digitalocean

def list_machine_types(project="your-project-id", zone="us-central1-a"):
    client = compute_v1.MachineTypesClient()
    request = compute_v1.ListMachineTypesRequest(project=project, zone=zone)

    data = []
    for machine_type in client.list(request=request):
        data.append({
            "Name": machine_type.name,
            "vCPUs": machine_type.guest_cpus,
            "MemoryGiB": machine_type.memory_mb / 1024,
            "Description": machine_type.description,
            "MaxPersistentDisks": machine_type.maximum_persistent_disks,
            "MaxPersistentDiskSizeGB": machine_type.maximum_persistent_disks_size_gb,
        })

    df = pd.DataFrame(data)
    return df


def fetch_ec2_instance_specs(region_name="us-east-1"):
    ec2_client = boto3.client("ec2", region_name=region_name)

    paginator = ec2_client.get_paginator('describe_instance_types')
    page_iterator = paginator.paginate()

    instance_data = []

    for page in page_iterator:
        for instance_type in page['InstanceTypes']:
            data = {
                "InstanceType": instance_type["InstanceType"],
                "vCPUs": instance_type["VCpuInfo"]["DefaultVCpus"],
                "MemoryGiB": instance_type["MemoryInfo"]["SizeInMiB"] / 1024,
                "NetworkPerformance": instance_type.get("NetworkInfo", {}).get("NetworkPerformance", "N/A"),
                "Storage": instance_type.get("InstanceStorageInfo", {}).get("TotalSizeInGB", "EBS only"),
                "ProcessorArchitecture": ", ".join(instance_type["ProcessorInfo"]["SupportedArchitectures"]),
                "GPU_Count": instance_type.get("GpuInfo", {}).get("Gpus", [{}])[0].get("Count", 0),
                "GPU_Name": instance_type.get("GpuInfo", {}).get("Gpus", [{}])[0].get("Name", "None"),
            }
            instance_data.append(data)

    df = pd.DataFrame(instance_data)
    return df

# Authenticate using Azure CLI or environment variables
credential = DefaultAzureCredential()
subscription_id = "<your_subscription_id>"

compute_client = ComputeManagementClient(credential, subscription_id)

vm_sizes = compute_client.virtual_machine_sizes.list(location="eastus")

data = []
for size in vm_sizes:
    data.append({
        "Name": size.name,
        "NumberOfCores": size.number_of_cores,
        "MemoryInMB": size.memory_in_mb,
        "MaxDataDiskCount": size.max_data_disk_count,
        "OSDiskSizeInMB": size.os_disk_size_in_mb,
        "ResourceDiskSizeInMB": size.resource_disk_size_in_mb
    })

df = pd.DataFrame(data)
print(df.head())
df.to_csv("azure_vm_sizes.csv", index=False)

import digitalocean
import pandas as pd

# Replace with your own API token
TOKEN = "your_digitalocean_api_token"

def fetch_digitalocean_droplet_specs(token=TOKEN):
    manager = digitalocean.Manager(token=token)
    sizes = manager.get_all_sizes()

    data = []
    for size in sizes:
        data.append({
            "Slug": size.slug,
            "vCPUs": size.vcpus,
            "MemoryGB": size.memory / 1024,
            "DiskGB": size.disk,
            "TransferTB": size.transfer,
            "PriceMonthlyUSD": size.price_monthly,
            "PriceHourlyUSD": size.price_hourly,
            "Regions": ", ".join(size.regions),
            "Available": size.available
        })

    df = pd.DataFrame(data)
    return df


if __name__ == "__main__":
    ec2_specs_df = fetch_ec2_instance_specs("us-east-1")
    print(ec2_specs_df.head())
    ec2_specs_df.to_csv("ec2_instance_specs.csv", index=False)
    
    gcp_specs_df = list_machine_types("your-project-id", "us-central1-a")
    print(gcp_specs_df.head())
    gcp_specs_df.to_csv("gcp_machine_types.csv", index=False)

    azure_specs_df = fetch_azure_instance_specs("eastus")
    print(azure_specs_df.head())
    azure_specs_df.to_csv("azure_instance_specs.csv", index=False)

    droplets_specs_df = fetch_digitalocean_droplet_specs()
    print(droplets_specs_df.head())
    droplets_specs_df.to_csv("digitalocean_droplet_specs.csv", index=False)