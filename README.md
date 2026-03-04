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
