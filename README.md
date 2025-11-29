# Pharma Bi Starter Kit

Starter kit for pharma BI analysts with templates, SQL queries, and best practices

## Features
- Data ingestion from CSV/Excel input files
- Automated analysis and KPI calculation
- Summary statistics and trend reporting
- Sample data generator for testing and development

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from src.main import PharmaBIStarterKit

analyzer = PharmaBIStarterKit()
df = analyzer.load_data("data/sample.csv")
result = analyzer.analyze(df)
print(result)
```

## Data Format

Expected CSV columns: `metric, value, target, period, product, territory, category`

## Project Structure

```
pharma-bi-starter-kit/
├── src/
│   ├── main.py          # Core analysis logic
│   └── data_generator.py # Sample data generator
├── data/                # Data directory (gitignored for real data)
├── examples/            # Usage examples
├── requirements.txt
└── README.md
```

## License

MIT License — free to use, modify, and distribute.

## 🚀 New Features (2026-03-02)
- Add advanced DAX patterns and Power BI governance templates
- Enhanced error handling and edge case coverage
- Comprehensive unit tests and integration examples
