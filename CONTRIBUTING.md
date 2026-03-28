# Contributing to Pharma BI Starter Kit

Thank you for your interest in contributing! This starter kit helps pharmaceutical BI teams build production-ready dashboards with Power BI and SQL. Contributions to DAX templates, SQL query patterns, sample datasets, and documentation are all welcome.

## Getting Started

1. Fork the repository and clone your fork
2. Create a virtual environment: `python -m venv venv && source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Create a branch: `git checkout -b feature/your-feature-name`

## Development Guidelines

- **SQL scripts** — test against SQL Server 2019+ or Azure SQL
- **DAX measures** — include comments explaining business logic and edge cases
- **Sample data** — anonymize and synthetic-ize all datasets before committing
- **Tests** — add `pytest` tests for Python utility functions in `tests/`

## Submitting Changes

1. Run tests: `pytest tests/ -v`
2. Update `CHANGELOG.md` with your addition
3. Open a pull request with a clear description

## Domain Context

This kit is designed for APAC pharma markets. KPI definitions follow IQVIA standard methodology where applicable. When adding new metrics, include a reference to the source methodology.

## Reporting Bugs

Open an issue with Power BI version, SQL Server version, and steps to reproduce.
