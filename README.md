# Pharma BI Starter Kit

Ready-to-use components for pharmaceutical business intelligence: sales rep performance,
territory KPIs, and SFE (Sales Force Effectiveness) analysis.

## Domain Context

Pharma BI analysts spend significant time on rep performance reporting. This kit provides
standardized KPI calculations aligned with common pharma BI frameworks used alongside
tools like IQVIA, Veeva CRM, and Power BI.

## Features
- **Rep performance report**: attainment %, performance tier, rank, calls-per-sale
- **Territory heatmap data**: territory-level aggregation for geographic visualization
- **10-rep sample data**: Indonesian pharma market with realistic names and territories
- **Configurable thresholds**: top performer %, target attainment cutoff

## Quick Start

```python
from src.main import PharmaBIStarterKit

kit = PharmaBIStarterKit(config={
    "target_attainment_threshold": 80.0,
    "top_performers_pct": 20.0,
})

df = kit.load_data("sample_data/rep_performance.csv")
kit.validate(df)

report = kit.sales_performance_report(df)
print(f"Team Attainment: {report['team_attainment_pct']:.1f}%")
print(f"Top Performers: {report['top_performers']}")
print(f"Below Target:   {report['below_target']}")
print(report["rep_summary"][["rep_id", "attainment_pct", "performance_tier", "rank"]])

# Territory view
territory = kit.territory_heatmap_data(df)
print(territory[["territory", "territory_attainment_pct", "rep_count"]])
```

## Running Tests
```bash
pytest tests/ -v
```

---

## [v1.3.0] Territory Performance Matrix

SFE quadrant analysis for sales force effectiveness:

```python
# Build territory performance matrix
matrix = kit.territory_performance_matrix(rep_df)
print(matrix[["territory", "attainment_pct", "quadrant", "opportunity_score"]])
#   territory  attainment_pct  quadrant  opportunity_score
#       South           110.0      Star              0.841
#       North            88.5  Efficient              0.712
#        West            80.0  At Risk               0.523

# Quick KPI summary card for dashboard
kpis = kit.kpi_summary_card(rep_df)
# {"total_actual_sales": 685000, "overall_attainment_pct": 87.3,
#  "reps_on_target": 5, "reps_at_risk": 3, "periods_covered": 1}
```
