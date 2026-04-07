# Changelog

## [0.11.0] - 2026-04-14

### Added
- **HCP Targeting Optimizer** (`src/hcp_targeting.py`)
  - `HCPTargetingOptimizer`: LP-based call frequency optimization across HCP segments
  - `segment_hcps()`: high/medium/low potential segmentation by volume + potential
  - `optimize_reach()`: scipy LP to maximize Rx lift given call capacity constraints
  - `calculate_roi_per_segment()`: call cost vs expected revenue per segment
  - `territory_balancer()`: balanced rep workload across HCP potential tiers
  - `next_best_action()`: next-best-action recommendations (detail/sample/trial/CME)
  - `HCPProfile` dataclass: specialty, region, volume, share, engagement data
- **Unit tests** — 30+ tests in `tests/test_hcp_targeting.py`
- **Sample data** — `sample_data/hcp_profiles.csv` (20 HCPs across oncology/CV/diabetes)

### References
- IQVIA APAC SFE Methodology (2023)
- Veeva CRM Segmentation best practices
- ISPOR Healthcare Decision Modelling Guidelines

## [1.5.0] - 2026-03-26

### Added
- **SalesForceEffectivenessScorer** (`src/sales_force_effectiveness_scorer.py`) — IQVIA-aligned SFE scoring engine
  - Four specialty benchmarks: Primary Care, Specialty, Hospital, Oncology (IQVIA APAC 2024)
  - Five weighted dimensions: coverage (25%), frequency (20%), quality (20%), NTB (20%), attainment (15%)
  - `RepPerformanceRecord` dataclass with computed properties: coverage%, calls/day, calls/prescriber, NTB rate, attainment%
  - Tier classification: A+ / A / B / C / D with per-tier thresholds
  - Benchmark comparison against low / median / top-quartile for each dimension
  - Strengths and coaching priority auto-identification
  - Actionable coaching recommendations per dimension gap
  - `score_team()`: batch scoring sorted by composite score descending
  - `team_summary()`: tier distribution, avg SFE score, coaching count
  - Custom dimension weight override with validation
- Unit tests: 12 new tests in `tests/test_sales_force_effectiveness_scorer.py`

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

## [1.6.0] - 2026-03-27

### Added
- **Patient Adherence Tracker** (`src/patient_adherence_tracker.py`) — MPR/PDC/persistence analytics from pharmacy claims
  - `PrescriptionFill` dataclass: patient_id, drug_name, fill_date, days_supply, quantity; computed `end_date` property
  - `PatientAdherenceTracker` class with configurable observation window (30–730 days), PDC threshold, discontinuation gap
  - `add_fill()` / `add_fills()` with type validation and batch support
  - `compute_metrics()`: PDC (Proportion of Days Covered, no overlap credit), MPR (capped at 1.0), adherence tier (adherent/partially_adherent/non_adherent), refill gap analysis, discontinuation flag, persistence days
  - `population_adherence_summary()`: fleet-level PDC, MPR, discontinuation rate, mean persistence
  - `at_risk_patients()`: identify patients past refill run-out with risk level (medium/high)
  - Industry-standard thresholds: PDC ≥ 80% = adherent (ISPOR); gap > 60 days = discontinuation
- **Unit tests** — 36 new tests in `tests/test_patient_adherence_tracker.py`

### References
- Nau et al. (2009) J Manag Care Pharm 15(6):S2-10 — MPR vs PDC
- Peterson et al. (2007) Am J Manag Care 13(3 Suppl):S68-85 — 80% threshold
