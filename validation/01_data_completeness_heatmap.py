# -*- coding: utf-8 -*-

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def set_publication_style(font_name="Arial"):
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [font_name, "Helvetica", "Arial", "DejaVu Sans"]
    plt.rcParams["font.size"] = 8
    plt.rcParams["axes.labelsize"] = 9
    plt.rcParams["xtick.labelsize"] = 8
    plt.rcParams["ytick.labelsize"] = 8
    plt.rcParams["legend.fontsize"] = 7
    plt.rcParams["axes.linewidth"] = 0.8
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"
    plt.rcParams["savefig.facecolor"] = "white"
    plt.rcParams["savefig.edgecolor"] = "white"
    plt.rcParams["axes.unicode_minus"] = False


def get_month_tick_positions(date_range):
    tick_positions = []
    tick_labels = []

    for index, date_value in enumerate(date_range):
        timestamp = pd.Timestamp(date_value)
        if timestamp.day == 1:
            tick_positions.append(index + 0.5)
            tick_labels.append(timestamp.strftime("%b %Y"))

    return tick_positions, tick_labels


def build_daily_completeness_matrix(data, station_ids, full_date_range):
    data = data.copy()
    data["date"] = data["datetime"].dt.date

    matrix = (
        data.groupby(["station_id", "date"])
        .size()
        .unstack(fill_value=0)
    )

    matrix = matrix.reindex(
        index=station_ids,
        columns=full_date_range,
        fill_value=0
    )

    matrix["valid_count"] = matrix.sum(axis=1)
    matrix = matrix.sort_values("valid_count", ascending=True)
    matrix = matrix.drop(columns=["valid_count"])

    return matrix


def compute_completeness_statistics(data, start_time, end_time):
    station_ids = sorted(data["station_id"].unique().tolist())

    full_date_range = pd.date_range(
        start=start_time.date(),
        end=end_time.date(),
        freq="D"
    ).date

    n_stations = len(station_ids)
    n_days = len(full_date_range)
    total_expected = n_stations * n_days * 24
    total_actual = len(data)
    missing_count = total_expected - total_actual
    missing_rate = missing_count / total_expected * 100 if total_expected > 0 else np.nan

    stats = {
        "station_ids": station_ids,
        "full_date_range": full_date_range,
        "n_stations": n_stations,
        "n_days": n_days,
        "total_expected": total_expected,
        "total_actual": total_actual,
        "missing_count": missing_count,
        "missing_rate": missing_rate
    }

    return stats


def load_dataset(input_file, start_time, end_time, station_col, datetime_col):
    input_path = Path(input_file)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    data = pd.read_csv(input_path, low_memory=False)

    required_cols = [station_col, datetime_col]
    missing_cols = [col for col in required_cols if col not in data.columns]

    if missing_cols:
        raise KeyError(f"Missing required columns: {missing_cols}")

    data = data[[station_col, datetime_col]].copy()
    data = data.rename(columns={station_col: "station_id", datetime_col: "datetime"})

    data["station_id"] = data["station_id"].astype(str).str.strip()
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    data = data.dropna(subset=["station_id", "datetime"]).copy()

    data = data[
        (data["datetime"] >= start_time) &
        (data["datetime"] <= end_time)
    ].copy()

    duplicate_count = int(data.duplicated(subset=["station_id", "datetime"]).sum())

    if duplicate_count > 0:
        data = data.drop_duplicates(subset=["station_id", "datetime"], keep="first").copy()

    return data, duplicate_count


