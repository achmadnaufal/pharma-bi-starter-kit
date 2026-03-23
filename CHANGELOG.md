# Changelog

## [1.4.0] - 2026-03-23

### Added
- `src/kpi_benchmarking_engine.py` — KPI benchmarking engine for pharma commercial teams
  - `KPIRecord` dataclass with attainment and delta properties
  - `KPIBenchmarkingEngine` with multi-KPI, multi-period, multi-segment support
  - `attainment_summary()` — on-target/below/above distribution + quartiles
  - `percentile_rank()` — entity ranking within peer group with tier classification
  - `zscore_analysis()` — outlier / best-in-class identification
  - `period_index()` — period-over-period index (base=100) tracking
  - `compare_to_industry()` — comparison vs IQVIA SFE benchmark ranges
  - Industry reference benchmarks for calls/day, coverage %, calls/prescriber
    across primary care, specialty, and hospital segments
- `data/sample_rep_kpi_data.csv` — 18 KPI observations for 6 oncology reps (Q1+Q2)
- 33 unit tests in `tests/test_kpi_benchmarking_engine.py`

### References
- IQVIA Pharma Benchmarking Survey 2024

## [1.3.0] - 2026-03-21

### Added
- **Data Quality Scorer** (`src/data_quality_scorer.py`) — DAMA-DMBOK2-aligned composite DQ scoring
  - 5 quality dimensions: completeness, validity, uniqueness, timeliness, consistency
  - Configurable dimension weights (default: completeness 30%, validity 25%, uniqueness 20%, timeliness 15%, consistency 10%)
  - Wilson-band rating: Excellent (≥90), Good (≥75), Acceptable (≥60), Poor (≥40), Critical (<40)
  - `score_column()` for lightweight single-column completeness check
  - Automated recommendations for the lowest-scoring dimensions
  - `DataQualityReport` and `DimensionScore` dataclasses for structured pipeline output
- **Sample data** — `sample_data/nsp_quality_sample.csv` with 10 NSP records across brands/geographies
- **Unit tests** — 21 new tests in `tests/test_data_quality_scorer.py`

## [CURRENT] - 2026-03-07

### Added
- Add advanced DAX formulas for clinical metrics
- Enhanced README with getting started guide
- Comprehensive unit tests for core functions
- Real-world sample data and fixtures

### Improved
- Edge case handling for null/empty inputs
- Boundary condition validation

### Fixed
- Various edge cases and corner scenarios

---

## [2026-03-08]
- Enhanced documentation and examples
- Added unit test fixtures and test coverage
- Added comprehensive docstrings to key functions
- Added error handling for edge cases
- Improved README with setup and usage examples
