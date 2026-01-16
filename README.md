# pharma-bi-starter-kit

**Domain:** Pharmaceutical Business Intelligence

A complete starter kit for pharmaceutical BI teams building dashboards with Power BI and SQL. Includes templates, DAX patterns, and sample datasets for common pharma metrics (sales, market share, clinical trial tracking).

## 🎯 Features

- **Power BI Templates:** Pre-built measures and calculated columns for pharma KPIs
- **Advanced DAX Formulas:** YoY growth, market share, trend analysis, variance calculations
- **Sample Datasets:** Pharma sales, competitive market data, healthcare provider networks
- **SQL Scripts:** T-SQL queries optimized for pharma data warehouses
- **Data Governance Framework:** Documentation for metric definitions and calculation rules

## 🚀 Quick Start

### Prerequisites

- Power BI Desktop (latest version)
- SQL Server or Azure SQL Database
- Excel 2019+ (for data prep)

### Installation

```bash
# Clone repository
git clone https://github.com/achmadnaufal/pharma-bi-starter-kit.git
cd pharma-bi-starter-kit

# Copy Power BI template to your workspace
cp templates/pharma-dashboard-template.pbit ~/Documents/Power\ BI\ Dashboards/
```

### Load Sample Data

```sql
-- SQL Server: Load sample sales data
USE [YourPharmacyAnalyticsDB]
GO

-- Create staging table
CREATE TABLE staging.pharma_sales (
    sale_id INT PRIMARY KEY,
    product_name NVARCHAR(100),
    therapeutic_area NVARCHAR(50),
    sale_date DATE,
    sale_amount DECIMAL(12,2),
    units_sold INT,
    healthcare_provider_id INT,
    region NVARCHAR(50)
)

-- Load sample data
INSERT INTO staging.pharma_sales VALUES
    (1, 'Lisinopril 10mg', 'Cardiovascular', '2026-03-01', 4500.00, 150, 101, 'North'),
    (2, 'Metformin 500mg', 'Endocrinology', '2026-03-01', 3200.00, 200, 102, 'South'),
    (3, 'Omeprazole 20mg', 'Gastroenterology', '2026-03-02', 2800.00, 140, 103, 'East'),
    (4, 'Atorvastatin 20mg', 'Cardiovascular', '2026-03-02', 5100.00, 170, 104, 'West');
```

## 📊 Power BI Setup

### Step 1: Create Data Model

```
1. Open pharma-dashboard-template.pbit in Power BI Desktop
2. Get Data → SQL Server
3. Connect to your pharma database
4. Select tables: pharma_sales, products, healthcare_providers, competitors
5. Apply transformations in Power Query
```

### Step 2: DAX Measure Examples

**Total Sales:**
```dax
Sales_Total = SUM(Sales[sale_amount])
```

**Year-over-Year Growth:**
```dax
Sales_YoY_Growth = 
VAR CurrentYear = YEAR(TODAY())
VAR PreviousYear = CurrentYear - 1
VAR CurrentSales = 
    CALCULATE(
        SUM(Sales[sale_amount]),
        YEAR(Sales[sale_date]) = CurrentYear
    )
VAR PreviousSales = 
    CALCULATE(
        SUM(Sales[sale_amount]),
        YEAR(Sales[sale_date]) = PreviousYear
    )
RETURN
    DIVIDE(CurrentSales - PreviousSales, PreviousSales, 0)
```

**Market Share by Therapeutic Area:**
```dax
Market_Share_Pct = 
VAR TotalMarket = CALCULATE(
    SUM(Sales[sale_amount]),
    ALL(Sales[product_name])
)
VAR OurSales = SUM(Sales[sale_amount])
RETURN
    DIVIDE(OurSales, TotalMarket, 0)
```

**Clinical Trial Enrollment Pace:**
```dax
Enrollment_Pace = 
VAR DaysElapsed = TODAY() - MIN(Trials[start_date])
VAR TotalEnrolled = SUM(Trials[enrolled_patients])
RETURN
    DIVIDE(TotalEnrolled, DaysElapsed, 0)  -- Patients per day
```

### Step 3: Create Visualizations

**Dashboard Components:**

1. **KPI Cards**
   - Total Sales (MTD)
   - Market Share %
   - Active Products
   - Clinical Trials in Progress

2. **Trend Line**
   - Sales by Month (last 12 months)
   - Competitor Trending
   - Market Share Trend

3. **Heat Map**
   - Sales by Therapeutic Area × Region
   - Product Performance Matrix

4. **Bar Chart**
   - Top 10 Products by Sales
   - Healthcare Provider Rankings
   - Competitive Pricing Analysis

