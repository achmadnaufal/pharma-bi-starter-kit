"""
HCP (Healthcare Professional) Targeting Optimizer for pharmaceutical BI analytics.

LP-based call frequency optimization across HCP segments using scipy.optimize.linprog.
Provides prescriber segmentation, ROI estimation, territory balancing, and
next-best-action recommendations aligned with IQVIA SFE methodology.

Key capabilities:
  - HCP segmentation: high/medium/low potential by volume + share gap
  - LP optimization: maximize expected Rx lift given call capacity constraints
  - ROI analysis: call cost vs expected revenue uplift per segment
  - Territory balancing: balanced rep workload across HCP potential tiers
  - Next-best-action: recommend detail call / sample drop / trial invite / CME

References:
  - IQVIA APAC SFE Methodology (2023)
  - Veeva CRM Segmentation best practices
  - ISPOR Healthcare Decision Modelling Guidelines

Author: github.com/achmadnaufal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import linprog


class Segment(str, Enum):
    """HCP potential segment classification."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NextBestAction(str, Enum):
    """Recommended next engagement action for an HCP."""
    DETAIL_CALL = "detail_call"
    SAMPLE_DROP = "sample_drop"
    CLINICAL_TRIAL_INVITE = "clinical_trial_invite"
    CME_SPONSORSHIP = "cme_sponsorship"
    NO_ACTION = "no_action"


class ActionType(str, Enum):
    """Type of engagement action (for ROI modelling)."""
    DETAIL_CALL = "detail_call"
    SAMPLE_DROP = "sample_drop"
    CLINICAL_TRIAL_INVITE = "clinical_trial_invite"
    CME_SPONSORSHIP = "cme_sponsorship"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class HCPProfile:
    """
    Healthcare Professional profile for targeting and call planning.

    Attributes:
        hcp_id: Unique HCP identifier.
        specialty: Therapeutic area (e.g. 'Cardiology', 'Oncology').
        region: Geographic territory (e.g. 'Jawa Barat', 'Bangkok').
        patient_volume: Annual patient volume (proxy for prescriber reach).
        current_share: Current brand share (%) among this HCP's patients.
        potential_share: Achievable brand share (%) with full engagement.
        last_activity_days_ago: Days since last rep activity.
        engagement_score: 0–10 scale rep-HCP relationship quality score.
        call_cost_usd: Cost per rep call visit (USD).
    """
    hcp_id: str
    specialty: str
    region: str
    patient_volume: int
    current_share: float
    potential_share: float
    last_activity_days_ago: int
    engagement_score: float
    call_cost_usd: float = 120.0


@dataclass
class SegmentSummary:
    """Aggregated metrics for an HCP segment."""
    segment: Segment
    count: int
    avg_patient_volume: float
    avg_share_gap: float
    avg_call_cost: float
    expected_rx_lift_per_call: float
    total_call_capacity: int
    estimated_revenue_uplift_usd: float
    estimated_cost_usd: float
    roi_ratio: float


@dataclass
class TerritoryAssignment:
    """HCP assignment for a single sales rep."""
    rep_id: str
    high_segment: List[HCPProfile]
    medium_segment: List[HCPProfile]
    low_segment: List[HCPProfile]

    @property
    def total_hcps(self) -> int:
        return len(self.high_segment) + len(self.medium_segment) + len(self.low_segment)

    @property
    def balanced_score(self) -> float:
        """Score measuring balance across segments (higher = more balanced)."""
        counts = [
            len(self.high_segment),
            len(self.medium_segment),
            len(self.low_segment),
        ]
        if max(counts) == 0:
            return 0.0
        return min(counts) / max(counts) if max(counts) > 0 else 0.0


# ---------------------------------------------------------------------------
# HCP Targeting Optimizer
# ---------------------------------------------------------------------------

