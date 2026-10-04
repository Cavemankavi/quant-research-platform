import io
import os

import boto3
import yfinance as yf


SYMBOLS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
]

BUCKET = os.environ["RESEARCH_DATA_BUCKET"]

s3 = boto3.client("s3")


def ingest_symbol(symbol: str) -> None:
    print(f"Downloading {symbol}...")

    df = yf.download(
        symbol,
        start="2020-01-01",
        end="2026-01-01",
        auto_adjust=False,
        progress=False,
    )

    if df.empty:
        raise RuntimeError(f"No data returned for {symbol}")

    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()

    df = df[
        [
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]
    ]

    buffer = io.StringIO()
    df.to_csv(buffer)

    key = f"raw/equities/{symbol}.csv"

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=buffer.getvalue(),
        ContentType="text/csv",
    )

    print(
        f"Uploaded {len(df)} rows "
        f"to s3://{BUCKET}/{key}"
    )


def main():
    for symbol in SYMBOLS:
        ingest_symbol(symbol)


if __name__ == "__main__":
    main()