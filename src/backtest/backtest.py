import argparse
import io
import json
import os
import time
import uuid

import boto3
import pandas as pd


BUCKET = os.environ["RESEARCH_DATA_BUCKET"]

s3 = boto3.client("s3")

def load_symbol_data(symbol: str) -> pd.DataFrame:
    prefix = f"curated/equities/symbol={symbol}/"

    response = s3.list_objects_v2(
        Bucket=BUCKET,
        Prefix=prefix,
    )

    objects = response.get("Contents", [])

    if not objects:
        raise RuntimeError(
            f"No curated data found for {symbol}"
        )

    frames = []

    for obj in objects:
        key = obj["Key"]

        if not key.endswith(".parquet"):
            continue

        response = s3.get_object(
            Bucket=BUCKET,
            Key=key,
        )

        data = response["Body"].read()

        frame = pd.read_parquet(
            io.BytesIO(data)
        )

        frames.append(frame)

    if not frames:
        raise RuntimeError(
            f"No Parquet partitions found for {symbol}"
        )

    df = pd.concat(
        frames,
        ignore_index=True,
    )

    df["date"] = pd.to_datetime(df["date"])

    df = df.sort_values("date")

    return df

def run_backtest(
    df: pd.DataFrame,
    fast_window: int,
    slow_window: int,
) -> dict:

    if fast_window >= slow_window:
        raise ValueError(
            "fast_window must be smaller than slow_window"
        )

    df = df.copy()

    df["fast_ma"] = (
        df["close"]
        .rolling(window=fast_window)
        .mean()
    )

    df["slow_ma"] = (
        df["close"]
        .rolling(window=slow_window)
        .mean()
    )

    df["position"] = (
        df["fast_ma"] > df["slow_ma"]
    ).astype(int)

    df["market_return"] = (
        df["close"].pct_change()
    )

    df["strategy_return"] = (
        df["position"].shift(1)
        * df["market_return"]
    )

    strategy_return = (
        (1 + df["strategy_return"].fillna(0))
        .prod()
        - 1
    )

    buy_and_hold_return = (
        df["close"].iloc[-1]
        / df["close"].iloc[0]
        - 1
    )

    trades = (
        df["position"]
        .diff()
        .abs()
        .fillna(0)
        .sum()
    )

    return {
        "strategy_return": float(strategy_return),
        "buy_and_hold_return": float(
            buy_and_hold_return
        ),
        "trades": int(trades),
        "rows_processed": len(df),
    }

def execute(
    symbol: str,
    fast_window: int,
    slow_window: int,
) -> dict:

    total_start = time.perf_counter()

    load_start = time.perf_counter()

    df = load_symbol_data(symbol)

    load_seconds = (
        time.perf_counter() - load_start
    )

    compute_start = time.perf_counter()

    results = run_backtest(
        df,
        fast_window,
        slow_window,
    )

    compute_seconds = (
        time.perf_counter() - compute_start
    )

    total_seconds = (
        time.perf_counter() - total_start
    )

    return {
        "symbol": symbol,
        "fast_window": fast_window,
        "slow_window": slow_window,
        **results,
        "timing": {
            "data_load_seconds": load_seconds,
            "compute_seconds": compute_seconds,
            "total_seconds": total_seconds,
        },
    }

def save_result(
    result: dict,
    run_id: str,
) -> None:

    symbol = result["symbol"]
    fast = result["fast_window"]
    slow = result["slow_window"]

    key = (
        f"results/{run_id}/"
        f"{symbol}-{fast}-{slow}.json"
    )

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(
            result,
            indent=2,
        ),
        ContentType="application/json",
    )

    print(
        f"Result written to "
        f"s3://{BUCKET}/{key}"
    )

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--symbol",
        required=True,
    )

    parser.add_argument(
        "--fast-window",
        required=True,
        type=int,
    )

    parser.add_argument(
        "--slow-window",
        required=True,
        type=int,
    )

    parser.add_argument(
        "--run-id",
        default=None,
    )

    args = parser.parse_args()

    run_id = (
        args.run_id
        or str(uuid.uuid4())
    )

    result = execute(
        args.symbol,
        args.fast_window,
        args.slow_window,
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )

    save_result(
        result,
        run_id,
    )


if __name__ == "__main__":
    main()