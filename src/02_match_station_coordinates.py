# -*- coding: utf-8 -*-

import argparse
from pathlib import Path

import pandas as pd


class StationCoordinateMatcher:
    def __init__(
        self,
        traffic_file: str,
        coordinate_file: str,
        output_file: str,
        missing_report_file: str,
        coordinate_sheet: str | None = None,
        station_id_col: str = "station_id",
        coordinate_id_col: str = "id",
        longitude_col: str = "x",
        latitude_col: str = "y"
    ):
        self.traffic_file = Path(traffic_file)
        self.coordinate_file = Path(coordinate_file)
        self.output_file = Path(output_file)
        self.missing_report_file = Path(missing_report_file)
        self.coordinate_sheet = coordinate_sheet
        self.station_id_col = station_id_col
        self.coordinate_id_col = coordinate_id_col
        self.longitude_col = longitude_col
        self.latitude_col = latitude_col

    @staticmethod
    def normalize_id(value):
        return str(value).strip().replace(".0", "")

    def load_traffic_data(self):
        if not self.traffic_file.exists():
            raise FileNotFoundError(f"Traffic file not found: {self.traffic_file}")

        traffic = pd.read_csv(self.traffic_file, low_memory=False)

        if self.station_id_col not in traffic.columns:
            raise KeyError(f"Missing station ID column: {self.station_id_col}")

        traffic[self.station_id_col] = traffic[self.station_id_col].map(self.normalize_id)
        return traffic

    def load_coordinate_data(self):
        if not self.coordinate_file.exists():
            raise FileNotFoundError(f"Coordinate file not found: {self.coordinate_file}")

        if self.coordinate_file.suffix.lower() in [".xlsx", ".xls"]:
            coordinates = pd.read_excel(
                self.coordinate_file,
                sheet_name=self.coordinate_sheet,
                dtype=str
            )
        else:
            coordinates = pd.read_csv(self.coordinate_file, dtype=str, low_memory=False)

        required_cols = [
            self.coordinate_id_col,
            self.longitude_col,
            self.latitude_col
        ]

        missing_cols = [col for col in required_cols if col not in coordinates.columns]

        if missing_cols:
            raise KeyError(f"Missing coordinate columns: {missing_cols}")

        coordinates = coordinates[required_cols].copy()

        coordinates = coordinates.rename(
            columns={
                self.coordinate_id_col: "coord_id",
                self.longitude_col: "lon",
                self.latitude_col: "lat"
            }
        )

        coordinates["coord_id"] = coordinates["coord_id"].map(self.normalize_id)
        coordinates["lon"] = pd.to_numeric(coordinates["lon"], errors="coerce")
        coordinates["lat"] = pd.to_numeric(coordinates["lat"], errors="coerce")

        coordinates = coordinates.dropna(subset=["coord_id", "lon", "lat"])
        coordinates = coordinates.drop_duplicates(subset=["coord_id"])

        return coordinates

    @staticmethod
    def build_coordinate_index(coordinates):
        return {
            row["coord_id"]: (row["lon"], row["lat"])
            for _, row in coordinates.iterrows()
        }

    @staticmethod
    def match_station_id(station_id, coordinate_index):
        candidate_ids = [station_id]

        if not station_id.startswith("0"):
            candidate_ids.extend([f"0{station_id}", f"00{station_id}"])

        if station_id.startswith("0"):
            stripped_id = station_id.lstrip("0")
            if stripped_id:
                candidate_ids.append(stripped_id)

        for candidate in candidate_ids:
            if candidate in coordinate_index:
                lon, lat = coordinate_index[candidate]
                return lon, lat, candidate

        station_id_lower = station_id.lower()

        for coordinate_id, coordinate_value in coordinate_index.items():
            if coordinate_id.lower() == station_id_lower:
                lon, lat = coordinate_value
                return lon, lat, coordinate_id

        return None, None, None

    def match_coordinates(self):
        traffic = self.load_traffic_data()
        coordinates = self.load_coordinate_data()
        coordinate_index = self.build_coordinate_index(coordinates)

        unique_station_ids = sorted(traffic[self.station_id_col].dropna().unique().tolist())

        matched_records = []
        missing_station_ids = []

        for station_id in unique_station_ids:
            lon, lat, matched_id = self.match_station_id(station_id, coordinate_index)

            if matched_id is None:
                missing_station_ids.append(station_id)
            else:
                matched_records.append(
                    {
                        self.station_id_col: station_id,
                        "lon": lon,
                        "lat": lat,
                        "matched_coordinate_id": matched_id
                    }
                )

        matches = pd.DataFrame(matched_records)

        merged = pd.merge(
            traffic,
            matches[[self.station_id_col, "lon", "lat"]],
            on=self.station_id_col,
            how="left"
        )

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.missing_report_file.parent.mkdir(parents=True, exist_ok=True)

        merged.to_csv(self.output_file, index=False, encoding="utf-8-sig")
        pd.DataFrame(
            {"missing_station_id": missing_station_ids}
        ).to_csv(self.missing_report_file, index=False, encoding="utf-8-sig")

        print(f"Traffic stations: {len(unique_station_ids):,}")
        print(f"Coordinate stations: {len(coordinates):,}")
        print(f"Matched stations: {len(matched_records):,}")
        print(f"Missing stations: {len(missing_station_ids):,}")
        print(f"Output file: {self.output_file}")
        print(f"Missing report: {self.missing_report_file}")

        return str(self.output_file)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--traffic-file", required=True)
    parser.add_argument("--coordinate-file", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--missing-report-file", required=True)
    parser.add_argument("--coordinate-sheet", default=None)
    parser.add_argument("--station-id-col", default="station_id")
    parser.add_argument("--coordinate-id-col", default="id")
    parser.add_argument("--longitude-col", default="x")
    parser.add_argument("--latitude-col", default="y")
    return parser.parse_args()


def main():
    args = parse_args()

    matcher = StationCoordinateMatcher(
        traffic_file=args.traffic_file,
        coordinate_file=args.coordinate_file,
        output_file=args.output_file,
        missing_report_file=args.missing_report_file,
        coordinate_sheet=args.coordinate_sheet,
        station_id_col=args.station_id_col,
        coordinate_id_col=args.coordinate_id_col,
        longitude_col=args.longitude_col,
        latitude_col=args.latitude_col
    )

    matcher.match_coordinates()


if __name__ == "__main__":
    main()
