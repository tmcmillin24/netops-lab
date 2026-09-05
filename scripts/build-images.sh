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
  --tag netops-network:phase7 \
  --file "$repo_dir/containers/network/Dockerfile" \
  "$repo_dir"

docker build \
  --tag netops-dc01:phase8 \
  --file "$repo_dir/containers/domain-controller/Dockerfile" \
  "$repo_dir"

docker build \
  --tag netops-file01:phase9 \
  --file "$repo_dir/containers/file-server/Dockerfile" \
  "$repo_dir"

echo "Built endpoint, network, DC01, and Phase 9 FILE01 images."
