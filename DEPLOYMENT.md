# Kubernetes Deployment Guide

This document provides the required `kubectl` commands to deploy the Carbon Scheduler system.

## Prerequisites

1. **cert-manager** must be installed in your cluster:
   ```bash
   kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
   ```
   Wait for cert-manager to be ready:
   ```bash
   kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=cert-manager -n cert-manager --timeout=300s
   ```

2. **Docker images** must be built and pushed:
   - `raghumaverick/carbon-scheduler:latest`
   - `raghumaverick/carbon-webhook:latest`

## Deployment Order

The resources must be deployed in this specific order to ensure dependencies are satisfied:

### Step 1: Deploy CustomResourceDefinition
```bash
kubectl apply -f k8s/vmtemplate-crd.yaml
```

### Step 2: Deploy Certificate and Issuer
```bash
kubectl apply -f k8s/certificate.yaml
```
Wait for the certificate to be ready:
```bash
kubectl wait --for=condition=ready certificate carbon-webhook-tls -n default --timeout=300s
```

### Step 3: Deploy Webhook Service
```bash
kubectl apply -f k8s/webhook-service.yaml
```

### Step 4: Deploy Webhook Deployment
```bash
kubectl apply -f k8s/webhook-deployment.yaml
```
Wait for the webhook pod to be ready:
```bash
kubectl wait --for=condition=ready pod -l app=carbon-webhook -n default --timeout=300s
```

### Step 5: Deploy Mutating Webhook Configuration
```bash
kubectl apply -f k8s/mutating-webhook-reg.yaml
```

### Step 6: Deploy Scheduler Service
```bash
kubectl apply -f k8s/scheduler-service.yaml
```

### Step 7: Deploy Scheduler Deployment
```bash
kubectl apply -f k8s/scheduler-deployment.yaml
```
Wait for the scheduler pod to be ready:
```bash
kubectl wait --for=condition=ready pod -l app=carbon-scheduler -n default --timeout=300s
```

### Step 8: (Optional) Deploy Example VM Templates
```bash
kubectl apply -f k8s/example_vm.yaml
kubectl apply -f k8s/example_vm_2.yaml
```

## Verification Commands

Check all pods are running:
```bash
kubectl get pods -l 'app in (carbon-scheduler, carbon-webhook)'
```

Check services:
```bash
kubectl get svc scheduler-service webhook-service
```

Check the CRD:
```bash
kubectl get crd vmtemplates.custom.greendeploy.io
```

Check the mutating webhook:
```bash
kubectl get mutatingwebhookconfiguration carbon-scheduler-webhook
```

Check certificate status:
```bash
kubectl get certificate carbon-webhook-tls
```

## All-in-One Deployment Script

For convenience, here's a script that deploys everything in order:

```bash
#!/bin/bash
set -e

echo "Deploying Carbon Scheduler..."

echo "Step 1: Deploying CRD..."
kubectl apply -f k8s/vmtemplate-crd.yaml

echo "Step 2: Deploying Certificate..."
kubectl apply -f k8s/certificate.yaml
echo "Waiting for certificate to be ready..."
kubectl wait --for=condition=ready certificate carbon-webhook-tls -n default --timeout=300s

echo "Step 3: Deploying Webhook Service..."
kubectl apply -f k8s/webhook-service.yaml

echo "Step 4: Deploying Webhook Deployment..."
kubectl apply -f k8s/webhook-deployment.yaml
echo "Waiting for webhook pod..."
kubectl wait --for=condition=ready pod -l app=carbon-webhook -n default --timeout=300s

echo "Step 5: Deploying Mutating Webhook Configuration..."
kubectl apply -f k8s/mutating-webhook-reg.yaml

echo "Step 6: Deploying Scheduler Service..."
kubectl apply -f k8s/scheduler-service.yaml

echo "Step 7: Deploying Scheduler Deployment..."
kubectl apply -f k8s/scheduler-deployment.yaml
echo "Waiting for scheduler pod..."
kubectl wait --for=condition=ready pod -l app=carbon-scheduler -n default --timeout=300s

echo "Deployment complete!"
```

## Cleanup (Undeploy)

To remove all resources, reverse the order:

```bash
kubectl delete -f k8s/mutating-webhook-reg.yaml
kubectl delete -f k8s/scheduler-deployment.yaml
kubectl delete -f k8s/scheduler-service.yaml
kubectl delete -f k8s/webhook-deployment.yaml
kubectl delete -f k8s/webhook-service.yaml
kubectl delete -f k8s/certificate.yaml
kubectl delete -f k8s/vmtemplate-crd.yaml
kubectl delete -f k8s/example_vm.yaml
kubectl delete -f k8s/example_vm_2.yaml
```

## Troubleshooting

If pods are not starting:
```bash
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

If webhook is failing:
```bash
kubectl logs -l app=carbon-webhook
```

If scheduler is failing:
```bash
kubectl logs -l app=carbon-scheduler
```

Check certificate issues:
```bash
kubectl describe certificate carbon-webhook-tls
kubectl describe secret carbon-webhook-tls
```

