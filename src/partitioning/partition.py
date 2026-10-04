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


def partition_symbol(symbol: str) -> None:

    key = f"normalized/equities/{symbol}.csv"

    print(f"Partitioning {symbol}...")

    response = s3.get_object(
        Bucket=BUCKET,
        Key=key,
    )

    df = pd.read_csv(
        response["Body"],
        parse_dates=["date"],
    )

    df["year"] = df["date"].dt.year

    for year, partition in df.groupby("year"):

        buffer = io.BytesIO()

        partition.drop(
            columns=["year"]
        ).to_parquet(
            buffer,
            index=False,
            engine="pyarrow",
        )

        output_key = (
            "curated/equities/"
            f"symbol={symbol}/"
            f"year={year}/"
            "data.parquet"
        )

        s3.put_object(
            Bucket=BUCKET,
            Key=output_key,
            Body=buffer.getvalue(),
            ContentType="application/octet-stream",
        )

        print(
            f"{symbol} {year}: "
            f"{len(partition)} rows"
        )


def main():

    for symbol in SYMBOLS:
        partition_symbol(symbol)


if __name__ == "__main__":
    main()