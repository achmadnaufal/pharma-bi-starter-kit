"""
Sales Force Effectiveness (SFE) Scorer for pharmaceutical BI analytics.

Evaluates pharma sales representative and territory performance using
IQVIA/IMS-aligned SFE frameworks. Provides individual rep scoring,
territory benchmarking, and coaching priority identification.

Key SFE metrics scored:
  - Prescriber coverage: % of target prescribers reached
  - Call frequency: average calls per prescriber per cycle
  - Call quality: detail quality score and message delivery
  - New prescriber acquisition: new-to-brand (NTB) prescriber conversion
  - Revenue attainment: actual vs quota performance
  - Digital engagement: hybrid HCP engagement rate

Scoring methodology:
  - Each metric normalised to 0–100 against territory-specific benchmarks
  - Composite SFE score (weighted): Coverage (25%) + Frequency (20%) +
    Quality (20%) + NTB (20%) + Attainment (15%)
  - Rank tier: A+ / A / B / C / D

References:
  - IQVIA SFE Benchmarking Survey APAC 2024
  - ZS Associates Call Planning Framework
  - Veeva CRM SFE Dashboard Standards

Author: github.com/achmadnaufal
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class RepTier(str, Enum):
    """Sales rep performance tier classification."""
    A_PLUS = "A+"      # SFE score ≥ 85
    A = "A"            # 70–84
    B = "B"            # 55–69
    C = "C"            # 40–54
    D = "D"            # < 40 — requires urgent coaching


class Specialty(str, Enum):
    """HCP specialty for benchmark selection."""
    PRIMARY_CARE = "primary_care"
    SPECIALTY = "specialty"
    HOSPITAL = "hospital"
    ONCOLOGY = "oncology"


# SFE benchmark ranges (IQVIA APAC 2024) by specialty
SFE_BENCHMARKS: Dict[Specialty, Dict[str, Dict[str, float]]] = {
    Specialty.PRIMARY_CARE: {
        "calls_per_day": {"low": 6.0, "median": 8.5, "top_quartile": 11.0},
        "coverage_pct": {"low": 55.0, "median": 72.0, "top_quartile": 85.0},
        "calls_per_prescriber": {"low": 2.0, "median": 3.5, "top_quartile": 5.5},
        "ntb_rate_pct": {"low": 3.0, "median": 6.0, "top_quartile": 10.0},
    },
    Specialty.SPECIALTY: {
        "calls_per_day": {"low": 4.0, "median": 6.0, "top_quartile": 8.5},
        "coverage_pct": {"low": 65.0, "median": 80.0, "top_quartile": 92.0},
        "calls_per_prescriber": {"low": 3.0, "median": 5.0, "top_quartile": 8.0},
        "ntb_rate_pct": {"low": 4.0, "median": 8.0, "top_quartile": 14.0},
    },
    Specialty.HOSPITAL: {
        "calls_per_day": {"low": 3.0, "median": 4.5, "top_quartile": 6.5},
        "coverage_pct": {"low": 75.0, "median": 88.0, "top_quartile": 96.0},
        "calls_per_prescriber": {"low": 4.0, "median": 6.5, "top_quartile": 9.0},
        "ntb_rate_pct": {"low": 2.0, "median": 5.0, "top_quartile": 9.0},
    },
    Specialty.ONCOLOGY: {
        "calls_per_day": {"low": 2.0, "median": 3.5, "top_quartile": 5.0},
        "coverage_pct": {"low": 70.0, "median": 85.0, "top_quartile": 95.0},
        "calls_per_prescriber": {"low": 5.0, "median": 8.0, "top_quartile": 12.0},
        "ntb_rate_pct": {"low": 2.0, "median": 4.5, "top_quartile": 8.0},
    },
}

# Composite SFE dimension weights (must sum to 1.0)
SFE_WEIGHTS: Dict[str, float] = {
    "coverage": 0.25,
    "frequency": 0.20,
    "quality": 0.20,
    "ntb": 0.20,
    "attainment": 0.15,
}

# Tier thresholds
TIER_THRESHOLDS: Dict[RepTier, float] = {
    RepTier.A_PLUS: 85.0,
    RepTier.A: 70.0,
    RepTier.B: 55.0,
    RepTier.C: 40.0,
    RepTier.D: 0.0,
}


@dataclass
class RepPerformanceRecord:
    """SFE performance data for a single sales representative per period.

    Attributes:
        rep_id: Unique rep identifier.
        rep_name: Display name.
        territory_id: Territory/district code.
        specialty: HCP specialty this rep targets.
        period: Reporting period (e.g., 'Q1 2026').
        target_prescribers: Total addressable prescribers in territory.
        prescribers_visited: Actual unique prescribers called.
        total_calls: Total calls made in period.
        total_working_days: Working days in period.
        avg_call_quality_score: Average call quality (0–10, from field coach/e-CLM).
        ntb_prescribers: New-to-brand prescribers converted in period.
        revenue_actual_usd: Actual revenue achieved.
        revenue_quota_usd: Revenue quota for period.
        digital_engagements: Digital HCP interactions (email, webinar, portal).
    """

    rep_id: str
    rep_name: str
    territory_id: str
    specialty: Specialty
    period: str
    target_prescribers: int
    prescribers_visited: int
    total_calls: int
    total_working_days: int
    avg_call_quality_score: float
    ntb_prescribers: int
    revenue_actual_usd: float
    revenue_quota_usd: float
    digital_engagements: int = 0

    def __post_init__(self) -> None:
        if self.target_prescribers <= 0:
            raise ValueError("target_prescribers must be positive")
        if self.prescribers_visited < 0:
            raise ValueError("prescribers_visited cannot be negative")
        if self.prescribers_visited > self.target_prescribers:
            raise ValueError("prescribers_visited cannot exceed target_prescribers")
        if self.total_working_days <= 0:
            raise ValueError("total_working_days must be positive")
        if not (0 <= self.avg_call_quality_score <= 10):
            raise ValueError("avg_call_quality_score must be 0–10")
        if self.revenue_quota_usd <= 0:
            raise ValueError("revenue_quota_usd must be positive")

    @property
    def coverage_pct(self) -> float:
        """Prescriber coverage rate (%)."""
        return (self.prescribers_visited / self.target_prescribers) * 100

    @property
    def calls_per_day(self) -> float:
        """Average calls made per working day."""
        return self.total_calls / self.total_working_days

    @property
    def calls_per_prescriber(self) -> float:
        """Average call frequency per visited prescriber."""
        if self.prescribers_visited == 0:
            return 0.0
        return self.total_calls / self.prescribers_visited

    @property
    def ntb_rate_pct(self) -> float:
        """New-to-brand prescriber conversion rate (%)."""
        return (self.ntb_prescribers / self.target_prescribers) * 100

    @property
    def revenue_attainment_pct(self) -> float:
        """Revenue attainment as % of quota."""
        return (self.revenue_actual_usd / self.revenue_quota_usd) * 100


@dataclass
class SFEScore:
    """Computed SFE scoring result for a single rep.

    Attributes:
        rep_id: Reference rep.
        rep_name: Display name.
        period: Reporting period.
        tier: Rep performance tier (A+ / A / B / C / D).
        composite_score: Weighted SFE composite score (0–100).
        dimension_scores: Per-dimension sub-scores (0–100).
        dimension_raw_values: Raw metric values for audit trail.
        benchmark_comparison: How each dimension compares to territory benchmark.
        strengths: Top-performing dimensions.
        coaching_priorities: Dimensions needing improvement.
        recommended_actions: Specific coaching and development actions.
    """

    rep_id: str
    rep_name: str
    period: str
    tier: RepTier
    composite_score: float
    dimension_scores: Dict[str, float]
    dimension_raw_values: Dict[str, float]
    benchmark_comparison: Dict[str, str]
    strengths: List[str]
    coaching_priorities: List[str]
    recommended_actions: List[str]


class SalesForceEffectivenessScorer:
    """Scores pharmaceutical sales rep performance using SFE framework.

    Benchmarks individual rep metrics against IQVIA specialty standards,
    assigns composite SFE scores, and generates coaching recommendations.

    Example:
        >>> scorer = SalesForceEffectivenessScorer()
        >>> record = RepPerformanceRecord(
        ...     rep_id="REP_001",
        ...     rep_name="Ahmad Solikhin",
        ...     territory_id="JKT_WEST",
        ...     specialty=Specialty.SPECIALTY,
        ...     period="Q1 2026",
        ...     target_prescribers=120,
        ...     prescribers_visited=96,
        ...     total_calls=480,
        ...     total_working_days=65,
        ...     avg_call_quality_score=7.5,
        ...     ntb_prescribers=14,
        ...     revenue_actual_usd=285_000,
        ...     revenue_quota_usd=300_000,
        ... )
        >>> score = scorer.score(record)
        >>> print(score.tier)
        RepTier.A
    """

    def __init__(
        self,
        coverage_quality_threshold: float = 6.5,
        custom_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        """Initialise the scorer.

        Args:
            coverage_quality_threshold: Min call quality for effective call count.
            custom_weights: Optional override for SFE dimension weights.
        """
        self.coverage_quality_threshold = coverage_quality_threshold
        self.weights = custom_weights or SFE_WEIGHTS
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"SFE weights must sum to 1.0; got {total:.3f}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(self, record: RepPerformanceRecord) -> SFEScore:
        """Compute SFE score for a single rep performance record.

        Args:
            record: RepPerformanceRecord with period activity metrics.

        Returns:
            SFEScore with tier, composite score, and coaching recommendations.
        """
        if not isinstance(record, RepPerformanceRecord):
            raise TypeError("record must be a RepPerformanceRecord instance")

        benchmarks = SFE_BENCHMARKS[record.specialty]

        dim_scores = {
            "coverage": self._score_coverage(record, benchmarks),
            "frequency": self._score_frequency(record, benchmarks),
            "quality": self._score_quality(record),
            "ntb": self._score_ntb(record, benchmarks),
            "attainment": self._score_attainment(record),
        }

        composite = sum(dim_scores[d] * self.weights[d] for d in dim_scores)
        tier = self._assign_tier(composite)

        raw_vals = {
            "coverage_pct": round(record.coverage_pct, 1),
            "calls_per_day": round(record.calls_per_day, 1),
            "calls_per_prescriber": round(record.calls_per_prescriber, 1),
            "ntb_rate_pct": round(record.ntb_rate_pct, 1),
            "revenue_attainment_pct": round(record.revenue_attainment_pct, 1),
            "avg_call_quality": round(record.avg_call_quality_score, 1),
        }

        bm_comparison = self._benchmark_comparison(record, benchmarks)
        strengths, coaching = self._classify_dimensions(dim_scores)
        actions = self._recommend_actions(record, tier, dim_scores, coaching)

        return SFEScore(
            rep_id=record.rep_id,
            rep_name=record.rep_name,
            period=record.period,
            tier=tier,
            composite_score=round(composite, 1),
            dimension_scores={k: round(v, 1) for k, v in dim_scores.items()},
            dimension_raw_values=raw_vals,
            benchmark_comparison=bm_comparison,
            strengths=strengths,
            coaching_priorities=coaching,
            recommended_actions=actions,
        )

    def score_team(self, records: List[RepPerformanceRecord]) -> List[SFEScore]:
        """Score all reps in a team, sorted by composite score descending.

        Args:
            records: List of RepPerformanceRecord instances.

        Returns:
            Sorted list of SFEScore (highest score first).

        Raises:
            ValueError: If records list is empty.
        """
        if not records:
            raise ValueError("records list cannot be empty")
        scores = [self.score(r) for r in records]
        return sorted(scores, key=lambda s: s.composite_score, reverse=True)

    def team_summary(self, scores: List[SFEScore]) -> Dict:
        """Generate team-level SFE summary statistics.

        Args:
            scores: List of SFEScore from score_team().

        Returns:
            Dict with tier distribution, average score, and coaching count.
        """
        if not scores:
            return {}
        by_tier: Dict[str, int] = {t.value: 0 for t in RepTier}
        for s in scores:
            by_tier[s.tier.value] += 1

        avg_score = sum(s.composite_score for s in scores) / len(scores)
        needs_coaching = sum(1 for s in scores if s.tier in (RepTier.C, RepTier.D))

        return {
            "total_reps": len(scores),
            "avg_sfe_score": round(avg_score, 1),
            "tier_distribution": by_tier,
            "reps_needing_coaching": needs_coaching,
            "top_rep": scores[0].rep_name if scores else None,
            "bottom_rep": scores[-1].rep_name if scores else None,
        }

    # ------------------------------------------------------------------
    # Private scorers
    # ------------------------------------------------------------------

    def _score_coverage(self, r: RepPerformanceRecord, bm: Dict) -> float:
        median = bm["coverage_pct"]["median"]
        top = bm["coverage_pct"]["top_quartile"]
        low = bm["coverage_pct"]["low"]
        return self._linear_score(r.coverage_pct, low, median, top)

    def _score_frequency(self, r: RepPerformanceRecord, bm: Dict) -> float:
        median = bm["calls_per_prescriber"]["median"]
        top = bm["calls_per_prescriber"]["top_quartile"]
        low = bm["calls_per_prescriber"]["low"]
        return self._linear_score(r.calls_per_prescriber, low, median, top)

    def _score_quality(self, r: RepPerformanceRecord) -> float:
        """Score based on call quality 0–10 scale."""
        return min(100, (r.avg_call_quality_score / 10) * 100)

    def _score_ntb(self, r: RepPerformanceRecord, bm: Dict) -> float:
        median = bm["ntb_rate_pct"]["median"]
        top = bm["ntb_rate_pct"]["top_quartile"]
        low = bm["ntb_rate_pct"]["low"]
        return self._linear_score(r.ntb_rate_pct, low, median, top)

    def _score_attainment(self, r: RepPerformanceRecord) -> float:
        """Score revenue attainment: 100% quota = 100pts, capped at 120%."""
        return min(100, r.revenue_attainment_pct)

    @staticmethod
    def _linear_score(value: float, low: float, median: float, top: float) -> float:
        """Linear interpolation scoring: low→25pts, median→60pts, top→100pts."""
        if value <= low:
            return max(0, (value / low) * 25) if low > 0 else 0
        elif value <= median:
            return 25 + ((value - low) / (median - low)) * 35
        else:
            return 60 + min(40, ((value - median) / (top - median)) * 40)

    @staticmethod
    def _assign_tier(score: float) -> RepTier:
        for tier in [RepTier.A_PLUS, RepTier.A, RepTier.B, RepTier.C]:
            if score >= TIER_THRESHOLDS[tier]:
                return tier
        return RepTier.D

    @staticmethod
    def _benchmark_comparison(r: RepPerformanceRecord, bm: Dict) -> Dict[str, str]:
        result: Dict[str, str] = {}
        metrics = [
            ("coverage_pct", r.coverage_pct, "coverage_pct"),
            ("frequency", r.calls_per_prescriber, "calls_per_prescriber"),
            ("ntb_rate_pct", r.ntb_rate_pct, "ntb_rate_pct"),
        ]
        for label, value, bm_key in metrics:
            if bm_key not in bm:
                continue
            if value >= bm[bm_key]["top_quartile"]:
                result[label] = "top_quartile"
            elif value >= bm[bm_key]["median"]:
                result[label] = "above_median"
            elif value >= bm[bm_key]["low"]:
                result[label] = "below_median"
            else:
                result[label] = "below_low"
        return result

    @staticmethod
    def _classify_dimensions(dim_scores: Dict[str, float]) -> Tuple[List[str], List[str]]:
        sorted_dims = sorted(dim_scores.items(), key=lambda x: x[1], reverse=True)
        strengths = [d for d, s in sorted_dims if s >= 70][:2]
        coaching = [d for d, s in sorted_dims if s < 55]
        return strengths, coaching

    @staticmethod
    def _recommend_actions(
        r: RepPerformanceRecord,
        tier: RepTier,
        dim_scores: Dict[str, float],
        coaching_priorities: List[str],
    ) -> List[str]:
        actions: List[str] = []
        if "coverage" in coaching_priorities:
            actions.append(
                f"Coverage at {r.coverage_pct:.0f}% — review call plan; add {r.target_prescribers - r.prescribers_visited} unvisited prescribers to priority list."
            )
        if "ntb" in coaching_priorities:
            actions.append(
                f"NTB conversion at {r.ntb_rate_pct:.1f}% — focus on 'gain new writers' detailing approach with field coach ride-alongs."
            )
        if "quality" in coaching_priorities:
            actions.append(
                f"Call quality score {r.avg_call_quality_score:.1f}/10 — schedule e-CLM coaching session and key message refresh."
            )
        if "attainment" in coaching_priorities:
            gap = r.revenue_quota_usd - r.revenue_actual_usd
            actions.append(
                f"Revenue gap USD {gap:,.0f} ({100 - r.revenue_attainment_pct:.1f}% below quota) — review product mix and account plan."
            )
        if tier == RepTier.A_PLUS:
            actions.append("High performer — nominate for peer coaching/buddy programme to scale best practices.")
        if not actions:
            actions.append("On track — maintain current activity level and monitor key metrics monthly.")
        return actions
