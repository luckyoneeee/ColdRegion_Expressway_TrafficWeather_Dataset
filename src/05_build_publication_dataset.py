# -*- coding: utf-8 -*-

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


TRAFFIC_COLUMNS = [
    "traffic_speed_kmh",
    "volume_total_veh",
    "volume_passenger_veh",
    "volume_truck_veh",
]

WEATHER_COLUMNS = [
    "snow_depth_mm",
    "temperature_c",
]


def read_csv_robust(path: Path) -> pd.DataFrame:
    encodings = ["utf-8-sig", "utf-8", "gbk", "gb18030"]
    last_error = None

    for encoding in encodings:
        try:
            return pd.read_csv(path, encoding=encoding, low_memory=False)
        except Exception as exc:
            last_error = exc

    raise last_error


def normalize_columns(data: pd.DataFrame) -> pd.DataFrame:
    data.columns = [str(col).strip() for col in data.columns]
    return data


def first_non_null(series: pd.Series):
    values = series.dropna()
    return values.iloc[0] if len(values) > 0 else np.nan


def safe_to_csv(data: pd.DataFrame, path: Path, **kwargs):
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if path.exists():
            path.unlink()
        data.to_csv(path, index=False, **kwargs)
    except PermissionError:
        raise PermissionError(
            f"Unable to write file: {path}. "
            "Please make sure the file is not opened by another program."
        )


def resolve_column(columns, candidates, target_name):
    lower_map = {str(col).lower(): col for col in columns}

    for candidate in candidates:
        candidate_lower = candidate.lower()
        if candidate_lower in lower_map:
            return lower_map[candidate_lower]

    for col in columns:
        col_lower = str(col).lower()

        if target_name == "traffic_speed_kmh" and "speed" in col_lower:
            return col

        if target_name == "volume_total_veh":
            if "total" in col_lower and ("volume" in col_lower or "flow" in col_lower):
                return col

        if target_name == "volume_passenger_veh":
            if "passenger" in col_lower and ("volume" in col_lower or "flow" in col_lower):
                return col

        if target_name == "volume_truck_veh":
            if ("truck" in col_lower or "freight" in col_lower) and ("volume" in col_lower or "flow" in col_lower):
                return col

        if target_name == "datetime":
            if "time" in col_lower or "date" in col_lower:
                return col

        if target_name == "raw_station_code":
            if "station" in col_lower and ("code" in col_lower or "id" in col_lower):
                return col

        if target_name == "longitude":
            if col_lower in ["lon", "lng"] or "longitude" in col_lower:
                return col

        if target_name == "latitude":
            if col_lower == "lat" or "latitude" in col_lower:
                return col

    return None


def to_numeric(series):
    return pd.to_numeric(series, errors="coerce")


