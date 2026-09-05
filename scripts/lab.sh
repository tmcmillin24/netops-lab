#!/bin/sh

set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(dirname -- "$script_dir")
base_topology="$repo_dir/lab/netops.clab.yml"
generated_topology=${NETOPS_GENERATED_TOPOLOGY:-"$HOME/netops-lab-state/netops.generated.clab.yml"}
topology="$base_topology"
[ -f "$generated_topology" ] && topology="$generated_topology"
runtime_dir=${CLAB_LABDIR_BASE:-"$HOME/containerlab-runtime"}
dc01_state_dir=${DC01_STATE_DIR:-"$HOME/netops-lab-state/dc01"}
file01_state_dir=${FILE01_STATE_DIR:-"$HOME/netops-lab-state/file01"}

export CLAB_LABDIR_BASE="$runtime_dir"
export DC01_STATE_DIR="$dc01_state_dir"
export FILE01_STATE_DIR="$file01_state_dir"

mkdir -p "$dc01_state_dir/config" "$dc01_state_dir/data"
mkdir -p "$file01_state_dir/shares/Public" "$file01_state_dir/shares/HR" \
  "$file01_state_dir/shares/Finance" "$file01_state_dir/shares/Engineering" \
  "$file01_state_dir/shares/IT-Tools"

case "${1:-}" in
  deploy)
    containerlab deploy -t "$topology"
    ;;
  destroy)
    containerlab destroy -t "$topology"
    ;;
  inspect)
    containerlab inspect -t "$topology"
    ;;
  *)
    echo "Usage: $0 {deploy|destroy|inspect}" >&2
    exit 2
    ;;
esac
