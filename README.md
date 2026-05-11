# Cold-Region Expressway Traffic–Weather Dataset

This repository provides the Python scripts used to process and validate a multi-source traffic–weather dataset for expressways in cold regions. The dataset integrates hourly toll-station traffic records with ERA5-derived winter meteorological variables and supports reproducible analyses of traffic operation under snow, low temperature, and other winter weather conditions.

The repository is associated with the data article describing the construction, quality control, and technical validation of a winter expressway traffic–weather dataset.

## Dataset overview

The dataset covers hourly traffic and meteorological observations during a full winter period:

- Study period: 2022-11-01 00:00:00 to 2023-03-31 23:00:00
- Temporal resolution: hourly
- Spatial unit: toll station
- Coordinate system: WGS-84
- Main data table: `ColdRegion_Expressway_TrafficWeather_Hourly.csv`
- Station metadata table: `Station_Locations.csv`

The public dataset uses anonymized continuous station identifiers. Station coordinates are rounded for public release.

## Repository structure

```text
.
├── README.md
├── LICENSE
├── requirements.txt
├── src/
│   ├── 01_aggregate_toll_records_hourly.py
│   ├── 02_match_station_coordinates.py
│   ├── 03_inspect_era5_netcdf_structure.py
│   ├── 04_update_snow_depth_from_fusion.py
│   └── 05_build_publication_dataset.py
└── validation/
    ├── 01_data_completeness_heatmap.py
    ├── 02_speed_distribution_diurnal_variation.py
    ├── 03_spatial_distribution_map.py
    ├── 04_weekly_traffic_profile.py
    ├── 05_spring_festival_hourly_profile.py
    ├── 06_hourly_speed_boxplot.py
    ├── 07_networkwide_traffic_weather_correlation.py
    └── 08_snow_sensitive_station_correlation.py
```

## Script description

### Data processing scripts

| Script | Purpose |
|---|---|
| `src/01_aggregate_toll_records_hourly.py` | Aggregates raw toll transaction records into hourly station-level traffic indicators. |
| `src/02_match_station_coordinates.py` | Matches toll-station traffic records with station coordinate information. |
| `src/03_inspect_era5_netcdf_structure.py` | Inspects the variable, coordinate, dimension, and time structure of ERA5 NetCDF files. |
| `src/04_update_snow_depth_from_fusion.py` | Updates the snow-depth field in the public table from the corrected weather-fusion result. |
| `src/05_build_publication_dataset.py` | Builds the final public data package, including the main table, station metadata, variable description table, and summary report. |

### Validation and figure-generation scripts

| Script | Purpose |
|---|---|
| `validation/01_data_completeness_heatmap.py` | Generates the station–date data completeness heatmap. |
| `validation/02_speed_distribution_diurnal_variation.py` | Generates the speed distribution histogram and diurnal speed boxplots. |
| `validation/03_spatial_distribution_map.py` | Generates spatial maps of cumulative traffic volume and average traffic speed. |
| `validation/04_weekly_traffic_profile.py` | Generates the weekly traffic-volume and speed profiles. |
| `validation/05_spring_festival_hourly_profile.py` | Generates the Spring Festival hourly traffic profile for the highest-volume stations. |
| `validation/06_hourly_speed_boxplot.py` | Generates the hourly speed boxplot with the hourly mean-speed curve. |
| `validation/07_networkwide_traffic_weather_correlation.py` | Generates the network-wide traffic–weather correlation matrix. |
| `validation/08_snow_sensitive_station_correlation.py` | Generates the correlation matrix for the top snow-sensitive stations. |

## Environment

The scripts were developed and tested using Python 3.11 with Anaconda. The required packages can be installed using:

```bash
pip install -r requirements.txt
```

A recommended `requirements.txt` is:

```text
pandas
numpy
matplotlib
seaborn
scipy
geopandas
cartopy
openpyxl
netCDF4
xarray
```