## 📈 Sample Report Scenarios

### Scenario 1: Daily Sales Briefing

```
Parameters: Today's date, Region filter
Visuals:
- YTD Sales vs Target (gauge)
- Top Products (bar)
- Regional Breakdown (pie)
- Variance Analysis (table)
```

### Scenario 2: Quarterly Business Review

```
Time Slice: Last 3 months
Metrics:
- Sales Growth vs Prior Quarter (YoY)
- Market Share by Therapeutic Area
- Competitive Win/Loss Analysis
- Pipeline Opportunities
```

### Scenario 3: Clinical Trial Dashboard

```
Filters: Trial Phase, Indication, Geography
Metrics:
- Total Enrolled vs Plan
- Enrollment Velocity (patients/day)
- Site Activation Rate
- Screen Failure Rate
```

## 🧪 Testing DAX Measures

```sql
-- Test YoY Growth calculation
WITH sales_by_year AS (
    SELECT 
        YEAR(sale_date) as sale_year,
        SUM(sale_amount) as annual_sales
    FROM pharma_sales
    GROUP BY YEAR(sale_date)
)
SELECT 
    sale_year,
    annual_sales,
    LAG(annual_sales) OVER (ORDER BY sale_year) as prev_year_sales,
    ROUND(
        (annual_sales - LAG(annual_sales) OVER (ORDER BY sale_year)) / 
        LAG(annual_sales) OVER (ORDER BY sale_year) * 100, 2
    ) as yoy_growth_pct
FROM sales_by_year
```

## 📊 Data Model Relationships

```
Relationships:
├── pharma_sales
│   ├── → products (product_id)
│   ├── → healthcare_providers (provider_id)
│   └── → calendar (sale_date)
├── products
│   ├── → therapeutic_areas (area_id)
│   └── → competitors (competitor_id)
└── clinical_trials
    ├── → products (product_id)
    └── → trial_sites (site_id)
```

## 🔒 Row-Level Security (RLS)

Restrict data by sales territory:

```dax
[Sales Manager Role]
Region = "North"

[Field Sales Rep Role]
Region = "North" AND 
HealthcareProvider = "Assigned Territory"
```

## 📁 File Structure

```
pharma-bi-starter-kit/
├── templates/
│   ├── pharma-dashboard-template.pbit
│   ├── sales-scorecard.pbit
│   └── market-analysis.pbit
├── data/
│   ├── sample-sales-data.csv
│   ├── competitors-data.xlsx
│   └── clinical-trials.xlsx
├── sql/
│   ├── schema-setup.sql
│   ├── etl-procedures.sql
│   └── sample-queries.sql
├── tests/
│   ├── test_main.py
│   └── test_dax_measures.py
├── docs/
│   ├── metric-definitions.md
│   ├── governance-framework.md
│   └── best-practices.md
└── README.md
```

## 🧪 Testing

Run unit tests for DAX calculations:

```bash
python -m pytest tests/test_dax_measures.py -v
```

## 💾 Loading Your Own Data

### Option 1: Direct SQL Queries

```python
import pyodbc

conn = pyodbc.connect(
    'Driver={ODBC Driver 17 for SQL Server};'
    'Server=your-server;'
    'Database=pharma_db;'
    'UID=sa;PWD=password'
)

query = "SELECT * FROM pharma_sales WHERE sale_date >= '2026-01-01'"
df = pd.read_sql(query, conn)
```

### Option 2: Power Query M Language

```m
let
    Source = Sql.Database("server-name", "pharma_db"),
    DboPharmaSales = Source{[Schema="dbo",Item="pharma_sales"]}[Data],
    FilteredData = Table.SelectRows(
        DboPharmaSales, 
        each [sale_date] >= #date(2026,1,1)
    )
in
    FilteredData
```

## 📚 Common Pharma KPIs

- **COGS %** = Cost of Goods Sold / Total Sales
- **Gross Margin** = (Revenue - COGS) / Revenue
- **Pipeline Value** = Sum of opportunity values in sales pipeline
- **Net Price Growth** = (Current Price - Prior Year Price) / Prior Year Price
- **Market Penetration** = Our Sales / Total Market Sales

## 🔄 Update Schedule

- Sample data refreshes: Monthly
- Dashboard scheduled refresh: Daily 6 AM UTC
- Competitive data: Weekly
- Clinical trial milestones: As submitted

## 📞 Support

For configuration help:
- Check `docs/best-practices.md` for DAX patterns
- Review sample queries in `sql/` folder
- See `docs/metric-definitions.md` for KPI documentation

## 📄 License

MIT License

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for recent improvements and additions.
