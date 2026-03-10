"""Unit tests for SalesForceEffectivenessScorer."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sales_force_effectiveness_scorer import (
    SalesForceEffectivenessScorer,
    RepPerformanceRecord,
    Specialty,
    RepTier,
    SFE_WEIGHTS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_record(
    rep_id="REP_001",
    specialty=Specialty.SPECIALTY,
    target_prescribers=120,
    prescribers_visited=96,
    total_calls=480,
    working_days=65,
    quality=7.5,
    ntb=14,
    revenue_actual=285_000,
    revenue_quota=300_000,
) -> RepPerformanceRecord:
    return RepPerformanceRecord(
        rep_id=rep_id,
        rep_name=f"Rep {rep_id}",
        territory_id="JKT_WEST",
        specialty=specialty,
        period="Q1 2026",
        target_prescribers=target_prescribers,
        prescribers_visited=prescribers_visited,
        total_calls=total_calls,
        total_working_days=working_days,
        avg_call_quality_score=quality,
        ntb_prescribers=ntb,
        revenue_actual_usd=revenue_actual,
        revenue_quota_usd=revenue_quota,
    )


# ---------------------------------------------------------------------------
# RepPerformanceRecord tests
# ---------------------------------------------------------------------------

class TestRepPerformanceRecord:
    def test_coverage_pct(self):
        r = make_record(target_prescribers=100, prescribers_visited=80)
        assert abs(r.coverage_pct - 80.0) < 0.01

    def test_calls_per_day(self):
        r = make_record(total_calls=130, working_days=65)
        assert abs(r.calls_per_day - 2.0) < 0.01

    def test_calls_per_prescriber(self):
        r = make_record(total_calls=480, prescribers_visited=96)
        assert abs(r.calls_per_prescriber - 5.0) < 0.01

    def test_ntb_rate_pct(self):
        r = make_record(target_prescribers=100, ntb=10)
        assert abs(r.ntb_rate_pct - 10.0) < 0.01

    def test_revenue_attainment(self):
        r = make_record(revenue_actual=250_000, revenue_quota=250_000)
        assert abs(r.revenue_attainment_pct - 100.0) < 0.01

    def test_prescribers_visited_exceeds_target_raises(self):
        with pytest.raises(ValueError):
            make_record(target_prescribers=50, prescribers_visited=60)

    def test_invalid_quality_raises(self):
        with pytest.raises(ValueError):
            make_record(quality=11)

    def test_zero_quota_raises(self):
        with pytest.raises(ValueError):
            make_record(revenue_quota=0)


# ---------------------------------------------------------------------------
# SalesForceEffectivenessScorer tests
# ---------------------------------------------------------------------------

class TestSFEScorer:
    def setup_method(self):
        self.scorer = SalesForceEffectivenessScorer()

    def test_score_returns_sfe_score(self):
        r = make_record()
        result = self.scorer.score(r)
        assert 0 <= result.composite_score <= 100
        assert isinstance(result.tier, RepTier)

    def test_high_performer_a_plus(self):
        r = make_record(
            prescribers_visited=120, total_calls=720, quality=9.5,
            ntb=18, revenue_actual=330_000, revenue_quota=300_000
        )
        result = self.scorer.score(r)
        assert result.tier in (RepTier.A_PLUS, RepTier.A)

    def test_low_performer_d_tier(self):
        r = make_record(
            prescribers_visited=30, total_calls=100, quality=3.0,
            ntb=1, revenue_actual=80_000, revenue_quota=300_000
        )
        result = self.scorer.score(r)
        assert result.tier in (RepTier.D, RepTier.C)

    def test_dimension_scores_all_present(self):
        r = make_record()
        result = self.scorer.score(r)
        expected_dims = {"coverage", "frequency", "quality", "ntb", "attainment"}
        assert set(result.dimension_scores.keys()) == expected_dims

    def test_score_team_sorted_descending(self):
        records = [
            make_record("R1", prescribers_visited=120, total_calls=720, quality=9.5, ntb=15, revenue_actual=310_000),
            make_record("R2", prescribers_visited=40, total_calls=150, quality=4.0, ntb=2, revenue_actual=90_000),
            make_record("R3", prescribers_visited=80, total_calls=400, quality=6.5, ntb=8, revenue_actual=200_000),
        ]
        scores = self.scorer.score_team(records)
        composite_scores = [s.composite_score for s in scores]
        assert composite_scores == sorted(composite_scores, reverse=True)

    def test_score_team_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            self.scorer.score_team([])

    def test_team_summary_keys(self):
        records = [make_record(f"R{i}") for i in range(3)]
        scores = self.scorer.score_team(records)
        summary = self.scorer.team_summary(scores)
        assert "avg_sfe_score" in summary
        assert "tier_distribution" in summary
        assert summary["total_reps"] == 3

    def test_coaching_priorities_low_quality(self):
        r = make_record(quality=2.0)
        result = self.scorer.score(r)
        assert "quality" in result.coaching_priorities

    def test_recommended_actions_not_empty(self):
        r = make_record()
        result = self.scorer.score(r)
        assert len(result.recommended_actions) >= 1

    def test_invalid_record_type_raises(self):
        with pytest.raises(TypeError):
            self.scorer.score({"rep_id": "bad"})

    def test_invalid_weights_raises(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            SalesForceEffectivenessScorer(custom_weights={"a": 0.5, "b": 0.3})