class PublicationDatasetBuilder:
    def __init__(
        self,
        traffic_file: str,
        weather_file: str,
        output_dir: str,
        panel_start: str,
        panel_end: str,
        coordinate_decimals: int = 2,
        strict_mode: bool = True,
        main_output_name: str = "ColdRegion_Expressway_TrafficWeather_Hourly.csv",
        station_output_name: str = "Station_Locations.csv",
        variable_output_name: str = "Variables_Description.csv",
        summary_output_name: str = "summary_report.txt"
    ):
        self.traffic_file = Path(traffic_file)
        self.weather_file = Path(weather_file)
        self.output_dir = Path(output_dir)
        self.panel_start = pd.Timestamp(panel_start)
        self.panel_end = pd.Timestamp(panel_end)
        self.coordinate_decimals = coordinate_decimals
        self.strict_mode = strict_mode
        self.main_output = self.output_dir / main_output_name
        self.station_output = self.output_dir / station_output_name
        self.variable_output = self.output_dir / variable_output_name
        self.summary_output = self.output_dir / summary_output_name
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_traffic_input(self):
        if not self.traffic_file.exists():
            raise FileNotFoundError(f"Traffic input file not found: {self.traffic_file}")

        traffic_raw = normalize_columns(read_csv_robust(self.traffic_file))

        candidate_map = {
            "datetime": ["datetime", "time", "timestamp", "date_time", "observation_time"],
            "raw_station_code": [
                "raw_station_code",
                "station_code",
                "station_id",
                "exit_station_code",
                "toll_station_code",
                "station",
                "out_station_code",
                "exit_code"
            ],
            "longitude": ["longitude", "lon", "lng", "station_longitude"],
            "latitude": ["latitude", "lat", "station_latitude"],
            "traffic_speed_kmh": ["traffic_speed_kmh", "avg_speed", "average_speed", "speed_kmh", "speed"],
            "volume_total_veh": ["volume_total_veh", "total_volume", "volume_total", "total_flow"],
            "volume_passenger_veh": ["volume_passenger_veh", "passenger_volume", "passenger_flow"],
            "volume_truck_veh": ["volume_truck_veh", "truck_volume", "truck_flow", "freight_volume"],
        }

        resolved = {
            target: resolve_column(traffic_raw.columns.tolist(), candidates, target)
            for target, candidates in candidate_map.items()
        }

        missing_targets = [target for target, source in resolved.items() if source is None]

        if missing_targets:
            raise KeyError(
                f"Unable to resolve the following traffic variables: {missing_targets}. "
                f"Resolved mapping: {resolved}"
            )

        traffic_work = pd.DataFrame()
        traffic_work["datetime"] = pd.to_datetime(traffic_raw[resolved["datetime"]], errors="coerce")
        traffic_work["raw_station_code"] = traffic_raw[resolved["raw_station_code"]].astype(str).str.strip()
        traffic_work["longitude"] = to_numeric(traffic_raw[resolved["longitude"]])
        traffic_work["latitude"] = to_numeric(traffic_raw[resolved["latitude"]])
        traffic_work["traffic_speed_kmh"] = to_numeric(traffic_raw[resolved["traffic_speed_kmh"]])
        traffic_work["volume_total_veh"] = to_numeric(traffic_raw[resolved["volume_total_veh"]])
        traffic_work["volume_passenger_veh"] = to_numeric(traffic_raw[resolved["volume_passenger_veh"]])
        traffic_work["volume_truck_veh"] = to_numeric(traffic_raw[resolved["volume_truck_veh"]])

        traffic_work = traffic_work.dropna(
            subset=["datetime", "raw_station_code", "longitude", "latitude"]
        ).copy()

        traffic_work = traffic_work[traffic_work["raw_station_code"].str.len() > 0].copy()
        traffic_work = traffic_work[
            (traffic_work["datetime"] >= self.panel_start) &
            (traffic_work["datetime"] <= self.panel_end)
        ].copy()

        return traffic_work

    def build_station_master(self, traffic_work):
        station_diagnostics = (
            traffic_work.groupby("raw_station_code")
            .agg(
                n_rows=("raw_station_code", "size"),
                lon_min=("longitude", "min"),
                lon_max=("longitude", "max"),
                lat_min=("latitude", "min"),
                lat_max=("latitude", "max"),
            )
            .reset_index()
        )

        station_diagnostics["lon_span"] = station_diagnostics["lon_max"] - station_diagnostics["lon_min"]
        station_diagnostics["lat_span"] = station_diagnostics["lat_max"] - station_diagnostics["lat_min"]

        safe_to_csv(
            station_diagnostics,
            self.output_dir / "station_coordinate_diagnostics.csv",
            encoding="utf-8-sig"
        )

        conflict_stations = station_diagnostics[
            (station_diagnostics["lon_span"] > 0.01) |
            (station_diagnostics["lat_span"] > 0.01)
        ].copy()

        if len(conflict_stations) > 0:
            safe_to_csv(
                conflict_stations,
                self.output_dir / "station_coordinate_conflicts.csv",
                encoding="utf-8-sig"
            )

            if self.strict_mode:
                raise RuntimeError(
                    f"{len(conflict_stations)} station codes have coordinate conflicts. "
                    "See station_coordinate_conflicts.csv."
                )

        station_master = (
            traffic_work.groupby("raw_station_code", as_index=False)
            .agg(
                longitude=("longitude", "mean"),
                latitude=("latitude", "mean")
            )
        )

        station_master = station_master.sort_values(
            by=["longitude", "latitude", "raw_station_code"]
        ).reset_index(drop=True)

        station_master["station_id"] = range(1, len(station_master) + 1)

        station_mapping = station_master[["raw_station_code", "station_id"]].copy()

        safe_to_csv(
            station_mapping,
            self.output_dir / "station_id_mapping_internal.csv",
            encoding="utf-8-sig"
        )

        return station_master

    def build_traffic_layer(self, traffic_work, station_master):
        traffic_panel = traffic_work.merge(
            station_master[["raw_station_code", "station_id"]],
            on="raw_station_code",
            how="left"
        )

        if traffic_panel["station_id"].isna().any():
            unmapped_rows = traffic_panel[traffic_panel["station_id"].isna()].copy()
            safe_to_csv(
                unmapped_rows,
                self.output_dir / "unmapped_traffic_rows.csv",
                encoding="utf-8-sig"
            )
            raise RuntimeError("Some traffic records could not be mapped to anonymized station IDs.")

        traffic_panel["station_id"] = traffic_panel["station_id"].astype(int)

        traffic_layer = traffic_panel[
            ["station_id", "datetime"] + TRAFFIC_COLUMNS
        ].copy()

        duplicate_count = int(traffic_layer.duplicated(subset=["station_id", "datetime"]).sum())

        if duplicate_count > 0:
            traffic_layer = (
                traffic_layer
                .groupby(["station_id", "datetime"], as_index=False)
                .agg({col: first_non_null for col in TRAFFIC_COLUMNS})
            )

        traffic_layer = traffic_layer[traffic_layer[TRAFFIC_COLUMNS].notna().any(axis=1)].copy()

        return traffic_layer

    def load_weather_layer(self, station_master):
        if not self.weather_file.exists():
            raise FileNotFoundError(f"Weather input file not found: {self.weather_file}")

        weather_raw = normalize_columns(read_csv_robust(self.weather_file))

        required_cols = ["station_id", "datetime"] + WEATHER_COLUMNS
        missing_cols = [col for col in required_cols if col not in weather_raw.columns]

        if missing_cols:
            raise KeyError(f"Missing weather columns: {missing_cols}")

        weather_raw["station_id"] = weather_raw["station_id"].astype(str).str.strip()
        weather_raw["datetime"] = pd.to_datetime(weather_raw["datetime"], errors="coerce")

        for col in WEATHER_COLUMNS:
            weather_raw[col] = to_numeric(weather_raw[col])

        weather_layer = weather_raw[
            ["station_id", "datetime"] + WEATHER_COLUMNS
        ].copy()

        raw_to_public = station_master[["raw_station_code", "station_id"]].copy()
        raw_to_public["raw_station_code"] = raw_to_public["raw_station_code"].astype(str).str.strip()

        weather_layer = weather_layer.rename(columns={"station_id": "raw_station_code"})
        weather_layer["raw_station_code"] = weather_layer["raw_station_code"].astype(str).str.strip()

        weather_layer = weather_layer.merge(
            raw_to_public,
            on="raw_station_code",
            how="left"
        )

        if weather_layer["station_id"].isna().any():
            unmapped_rows = weather_layer[weather_layer["station_id"].isna()].copy()
            safe_to_csv(
                unmapped_rows,
                self.output_dir / "unmapped_weather_rows.csv",
                encoding="utf-8-sig"
            )
            raise RuntimeError("Some weather records could not be mapped to anonymized station IDs.")

        weather_layer["station_id"] = weather_layer["station_id"].astype(int)
        weather_layer = weather_layer.drop(columns=["raw_station_code"])

        duplicate_count = int(weather_layer.duplicated(subset=["station_id", "datetime"]).sum())

        if duplicate_count > 0:
            weather_layer = (
                weather_layer
                .groupby(["station_id", "datetime"], as_index=False)
                .agg({col: first_non_null for col in WEATHER_COLUMNS})
            )

        weather_layer = weather_layer[weather_layer[WEATHER_COLUMNS].notna().any(axis=1)].copy()

        return weather_layer

    def build_public_panel(self, station_master, traffic_layer, weather_layer):
        full_time_range = pd.date_range(
            start=self.panel_start,
            end=self.panel_end,
            freq="h"
        )

        station_ids = sorted(station_master["station_id"].astype(int).unique().tolist())

        full_grid = pd.MultiIndex.from_product(
            [station_ids, full_time_range],
            names=["station_id", "datetime"]
        ).to_frame(index=False)

        public_data = full_grid.merge(
            weather_layer,
            on=["station_id", "datetime"],
            how="left"
        )

        public_data = public_data.merge(
            traffic_layer,
            on=["station_id", "datetime"],
            how="left"
        )

        for col in ["volume_total_veh", "volume_passenger_veh", "volume_truck_veh"]:
            public_data[col] = public_data[col].fillna(0).astype(int)

        public_data = public_data[
            ["datetime", "station_id"] + TRAFFIC_COLUMNS + WEATHER_COLUMNS
        ].copy()

        public_data = public_data.sort_values(
            ["station_id", "datetime"]
        ).reset_index(drop=True)

        duplicate_count = int(public_data.duplicated(subset=["station_id", "datetime"]).sum())

        if duplicate_count > 0:
            duplicated_rows = public_data[
                public_data.duplicated(subset=["station_id", "datetime"], keep=False)
            ].copy()

            safe_to_csv(
                duplicated_rows,
                self.output_dir / "final_duplicate_station_datetime.csv",
                encoding="utf-8-sig"
            )

            raise RuntimeError(
                f"Final dataset contains {duplicate_count} duplicated station-time keys."
            )

        return public_data

    def build_station_public(self, station_master):
        station_public = station_master[["station_id", "longitude", "latitude"]].copy()
        station_public["longitude"] = to_numeric(station_public["longitude"]).round(self.coordinate_decimals)
        station_public["latitude"] = to_numeric(station_public["latitude"]).round(self.coordinate_decimals)
        station_public = station_public.sort_values("station_id").reset_index(drop=True)
        return station_public

    @staticmethod
    def build_variable_description():
        return pd.DataFrame(
            [
                ["station_id", "-", "Anonymized continuous integer station identifier.", "Derived from internal station mapping"],
                ["longitude", "degree", "Longitude in the WGS-84 coordinate system, rounded for public release.", "Derived from internal station coordinates"],
                ["latitude", "degree", "Latitude in the WGS-84 coordinate system, rounded for public release.", "Derived from internal station coordinates"],
                ["datetime", "-", "Hourly timestamp in local time.", "Traffic-weather merged dataset"],
                ["traffic_speed_kmh", "km/h", "Average traffic speed at the station-hour level. Missing values indicate no valid traffic observation.", "Derived from toll transaction records"],
                ["volume_total_veh", "veh/h", "Total hourly traffic volume. Values are set to 0 when no valid traffic observation is available.", "Derived from toll transaction records"],
                ["volume_passenger_veh", "veh/h", "Hourly passenger-vehicle volume. Values are set to 0 when no valid traffic observation is available.", "Derived from toll transaction records"],
                ["volume_truck_veh", "veh/h", "Hourly truck volume. Values are set to 0 when no valid traffic observation is available.", "Derived from toll transaction records"],
                ["snow_depth_mm", "mm", "ERA5 snow-depth variable matched to each station-hour record.", "Derived from ERA5-based weather variables"],
                ["temperature_c", "°C", "ERA5 2 m air temperature matched to each station-hour record.", "Derived from ERA5-based weather variables"],
            ],
            columns=["Column_Name", "Unit", "Description", "Source"]
        )

    def build_summary(self, public_data, station_public):
        station_count = station_public["station_id"].nunique()
        row_count = len(public_data)
        start_time = public_data["datetime"].min()
        end_time = public_data["datetime"].max()

        days = None
        expected_total = None
        valid_traffic_records = None
        traffic_missing_rate = None
        weather_valid_records = None
        weather_valid_rate = None

        if pd.notna(start_time) and pd.notna(end_time):
            days = (start_time.normalize() - start_time.normalize()).days + 1
            days = (end_time.normalize() - start_time.normalize()).days + 1
            expected_total = station_count * days * 24
            valid_traffic_records = int(public_data["traffic_speed_kmh"].notna().sum())
            traffic_missing_rate = 1 - valid_traffic_records / expected_total if expected_total > 0 else np.nan
            weather_valid_records = int(public_data[WEATHER_COLUMNS].notna().any(axis=1).sum())
            weather_valid_rate = weather_valid_records / expected_total if expected_total > 0 else np.nan

        missing_rates = public_data.isna().mean().sort_values(ascending=False)

        lines = [
            "Publication dataset summary",
            f"Traffic input file: {self.traffic_file}",
            f"Weather input file: {self.weather_file}",
            f"Output directory: {self.output_dir}",
            f"Station count: {station_count:,}",
            f"Panel rows: {row_count:,}",
            f"Valid traffic-speed records: {valid_traffic_records:,}" if valid_traffic_records is not None else "Valid traffic-speed records: N/A",
            f"Weather-valid rows: {weather_valid_records:,}" if weather_valid_records is not None else "Weather-valid rows: N/A",
            f"Station ID range: {public_data['station_id'].min()} - {public_data['station_id'].max()}",
            f"Time range: {start_time} -> {end_time}",
            f"Covered days: {days}",
            f"Theoretical complete records: {expected_total:,}" if expected_total is not None else "Theoretical complete records: N/A",
            f"Traffic missing rate: {traffic_missing_rate:.4%}" if pd.notna(traffic_missing_rate) else "Traffic missing rate: N/A",
            f"Weather coverage rate: {weather_valid_rate:.4%}" if pd.notna(weather_valid_rate) else "Weather coverage rate: N/A",
            f"Duplicated station-time keys: {public_data.duplicated(['station_id', 'datetime']).sum()}",
            "",
            "Variable missing rates"
        ]

        for key, value in missing_rates.items():
            lines.append(f"{key}: {value:.4%}")

        lines.extend(
            [
                "",
                "Output files",
                str(self.main_output),
                str(self.station_output),
                str(self.variable_output)
            ]
        )

        return "\n".join(lines)

    def run(self):
        traffic_work = self.load_traffic_input()
        station_master = self.build_station_master(traffic_work)
        traffic_layer = self.build_traffic_layer(traffic_work, station_master)
        weather_layer = self.load_weather_layer(station_master)
        public_data = self.build_public_panel(station_master, traffic_layer, weather_layer)
        station_public = self.build_station_public(station_master)
        variable_description = self.build_variable_description()
        summary = self.build_summary(public_data, station_public)

        safe_to_csv(
            public_data,
            self.main_output,
            encoding="utf-8-sig"
        )

        safe_to_csv(
            station_public,
            self.station_output,
            encoding="utf-8-sig",
            float_format=f"%.{self.coordinate_decimals}f"
        )

        safe_to_csv(
            variable_description,
            self.variable_output,
            encoding="utf-8-sig"
        )

        self.summary_output.write_text(summary, encoding="utf-8-sig")

        print(summary)

        return {
            "main_output": str(self.main_output),
            "station_output": str(self.station_output),
            "variable_output": str(self.variable_output),
            "summary_output": str(self.summary_output),
        }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--traffic-file", required=True)
    parser.add_argument("--weather-file", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--panel-start", default="2022-11-01 00:00:00")
    parser.add_argument("--panel-end", default="2023-03-31 23:00:00")
    parser.add_argument("--coordinate-decimals", type=int, default=2)
    parser.add_argument("--strict-mode", action="store_true")
    parser.add_argument("--no-strict-mode", action="store_false", dest="strict_mode")
    parser.set_defaults(strict_mode=True)
    parser.add_argument("--main-output-name", default="ColdRegion_Expressway_TrafficWeather_Hourly.csv")
    parser.add_argument("--station-output-name", default="Station_Locations.csv")
    parser.add_argument("--variable-output-name", default="Variables_Description.csv")
    parser.add_argument("--summary-output-name", default="summary_report.txt")
    return parser.parse_args()


def main():
    args = parse_args()

    builder = PublicationDatasetBuilder(
        traffic_file=args.traffic_file,
        weather_file=args.weather_file,
        output_dir=args.output_dir,
        panel_start=args.panel_start,
        panel_end=args.panel_end,
        coordinate_decimals=args.coordinate_decimals,
        strict_mode=args.strict_mode,
        main_output_name=args.main_output_name,
        station_output_name=args.station_output_name,
        variable_output_name=args.variable_output_name,
        summary_output_name=args.summary_output_name
    )

    builder.run()


if __name__ == "__main__":
    main()
