# Changelog

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
