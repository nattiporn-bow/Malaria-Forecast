# District-level malaria forecasting in Thailand using climate-informed GeoAI and time-series models

This repository contains the analysis code for the master's thesis *Development of an Intelligent Spatial Model for Malaria Forecasting in Thailand Using Machine Learning and Deep Learning Techniques* (Kasetsart University) and the related manuscript *District-level malaria forecasting in Thailand using climate-informed GeoAI and time-series models*.

The pipeline links national malaria surveillance data with ERA5-Land climate data for 2016–2025. It fits seven forecasting models for each spatial unit, forecasts monthly malaria cases for 2026 and labels each unit as high or low risk.

The manuscript analysis uses restricted case-level records at district level (811 districts). This repository includes a **province-level demo** (77 provinces) with its input data, so that the whole pipeline can be run without access to the restricted records.

## Repository contents

| Path | Description |
|---|---|
| `RunModel27.2-province-demo.ipynb` | Province-level demo notebook, without outputs. Run this one. |
| `RunModel27.2-province-demo_local_run.ipynb` | The same notebook executed for all 77 provinces, showing the expected outputs |
| `malaria_province_monthly_2559_2568.csv` | Demo input: monthly malaria counts by province, 2016–2025 |
| `ERA5Land_Thailand_2016_2025.csv` | Demo input: monthly ERA5-Land climate by district, 2016–2025 |
| `download_malaria_monthly_2568.py` | Downloads the monthly province table from the public DDC malaria MIS overview |
| `LICENSE` | MIT License |

The notebook is self-contained: it needs no other code file from this repository.

## Data

### Included demo data

- **`malaria_province_monthly_2559_2568.csv`**: monthly malaria counts by province from the Malaria Online system of the Division of Vector Borne Diseases, Department of Disease Control (DDC), Ministry of Public Health, Thailand. There is one row per province per month for 2016–2025 (77 provinces × 120 months). The columns are `year_be`, `year_ce`, `month`, `month_th`, `period`, `province_id` (2-digit DOPA province code), `province` (Thai name) and `All_All` (all cases: Thai and foreign patients, all species).
- **`ERA5Land_Thailand_2016_2025.csv`**: ERA5-Land monthly aggregates (Muñoz-Sabater et al., 2021), extracted by district through Google Earth Engine. It has one row per district per month, with `ADM2_CODE`, `district`, `province`, `rain_mm_sum`, `temp_c_mean` and `RH_mean`. ERA5-Land is distributed under the Copernicus licence, which requires attribution.

The demo notebook averages the district climate values within each province (unweighted mean) and joins them to the malaria counts on `province_id` = `ADM2_CODE` // 100.

