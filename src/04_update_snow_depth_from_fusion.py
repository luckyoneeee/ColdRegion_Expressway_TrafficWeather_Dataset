# -*- coding: utf-8 -*-

import argparse
from pathlib import Path

import pandas as pd


class SnowDepthUpdater:
    def __init__(
        self,
        published_file: str,
        fusion_file: str,
        mapping_file: str,
        output_file: str,
        summary_file: str | None = None,
        datetime_col: str = "datetime",
        station_id_col: str = "station_id",
        fusion_station_id_col: str = "station_id",
        mapping_station_id_col: str = "station_id",
        mapping_raw_id_col: str | None = None,
        fusion_snow_depth_col: str = "snow_depth_cumulative_cm",
        output_snow_depth_col: str = "snow_depth_mm",
        input_snow_depth_unit: str = "cm"
    ):
        self.published_file = Path(published_file)
        self.fusion_file = Path(fusion_file)
        self.mapping_file = Path(mapping_file)
        self.output_file = Path(output_file)
        self.summary_file = Path(summary_file) if summary_file else None
        self.datetime_col = datetime_col
        self.station_id_col = station_id_col
        self.fusion_station_id_col = fusion_station_id_col
        self.mapping_station_id_col = mapping_station_id_col
        self.mapping_raw_id_col = mapping_raw_id_col
        self.fusion_snow_depth_col = fusion_snow_depth_col
        self.output_snow_depth_col = output_snow_depth_col
        self.input_snow_depth_unit = input_snow_depth_unit.lower()

    @staticmethod
    def normalize_id(series):
        return series.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)

    def read_inputs(self):
        for file_path in [self.published_file, self.fusion_file, self.mapping_file]:
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

        published = pd.read_csv(
            self.published_file,
            parse_dates=[self.datetime_col],
            low_memory=False
        )

        fusion = pd.read_csv(
            self.fusion_file,
            parse_dates=[self.datetime_col],
            low_memory=False
        )

        mapping = pd.read_csv(
            self.mapping_file,
            low_memory=False
        )

        return published, fusion, mapping

    def build_station_mapping(self, mapping):
        if self.mapping_station_id_col not in mapping.columns:
            raise KeyError(f"Missing anonymized station ID column: {self.mapping_station_id_col}")

        mapping = mapping.copy()
        mapping[self.mapping_station_id_col] = self.normalize_id(mapping[self.mapping_station_id_col])

        if self.mapping_raw_id_col is not None:
            if self.mapping_raw_id_col not in mapping.columns:
                raise KeyError(f"Missing raw station ID column: {self.mapping_raw_id_col}")
            raw_col = self.mapping_raw_id_col
        elif "raw_station_code" in mapping.columns:
            raw_col = "raw_station_code"
        elif "raw_station_id" in mapping.columns:
            raw_col = "raw_station_id"
        elif len(mapping.columns) == 2:
            raw_candidates = [col for col in mapping.columns if col != self.mapping_station_id_col]
            if not raw_candidates:
                raise ValueError("Unable to detect raw station ID column from the mapping file.")
            raw_col = raw_candidates[0]
        else:
            raise ValueError(
                "Unable to detect raw station ID column. "
                "Please specify --mapping-raw-id-col."
            )

        mapping[raw_col] = self.normalize_id(mapping[raw_col])

        station_map = (
            mapping[[raw_col, self.mapping_station_id_col]]
            .dropna()
            .drop_duplicates(subset=[raw_col])
            .rename(
                columns={
                    raw_col: "raw_station_id",
                    self.mapping_station_id_col: self.station_id_col
                }
            )
        )

        return station_map

    def convert_snow_depth_to_mm(self, series):
        values = pd.to_numeric(series, errors="coerce")

        if self.input_snow_depth_unit == "cm":
            return values * 10.0

        if self.input_snow_depth_unit == "mm":
            return values

        if self.input_snow_depth_unit == "m":
            return values * 1000.0

        raise ValueError("input_snow_depth_unit must be one of: cm, mm, m")

    def update_snow_depth(self):
        published, fusion, mapping = self.read_inputs()

        required_published_cols = [self.station_id_col, self.datetime_col]
        required_fusion_cols = [
            self.fusion_station_id_col,
            self.datetime_col,
            self.fusion_snow_depth_col
        ]

        missing_published_cols = [
            col for col in required_published_cols
            if col not in published.columns
        ]

        missing_fusion_cols = [
            col for col in required_fusion_cols
            if col not in fusion.columns
        ]

        if missing_published_cols:
            raise KeyError(f"Missing columns in published file: {missing_published_cols}")

        if missing_fusion_cols:
            raise KeyError(f"Missing columns in fusion file: {missing_fusion_cols}")

        published[self.station_id_col] = self.normalize_id(published[self.station_id_col])
        fusion[self.fusion_station_id_col] = self.normalize_id(fusion[self.fusion_station_id_col])

        station_map = self.build_station_mapping(mapping)

        fusion = fusion.rename(columns={self.fusion_station_id_col: "raw_station_id"})

        fusion = fusion.merge(
            station_map[["raw_station_id", self.station_id_col]],
            on="raw_station_id",
            how="left"
        )

        unmapped_records = fusion[self.station_id_col].isna().sum()

        snow_map = fusion[
            [self.station_id_col, self.datetime_col, self.fusion_snow_depth_col]
        ].copy()

        snow_map = snow_map.dropna(subset=[self.station_id_col, self.datetime_col])
        snow_map[self.station_id_col] = self.normalize_id(snow_map[self.station_id_col])
        snow_map[self.output_snow_depth_col] = self.convert_snow_depth_to_mm(
            snow_map[self.fusion_snow_depth_col]
        )

        snow_map = snow_map.drop(columns=[self.fusion_snow_depth_col])
        snow_map = snow_map.drop_duplicates(
            subset=[self.station_id_col, self.datetime_col],
            keep="first"
        )

        if self.output_snow_depth_col in published.columns:
            published = published.drop(columns=[self.output_snow_depth_col])

        updated = published.merge(
            snow_map,
            on=[self.station_id_col, self.datetime_col],
            how="left"
        )

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        updated.to_csv(self.output_file, index=False, encoding="utf-8-sig")

        missing_rate = updated[self.output_snow_depth_col].isna().mean()
        summary_lines = [
            f"Published input: {self.published_file}",
            f"Fusion input: {self.fusion_file}",
            f"Mapping input: {self.mapping_file}",
            f"Output file: {self.output_file}",
            f"Updated shape: {updated.shape}",
            f"Unmapped fusion records: {unmapped_records:,}",
            f"{self.output_snow_depth_col} missing rate: {missing_rate:.6f}"
        ]

        if pd.api.types.is_datetime64_any_dtype(updated[self.datetime_col]):
            month_missing = (
                updated.assign(month=updated[self.datetime_col].dt.to_period("M"))
                .groupby("month")[self.output_snow_depth_col]
                .apply(lambda x: x.isna().mean())
            )

            summary_lines.append("")
            summary_lines.append("Monthly missing rate:")
            summary_lines.append(month_missing.to_string())

        if self.summary_file is not None:
            self.summary_file.parent.mkdir(parents=True, exist_ok=True)
            self.summary_file.write_text("\n".join(summary_lines), encoding="utf-8-sig")

        print("\n".join(summary_lines))

        return str(self.output_file)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--published-file", required=True)
    parser.add_argument("--fusion-file", required=True)
    parser.add_argument("--mapping-file", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--summary-file", default=None)
    parser.add_argument("--datetime-col", default="datetime")
    parser.add_argument("--station-id-col", default="station_id")
    parser.add_argument("--fusion-station-id-col", default="station_id")
    parser.add_argument("--mapping-station-id-col", default="station_id")
    parser.add_argument("--mapping-raw-id-col", default=None)
    parser.add_argument("--fusion-snow-depth-col", default="snow_depth_cumulative_cm")
    parser.add_argument("--output-snow-depth-col", default="snow_depth_mm")
    parser.add_argument("--input-snow-depth-unit", default="cm", choices=["cm", "mm", "m"])
    return parser.parse_args()


def main():
    args = parse_args()

    updater = SnowDepthUpdater(
        published_file=args.published_file,
        fusion_file=args.fusion_file,
        mapping_file=args.mapping_file,
        output_file=args.output_file,
        summary_file=args.summary_file,
        datetime_col=args.datetime_col,
        station_id_col=args.station_id_col,
        fusion_station_id_col=args.fusion_station_id_col,
        mapping_station_id_col=args.mapping_station_id_col,
        mapping_raw_id_col=args.mapping_raw_id_col,
        fusion_snow_depth_col=args.fusion_snow_depth_col,
        output_snow_depth_col=args.output_snow_depth_col,
        input_snow_depth_unit=args.input_snow_depth_unit
    )

    updater.update_snow_depth()


if __name__ == "__main__":
    main()
