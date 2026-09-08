#!/usr/bin/env bash
# Build the API image and push it to ECR.
#
#   ./deploy/push-image.sh [tag]
#
# Run from the repository root. Creates the ECR repository on first use.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
REPO="${ECR_REPO:-forexmatch-api}"
TAG="${1:-latest}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE="${REGISTRY}/${REPO}:${TAG}"

echo "==> Ensuring ECR repository '${REPO}' exists"
aws ecr describe-repositories --repository-names "${REPO}" --region "${REGION}" >/dev/null 2>&1 ||
  aws ecr create-repository \
    --repository-name "${REPO}" \
    --region "${REGION}" \
    --image-scanning-configuration scanOnPush=true >/dev/null

echo "==> Logging in to ${REGISTRY}"
aws ecr get-login-password --region "${REGION}" |
  docker login --username AWS --password-stdin "${REGISTRY}"

# App Runner runs on x86_64. Building on an Apple Silicon Mac without this flag
# produces an arm64 image that starts and then dies with an exec format error.
echo "==> Building ${IMAGE} (linux/amd64)"
docker build --platform linux/amd64 -f backend/Dockerfile -t "${IMAGE}" .

echo "==> Pushing"
docker push "${IMAGE}"

echo
echo "Image: ${IMAGE}"