`download_malaria_monthly_2568.py` downloads the province table from the public DDC malaria MIS overview (<https://malaria.ddc.moph.go.th/malariar10/malaria_summary.php>), one month per request:

```bash
python download_malaria_monthly_2568.py 2016 2025
```

The site limits the request rate. The script waits 2 seconds between requests, skips years that are already downloaded and stops on HTTP 429.

### Restricted data (manuscript analysis)

The district-level results in the manuscript use case-level surveillance records from the Malaria Online system. These records are not included, because access is restricted by public health data governance rules. Request access from the Department of Disease Control. District boundaries come from the Department of Provincial Administration (DOPA), subject to the provider's licence.

## Requirements

The published results were produced on Ubuntu under WSL 2 with these versions:

| Package | Version |
|---|---|
| Python | 3.13.13 |
| numpy | 2.4.6 |
| pandas | 3.0.3 |
| scikit-learn | 1.8.0 |
| statsmodels | 0.14.6 |
| xgboost | 3.3.0 |
| tensorflow | 2.21.0 |
| keras | 3.14.1 |
| matplotlib | 3.10.9 |
| geopandas | 1.1.4 |
| nbconvert | 7.17.1 |

Install them with:

```bash
pip install numpy pandas scikit-learn statsmodels xgboost tensorflow matplotlib geopandas jupyter nbconvert
```

The optional GeoAI extension (Section AA) also needs `geoai-py` (<https://opengeoai.org/>).

## Running the demo

1. Clone the repository. The two demo input files are already in the repository folder.
2. Set `PARALLEL_WORKERS` in the first code cell:
   - `PARALLEL_WORKERS > 1` runs that many provinces at once in forked worker processes on the CPU. This mode needs Linux or WSL, because it uses `fork`. The example run used 8 workers.
   - `PARALLEL_WORKERS = 1` runs one province at a time in the kernel and uses a GPU when TensorFlow finds one. Use this mode on Windows.
3. Run the whole notebook from the first cell:

```bash
jupyter nbconvert --to notebook --execute RunModel27.2-province-demo.ipynb --output RunModel27.2-province-demo_run.ipynb --ExecutePreprocessor.timeout=-1
```

Results are written to `outputs_model27_2_province_demo/`. For a quick trial, set `MAX_DISTRICTS` in Section A to a small integer; in this notebook it limits the number of provinces.

Paths are relative to the folder the notebook runs from. To read data from, and write outputs to, another folder, set the `MALARIA_PROJECT_DIR` environment variable. To use another malaria file, set `MALARIA_FILE` to its path.

### Notes on the demo notebook

- The modelling code is the same as in the manuscript analysis. Only data loading, integration and descriptive text differ.
- To keep the modelling code unchanged, the unit column is still named `ADM2_CODE`, and the word "district" is kept in code, file names and figure titles. In the demo, `ADM2_CODE` holds the 2-digit province code and "district" means province.
- Sex and age tables are not produced, because the demo input is aggregated.
- The province-level results show that the tool runs end to end. They are not the district-level results reported in the manuscript.

### Main settings (Sections A and A1)

| Setting | Value | Meaning |
|---|---|---|
| `HIST_START_YEAR`–`HIST_END_YEAR` | 2016–2025 | Study period |
| `TEST_YEAR` | 2025 | External test year, not used for model selection |
| `FORECAST_YEAR` | 2026 | Forecast year |
| `EXPANDING_VALIDATION_YEARS` | 2020–2024 | Validation year of each of the five folds |
| `LOOK_BACK` | 12 | Months of history used by LSTM, GRU and XGBoost |
| `RECENT_MEDIAN_START` | 2021 | Start of the five-year baseline for risk labels |
| `KNN_CANDIDATES` | 3, 5, 7, 9, 11 | k values tested for KNN imputation |
| `FAST_MODE` | True | Uses the reduced ARIMA/SARIMA grid and one fixed LSTM specification |
| `MC_DROPOUT_ITER` | 30 | Monte Carlo dropout paths for neural network intervals |

## Outputs

Main files in `outputs_model27_2_province_demo/`:

| File or folder | Content |
|---|---|
| `integration_summary.csv`, `preprocessing_summary.csv`, `train_test_split_summary.csv` | Record counts at each processing step |
| `rolling_validation_results_all_models.csv`, `model_summary_mean_performance.csv` | Fold-level and mean validation metrics for all models |
| `best_model_by_district.csv` | Selected model and its metrics for each unit |
| `test_predictions_2025_best_model.csv` | External test predictions for 2025 |
| `forecast_2026_by_district_month.csv` | Monthly 2026 forecasts with 95% intervals |
| `risk_districts_2026_vs_recent5yrmedian.csv`, `hotspot_map_ready_risk_districts_2026.csv` | 2026 risk labels, ready to join to boundary polygons |
| `uncertainty_interval_summary_validation.csv` | Mean 95% interval bounds by unit, fold and model |
| `uncertainty_summary_by_best_model.csv` | Interval width and 95% coverage by selected model |
| `train_test_predicted_by_model/`, `train_test_predicted_ci_by_model/`, `publication_validation_results/` | Figures |
| `study_parameters.csv` | All parameters of the run |

## Reproducibility notes

- Each unit is seeded from its own `ADM2_CODE` with `keras.utils.set_random_seed`. Results therefore do not depend on the number of workers.
- CPU and GPU runs of the neural networks give slightly different numbers. The device is part of the run signature, so checkpoints from the two devices are never mixed.
- Each unit writes its own checkpoint. An interrupted run resumes from the last finished unit. A change to the parameters or to `PIPELINE_CODE_VERSION` invalidates old checkpoints and forces a full recomputation.
- In parallel mode, the notebook kernel must not import TensorFlow before Section Q. The notebook stops with an error if TensorFlow is already loaded, because forked workers would otherwise deadlock.

## Citation

If you use this code, please cite the manuscript (citation details will be added after publication):

> Thepwilai, N. & Saethang, T. District-level malaria forecasting in Thailand using climate-informed GeoAI and time-series models. *(in preparation)*.

## License

The code is released under the [MIT License](LICENSE). The licence covers the code only. The malaria counts remain subject to the terms of the Department of Disease Control, and the ERA5-Land data to the Copernicus licence.

## Acknowledgements

We thank the Division of Vector Borne Diseases, Department of Disease Control, Ministry of Public Health, Thailand, for access to the malaria surveillance data. The study was reviewed and exempted by the Kasetsart University Research Ethics Committee (COE No. COE69/07).

## Contact

Nattiporn Thepwilai, Department of Biomedical Data Science, Faculty of Science, Kasetsart University. Open an issue in this repository for questions about the code.
