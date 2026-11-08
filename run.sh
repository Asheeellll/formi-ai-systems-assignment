
#!/usr/bin/env bash
set -euo pipefail

# Usage: ./run.sh <SIM_URL>
# Example: ./run.sh http://127.0.0.1:8700

if [ "$#" -ne 1 ]; then
    echo "Usage: ./run.sh <SIM_URL>" >&2
    exit 2
fi

SIM_URL="$1"
export SIM_URL

# The evaluator invokes this script from the project root.
cd "$(dirname "$0")"

# Run until the simulator reports completion.
# A zero value disables bounded test execution.
export MAX_TICKS=0

# Ensure logs appear immediately.
export PYTHONUNBUFFERED=1

exec python -m controller.main