def plot_data_completeness(
    input_file,
    output_dir,
    output_prefix,
    start_time,
    end_time,
    station_col,
    datetime_col,
    font_name,
    figure_width,
    figure_height
):
    set_publication_style(font_name)

    start_time = pd.Timestamp(start_time)
    end_time = pd.Timestamp(end_time)

    data, duplicate_count = load_dataset(
        input_file=input_file,
        start_time=start_time,
        end_time=end_time,
        station_col=station_col,
        datetime_col=datetime_col
    )

    stats = compute_completeness_statistics(data, start_time, end_time)

    matrix = build_daily_completeness_matrix(
        data=data,
        station_ids=stats["station_ids"],
        full_date_range=stats["full_date_range"]
    )

    fig, ax = plt.subplots(
        figsize=(figure_width, figure_height),
        dpi=600,
        constrained_layout=False
    )

    heatmap = sns.heatmap(
        matrix,
        cmap="YlGnBu",
        vmin=0,
        vmax=24,
        xticklabels=False,
        yticklabels=False,
        linewidths=0,
        cbar_kws={
            "label": "Available hours per day (0–24)",
            "pad": 0.015,
            "shrink": 0.90
        },
        ax=ax
    )

    tick_positions, tick_labels = get_month_tick_positions(stats["full_date_range"])

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(
        tick_labels,
        rotation=0,
        ha="center",
        fontsize=8
    )

    ax.set_xlabel("Date")
    ax.set_ylabel(f"Toll stations (n = {stats['n_stations']:,})")

    colorbar = heatmap.collections[0].colorbar
    colorbar.ax.tick_params(labelsize=8, length=3, width=0.8)
    colorbar.set_label("Available hours per day (0–24)", fontsize=8, labelpad=6)

    stats_text = (
        f"Expected records: {stats['total_expected']:,}\n"
        f"Actual records: {stats['total_actual']:,}\n"
        f"Missing rate: {stats['missing_rate']:.2f}%"
    )

    fig.text(
        0.875,
        0.945,
        stats_text,
        ha="left",
        va="top",
        fontsize=7,
        bbox=dict(
            boxstyle="round,pad=0.35",
            facecolor="white",
            edgecolor="0.5",
            linewidth=0.6,
            alpha=0.95
        )
    )

    ax.tick_params(
        axis="both",
        direction="out",
        length=3,
        width=0.8
    )

    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.8)

    fig.subplots_adjust(
        left=0.08,
        right=0.84,
        bottom=0.14,
        top=0.96
    )

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    output_tif = output_path / f"{output_prefix}.tif"
    output_png = output_path / f"{output_prefix}_preview.png"
    output_txt = output_path / f"{output_prefix}_summary.txt"

    fig.savefig(
        output_tif,
        dpi=600,
        format="tiff",
        pil_kwargs={"compression": "tiff_lzw"},
        bbox_inches="tight"
    )

    fig.savefig(
        output_png,
        dpi=300,
        format="png",
        bbox_inches="tight"
    )

    plt.close(fig)

    summary_lines = [
        f"Input file: {input_file}",
        f"Start time: {start_time}",
        f"End time: {end_time}",
        f"Number of stations: {stats['n_stations']:,}",
        f"Number of days: {stats['n_days']:,}",
        f"Theoretical complete records: {stats['total_expected']:,}",
        f"Actual records: {stats['total_actual']:,}",
        f"Missing records: {stats['missing_count']:,}",
        f"Missing rate: {stats['missing_rate']:.6f}%",
        f"Duplicated station-time keys: {duplicate_count:,}",
        f"TIFF output: {output_tif}",
        f"PNG preview: {output_png}"
    ]

    output_txt.write_text("\n".join(summary_lines), encoding="utf-8-sig")

    print("\n".join(summary_lines))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-prefix", default="figure_data_completeness")
    parser.add_argument("--start-time", default="2022-11-01 00:00:00")
    parser.add_argument("--end-time", default="2023-03-31 23:00:00")
    parser.add_argument("--station-col", default="station_id")
    parser.add_argument("--datetime-col", default="datetime")
    parser.add_argument("--font-name", default="Arial")
    parser.add_argument("--figure-width", type=float, default=7.2)
    parser.add_argument("--figure-height", type=float, default=4.8)
    return parser.parse_args()


def main():
    args = parse_args()

    plot_data_completeness(
        input_file=args.input_file,
        output_dir=args.output_dir,
        output_prefix=args.output_prefix,
        start_time=args.start_time,
        end_time=args.end_time,
        station_col=args.station_col,
        datetime_col=args.datetime_col,
        font_name=args.font_name,
        figure_width=args.figure_width,
        figure_height=args.figure_height
    )


if __name__ == "__main__":
    main()
