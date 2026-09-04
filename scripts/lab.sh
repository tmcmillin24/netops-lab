#!/bin/sh

set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(dirname -- "$script_dir")
topology="$repo_dir/lab/netops.clab.yml"
runtime_dir=${CLAB_LABDIR_BASE:-"$HOME/containerlab-runtime"}

export CLAB_LABDIR_BASE="$runtime_dir"

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