class HCPTargetingOptimizer:
    """
    LP-based HCP targeting optimizer for pharmaceutical sales force planning.

    Uses linear programming (scipy.optimize.linprog) to maximize expected
    prescription lift given total call capacity constraints and product
    priority weights. Supports territory balancing and next-best-action
    recommendations per HCP.

    Attributes:
        total_call_capacity: Maximum calls available across all reps per planning cycle.
        min_calls_per_hcp: Minimum calls to assign to any contacted HCP (default 1).
        max_calls_per_hcp: Maximum calls per HCP per cycle (default 10).
        share_gap_weight: Weight for share gap in potential scoring (default 0.5).
        volume_weight: Weight for patient volume in potential scoring (default 0.3).
        engagement_weight: Weight for engagement score in potential scoring (default 0.2).

    Example:
        >>> optimizer = HCPTargetingOptimizer(total_call_capacity=200)
        >>> profiles = [
        ...     HCPProfile(hcp_id="H001", specialty="Cardiology",
        ...                  region="Jawa Barat", patient_volume=200,
        ...                  current_share=15.0, potential_share=40.0,
        ...                  last_activity_days_ago=45, engagement_score=6.5),
        ... ]
        >>> segments = optimizer.segment_hcps(profiles)
        >>> allocation = optimizer.optimize_reach(profiles, total_calls=200)
    """

    # Segment thresholds (share gap = potential_share - current_share)
    HIGH_SHARE_GAP_THRESHOLD: float = 15.0  # percentage points
    MEDIUM_SHARE_GAP_THRESHOLD: float = 5.0  # percentage points

    # Volume thresholds (patient volume percentile)
    HIGH_VOLUME_PERCENTILE: float = 75.0
    LOW_VOLUME_PERCENTILE: float = 25.0

    # Action effectiveness multipliers (expected Rx lift multiplier by action type)
    ACTION_EFFECTIVENESS: Dict[ActionType, float] = {
        ActionType.DETAIL_CALL: 1.0,
        ActionType.SAMPLE_DROP: 0.7,
        ActionType.CLINICAL_TRIAL_INVITE: 1.3,
        ActionType.CME_SPONSORSHIP: 0.9,
    }

    # Action cost (USD per engagement)
    ACTION_COST: Dict[ActionType, float] = {
        ActionType.DETAIL_CALL: 0.0,  # already in call_cost_usd
        ActionType.SAMPLE_DROP: 80.0,
        ActionType.CLINICAL_TRIAL_INVITE: 500.0,
        ActionType.CME_SPONSORSHIP: 350.0,
    }

    # Average revenue per Rx lift point (USD) — baseline for ROI estimation
    REVENUE_PER_RX_POINT: float = 5000.0

    def __init__(
        self,
        total_call_capacity: int = 200,
        min_calls_per_hcp: int = 1,
        max_calls_per_hcp: int = 10,
        share_gap_weight: float = 0.5,
        volume_weight: float = 0.3,
        engagement_weight: float = 0.2,
    ) -> None:
        if total_call_capacity < 0:
            raise ValueError("total_call_capacity must be non-negative")
        if not (0 <= share_gap_weight <= 1) or not (0 <= volume_weight <= 1):
            raise ValueError("Weights must be in [0, 1]")
        if share_gap_weight + volume_weight + engagement_weight > 1.0 + 1e-9:
            raise ValueError("Weights must sum to 1.0")

        self.total_call_capacity = total_call_capacity
        self.min_calls_per_hcp = min_calls_per_hcp
        self.max_calls_per_hcp = max_calls_per_hcp
        self.share_gap_weight = share_gap_weight
        self.volume_weight = volume_weight
        self.engagement_weight = engagement_weight

    # -------------------------------------------------------------------------
    # Segmentation
    # -------------------------------------------------------------------------

    def segment_hcps(self, profiles: List[HCPProfile]) -> pd.DataFrame:
        """
        Segment HCPs into high/medium/low potential tiers.

        Segmentation is based on share gap (potential_share - current_share)
        and patient volume percentile, combined into a composite potential score.

        Args:
            profiles: List of HCPProfile dataclass instances.

        Returns:
            DataFrame with original profile fields plus:
            - `share_gap`: potential_share - current_share
            - `potential_score`: composite score (0–100)
            - `segment`: Segment enum value ('high', 'medium', 'low')
            - `volume_percentile`: percentile rank of patient_volume within input set
        """
        if not profiles:
            df = pd.DataFrame(columns=[
                "hcp_id", "specialty", "region", "patient_volume",
                "current_share", "potential_share", "last_activity_days_ago",
                "engagement_score", "call_cost_usd", "share_gap",
                "potential_score", "segment", "volume_percentile",
            ])
            return df

        data = [{
            "hcp_id": p.hcp_id,
            "specialty": p.specialty,
            "region": p.region,
            "patient_volume": p.patient_volume,
            "current_share": p.current_share,
            "potential_share": p.potential_share,
            "last_activity_days_ago": p.last_activity_days_ago,
            "engagement_score": p.engagement_score,
            "call_cost_usd": p.call_cost_usd,
            "share_gap": p.potential_share - p.current_share,
        } for p in profiles]

        df = pd.DataFrame(data)

        # Volume percentile
        df["volume_percentile"] = df["patient_volume"].rank(pct=True) * 100

        # Composite potential score (0–100)
        # Normalize each component to 0–100 scale
        max_vol = df["patient_volume"].max()
        df["vol_score"] = (df["patient_volume"] / max_vol * 100) if max_vol > 0 else 0
        df["gap_score"] = df["share_gap"]  # already in percentage points
        df["eng_score"] = df["engagement_score"] * 10  # 0–10 → 0–100

        df["potential_score"] = (
            df["gap_score"] * self.share_gap_weight
            + df["vol_score"] * self.volume_weight
            + df["eng_score"] * self.engagement_weight
        )

        # Segment assignment using thresholds
        def assign_segment(row: pd.Series) -> Segment:
            gap = row["share_gap"]
            vol_pct = row["volume_percentile"]
            if gap >= self.HIGH_SHARE_GAP_THRESHOLD and vol_pct >= self.HIGH_VOLUME_PERCENTILE:
                return Segment.HIGH
            elif gap >= self.MEDIUM_SHARE_GAP_THRESHOLD or vol_pct >= self.LOW_VOLUME_PERCENTILE:
                return Segment.MEDIUM
            else:
                return Segment.LOW

        df["segment"] = df.apply(assign_segment, axis=1)

        return df

    # -------------------------------------------------------------------------
    # LP Optimization
    # -------------------------------------------------------------------------

    def _compute_potential_scores(self, profiles: List[HCPProfile]) -> np.ndarray:
        """Compute normalized potential score for each HCP."""
        if not profiles:
            return np.array([])

        scores = []
        for p in profiles:
            share_gap = p.potential_share - p.current_share
            vol_score = p.patient_volume / 1000 * 100  # normalise 1000 patients → 100
            eng_score = p.engagement_score * 10
            score = (
                share_gap * self.share_gap_weight
                + vol_score * self.volume_weight
                + eng_score * self.engagement_weight
            )
            scores.append(min(score, 100.0))  # cap at 100
        return np.array(scores)

    def optimize_reach(
        self,
        profiles: List[HCPProfile],
        total_calls: Optional[int] = None,
        priority_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, int]:
        """
        Optimize call frequency allocation across HCPs using LP.

        Maximizes expected prescription lift subject to total call capacity
        constraints and per-HCP call limits.

        LP formulation:
          Maximise: sum(c_i * s_i * w_i)  for each HCP i
          Subject to:
            sum(c_i) <= total_calls
            min_calls <= c_i <= max_calls  for all i

        Where:
          c_i = number of calls allocated to HCP i
          s_i = potential score of HCP i
          w_i = priority weight of HCP i (default 1.0)

        Args:
            profiles: List of HCPProfile instances to allocate calls for.
            total_calls: Override total call capacity (defaults to self.total_call_capacity).
            priority_weights: Dict of hcp_id → priority multiplier.

        Returns:
            Dict mapping hcp_id → optimal call frequency (integer).
            Returns empty dict if profiles is empty or total_calls == 0.
        """
        n_calls = total_calls if total_calls is not None else self.total_call_capacity

        if not profiles or n_calls <= 0:
            return {p.hcp_id: 0 for p in profiles}

        n_hcps = len(profiles)
        weights = priority_weights or {}
        scores = self._compute_potential_scores(profiles)

        # Objective: maximise sum(c_i * scores[i] * weights[i])
        # linprog minimizes, so we negate
        c = -scores * np.array([weights.get(p.hcp_id, 1.0) for p in profiles])

        # Inequality constraints: sum(c_i) <= n_calls
        # i.e. -sum(c_i) >= -n_calls
        A_ub = -np.ones((1, n_hcps))
        b_ub = np.array([-n_calls])

        # Bounds: min_calls <= c_i <= max_calls
        bounds = [(self.min_calls_per_hcp, self.max_calls_per_hcp) for _ in range(n_hcps)]

        # Handle edge case: capacity smaller than min_calls * n_hcps
        min_total = self.min_calls_per_hcp * n_hcps
        if n_calls < min_total:
            # Feasible region may be empty — still run linprog, it returns best effort
            pass

        result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")

        allocation = {}
        if result.success or result.status in (0, 4):  # 4 = bounded solution found
            sol = np.maximum(result.x, 0).round().astype(int)
            # Clip to feasible range
            sol = np.clip(sol, self.min_calls_per_hcp, self.max_calls_per_hcp)
            # Re-scale if total exceeds capacity
            if sol.sum() > n_calls:
                scale = n_calls / sol.sum()
                sol = (sol * scale).astype(int)
                sol = np.clip(sol, self.min_calls_per_hcp, self.max_calls_per_hcp)
        else:
            # Fallback: uniform allocation respecting min/max
            sol = np.full(n_hcps, min(self.max_calls_per_hcp, n_calls // n_hcps))
            remainder = n_calls - sol.sum() * n_hcps
            # Distribute remainder to highest potential
            order = np.argsort(-scores)
            for i in range(int(remainder)):
                idx = order[i % n_hcps]
                if sol[idx] < self.max_calls_per_hcp:
                    sol[idx] += 1

        for i, p in enumerate(profiles):
            allocation[p.hcp_id] = int(sol[i])

        return allocation

    # -------------------------------------------------------------------------
    # ROI Analysis
    # -------------------------------------------------------------------------

    def calculate_roi_per_segment(
        self,
        profiles: List[HCPProfile],
        allocation: Optional[Dict[str, int]] = None,
    ) -> Dict[Segment, SegmentSummary]:
        """
        Estimate ROI per HCP segment (call cost vs expected revenue uplift).

        Revenue uplift is estimated as:
          expected_rx_lift = sum(call_frequency_i * potential_score_i * action_multiplier)
          revenue_uplift = expected_rx_lift * REVENUE_PER_RX_POINT

        Args:
            profiles: List of HCPProfile instances.
            allocation: Optional dict of hcp_id → call count override.

        Returns:
            Dict mapping Segment → SegmentSummary with cost, uplift, and ROI ratio.
        """
        if not profiles:
            return {}

        df = self.segment_hcps(profiles)
        alloc = allocation or {}

        roi_results: Dict[Segment, SegmentSummary] = {}

        for seg in [Segment.HIGH, Segment.MEDIUM, Segment.LOW]:
            seg_df = df[df["segment"] == seg]
            if seg_df.empty:
                roi_results[seg] = SegmentSummary(
                    segment=seg,
                    count=0,
                    avg_patient_volume=0.0,
                    avg_share_gap=0.0,
                    avg_call_cost=0.0,
                    expected_rx_lift_per_call=0.0,
                    total_call_capacity=0,
                    estimated_revenue_uplift_usd=0.0,
                    estimated_cost_usd=0.0,
                    roi_ratio=0.0,
                )
                continue

            count = len(seg_df)
            avg_vol = seg_df["patient_volume"].mean()
            avg_gap = seg_df["share_gap"].mean()
            avg_cost = seg_df["call_cost_usd"].mean()
            avg_pot = seg_df["potential_score"].mean()

            # Call capacity
            total_cap = sum(alloc.get(hcp_id, self.min_calls_per_hcp) for hcp_id in seg_df["hcp_id"])
            total_cost = sum(seg_df["call_cost_usd"] * np.array([
                alloc.get(hcp_id, self.min_calls_per_hcp) for hcp_id in seg_df["hcp_id"]
            ]))

            # Expected Rx lift (simplified: calls * potential_score / 100 * 10 points)
            rx_lift = total_cap * (avg_pot / 100) * 10 * self.ACTION_EFFECTIVENESS[ActionType.DETAIL_CALL]
            revenue = rx_lift * self.REVENUE_PER_RX_POINT

            roi = revenue / total_cost if total_cost > 0 else 0.0

            roi_results[seg] = SegmentSummary(
                segment=seg,
                count=count,
                avg_patient_volume=avg_vol,
                avg_share_gap=avg_gap,
                avg_call_cost=avg_cost,
                expected_rx_lift_per_call=(rx_lift / total_cap if total_cap > 0 else 0.0),
                total_call_capacity=total_cap,
                estimated_revenue_uplift_usd=revenue,
                estimated_cost_usd=total_cost,
                roi_ratio=roi,
            )

        return roi_results

    # -------------------------------------------------------------------------
    # Territory Balancing
    # -------------------------------------------------------------------------

    def territory_balancer(
        self,
        profiles: List[HCPProfile],
        rep_ids: List[str],
    ) -> List[TerritoryAssignment]:
        """
        Balance HCP assignments across reps so each rep gets similar
        high/medium/low segment counts.

        Uses a greedy round-robin assignment sorted by potential score
        to ensure balanced distribution.

        Args:
            profiles: List of HCPProfile instances to distribute.
            rep_ids: List of rep identifiers to assign HCPS to.

        Returns:
            List of TerritoryAssignment, one per rep.
        """
        if not rep_ids:
            return []

        # If fewer reps than segments needed, cycle through
        df = self.segment_hcps(profiles)
        if df.empty:
            return [
                TerritoryAssignment(rep_id=rep, high_segment=[], medium_segment=[], low_segment=[])
                for rep in rep_ids
            ]

        # Sort all HCPs by potential score descending
        sorted_profiles = sorted(profiles, key=lambda p: (
            -(p.potential_share - p.current_share)
        ))

        # Build segment buckets
        hcp_to_profile = {p.hcp_id: p for p in profiles}
        buckets: Dict[Segment, List[HCPProfile]] = {
            Segment.HIGH: [],
            Segment.MEDIUM: [],
            Segment.LOW: [],
        }
        for _, row in df.iterrows():
            hcp = hcp_to_profile[row["hcp_id"]]
            buckets[row["segment"]].append(hcp)

        # Round-robin assign each segment bucket to reps
        assignments: Dict[str, Dict[Segment, List[HCPProfile]]] = {
            rep: {Segment.HIGH: [], Segment.MEDIUM: [], Segment.LOW: []}
            for rep in rep_ids
        }

        for seg in [Segment.HIGH, Segment.MEDIUM, Segment.LOW]:
            for i, hcp in enumerate(buckets[seg]):
                rep = rep_ids[i % len(rep_ids)]
                assignments[rep][seg].append(hcp)

        return [
            TerritoryAssignment(
                rep_id=rep,
                high_segment=assignments[rep][Segment.HIGH],
                medium_segment=assignments[rep][Segment.MEDIUM],
                low_segment=assignments[rep][Segment.LOW],
            )
            for rep in rep_ids
        ]

    # -------------------------------------------------------------------------
    # Next Best Action
    # -------------------------------------------------------------------------

    def next_best_action(
        self,
        profile: HCPProfile,
        competitive_activity_level: str = "medium",
    ) -> NextBestAction:
        """
        Recommend the next engagement action for a given HCP.

        Decision logic:
          - Last activity > 60 days → clinical trial invite (re-engage)
          - High engagement (>7) + low share gap → CME sponsorship
          - High engagement (>7) + large share gap → detail call
          - Medium engagement (4–7) → sample drop
          - Low engagement (<4) → detail call (build relationship)
          - Very recent activity (<14 days) → no action

        Competitive activity modifier:
          - 'high' competition → prioritises detail call + sample drop
          - 'low' competition → opens CME + trial invite

        Args:
            profile: HCPProfile instance.
            competitive_activity_level: 'low', 'medium', or 'high'.

        Returns:
            NextBestAction enum value.
        """
        days = profile.last_activity_days_ago
        eng = profile.engagement_score
        share_gap = profile.potential_share - profile.current_share

        # Very recent contact — no action needed
        if days < 14:
            return NextBestAction.NO_ACTION

        # Long time since activity — re-engage
        if days > 60:
            if competitive_activity_level == "high":
                return NextBestAction.DETAIL_CALL
            return NextBestAction.CLINICAL_TRIAL_INVITE

        # High engagement HCPs
        if eng > 7:
            if share_gap > 20:
                return NextBestAction.DETAIL_CALL
            elif competitive_activity_level == "low":
                return NextBestAction.CME_SPONSORSHIP
            else:
                return NextBestAction.DETAIL_CALL

        # Medium engagement
        if 4 <= eng <= 7:
            if share_gap > 15 and competitive_activity_level == "high":
                return NextBestAction.SAMPLE_DROP
            return NextBestAction.DETAIL_CALL

        # Low engagement
        return NextBestAction.DETAIL_CALL
