"""
Unit tests for DataQualityScorer.
"""

import pandas as pd
import pytest
from src.data_quality_scorer import DataQualityScorer, DataQualityReport


def make_good_df():
    return pd.DataFrame({
        "period":    ["2025-Q4"] * 5,
        "brand":     ["BrandA", "BrandB", "BrandC", "BrandA", "BrandB"],
        "outlet_id": ["P001", "P002", "P003", "P004", "P005"],
        "channel":   ["chain", "chain", "hospital", "independent", "chain"],
        "sales_usd": [100_000, 200_000, 150_000, 80_000, 120_000],
        "date":      ["2025-12-01"] * 5,
    })


@pytest.fixture
def scorer():
    return DataQualityScorer(
        dataset_name="test-dataset",
        required_columns=["period", "brand", "sales_usd"],
        valid_ranges={"sales_usd": (0, 5_000_000)},
        valid_categories={"channel": {"chain", "independent", "hospital"}},
        unique_key_columns=["period", "brand", "outlet_id"],
        max_age_days=90,
        pass_threshold=75.0,
    )


class TestInit:
    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="dataset_name"):
            DataQualityScorer(dataset_name="   ")

    def test_invalid_pass_threshold_raises(self):
        with pytest.raises(ValueError, match="pass_threshold"):
            DataQualityScorer(dataset_name="test", pass_threshold=150)

    def test_invalid_weight_sum_raises(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            DataQualityScorer(
                dataset_name="test",
                dimension_weights={"completeness": 0.5, "validity": 0.5,
                                   "uniqueness": 0.5, "timeliness": 0.5, "consistency": 0.5},
            )


class TestScore:
    def test_returns_report(self, scorer):
        report = scorer.score(make_good_df())
        assert isinstance(report, DataQualityReport)

    def test_good_data_passes(self, scorer):
        report = scorer.score(make_good_df(), date_column="date",
                               reference_date="2026-01-01")
        assert report.passed is True

    def test_composite_score_between_0_and_100(self, scorer):
        report = scorer.score(make_good_df())
        assert 0 <= report.composite_score <= 100

    def test_empty_df_returns_critical(self, scorer):
        report = scorer.score(pd.DataFrame())
        assert report.rating == "Critical"
        assert report.passed is False

    def test_null_values_reduce_completeness(self, scorer):
        df = make_good_df()
        df.loc[0:2, "brand"] = None
        report = scorer.score(df)
        completeness_score = report.dimension_scores["completeness"].raw_score
        assert completeness_score < 100

    def test_out_of_range_values_reduce_validity(self, scorer):
        df = make_good_df()
        df.loc[0, "sales_usd"] = -500_000  # below min
        report = scorer.score(df)
        validity_score = report.dimension_scores["validity"].raw_score
        assert validity_score < 100

    def test_duplicate_rows_reduce_uniqueness(self, scorer):
        df = make_good_df()
        df = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # add duplicate
        report = scorer.score(df)
        uniqueness_score = report.dimension_scores["uniqueness"].raw_score
        assert uniqueness_score < 100

    def test_invalid_category_reduces_validity(self, scorer):
        df = make_good_df()
        df.loc[0, "channel"] = "online"  # not in allowed set
        report = scorer.score(df)
        assert report.dimension_scores["validity"].raw_score < 100

    def test_old_data_reduces_timeliness(self, scorer):
        df = make_good_df()
        report = scorer.score(df, date_column="date", reference_date="2026-06-01")
        # Data is from 2025-12 — 182 days old, exceeds max_age_days=90
        timeliness_score = report.dimension_scores["timeliness"].raw_score
        assert timeliness_score < 100

    def test_dimension_scores_present(self, scorer):
        report = scorer.score(make_good_df())
        assert set(report.dimension_scores.keys()) == {
            "completeness", "validity", "uniqueness", "timeliness", "consistency"
        }


class TestScoreColumn:
    def test_fully_complete_column(self, scorer):
        s = pd.Series([1, 2, 3, 4, 5])
        result = scorer.score_column(s)
        assert result["completeness_pct"] == 100.0
        assert result["null_count"] == 0

    def test_partial_null_column(self, scorer):
        s = pd.Series([1, None, 3, None, 5])
        result = scorer.score_column(s)
        assert result["null_count"] == 2
        assert result["completeness_pct"] == pytest.approx(60.0)
