import itertools
import json
import os
import uuid

import boto3


BUCKET = os.environ["RESEARCH_DATA_BUCKET"]

s3 = boto3.client("s3")


SYMBOLS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
]

FAST_WINDOWS = [
    5,
    10,
    15,
    20,
    25,
]

SLOW_WINDOWS = [
    30,
    40,
    50,
    60,
    70,
]


def main():

    run_id = str(uuid.uuid4())

    jobs = []

    for job_id, (
        symbol,
        fast,
        slow,
    ) in enumerate(
        itertools.product(
            SYMBOLS,
            FAST_WINDOWS,
            SLOW_WINDOWS,
        )
    ):

        jobs.append({
            "job_id": job_id,
            "symbol": symbol,
            "fast_window": fast,
            "slow_window": slow,
        })

    manifest = {
        "run_id": run_id,
        "job_count": len(jobs),
        "jobs": jobs,
    }

    key = (
        f"manifests/{run_id}.json"
    )

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(
            manifest,
            indent=2,
        ),
        ContentType="application/json",
    )

    print(
        f"Created run {run_id}"
    )

    print(
        f"Jobs: {len(jobs)}"
    )

    print(
        f"Manifest: s3://{BUCKET}/{key}"
    )


if __name__ == "__main__":
    main()