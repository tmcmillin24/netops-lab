#!/bin/sh

set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(dirname -- "$script_dir")

docker build \
  --tag netops-printer:phase3 \
  --file "$repo_dir/containers/printer/Dockerfile" \
  "$repo_dir"

docker build \
  --tag netops-workstation:phase3 \
  --file "$repo_dir/containers/workstation/Dockerfile" \
  "$repo_dir"

docker build \
  --tag netops-network:phase2 \
  --file "$repo_dir/containers/network/Dockerfile" \
  "$repo_dir"

echo "Built Phase 3 endpoint images and the unchanged Phase 2 network image."
