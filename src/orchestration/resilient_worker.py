import argparse
import json
import os
import socket
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


BUCKET = os.environ["RESEARCH_DATA_BUCKET"]
s3 = boto3.client("s3")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def checkpoint_key(run_id, task_id):
    return f"checkpoints/{run_id}/task-{task_id}.json"


def result_key(run_id, task_id):
    return f"results/{run_id}/task-{task_id}.json"


def load_checkpoint(run_id, task_id):
    key = checkpoint_key(run_id, task_id)

    try:
        response = s3.get_object(Bucket=BUCKET, Key=key)
        return json.loads(response["Body"].read())

    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return None
        raise


def save_checkpoint(run_id, task_id, completed_chunk, total_chunks):
    checkpoint = {
        "run_id": run_id,
        "task_id": task_id,
        "completed_chunk": completed_chunk,
        "total_chunks": total_chunks,
        "status": "RUNNING",
        "hostname": socket.gethostname(),
        "slurm_job_id": os.getenv("SLURM_JOB_ID"),
        "slurm_restart_count": os.getenv("SLURM_RESTART_COUNT", "0"),
        "updated_at": utc_now(),
    }

    s3.put_object(
        Bucket=BUCKET,
        Key=checkpoint_key(run_id, task_id),
        Body=json.dumps(checkpoint, indent=2),
        ContentType="application/json",
    )


def save_result(run_id, task_id, total_chunks):
    result = {
        "run_id": run_id,
        "task_id": task_id,
        "total_chunks": total_chunks,
        "status": "SUCCEEDED",
        "hostname": socket.gethostname(),
        "slurm_job_id": os.getenv("SLURM_JOB_ID"),
        "slurm_restart_count": os.getenv("SLURM_RESTART_COUNT", "0"),
        "completed_at": utc_now(),
    }

    s3.put_object(
        Bucket=BUCKET,
        Key=result_key(run_id, task_id),
        Body=json.dumps(result, indent=2),
        ContentType="application/json",
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-id", required=True, type=int)
    parser.add_argument("--chunks", type=int, default=20)
    parser.add_argument("--seconds-per-chunk", type=int, default=30)

    args = parser.parse_args()

    hostname = socket.gethostname()

    print("=== Resilient Worker ===", flush=True)
    print(f"Run ID: {args.run_id}", flush=True)
    print(f"Task ID: {args.task_id}", flush=True)
    print(f"Hostname: {hostname}", flush=True)
    print(
        f"Slurm restart count: {os.getenv('SLURM_RESTART_COUNT', '0')}",
        flush=True,
    )

    checkpoint = load_checkpoint(args.run_id, args.task_id)

    if checkpoint:
        start_chunk = checkpoint["completed_chunk"] + 1

        print(
            f"Checkpoint found. "
            f"Last completed chunk: {checkpoint['completed_chunk']}",
            flush=True,
        )
        print(f"Resuming from chunk {start_chunk}", flush=True)

    else:
        start_chunk = 1

        print("No checkpoint found.", flush=True)
        print("Starting from chunk 1.", flush=True)

    for chunk in range(start_chunk, args.chunks + 1):

        print(
            f"Processing chunk {chunk}/{args.chunks} "
            f"on {hostname}",
            flush=True,
        )

        # Simulates expensive computation.
        time.sleep(args.seconds_per_chunk)

        save_checkpoint(
            args.run_id,
            args.task_id,
            chunk,
            args.chunks,
        )

        print(
            f"Checkpoint saved after chunk {chunk}",
            flush=True,
        )

    save_result(
        args.run_id,
        args.task_id,
        args.chunks,
    )

    print("Task completed successfully.", flush=True)


if __name__ == "__main__":
    main()