Some spatial scripts require a working geospatial Python environment. If installation through `pip` fails for `geopandas` or `cartopy`, using `conda` is recommended:

```bash
conda install -c conda-forge geopandas cartopy shapely pyproj fiona
```

## Data availability

The processed public dataset should be downloaded from the corresponding public data repository, such as Figshare or Zenodo. The repository is designed to reproduce the processing workflow and technical validation figures when the required input files are placed under the local data directory.

For reproducibility, users may organize the local data files as follows:

```text
data/
├── raw_toll_records/
├── raw_weather/
├── processed/
├── publication_package/
└── gis/
    ├── admin_boundary.shp
    └── expressway_network/
```

The original raw toll transaction records may contain sensitive operational information and are not included in this repository. Publicly released data should use anonymized station identifiers and rounded coordinates.

## Typical workflow

### Step 1. Aggregate raw toll records to hourly station-level traffic records

```bash
python src/01_aggregate_toll_records_hourly.py ^
  --input-dir "data/raw_toll_records" ^
  --output-dir "data/processed" ^
  --output-name "hourly_toll_traffic_records.csv"
```

### Step 2. Match station coordinates

```bash
python src/02_match_station_coordinates.py ^
  --traffic-file "data/processed/hourly_toll_traffic_records.csv" ^
  --coordinate-file "data/raw_toll_records/tollgate_data.xlsx" ^
  --coordinate-sheet "高速收费站（截至2023.8）" ^
  --output-file "data/processed/traffic_records_with_coordinates.csv" ^
  --missing-report-file "data/processed/missing_station_report.csv"
```

### Step 3. Inspect ERA5 NetCDF files

```bash
python src/03_inspect_era5_netcdf_structure.py ^
  --input-file "data/raw_weather/CORRECT_instant_winter_2022_2023_final.nc" ^
  --output-file "data/processed/netcdf_structure_report.txt"
```

### Step 4. Update snow-depth information

```bash
python src/04_update_snow_depth_from_fusion.py ^
  --published-file "data/processed/ColdRegion_Expressway_TrafficWeather_Hourly_v2.csv" ^
  --fusion-file "data/processed/Jilin_Traffic_Weather_Final_v6_nearest.csv" ^
  --mapping-file "data/processed/station_id_mapping_internal.csv" ^
  --output-file "data/processed/ColdRegion_Expressway_TrafficWeather_Hourly_v3.csv" ^
  --summary-file "data/processed/snow_depth_update_summary.txt"
```

### Step 5. Build the final publication package

```bash
python src/05_build_publication_dataset.py ^
  --traffic-file "data/processed/traffic_weather_fixed_mm.csv" ^
  --weather-file "data/processed/weather_only_rebuilt.csv" ^
  --output-dir "data/publication_package" ^
  --panel-start "2022-11-01 00:00:00" ^
  --panel-end "2023-03-31 23:00:00" ^
  --coordinate-decimals 2
```

The expected outputs include:

```text
data/publication_package/
├── ColdRegion_Expressway_TrafficWeather_Hourly.csv
├── Station_Locations.csv
├── Variables_Description.csv
└── summary_report.txt
```

## Technical validation and figure reproduction

All validation scripts use command-line arguments and generate both high-resolution TIFF files and PNG preview files. The TIFF files are saved at 600 DPI.

### Data completeness heatmap

```bash
python validation/01_data_completeness_heatmap.py ^
  --input-file "data/publication_package/ColdRegion_Expressway_TrafficWeather_Hourly.csv" ^
  --output-dir "outputs/figures" ^
  --output-prefix "figure_2_data_completeness"
```

### Speed distribution and diurnal variation

```bash
python validation/02_speed_distribution_diurnal_variation.py ^
  --input-file "data/publication_package/ColdRegion_Expressway_TrafficWeather_Hourly.csv" ^
  --output-dir "outputs/figures" ^
  --output-prefix "figure_3_speed_distribution"
```

