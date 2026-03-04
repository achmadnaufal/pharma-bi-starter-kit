# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.2.0] - 2026-03-04
### Added
- `sales_performance_report()`: rep attainment %, performance tiers, rank, sales/call efficiency
- `territory_heatmap_data()`: territory-level KPI aggregation for heatmap visualization
- Indonesian pharma sales rep sample data (10 reps, 5 territories)
- 15 unit tests covering validation, KPI math, territory aggregation
### Fixed
- `validate()` checks for rep_id, actual_sales, and target_sales columns
- Division-by-zero guard for reps with zero target or call count
## [1.1.0] - 2026-03-02
### Added
- Add advanced DAX patterns and Power BI governance templates
- Improved unit test coverage
- Enhanced documentation with realistic examples
