# -*- coding: utf-8 -*-

import argparse
from pathlib import Path

import xarray as xr


def inspect_netcdf_file(input_file: str, output_file: str | None = None):
    input_path = Path(input_file)

    if not input_path.exists():
        raise FileNotFoundError(f"NetCDF file not found: {input_path}")

    lines = []
    lines.append(f"Input file: {input_path}")

    with xr.open_dataset(input_path) as ds:
        lines.append("")
        lines.append("Dimensions")
        lines.append(str(ds.dims))

        lines.append("")
        lines.append("Coordinates")
        lines.append(str(ds.coords))

        lines.append("")
        lines.append("Data variables")
        lines.append(str(list(ds.data_vars)))

        lines.append("")
        lines.append("Dataset summary")
        lines.append(str(ds))

        time_candidates = [
            name for name in list(ds.dims) + list(ds.coords)
            if "time" in name.lower() or "valid" in name.lower()
        ]

        lines.append("")
        lines.append("Possible time coordinates")
        if time_candidates:
            lines.extend(time_candidates)
        else:
            lines.append("No explicit time coordinate was detected.")

    report = "\n".join(lines)
    print(report)

    if output_file is not None:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"Report saved to: {output_path}")

    return report


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--output-file", default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    inspect_netcdf_file(
        input_file=args.input_file,
        output_file=args.output_file
    )


if __name__ == "__main__":
    main()
