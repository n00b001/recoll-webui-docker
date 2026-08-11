#!/bin/bash
set -euo pipefail

# Runtime synchronization: mirror /generated to /runtime (bind mount)
# /runtime is the host bind-mount point; this ensures the host directory
# becomes an exact copy of the image's generated assets on every startup.
mkdir -p /runtime
rsync -a --delete /generated/ /runtime/ || true

# Execute the original command
exec "$@"