### Spatial distribution of traffic volume and speed

```bash
python validation/03_spatial_distribution_map.py ^
  --data-file "data/publication_package/ColdRegion_Expressway_TrafficWeather_Hourly.csv" ^
  --coordinate-file "data/publication_package/Station_Locations.csv" ^
  --admin-shp "data/gis/admin_boundary.shp" ^
  --road-shp-dir "data/gis/expressway_network" ^
  --output-dir "outputs/figures" ^
  --output-prefix "figure_4_spatial_distribution" ^
  --speed-col "traffic_speed_kmh" ^
  --volume-col "volume_total_veh" ^
  --station-col "station_id" ^
  --lon-col "longitude" ^
  --lat-col "latitude" ^
  --extent 120.5 132.5 39.5 47.5
```

### Weekly traffic profile

```bash
python validation/04_weekly_traffic_profile.py ^
  --input-file "data/publication_package/ColdRegion_Expressway_TrafficWeather_Hourly.csv" ^
  --output-dir "outputs/figures" ^
  --output-prefix "figure_5_weekly_traffic_profile"
```

### Spring Festival hourly profile

```bash
python validation/05_spring_festival_hourly_profile.py ^
  --input-file "data/publication_package/ColdRegion_Expressway_TrafficWeather_Hourly.csv" ^
  --output-dir "outputs/figures" ^
  --output-prefix "figure_6_spring_festival_hourly_profile" ^
  --cny-date "2023-01-22"
```

### Hourly speed boxplot

```bash
python validation/06_hourly_speed_boxplot.py ^
  --input-file "data/publication_package/ColdRegion_Expressway_TrafficWeather_Hourly.csv" ^
  --output-dir "outputs/figures" ^
  --output-prefix "figure_7_hourly_speed_boxplot"
```

### Network-wide traffic–weather correlation matrix

```bash
python validation/07_networkwide_traffic_weather_correlation.py ^
  --input-file "data/publication_package/ColdRegion_Expressway_TrafficWeather_Hourly.csv" ^
  --output-dir "outputs/figures" ^
  --output-prefix "figure_8_networkwide_correlation_matrix"
```

### Snow-sensitive station correlation matrix

```bash
python validation/08_snow_sensitive_station_correlation.py ^
  --input-file "data/publication_package/ColdRegion_Expressway_TrafficWeather_Hourly.csv" ^
  --output-dir "outputs/figures" ^
  --output-prefix "figure_9_snow_sensitive_station_correlation" ^
  --snow-threshold-mm 20 ^
  --top-k 5
```

## Output figures

The validation scripts generate publication-ready figures in TIFF format and preview images in PNG format. Typical outputs are written to:

```text
outputs/figures/
├── figure_2_data_completeness.tif
├── figure_3_speed_distribution.tif
├── figure_4_spatial_distribution.tif
├── figure_5_weekly_traffic_profile.tif
├── figure_6_spring_festival_hourly_profile.tif
├── figure_7_hourly_speed_boxplot.tif
├── figure_8_networkwide_correlation_matrix.tif
└── figure_9_snow_sensitive_station_correlation.tif
```

## Notes on reproducibility

1. All scripts use command-line arguments to avoid hard-coded local paths.
2. Public station identifiers are anonymized continuous integers.
3. Public coordinates are rounded to reduce location sensitivity.
4. Traffic-volume missing values are represented as zero when no valid station-hour traffic observation is available.
5. Speed values outside the specified cleaning range are excluded from selected validation figures.
6. The spatial map requires local GIS shapefiles for administrative boundaries and the expressway network.

## License

The code in this repository is released under the license specified in `LICENSE`. The public dataset should follow the license of the corresponding data repository. For open scientific reuse, CC BY 4.0 is recommended for the released dataset.

## Citation

If you use this dataset or code, please cite the associated data article and the public dataset repository DOI once available.
