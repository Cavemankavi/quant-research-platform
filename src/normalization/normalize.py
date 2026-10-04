import io
import os

import boto3
import pandas as pd


BUCKET = os.environ["RESEARCH_DATA_BUCKET"]

SYMBOLS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
]

s3 = boto3.client("s3")


def normalize_symbol(symbol: str) -> None:

    raw_key = f"raw/equities/{symbol}.csv"

    print(f"Normalizing {symbol}...")

    response = s3.get_object(
        Bucket=BUCKET,
        Key=raw_key,
    )

    df = pd.read_csv(response["Body"])

    df = df.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )

    df["symbol"] = symbol

    df["date"] = pd.to_datetime(df["date"])

    columns = [
        "date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    df = df[columns]

    validate(df, symbol)

    output = io.StringIO()
    df.to_csv(output, index=False)

    normalized_key = (
        f"normalized/equities/{symbol}.csv"
    )

    s3.put_object(
        Bucket=BUCKET,
        Key=normalized_key,
        Body=output.getvalue(),
        ContentType="text/csv",
    )

    print(
        f"Normalized {len(df)} rows "
        f"to s3://{BUCKET}/{normalized_key}"
    )


def validate(df: pd.DataFrame, symbol: str) -> None:

    if df.empty:
        raise ValueError(f"{symbol}: dataset is empty")

    if df["date"].isnull().any():
        raise ValueError(f"{symbol}: null dates found")

    if df["symbol"].isnull().any():
        raise ValueError(f"{symbol}: null symbols found")

    if df.duplicated(
        subset=["date", "symbol"]
    ).any():
        raise ValueError(
            f"{symbol}: duplicate date/symbol rows found"
        )

    price_columns = [
        "open",
        "high",
        "low",
        "close",
    ]

    if (df[price_columns] <= 0).any().any():
        raise ValueError(
            f"{symbol}: invalid price <= 0 found"
        )

    if (df["volume"] < 0).any():
        raise ValueError(
            f"{symbol}: negative volume found"
        )


def main():

    for symbol in SYMBOLS:
        normalize_symbol(symbol)


if __name__ == "__main__":
    main()