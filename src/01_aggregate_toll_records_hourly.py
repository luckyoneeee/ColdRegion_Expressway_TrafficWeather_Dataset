# -*- coding: utf-8 -*-

import argparse
import gc
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


class TollTransactionAggregator:
    def __init__(self, input_dir: str, output_dir: str | None = None):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir) if output_dir else self.input_dir.parent / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.data = None
        self.hourly_data = None

    def ingest_data(self, file_pattern: str = "*.csv") -> pd.DataFrame:
        print("=" * 60)
        print("Step 1: Data ingestion and merging")
        print("=" * 60)

        csv_files = list(self.input_dir.glob(file_pattern))

        if not csv_files:
            raise FileNotFoundError(f"No CSV files were found in {self.input_dir}")

        usecols = ["出口站编号", "最终车型", "出口日期时间", "入口日期时间", "实际里程"]
        frames = []

        for file_path in csv_files:
            df = self._read_csv_with_encoding(file_path, usecols=usecols)
            if df is not None:
                frames.append(df)
                print(f"Loaded {file_path.name}: {len(df):,} records")

        if not frames:
            raise ValueError("No valid input files were loaded.")

        self.data = pd.concat(frames, ignore_index=True)
        del frames
        gc.collect()

        print(f"Merged records: {len(self.data):,}")
        return self.data

    @staticmethod
    def _read_csv_with_encoding(file_path: Path, usecols=None) -> pd.DataFrame | None:
        encodings = ["utf-8", "gbk", "gb18030", "latin-1"]

        for encoding in encodings:
            try:
                return pd.read_csv(
                    file_path,
                    encoding=encoding,
                    usecols=usecols,
                    low_memory=False
                )
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception as exc:
                print(f"Failed to read {file_path.name}: {exc}")
                return None

        print(f"Failed to identify encoding for {file_path.name}")
        return None

    def clean_and_format(self) -> pd.DataFrame:
        print("=" * 60)
        print("Step 2: Cleaning and formatting")
        print("=" * 60)

        if self.data is None:
            raise ValueError("Run ingest_data() before clean_and_format().")

        initial_count = len(self.data)

        self.data["exit_datetime"] = pd.to_datetime(
            self.data["出口日期时间"],
            errors="coerce"
        )
        self.data["entry_datetime"] = pd.to_datetime(
            self.data["入口日期时间"],
            errors="coerce"
        )

        self.data.drop(columns=["出口日期时间", "入口日期时间"], inplace=True)

        self.data = self.data.loc[
            self.data["exit_datetime"].notna() &
            self.data["entry_datetime"].notna()
        ].reset_index(drop=True)

        self.data["duration_h"] = (
            self.data["exit_datetime"] - self.data["entry_datetime"]
        ).dt.total_seconds() / 3600

        self.data = self.data.loc[self.data["duration_h"] > 0].reset_index(drop=True)

        self.data["distance_km"] = pd.to_numeric(
            self.data["实际里程"],
            errors="coerce"
        ) / 1000

        self.data.drop(columns=["实际里程"], inplace=True)

        self.data = self.data.loc[
            self.data["distance_km"].notna() &
            (self.data["distance_km"] > 0)
        ].reset_index(drop=True)

        gc.collect()

        print(f"Cleaned records: {initial_count:,} -> {len(self.data):,}")
        return self.data

    def engineer_features(self, min_speed: float = 5.0, max_speed: float = 160.0) -> pd.DataFrame:
        print("=" * 60)
        print("Step 3: Feature engineering")
        print("=" * 60)

        if self.data is None:
            raise ValueError("Run clean_and_format() before engineer_features().")

        initial_count = len(self.data)

        vehicle_code = pd.to_numeric(
            self.data["最终车型"],
            errors="coerce"
        ).fillna(0).astype(int)

        self.data["vehicle_category"] = np.where(
            (vehicle_code >= 1) & (vehicle_code <= 4),
            "passenger",
            np.where(vehicle_code >= 11, "truck", "other")
        )

        self.data.drop(columns=["最终车型"], inplace=True)
        del vehicle_code

        self.data["speed_kmh"] = self.data["distance_km"] / self.data["duration_h"]

        self.data = self.data.loc[
            (self.data["speed_kmh"] >= min_speed) &
            (self.data["speed_kmh"] <= max_speed)
        ].reset_index(drop=True)

        gc.collect()

        print(f"Valid records after speed filtering: {initial_count:,} -> {len(self.data):,}")
        return self.data

    def aggregate_hourly(self) -> pd.DataFrame:
        print("=" * 60)
        print("Step 4: Hourly aggregation")
        print("=" * 60)

        if self.data is None:
            raise ValueError("Run engineer_features() before aggregate_hourly().")

        self.data["hour_datetime"] = self.data["exit_datetime"].dt.floor("h")

        self.data.drop(
            columns=[
                "exit_datetime",
                "entry_datetime",
                "distance_km",
                "duration_h"
            ],
            inplace=True
        )

        self.hourly_data = (
            self.data
            .groupby(["出口站编号", "hour_datetime"])
            .agg(
                total_volume=("speed_kmh", "count"),
                passenger_volume=("vehicle_category", lambda x: (x == "passenger").sum()),
                truck_volume=("vehicle_category", lambda x: (x == "truck").sum()),
                avg_speed=("speed_kmh", "mean")
            )
            .reset_index()
            .rename(
                columns={
                    "出口站编号": "station_id",
                    "hour_datetime": "datetime"
                }
            )
        )

        self.hourly_data["avg_speed"] = self.hourly_data["avg_speed"].round(2)

        del self.data
        self.data = None
        gc.collect()

        print(f"Stations: {self.hourly_data['station_id'].nunique():,}")
        print(f"Hourly records: {len(self.hourly_data):,}")
        print(f"Time range: {self.hourly_data['datetime'].min()} to {self.hourly_data['datetime'].max()}")

        return self.hourly_data

    def export_data(self, output_name: str = "hourly_toll_traffic_records.csv") -> str:
        print("=" * 60)
        print("Step 5: Export")
        print("=" * 60)

        if self.hourly_data is None:
            raise ValueError("Run aggregate_hourly() before export_data().")

        output_path = self.output_dir / output_name
        output_df = self.hourly_data.copy()

        output_df["datetime"] = output_df["datetime"].dt.strftime("%Y-%m-%d %H:00")
        output_df["total_volume"] = output_df["total_volume"].astype(int)
        output_df["passenger_volume"] = output_df["passenger_volume"].astype(int)
        output_df["truck_volume"] = output_df["truck_volume"].astype(int)

        output_df.to_csv(output_path, index=False, encoding="utf-8-sig")

        print(f"Output file: {output_path}")
        return str(output_path)

    def run(
        self,
        output_name: str = "hourly_toll_traffic_records.csv",
        file_pattern: str = "*.csv",
        min_speed: float = 5.0,
        max_speed: float = 160.0
    ) -> str:
        print("=" * 60)
        print("Toll transaction hourly aggregation pipeline")
        print("=" * 60)
        print(f"Input directory: {self.input_dir}")
        print(f"Output directory: {self.output_dir}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        self.ingest_data(file_pattern=file_pattern)
        self.clean_and_format()
        self.engineer_features(min_speed=min_speed, max_speed=max_speed)
        self.aggregate_hourly()
        output_path = self.export_data(output_name=output_name)

        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return output_path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-name", default="hourly_toll_traffic_records.csv")
    parser.add_argument("--file-pattern", default="*.csv")
    parser.add_argument("--min-speed", type=float, default=5.0)
    parser.add_argument("--max-speed", type=float, default=160.0)
    return parser.parse_args()


def main():
    args = parse_args()

    processor = TollTransactionAggregator(
        input_dir=args.input_dir,
        output_dir=args.output_dir
    )

    output_file = processor.run(
        output_name=args.output_name,
        file_pattern=args.file_pattern,
        min_speed=args.min_speed,
        max_speed=args.max_speed
    )

    print(f"Completed: {output_file}")


if __name__ == "__main__":
    main()
