# Configuration
$REGISTRY="registry.promptxchange.com"
$IMAGE_NAME="callsigndix_api"
$TAG="latest"
$FULL_IMAGE_NAME="$REGISTRY/$IMAGE_NAME`:$TAG"

Write-Host "Starting deployment process for CallsignDix API..." -ForegroundColor Cyan

# Step 1: Build Docker Image
Write-Host "Building Docker image: $FULL_IMAGE_NAME" -ForegroundColor Yellow
# Remove existing builder if it exists
#docker buildx rm arm64builder
# Create and use a new builder instance
#docker buildx create --name arm64builder --use
# Build and push in one command using buildx
docker buildx build --platform linux/arm64 -t $FULL_IMAGE_NAME --push .
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker build failed" -ForegroundColor Red
    exit 1
}
Write-Host "Docker image built successfully" -ForegroundColor Green

# Step 4: Deploy to Kubernetes
Write-Host "Deploying to Kubernetes..." -ForegroundColor Yellow
kubectl apply -f ./callsigndix-api-deployment.yaml
if ($LASTEXITCODE -ne 0) {
    Write-Host "Kubernetes deployment failed" -ForegroundColor Red
    exit 1
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "Kubernetes deployment failed" -ForegroundColor Red
    exit 1
}
Write-Host "Kubernetes deployment completed" -ForegroundColor Green

# Step 5: Verify Deployment
Write-Host "Verifying deployment..." -ForegroundColor Yellow
kubectl get pods -n callsigndix -l app=api
kubectl get service -n callsigndix

Write-Host "Deployment process completed!" -ForegroundColor Cyan