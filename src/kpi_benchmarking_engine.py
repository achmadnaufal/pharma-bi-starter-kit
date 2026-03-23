"""
KPI Benchmarking Engine for Pharmaceutical BI.

Pharmaceutical companies typically benchmark their commercial performance
against industry peers, internal targets, and historical baselines.
This module provides a structured benchmarking framework for common pharma KPIs.

Supported KPI categories:
  - Sales Force Effectiveness (SFE): call rate, coverage, frequency, reach
  - Commercial: market share, revenue vs target, growth rate, brand index
  - Digital / Omnichannel: HCP engagement rate, digital reach
  - Customer Engagement: prescriber call frequency, new prescriber acquisition

Benchmarking methods:
  - Target attainment (% vs quota)
  - Percentile ranking within peer group
  - Z-score vs population (for outlier / best-in-class identification)
  - Period-over-period index (base 100)

Author: github.com/achmadnaufal
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Industry benchmark reference values
# ---------------------------------------------------------------------------

# SFE benchmarks — IQVIA Pharma Benchmarking Survey 2024 reference ranges
SFE_BENCHMARKS: Dict[str, Dict[str, float]] = {
    "calls_per_rep_per_day": {
        "primary_care": {"low": 6.0, "median": 8.5, "high": 12.0},
        "specialty": {"low": 4.0, "median": 6.0, "high": 9.0},
        "hospital": {"low": 3.0, "median": 4.5, "high": 7.0},
    },
    "prescriber_coverage_pct": {
        "primary_care": {"low": 55.0, "median": 70.0, "high": 85.0},
        "specialty": {"low": 65.0, "median": 80.0, "high": 92.0},
        "hospital": {"low": 75.0, "median": 88.0, "high": 96.0},
    },
    "calls_per_prescriber": {
        "primary_care": {"low": 2.0, "median": 3.5, "high": 6.0},
        "specialty": {"low": 3.0, "median": 5.0, "high": 8.0},
        "hospital": {"low": 4.0, "median": 6.5, "high": 9.0},
    },
}


@dataclass
class KPIRecord:
    """
    A single KPI observation for a rep, territory, or team.

    Attributes:
        entity_id: Rep ID, territory code, or team name.
        kpi_name: KPI identifier (e.g., ``calls_per_rep_per_day``).
        value: Observed KPI value.
        target: Target or quota value (used for attainment calculation).
        period: Period label (e.g., ``2025-Q1``, ``2025-03``).
        segment: Business segment (e.g., ``primary_care``, ``specialty``).
        entity_type: Type of entity (``rep``, ``territory``, ``team``).
    """

    entity_id: str
    kpi_name: str
    value: float
    target: float
    period: str
    segment: str = "specialty"
    entity_type: str = "rep"

    def __post_init__(self) -> None:
        if not self.entity_id.strip():
            raise ValueError("entity_id cannot be empty.")
        if not self.kpi_name.strip():
            raise ValueError("kpi_name cannot be empty.")
        if self.target < 0:
            raise ValueError("target cannot be negative.")

    @property
    def attainment_pct(self) -> float:
        """Target attainment percentage."""
        if self.target == 0:
            return 0.0
        return round(self.value / self.target * 100, 2)

    @property
    def vs_target_delta(self) -> float:
        """Absolute gap between value and target."""
        return round(self.value - self.target, 4)


class KPIBenchmarkingEngine:
    """
    Benchmarks pharmaceutical KPIs against peers, targets, and industry norms.

    Supports:
    - Target attainment distribution (on-target / below / above)
    - Percentile ranking of entities within a peer group
    - Z-score identification of outliers and best-in-class performers
    - Period-over-period index tracking
    - Industry benchmark comparison (IQVIA reference ranges for SFE KPIs)

    Attributes:
        team_name (str): Commercial team or brand being benchmarked.
        records (list[KPIRecord]): Registered KPI records.
        attainment_on_target_threshold (float): % attainment to classify as on-target.

    Example::

        engine = KPIBenchmarkingEngine(team_name="Oncology - SEA")
        engine.add_record(KPIRecord(
            entity_id="REP-ID-001", kpi_name="calls_per_rep_per_day",
            value=7.2, target=8.0, period="2025-Q1", segment="specialty"
        ))
        print(engine.attainment_summary("calls_per_rep_per_day", period="2025-Q1"))
        print(engine.percentile_rank("REP-ID-001", "calls_per_rep_per_day"))
    """

    def __init__(
        self,
        team_name: str = "Pharma Team",
        attainment_on_target_threshold: float = 80.0,
    ) -> None:
        """
        Initialize the benchmarking engine.

        Args:
            team_name: Commercial team or brand name.
            attainment_on_target_threshold: Minimum % attainment to be classified
                as "on-target". Default 80%.
        """
        if not (0 < attainment_on_target_threshold <= 200):
            raise ValueError("attainment_on_target_threshold must be in (0, 200].")
        self.team_name = team_name
        self.attainment_on_target_threshold = attainment_on_target_threshold
        self.records: List[KPIRecord] = []

    # ------------------------------------------------------------------
    # Data management
    # ------------------------------------------------------------------

    def add_record(self, record: KPIRecord) -> None:
        """Register a KPI observation."""
        self.records.append(record)

    def add_records_bulk(self, records: List[KPIRecord]) -> int:
        """Bulk-add KPI records. Returns number added."""
        for r in records:
            self.records.append(r)
        return len(records)

    def filter_records(
        self,
        kpi_name: Optional[str] = None,
        period: Optional[str] = None,
        segment: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> List[KPIRecord]:
        """
        Filter records by KPI, period, segment, or entity type.

        Args:
            kpi_name: Filter to this KPI.
            period: Filter to this period.
            segment: Filter to this business segment.
            entity_type: Filter to this entity type.

        Returns:
            List of matching :class:`KPIRecord` instances.
        """
        result = self.records
        if kpi_name is not None:
            result = [r for r in result if r.kpi_name == kpi_name]
        if period is not None:
            result = [r for r in result if r.period == period]
        if segment is not None:
            result = [r for r in result if r.segment == segment]
        if entity_type is not None:
            result = [r for r in result if r.entity_type == entity_type]
        return result

    # ------------------------------------------------------------------
    # Attainment analysis
    # ------------------------------------------------------------------

    def attainment_summary(
        self,
        kpi_name: str,
        period: Optional[str] = None,
    ) -> Dict:
        """
        Summarise target attainment distribution for a KPI.

        Args:
            kpi_name: KPI to analyse.
            period: Optional period filter.

        Returns:
            dict with:

            - ``kpi_name`` – KPI identifier
            - ``n_entities`` – number of entities evaluated
            - ``avg_attainment_pct`` – mean attainment %
            - ``median_attainment_pct`` – median attainment %
            - ``min_attainment_pct`` / ``max_attainment_pct``
            - ``on_target_pct`` – % of entities meeting threshold
            - ``below_target_pct`` – % below threshold
            - ``above_target_pct`` – % exceeding 100% attainment
        """
        records = self.filter_records(kpi_name=kpi_name, period=period)
        if not records:
            return {"kpi_name": kpi_name, "n_entities": 0}

        attainments = sorted(r.attainment_pct for r in records)
        n = len(attainments)
        avg = round(sum(attainments) / n, 2)
        median = attainments[n // 2] if n % 2 else (attainments[n//2 - 1] + attainments[n//2]) / 2

        on_target = sum(1 for a in attainments if a >= self.attainment_on_target_threshold)
        above_100 = sum(1 for a in attainments if a >= 100.0)

        return {
            "kpi_name": kpi_name,
            "period": period or "All",
            "n_entities": n,
            "avg_attainment_pct": avg,
            "median_attainment_pct": round(median, 2),
            "min_attainment_pct": round(attainments[0], 2),
            "max_attainment_pct": round(attainments[-1], 2),
            "on_target_count": on_target,
            "on_target_pct": round(on_target / n * 100, 1),
            "below_target_pct": round((n - on_target) / n * 100, 1),
            "above_100_pct": round(above_100 / n * 100, 1),
            "threshold_used": self.attainment_on_target_threshold,
        }

    # ------------------------------------------------------------------
    # Ranking and percentiles
    # ------------------------------------------------------------------

    def percentile_rank(
        self,
        entity_id: str,
        kpi_name: str,
        period: Optional[str] = None,
    ) -> Dict:
        """
        Calculate an entity's percentile rank within its peer group.

        Args:
            entity_id: Entity to rank.
            kpi_name: KPI to use for ranking.
            period: Optional period filter.

        Returns:
            dict with ``entity_id``, ``value``, ``percentile``,
            ``rank``, and ``peer_group_size``.

        Raises:
            KeyError: If entity_id is not found.
        """
        records = self.filter_records(kpi_name=kpi_name, period=period)
        target_records = [r for r in records if r.entity_id == entity_id]
        if not target_records:
            raise KeyError(f"Entity '{entity_id}' not found for KPI '{kpi_name}'.")

        # Use the most recent record if multiple exist
        target = target_records[-1]
        all_values = sorted(r.value for r in records)
        n = len(all_values)
        rank = sum(1 for v in all_values if v <= target.value)
        percentile = round(rank / n * 100, 1)

        return {
            "entity_id": entity_id,
            "kpi_name": kpi_name,
            "value": target.value,
            "target": target.target,
            "attainment_pct": target.attainment_pct,
            "rank": rank,
            "peer_group_size": n,
            "percentile": percentile,
            "classification": self._classify_percentile(percentile),
        }

    @staticmethod
    def _classify_percentile(percentile: float) -> str:
        """Classify performance tier by percentile."""
        if percentile >= 80:
            return "Top Performer"
        elif percentile >= 60:
            return "Above Average"
        elif percentile >= 40:
            return "Average"
        elif percentile >= 20:
            return "Below Average"
        else:
            return "Needs Attention"

    # ------------------------------------------------------------------
    # Z-score (outlier detection)
    # ------------------------------------------------------------------

    def zscore_analysis(
        self, kpi_name: str, period: Optional[str] = None
    ) -> List[Dict]:
        """
        Compute Z-scores for all entities on a given KPI.

        Z-score > +2 → significantly above average (best-in-class)
        Z-score < -2 → significantly below average (at-risk)

        Args:
            kpi_name: KPI to evaluate.
            period: Optional period filter.

        Returns:
            List of dicts per entity with ``entity_id``, ``value``,
            ``zscore``, and ``alert`` flag (``"HIGH"``/``"LOW"``/``None``).
        """
        records = self.filter_records(kpi_name=kpi_name, period=period)
        if not records:
            return []

        values = [r.value for r in records]
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std = math.sqrt(variance) if variance > 0 else 1e-9  # avoid division by zero

        result = []
        for r in records:
            z = round((r.value - mean) / std, 3)
            alert = "HIGH" if z > 2.0 else ("LOW" if z < -2.0 else None)
            result.append({
                "entity_id": r.entity_id,
                "value": r.value,
                "zscore": z,
                "alert": alert,
            })
        return sorted(result, key=lambda x: -x["zscore"])

    # ------------------------------------------------------------------
    # Period-over-period index
    # ------------------------------------------------------------------

    def period_index(
        self,
        entity_id: str,
        kpi_name: str,
        base_period: str,
        compare_period: str,
    ) -> Dict:
        """
        Calculate a period-over-period index (base = 100) for an entity.

        Args:
            entity_id: Entity to track.
            kpi_name: KPI to index.
            base_period: Denominator period.
            compare_period: Numerator period.

        Returns:
            dict with ``index`` (base=100), ``base_value``, ``compare_value``,
            and ``change_pct``.

        Raises:
            KeyError: If entity or period not found.
        """
        base_recs = [r for r in self.records
                     if r.entity_id == entity_id and r.kpi_name == kpi_name and r.period == base_period]
        comp_recs = [r for r in self.records
                     if r.entity_id == entity_id and r.kpi_name == kpi_name and r.period == compare_period]

        if not base_recs:
            raise KeyError(f"No records for '{entity_id}' in base period '{base_period}'.")
        if not comp_recs:
            raise KeyError(f"No records for '{entity_id}' in compare period '{compare_period}'.")

        base_val = base_recs[-1].value
        comp_val = comp_recs[-1].value
        index = round(comp_val / base_val * 100, 2) if base_val != 0 else None
        change_pct = round((comp_val - base_val) / base_val * 100, 2) if base_val != 0 else None

        return {
            "entity_id": entity_id,
            "kpi_name": kpi_name,
            "base_period": base_period,
            "compare_period": compare_period,
            "base_value": base_val,
            "compare_value": comp_val,
            "index": index,
            "change_pct": change_pct,
        }

    # ------------------------------------------------------------------
    # Industry benchmark comparison
    # ------------------------------------------------------------------

    def compare_to_industry(
        self, kpi_name: str, segment: str = "specialty", period: Optional[str] = None
    ) -> Dict:
        """
        Compare team average to IQVIA industry benchmark reference range.

        Only available for SFE KPIs in :data:`SFE_BENCHMARKS`.

        Args:
            kpi_name: SFE KPI to benchmark (must be in ``SFE_BENCHMARKS``).
            segment: Channel/segment (``primary_care``, ``specialty``, ``hospital``).
            period: Optional period filter.

        Returns:
            dict with team average, industry quartiles, and relative position.

        Raises:
            KeyError: If kpi_name or segment not found in SFE_BENCHMARKS.
        """
        if kpi_name not in SFE_BENCHMARKS:
            raise KeyError(
                f"'{kpi_name}' not in industry benchmarks. "
                f"Available: {list(SFE_BENCHMARKS)}"
            )
        if segment not in SFE_BENCHMARKS[kpi_name]:
            raise KeyError(
                f"Segment '{segment}' not found for '{kpi_name}'. "
                f"Available: {list(SFE_BENCHMARKS[kpi_name])}"
            )

        records = self.filter_records(kpi_name=kpi_name, period=period, segment=segment)
        ref = SFE_BENCHMARKS[kpi_name][segment]
        team_avg = round(sum(r.value for r in records) / len(records), 3) if records else None

        position = None
        if team_avg is not None:
            if team_avg >= ref["high"]:
                position = "Above Industry Top"
            elif team_avg >= ref["median"]:
                position = "Above Median"
            elif team_avg >= ref["low"]:
                position = "Below Median"
            else:
                position = "Below Industry Low"

        return {
            "kpi_name": kpi_name,
            "segment": segment,
            "team_avg": team_avg,
            "industry_low": ref["low"],
            "industry_median": ref["median"],
            "industry_high": ref["high"],
            "team_position": position,
            "n_entities": len(records),
        }

    def __len__(self) -> int:
        return len(self.records)

    def __repr__(self) -> str:
        return (
            f"KPIBenchmarkingEngine(team={self.team_name!r}, "
            f"records={len(self.records)})"
        )
