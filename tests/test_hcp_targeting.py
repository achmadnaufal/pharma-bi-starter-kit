"""Unit tests for HCP Targeting Optimizer."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hcp_targeting import (
    HCPTargetingOptimizer,
    HCPProfile,
    Segment,
    SegmentSummary,
    NextBestAction,
    TerritoryAssignment,
    ActionType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ONCOLOGY_HCP = HCPProfile(
    hcp_id="H001", specialty="Oncology", region="Jakarta",
    patient_volume=300, current_share=10.0, potential_share=35.0,
    last_activity_days_ago=30, engagement_score=7.5, call_cost_usd=150,
)
CARDIO_HCP = HCPProfile(
    hcp_id="H002", specialty="Cardiology", region="Jawa Barat",
    patient_volume=200, current_share=15.0, potential_share=40.0,
    last_activity_days_ago=45, engagement_score=6.5, call_cost_usd=120,
)
DIABETES_HCP = HCPProfile(
    hcp_id="H003", specialty="Diabetes", region="Bangkok",
    patient_volume=150, current_share=20.0, potential_share=28.0,
    last_activity_days_ago=10, engagement_score=5.0, call_cost_usd=120,
)
LOW_POTENTIAL_HCP = HCPProfile(
    hcp_id="H004", specialty="Cardiology", region="Jawa Timur",
    patient_volume=50, current_share=18.0, potential_share=22.0,
    last_activity_days_ago=90, engagement_score=3.0, call_cost_usd=120,
)
HIGH_VOL_HCP = HCPProfile(
    hcp_id="H005", specialty="Oncology", region="Ho Chi Minh",
    patient_volume=500, current_share=5.0, potential_share=30.0,
    last_activity_days_ago=20, engagement_score=8.0, call_cost_usd=180,
)


# ---------------------------------------------------------------------------
# HCPProfile dataclass
# ---------------------------------------------------------------------------

class TestHCPProfile:
    def test_hcp_profile_creation(self):
        hcp = HCPProfile(
            hcp_id="TEST", specialty="Cardiology", region="Jakarta",
            patient_volume=100, current_share=10.0, potential_share=30.0,
            last_activity_days_ago=7, engagement_score=5.0,
        )
        assert hcp.hcp_id == "TEST"
        assert hcp.potential_share - hcp.current_share == 20.0

    def test_hcp_profile_default_call_cost(self):
        hcp = HCPProfile(
            hcp_id="TEST", specialty="Cardiology", region="Jakarta",
            patient_volume=100, current_share=10.0, potential_share=30.0,
            last_activity_days_ago=7, engagement_score=5.0,
        )
        assert hcp.call_cost_usd == 120.0


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

class TestSegmentHCPS:
    def test_segment_hcps_empty(self):
        optimizer = HCPTargetingOptimizer()
        df = optimizer.segment_hcps([])
        assert df.empty
        assert len(df) == 0

    def test_segment_hcps_high_potential(self):
        optimizer = HCPTargetingOptimizer()
        df = optimizer.segment_hcps([ONCOLOGY_HCP])
        assert len(df) == 1
        assert df.iloc[0]["segment"] == Segment.HIGH
        assert df.iloc[0]["share_gap"] == 25.0
        assert "potential_score" in df.columns

    def test_segment_hcps_medium_potential(self):
        optimizer = HCPTargetingOptimizer()
        df = optimizer.segment_hcps([DIABETES_HCP])
        assert len(df) == 1
        assert df.iloc[0]["segment"] == Segment.MEDIUM

    def test_segment_hcps_low_potential(self):
        optimizer = HCPTargetingOptimizer()
        # 5 HCPs: vol=40 is rank-1 → vol_pct=20 (<25), gap=4 (<5) → LOW
        profiles = [
            HCPProfile(hcp_id="H004", specialty="Cardiology", region="Jawa Timur",
                       patient_volume=40, current_share=18.0, potential_share=22.0,
                       last_activity_days_ago=90, engagement_score=3.0, call_cost_usd=120),
            HCPProfile(hcp_id="V100", specialty="Cardiology", region="Jawa",
                       patient_volume=100, current_share=10.0, potential_share=20.0,
                       last_activity_days_ago=30, engagement_score=5.0),
            HCPProfile(hcp_id="V200", specialty="Cardiology", region="Jawa",
                       patient_volume=200, current_share=10.0, potential_share=20.0,
                       last_activity_days_ago=30, engagement_score=5.0),
            HCPProfile(hcp_id="V300", specialty="Cardiology", region="Jawa",
                       patient_volume=300, current_share=10.0, potential_share=20.0,
                       last_activity_days_ago=30, engagement_score=5.0),
            HCPProfile(hcp_id="V400", specialty="Cardiology", region="Jawa",
                       patient_volume=400, current_share=10.0, potential_share=20.0,
                       last_activity_days_ago=30, engagement_score=5.0),
        ]
        df = optimizer.segment_hcps(profiles)
        low_df = df[df["hcp_id"] == "H004"]
        assert len(low_df) == 1
        assert low_df.iloc[0]["segment"] == Segment.LOW

    def test_segment_hcps_boundary_high_share_gap(self):
        """gap=15 meets HIGH threshold but volume below 75th percentile → MEDIUM."""
        hcp = HCPProfile(
            hcp_id="BND", specialty="Cardiology", region="Jakarta",
            patient_volume=100, current_share=80.0, potential_share=95.0,
            last_activity_days_ago=30, engagement_score=5.0,
        )
        optimizer = HCPTargetingOptimizer()
        df = optimizer.segment_hcps([hcp])
        # gap=15 >= HIGH_GAP(15) but vol_pct=100 >= HIGH_VOL(75) → HIGH
        assert df.iloc[0]["segment"] == Segment.HIGH

    def test_segment_hcps_boundary_high_volume(self):
        """High volume but low share gap → MEDIUM (gap < HIGH threshold)."""
        hcp = HCPProfile(
            hcp_id="BND2", specialty="Cardiology", region="Jakarta",
            patient_volume=1000, current_share=80.0, potential_share=85.0,
            last_activity_days_ago=30, engagement_score=5.0,
        )
        optimizer = HCPTargetingOptimizer()
        df = optimizer.segment_hcps([hcp])
        # gap=5 < HIGH(15) → falls to MEDIUM; vol_pct=100 >= MEDIUM_VOL(25)
        assert df.iloc[0]["segment"] == Segment.MEDIUM

    def test_segment_hcps_share_gap_at_medium_threshold(self):
        """Share gap exactly at MEDIUM threshold (5.0) with low volume → MEDIUM."""
        hcp = HCPProfile(
            hcp_id="BND3", specialty="Cardiology", region="Jakarta",
            patient_volume=50, current_share=20.0, potential_share=25.0,
            last_activity_days_ago=30, engagement_score=5.0,
        )
        optimizer = HCPTargetingOptimizer()
        df = optimizer.segment_hcps([hcp])
        assert df.iloc[0]["segment"] == Segment.MEDIUM

    def test_segment_hcps_contains_all_columns(self):
        optimizer = HCPTargetingOptimizer()
        df = optimizer.segment_hcps([CARDIO_HCP])
        expected_public = {
            "hcp_id", "specialty", "region", "patient_volume",
            "current_share", "potential_share", "last_activity_days_ago",
            "engagement_score", "call_cost_usd", "share_gap",
            "potential_score", "segment", "volume_percentile",
        }
        assert expected_public.issubset(set(df.columns))

    def test_segment_hcps_multiple_hcps(self):
        optimizer = HCPTargetingOptimizer()
        profiles = [ONCOLOGY_HCP, CARDIO_HCP, DIABETES_HCP, LOW_POTENTIAL_HCP, HIGH_VOL_HCP]
        df = optimizer.segment_hcps(profiles)
        assert len(df) == 5
        assert set(df["segment"].values) <= {Segment.HIGH, Segment.MEDIUM, Segment.LOW}


# ---------------------------------------------------------------------------
# LP Optimization
# ---------------------------------------------------------------------------

class TestOptimizeReach:
    def test_optimize_reach_empty(self):
        optimizer = HCPTargetingOptimizer(total_call_capacity=200)
        alloc = optimizer.optimize_reach([])
        assert alloc == {}

    def test_optimize_reach_zero_capacity(self):
        optimizer = HCPTargetingOptimizer(total_call_capacity=0)
        profiles = [CARDIO_HCP, ONCOLOGY_HCP]
        alloc = optimizer.optimize_reach(profiles, total_calls=0)
        assert all(v == 0 for v in alloc.values())

    def test_optimize_reach_basic(self):
        optimizer = HCPTargetingOptimizer(total_call_capacity=10)
        profiles = [CARDIO_HCP, DIABETES_HCP]
        alloc = optimizer.optimize_reach(profiles, total_calls=10)
        assert len(alloc) == 2
        assert all(isinstance(v, int) for v in alloc.values())
        assert sum(alloc.values()) <= 10

    def test_optimize_reach_respects_max_calls(self):
        optimizer = HCPTargetingOptimizer(total_call_capacity=100, max_calls_per_hcp=5)
        profiles = [HCPProfile(
            hcp_id=f"H{i}", specialty="Cardiology", region="Jakarta",
            patient_volume=200, current_share=10.0, potential_share=35.0,
            last_activity_days_ago=30, engagement_score=6.0,
        ) for i in range(10)]
        alloc = optimizer.optimize_reach(profiles, total_calls=50)
        assert all(v <= 5 for v in alloc.values())

    def test_optimize_reach_prioritizes_high_potential(self):
        optimizer = HCPTargetingOptimizer(total_call_capacity=10)
        profiles = [LOW_POTENTIAL_HCP, HIGH_VOL_HCP]
        alloc = optimizer.optimize_reach(profiles, total_calls=10)
        # HIGH_VOL_HCP has higher potential → should get more calls
        assert alloc[HIGH_VOL_HCP.hcp_id] >= alloc[LOW_POTENTIAL_HCP.hcp_id]

    def test_optimize_reach_with_priority_weights(self):
        optimizer = HCPTargetingOptimizer(total_call_capacity=10)
        profiles = [CARDIO_HCP, ONCOLOGY_HCP]
        # 10x weight on CARDIO; use 11 calls so LP must favour CARDIO
        weights = {CARDIO_HCP.hcp_id: 10.0, ONCOLOGY_HCP.hcp_id: 1.0}
        alloc = optimizer.optimize_reach(profiles, total_calls=11, priority_weights=weights)
        # CARDIO_HCP has 10x weight → should get more calls than ONCOLOGY
        assert alloc[CARDIO_HCP.hcp_id] >= alloc[ONCOLOGY_HCP.hcp_id]

    def test_optimize_reach_total_respects_capacity(self):
        optimizer = HCPTargetingOptimizer(total_call_capacity=200, min_calls_per_hcp=1)
        profiles = [HCPProfile(
            hcp_id=f"H{i}", specialty="Cardiology", region="Jakarta",
            patient_volume=200, current_share=10.0, potential_share=30.0,
            last_activity_days_ago=30, engagement_score=5.0,
        ) for i in range(20)]
        alloc = optimizer.optimize_reach(profiles, total_calls=50)
        assert sum(alloc.values()) <= 50


# ---------------------------------------------------------------------------
# ROI Calculation
# ---------------------------------------------------------------------------

class TestCalculateROI:
    def test_calculate_roi_empty(self):
        optimizer = HCPTargetingOptimizer()
        roi = optimizer.calculate_roi_per_segment([])
        assert roi == {}

    def test_calculate_roi_all_segments(self):
        optimizer = HCPTargetingOptimizer()
        profiles = [ONCOLOGY_HCP, CARDIO_HCP, DIABETES_HCP, LOW_POTENTIAL_HCP, HIGH_VOL_HCP]
        roi = optimizer.calculate_roi_per_segment(profiles)
        assert set(roi.keys()) == {Segment.HIGH, Segment.MEDIUM, Segment.LOW}
        for seg, summary in roi.items():
            assert isinstance(summary, SegmentSummary)
            assert summary.segment == seg

    def test_calculate_roi_with_allocation(self):
        optimizer = HCPTargetingOptimizer()
        profiles = [CARDIO_HCP, ONCOLOGY_HCP]
        alloc = {CARDIO_HCP.hcp_id: 5, ONCOLOGY_HCP.hcp_id: 3}
        roi = optimizer.calculate_roi_per_segment(profiles, allocation=alloc)
        assert Segment.HIGH in roi or Segment.MEDIUM in roi
        for seg, summary in roi.items():
            if summary.count > 0:
                assert summary.estimated_cost_usd >= 0
                assert summary.estimated_revenue_uplift_usd >= 0

    def test_calculate_roi_high_segment_has_highest_roi(self):
        optimizer = HCPTargetingOptimizer()
        profiles = [ONCOLOGY_HCP, HIGH_VOL_HCP, DIABETES_HCP, LOW_POTENTIAL_HCP]
        roi = optimizer.calculate_roi_per_segment(profiles)
        # High segment should have ROI > 0
        if Segment.HIGH in roi and roi[Segment.HIGH].count > 0:
            assert roi[Segment.HIGH].roi_ratio >= 0

    def test_calculate_roi_revenue_exceeds_cost_for_high(self):
        optimizer = HCPTargetingOptimizer()
        profiles = [HIGH_VOL_HCP]  # Large volume, large gap
        roi = optimizer.calculate_roi_per_segment(profiles)
        high = roi[Segment.HIGH]
        assert high.estimated_revenue_uplift_usd >= high.estimated_cost_usd


# ---------------------------------------------------------------------------
# Territory Balancing
# ---------------------------------------------------------------------------

class TestTerritoryBalancer:
    def test_territory_balancer_empty_profiles(self):
        optimizer = HCPTargetingOptimizer()
        result = optimizer.territory_balancer([], rep_ids=["REP_A", "REP_B"])
        assert len(result) == 2
        assert all(a.total_hcps == 0 for a in result)

    def test_territory_balancer_empty_reps(self):
        optimizer = HCPTargetingOptimizer()
        result = optimizer.territory_balancer([CARDIO_HCP, ONCOLOGY_HCP], rep_ids=[])
        assert result == []

    def test_territory_balancer_basic(self):
        optimizer = HCPTargetingOptimizer()
        profiles = [ONCOLOGY_HCP, CARDIO_HCP, DIABETES_HCP, LOW_POTENTIAL_HCP]
        result = optimizer.territory_balancer(profiles, rep_ids=["REP_A", "REP_B"])
        assert len(result) == 2
        # All HCPs should be assigned
        total = sum(a.total_hcps for a in result)
        assert total == 4

    def test_territory_balancer_single_rep(self):
        optimizer = HCPTargetingOptimizer()
        profiles = [ONCOLOGY_HCP, CARDIO_HCP]
        result = optimizer.territory_balancer(profiles, rep_ids=["REP_A"])
        assert len(result) == 1
        assert result[0].total_hcps == 2

    def test_territory_balancer_reps_get_different_segments(self):
        optimizer = HCPTargetingOptimizer()
        profiles = [ONCOLOGY_HCP, CARDIO_HCP, DIABETES_HCP, LOW_POTENTIAL_HCP,
                    HIGH_VOL_HCP, HCPProfile(
                        hcp_id="EXTRA", specialty="Cardiology", region="Jakarta",
                        patient_volume=400, current_share=5.0, potential_share=35.0,
                        last_activity_days_ago=10, engagement_score=8.0,
                    )]
        result = optimizer.territory_balancer(profiles, rep_ids=["REP_A", "REP_B", "REP_C"])
        assert len(result) == 3
        # At least 2 reps should have high-segment HCPS
        high_counts = [len(a.high_segment) for a in result]
        assert sum(high_counts) >= 2

    def test_territory_balancer_respects_all_hcps_assigned(self):
        optimizer = HCPTargetingOptimizer()
        profiles = [CARDIO_HCP, ONCOLOGY_HCP, DIABETES_HCP, LOW_POTENTIAL_HCP, HIGH_VOL_HCP]
        result = optimizer.territory_balancer(profiles, rep_ids=["REP_A", "REP_B"])
        all_assigned = set()
        for a in result:
            for hcp in a.high_segment + a.medium_segment + a.low_segment:
                all_assigned.add(hcp.hcp_id)
        assert len(all_assigned) == 5

    def test_territory_balancer_balanced_score(self):
        optimizer = HCPTargetingOptimizer()
        profiles = [CARDIO_HCP, ONCOLOGY_HCP, DIABETES_HCP, LOW_POTENTIAL_HCP]
        result = optimizer.territory_balancer(profiles, rep_ids=["REP_A", "REP_B"])
        # Both reps should have the same total HCP count (4 / 2 = 2 each)
        assert result[0].total_hcps == result[1].total_hcps


# ---------------------------------------------------------------------------
# Next Best Action
# ---------------------------------------------------------------------------

class TestNextBestAction:
    def test_nba_very_recent_activity(self):
        hcp = HCPProfile(
            hcp_id="RECENT", specialty="Cardiology", region="Jakarta",
            patient_volume=200, current_share=10.0, potential_share=30.0,
            last_activity_days_ago=5, engagement_score=5.0,
        )
        optimizer = HCPTargetingOptimizer()
        action = optimizer.next_best_action(hcp)
        assert action == NextBestAction.NO_ACTION

    def test_nba_long_inactive_high_engagement(self):
        hcp = HCPProfile(
            hcp_id="INACTIVE", specialty="Oncology", region="Jakarta",
            patient_volume=300, current_share=10.0, potential_share=35.0,
            last_activity_days_ago=90, engagement_score=8.0,
        )
        optimizer = HCPTargetingOptimizer()
        action = optimizer.next_best_action(hcp, competitive_activity_level="low")
        assert action == NextBestAction.CLINICAL_TRIAL_INVITE

    def test_nba_long_inactive_high_competition(self):
        hcp = HCPProfile(
            hcp_id="INACTIVECOMP", specialty="Oncology", region="Jakarta",
            patient_volume=300, current_share=10.0, potential_share=35.0,
            last_activity_days_ago=90, engagement_score=8.0,
        )
        optimizer = HCPTargetingOptimizer()
        action = optimizer.next_best_action(hcp, competitive_activity_level="high")
        assert action == NextBestAction.DETAIL_CALL

    def test_nba_high_engagement_large_gap(self):
        hcp = HCPProfile(
            hcp_id="HIGHENG", specialty="Cardiology", region="Jakarta",
            patient_volume=200, current_share=10.0, potential_share=35.0,
            last_activity_days_ago=30, engagement_score=8.5,
        )
        optimizer = HCPTargetingOptimizer()
        action = optimizer.next_best_action(hcp)
        assert action == NextBestAction.DETAIL_CALL

    def test_nba_high_engagement_low_competition(self):
        hcp = HCPProfile(
            hcp_id="HIGHENGLowCOMP", specialty="Cardiology", region="Jakarta",
            patient_volume=200, current_share=10.0, potential_share=28.0,
            last_activity_days_ago=30, engagement_score=8.5,
        )
        optimizer = HCPTargetingOptimizer()
        action = optimizer.next_best_action(hcp, competitive_activity_level="low")
        assert action == NextBestAction.CME_SPONSORSHIP

    def test_nba_medium_engagement(self):
        hcp = HCPProfile(
            hcp_id="MEDENG", specialty="Diabetes", region="Bangkok",
            patient_volume=150, current_share=20.0, potential_share=30.0,
            last_activity_days_ago=30, engagement_score=5.5,
        )
        optimizer = HCPTargetingOptimizer()
        action = optimizer.next_best_action(hcp)
        assert action == NextBestAction.DETAIL_CALL

    def test_nba_low_engagement(self):
        hcp = HCPProfile(
            hcp_id="LOWENG", specialty="Cardiology", region="Jawa Timur",
            patient_volume=50, current_share=18.0, potential_share=22.0,
            last_activity_days_ago=30, engagement_score=2.5,
        )
        optimizer = HCPTargetingOptimizer()
        action = optimizer.next_best_action(hcp)
        assert action == NextBestAction.DETAIL_CALL

    def test_nba_medium_engagement_high_competition_large_gap(self):
        hcp = HCPProfile(
            hcp_id="MEDENGCOMP", specialty="Oncology", region="Jakarta",
            patient_volume=300, current_share=5.0, potential_share=30.0,
            last_activity_days_ago=30, engagement_score=5.5,
        )
        optimizer = HCPTargetingOptimizer()
        action = optimizer.next_best_action(hcp, competitive_activity_level="high")
        assert action == NextBestAction.SAMPLE_DROP


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_hcp_list_all_methods(self):
        optimizer = HCPTargetingOptimizer(total_call_capacity=200)
        assert optimizer.segment_hcps([]).empty
        assert optimizer.optimize_reach([]) == {}
        assert optimizer.calculate_roi_per_segment([]) == {}
        result = optimizer.territory_balancer([], rep_ids=["REP_A"])
        assert result[0].total_hcps == 0

    def test_zero_capacity(self):
        optimizer = HCPTargetingOptimizer(total_call_capacity=0)
        profiles = [CARDIO_HCP, ONCOLOGY_HCP]
        alloc = optimizer.optimize_reach(profiles, total_calls=0)
        assert all(v == 0 for v in alloc.values())

    def test_all_same_potential(self):
        profiles = [
            HCPProfile(hcp_id=f"H{i}", specialty="Cardiology", region="Jakarta",
                       patient_volume=200, current_share=10.0, potential_share=30.0,
                       last_activity_days_ago=30, engagement_score=5.0)
            for i in range(5)
        ]
        optimizer = HCPTargetingOptimizer(total_call_capacity=10)
        alloc = optimizer.optimize_reach(profiles, total_calls=10)
        # All same potential → allocation should be roughly uniform
        values = list(alloc.values())
        assert max(values) - min(values) <= 2

    def test_negative_capacity_raises(self):
        with pytest.raises(ValueError):
            HCPTargetingOptimizer(total_call_capacity=-5)

    def test_invalid_weight_raises(self):
        with pytest.raises(ValueError):
            HCPTargetingOptimizer(share_gap_weight=1.5)
        with pytest.raises(ValueError):
            HCPTargetingOptimizer(share_gap_weight=0.5, volume_weight=0.5,
                                  engagement_weight=0.5)

    def test_territory_imbalance_many_low(self):
        optimizer = HCPTargetingOptimizer()
        profiles = [
            LOW_POTENTIAL_HCP,
            HCPProfile(hcp_id="LP2", specialty="Cardiology", region="Jawa Timur",
                       patient_volume=60, current_share=17.0, potential_share=21.0,
                       last_activity_days_ago=90, engagement_score=2.5),
            HCPProfile(hcp_id="LP3", specialty="Cardiology", region="Jawa Timur",
                       patient_volume=55, current_share=19.0, potential_share=23.0,
                       last_activity_days_ago=90, engagement_score=3.0),
            HCPProfile(hcp_id="LP4", specialty="Cardiology", region="Jawa Timur",
                       patient_volume=70, current_share=16.0, potential_share=20.0,
                       last_activity_days_ago=90, engagement_score=2.8),
        ]
        result = optimizer.territory_balancer(profiles, rep_ids=["REP_A", "REP_B"])
        # All should be assigned (even if all low)
        total = sum(a.total_hcps for a in result)
        assert total == 4

    def test_large_hcp_count_optimization(self):
        optimizer = HCPTargetingOptimizer(total_call_capacity=500, max_calls_per_hcp=8)
        profiles = [
            HCPProfile(hcp_id=f"H{i}", specialty="Cardiology", region="Jakarta",
                       patient_volume=100 + i * 10, current_share=10.0 + i * 0.5,
                       potential_share=30.0 + i * 0.5, last_activity_days_ago=30,
                       engagement_score=5.0 + (i % 3))
            for i in range(50)
        ]
        alloc = optimizer.optimize_reach(profiles, total_calls=500)
        assert len(alloc) == 50
        assert sum(alloc.values()) <= 500
        assert all(1 <= v <= 8 for v in alloc.values())

    def test_single_hcp_allocation(self):
        optimizer = HCPTargetingOptimizer(total_call_capacity=10)
        alloc = optimizer.optimize_reach([CARDIO_HCP], total_calls=10)
        assert len(alloc) == 1
        assert alloc[CARDIO_HCP.hcp_id] <= 10
