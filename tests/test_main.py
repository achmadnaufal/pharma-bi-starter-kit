"""Unit tests for PharmaBIStarterKit."""
import pytest
import pandas as pd
import sys
sys.path.insert(0, "/Users/johndoe/projects/pharma-bi-starter-kit")
from src.main import PharmaBIStarterKit


@pytest.fixture
def rep_df():
    return pd.DataFrame({
        "rep_id": [f"REP{i:02d}" for i in range(1, 9)],
        "territory": ["North", "North", "South", "South", "East", "East", "West", "West"],
        "actual_sales": [85000, 92000, 78000, 110000, 65000, 95000, 88000, 72000],
        "target_sales": [100000, 100000, 90000, 100000, 80000, 100000, 100000, 90000],
        "call_count": [45, 52, 38, 60, 30, 55, 48, 40],
        "period": ["2026-Q1"] * 8,
    })


@pytest.fixture
def kit():
    return PharmaBIStarterKit(config={"target_attainment_threshold": 80.0, "top_performers_pct": 20.0})


class TestValidation:
    def test_empty_raises(self, kit):
        with pytest.raises(ValueError, match="empty"):
            kit.validate(pd.DataFrame())

    def test_missing_columns_raises(self, kit):
        df = pd.DataFrame({"rep_id": ["R1"], "actual_sales": [100]})
        with pytest.raises(ValueError, match="Missing required columns"):
            kit.validate(df)

    def test_valid_passes(self, kit, rep_df):
        assert kit.validate(rep_df) is True


class TestSalesPerformanceReport:
    def test_returns_expected_keys(self, kit, rep_df):
        result = kit.sales_performance_report(rep_df)
        assert "rep_summary" in result
        assert "top_performers" in result
        assert "below_target" in result
        assert "team_attainment_pct" in result

    def test_attainment_values_in_range(self, kit, rep_df):
        result = kit.sales_performance_report(rep_df)
        attainments = result["rep_summary"]["attainment_pct"]
        assert (attainments > 0).all()
        assert (attainments <= 200).all()

    def test_rank_column_present(self, kit, rep_df):
        result = kit.sales_performance_report(rep_df)
        assert "rank" in result["rep_summary"].columns

    def test_below_target_all_below_threshold(self, kit, rep_df):
        result = kit.sales_performance_report(rep_df)
        summary = result["rep_summary"]
        below_ids = result["below_target"]
        below_rows = summary[summary["rep_id"].isin(below_ids)]
        assert (below_rows["attainment_pct"] < 80.0).all()

    def test_team_attainment_is_float(self, kit, rep_df):
        result = kit.sales_performance_report(rep_df)
        assert isinstance(result["team_attainment_pct"], float)

    def test_sales_per_call_calculated(self, kit, rep_df):
        result = kit.sales_performance_report(rep_df)
        assert "sales_per_call" in result["rep_summary"].columns

    def test_total_actual_matches_sum(self, kit, rep_df):
        result = kit.sales_performance_report(rep_df)
        avt = result["total_actual_vs_target"]
        assert abs(avt["actual"] - rep_df["actual_sales"].sum()) < 0.01

    def test_gap_is_target_minus_actual(self, kit, rep_df):
        result = kit.sales_performance_report(rep_df)
        avt = result["total_actual_vs_target"]
        assert abs(avt["gap"] - (avt["target"] - avt["actual"])) < 0.01


class TestTerritoryHeatmap:
    def test_returns_dataframe(self, kit, rep_df):
        result = kit.territory_heatmap_data(rep_df)
        assert isinstance(result, pd.DataFrame)

    def test_territory_column_present(self, kit, rep_df):
        result = kit.territory_heatmap_data(rep_df)
        assert "territory" in result.columns

    def test_missing_territory_raises(self, kit):
        df = pd.DataFrame({"rep_id": ["R1"], "actual_sales": [100], "target_sales": [120]})
        with pytest.raises(ValueError, match="territory"):
            kit.territory_heatmap_data(df)

    def test_four_territories(self, kit, rep_df):
        result = kit.territory_heatmap_data(rep_df)
        assert len(result) == 4
