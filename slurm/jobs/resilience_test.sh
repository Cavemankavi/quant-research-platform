#!/bin/bash
#SBATCH --job-name=resilience-test
#SBATCH --partition=spot
#SBATCH --array=0-7%4
#SBATCH --output=resilience-%A-%a.out
#SBATCH --error=resilience-%A-%a.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --requeue

set -e

PROJECT_DIR="/home/ubuntu/quant-research-platform"

cd "$PROJECT_DIR"

source .venv/bin/activate

export RESEARCH_DATA_BUCKET="quant-research-platform-dev-data-715a93fa9e5f586ca7bcc3f901"

RUN_ID="resilience-${SLURM_ARRAY_JOB_ID}"
TASK_ID="${SLURM_ARRAY_TASK_ID}"

echo "======================================"
echo "Resilience Test"
echo "======================================"
echo "Slurm Job ID: $SLURM_JOB_ID"
echo "Array Job ID: $SLURM_ARRAY_JOB_ID"
echo "Task ID: $TASK_ID"
echo "Hostname: $(hostname)"
echo "Restart count: ${SLURM_RESTART_COUNT:-0}"
echo "Started: $(date)"
echo "======================================"

python -m src.orchestration.resilient_worker \
    --run-id "$RUN_ID" \
    --task-id "$TASK_ID" \
    --chunks 20 \
    --seconds-per-chunk 30

echo
echo "Finished: $(date)"