"""
patient_adherence_tracker.py — Medication adherence and persistency analytics for pharma BI.

Implements industry-standard adherence metrics used in pharmacoepidemiology,
HEOR, and commercial analytics:

  - MPR (Medication Possession Ratio): proportion of days covered by supply
  - PDC (Proportion of Days Covered): preferred for chronic medications per ISPOR
  - Therapy Persistence: time on therapy before discontinuation
  - Refill Gap Analysis: identify patients at risk of dropout
  - Adherence tier classification (adherent / partially adherent / non-adherent)

References:
    - Nau et al. (2009) J Manag Care Pharm 15(6):S2-10 — MPR vs PDC
    - Cramer et al. (2008) Value in Health 11(1):44-47 — Adherence definitions
    - ISPOR (2009) Medication Adherence Working Group Definitions
    - Peterson et al. (2007) Am J Manag Care 13(3 Suppl):S68-85 — PDC threshold 80%
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Industry-standard adherence threshold: ≥80% PDC/MPR = adherent
PDC_ADHERENCE_THRESHOLD = 0.80
MPR_ADHERENCE_THRESHOLD = 0.80

# Maximum days to consider a refill gap before classifying as discontinuation
DISCONTINUATION_GAP_DAYS = 60


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PrescriptionFill:
    """A single pharmacy prescription fill event.

    Attributes:
        patient_id: Unique patient identifier.
        drug_name: Drug name (brand or generic).
        fill_date: Date the prescription was filled.
        days_supply: Number of days of medication supplied.
        quantity: Number of units dispensed.
        ndc: National Drug Code (optional).
        pharmacy_id: Pharmacy identifier (optional).

    Raises:
        ValueError: If days_supply or quantity is non-positive.

    Example:
        >>> fill = PrescriptionFill(
        ...     patient_id="P001",
        ...     drug_name="Metformin 500mg",
        ...     fill_date=date(2025, 1, 15),
        ...     days_supply=30,
        ...     quantity=30,
        ... )
        >>> fill.end_date
        datetime.date(2025, 2, 14)
    """

    patient_id: str
    drug_name: str
    fill_date: date
    days_supply: int
    quantity: int = 1
    ndc: str = ""
    pharmacy_id: str = ""

    def __post_init__(self) -> None:
        if not self.patient_id.strip():
            raise ValueError("patient_id must not be empty.")
        if not self.drug_name.strip():
            raise ValueError("drug_name must not be empty.")
        if self.days_supply <= 0:
            raise ValueError(f"days_supply must be positive; got {self.days_supply}.")
        if self.quantity <= 0:
            raise ValueError(f"quantity must be positive; got {self.quantity}.")

    @property
    def end_date(self) -> date:
        """Last day of medication supply coverage."""
        return self.fill_date + timedelta(days=self.days_supply - 1)


@dataclass
class AdherenceMetrics:
    """Computed adherence metrics for a patient over an observation period.

    Attributes:
        patient_id: Patient identifier.
        drug_name: Drug name.
        observation_start: Start of observation window.
        observation_end: End of observation window.
        observation_days: Total length of observation window (days).
        n_fills: Number of prescription fills in window.
        total_days_supply: Total days of medication dispensed.
        days_covered: Days actually covered (PDC method — no overlap credit).
        mpr: Medication Possession Ratio (total_days_supply / observation_days).
        pdc: Proportion of Days Covered (days_covered / observation_days).
        adherence_tier: 'adherent' (PDC≥80%), 'partially_adherent' (50–79%), 'non_adherent' (<50%).
        days_gap_max: Maximum single refill gap (days).
        discontinued: True if a gap > DISCONTINUATION_GAP_DAYS was observed.
        persistence_days: Days from first fill to discontinuation or end of window.
    """

    patient_id: str
    drug_name: str
    observation_start: date
    observation_end: date
    observation_days: int
    n_fills: int
    total_days_supply: int
    days_covered: int
    mpr: float
    pdc: float
    adherence_tier: str
    days_gap_max: int
    discontinued: bool
    persistence_days: int


# ---------------------------------------------------------------------------
# Core tracker
# ---------------------------------------------------------------------------


class PatientAdherenceTracker:
    """Compute MPR, PDC, persistence, and refill gap metrics from pharmacy claims.

    Args:
        observation_window_days: Length of the observation period (days).
            Default 365 (1 year). Must be between 30 and 730.
        adherence_threshold_pdc: PDC threshold for 'adherent' classification.
            Default 0.80 (80%).
        discontinuation_gap_days: Gap (days) triggering discontinuation classification.
            Default 60.

    Example:
        >>> tracker = PatientAdherenceTracker(observation_window_days=365)
        >>> tracker.add_fill(PrescriptionFill("P001", "Metformin", date(2025,1,1), 30))
        >>> metrics = tracker.compute_metrics("P001", "Metformin", date(2025,1,1))
        >>> metrics.pdc
        0.082  # approximately (30/365)
    """

    def __init__(
        self,
        observation_window_days: int = 365,
        adherence_threshold_pdc: float = PDC_ADHERENCE_THRESHOLD,
        discontinuation_gap_days: int = DISCONTINUATION_GAP_DAYS,
    ) -> None:
        if not (30 <= observation_window_days <= 730):
            raise ValueError("observation_window_days must be between 30 and 730.")
        if not (0.0 < adherence_threshold_pdc <= 1.0):
            raise ValueError("adherence_threshold_pdc must be in (0, 1].")
        if discontinuation_gap_days < 7:
            raise ValueError("discontinuation_gap_days must be at least 7.")
        self._window = observation_window_days
        self._threshold = adherence_threshold_pdc
        self._disc_gap = discontinuation_gap_days
        self._fills: List[PrescriptionFill] = []

    def add_fill(self, fill: PrescriptionFill) -> None:
        """Add a prescription fill event.

        Args:
            fill: A validated PrescriptionFill instance.

        Raises:
            TypeError: If fill is not a PrescriptionFill.
        """
        if not isinstance(fill, PrescriptionFill):
            raise TypeError(f"Expected PrescriptionFill, got {type(fill).__name__}.")
        self._fills.append(fill)

    def add_fills(self, fills: List[PrescriptionFill]) -> int:
        """Batch-add prescription fills. Returns count added."""
        count = 0
        for f in fills:
            self.add_fill(f)
            count += 1
        return count

    def get_fills(
        self,
        patient_id: Optional[str] = None,
        drug_name: Optional[str] = None,
    ) -> List[PrescriptionFill]:
        """Filter fills by patient and/or drug."""
        result = self._fills
        if patient_id is not None:
            result = [f for f in result if f.patient_id == patient_id]
        if drug_name is not None:
            result = [f for f in result if f.drug_name.lower() == drug_name.lower()]
        return sorted(result, key=lambda x: x.fill_date)

    def compute_metrics(
        self,
        patient_id: str,
        drug_name: str,
        index_date: date,
        observation_end: Optional[date] = None,
    ) -> Optional[AdherenceMetrics]:
        """Compute adherence metrics for a patient × drug over the observation window.

        The observation window runs from index_date to index_date + observation_window_days.
        Only fills within this window are included.

        Args:
            patient_id: Target patient ID.
            drug_name: Target drug name.
            index_date: Start of observation window (e.g., first fill date or index event).
            observation_end: Optional explicit end date (overrides window calculation).

        Returns:
            AdherenceMetrics instance, or None if no fills exist in the window.

        Example:
            >>> metrics = tracker.compute_metrics("P001", "Metformin", date(2025, 1, 1))
            >>> metrics.adherence_tier
            'non_adherent'
        """
        if observation_end is None:
            obs_end = index_date + timedelta(days=self._window - 1)
        else:
            obs_end = observation_end

        if obs_end <= index_date:
            raise ValueError("observation_end must be after index_date.")

        obs_days = (obs_end - index_date).days + 1

        # Get fills within window
        fills = self.get_fills(patient_id, drug_name)
        window_fills = [
            f for f in fills
            if index_date <= f.fill_date <= obs_end
        ]

        if not window_fills:
            return None

        # PDC: mark covered days, clamp to window, no overlap credit
        covered_days_set: set = set()
        for f in window_fills:
            # Clamp fill end to observation end
            fill_end = min(f.end_date, obs_end)
            for d in range((fill_end - f.fill_date).days + 1):
                covered_days_set.add(f.fill_date + timedelta(days=d))

        # Only count days within window
        covered_in_window = sum(
            1 for d in covered_days_set if index_date <= d <= obs_end
        )

        # MPR: total days supply / observation days (can exceed 1.0 if oversupplied)
        total_supply = sum(f.days_supply for f in window_fills)
        mpr = min(total_supply / obs_days, 1.0)  # cap at 1.0
        pdc = covered_in_window / obs_days

        # Adherence tier
        if pdc >= self._threshold:
            tier = "adherent"
        elif pdc >= 0.50:
            tier = "partially_adherent"
        else:
            tier = "non_adherent"

        # Refill gaps
        gaps = self._compute_refill_gaps(window_fills)
        max_gap = max(gaps) if gaps else 0

        # Discontinuation: any gap > threshold
        discontinued = max_gap > self._disc_gap

        # Persistence: time from first fill to discontinuation or end
        first_fill = window_fills[0].fill_date
        if discontinued:
            disc_start = self._find_discontinuation_start(window_fills)
            persistence = (disc_start - first_fill).days if disc_start else obs_days
        else:
            persistence = (obs_end - first_fill).days + 1

        return AdherenceMetrics(
            patient_id=patient_id,
            drug_name=drug_name,
            observation_start=index_date,
            observation_end=obs_end,
            observation_days=obs_days,
            n_fills=len(window_fills),
            total_days_supply=total_supply,
            days_covered=covered_in_window,
            mpr=round(mpr, 4),
            pdc=round(pdc, 4),
            adherence_tier=tier,
            days_gap_max=max_gap,
            discontinued=discontinued,
            persistence_days=persistence,
        )

    def _compute_refill_gaps(self, fills: List[PrescriptionFill]) -> List[int]:
        """Compute gaps (days) between consecutive fills."""
        gaps = []
        for i in range(1, len(fills)):
            prev_end = fills[i - 1].end_date
            next_start = fills[i].fill_date
            gap = (next_start - prev_end).days - 1
            if gap > 0:
                gaps.append(gap)
        return gaps

    def _find_discontinuation_start(
        self, fills: List[PrescriptionFill]
    ) -> Optional[date]:
        """Find the date when the first discontinuation gap starts."""
        for i in range(1, len(fills)):
            prev_end = fills[i - 1].end_date
            next_start = fills[i].fill_date
            gap = (next_start - prev_end).days - 1
            if gap > self._disc_gap:
                return prev_end + timedelta(days=1)
        return None

    def population_adherence_summary(
        self,
        drug_name: str,
        index_date: date,
    ) -> Optional[Dict]:
        """Compute adherence summary across all patients for a drug.

        Args:
            drug_name: Drug to analyse.
            index_date: Common index date for all patients.

        Returns:
            Dict with n_patients, pct_adherent, pct_partially_adherent,
            pct_non_adherent, mean_pdc, mean_mpr, pct_discontinued,
            mean_persistence_days; or None if no data.
        """
        patient_ids = sorted({f.patient_id for f in self.get_fills(drug_name=drug_name)})
        if not patient_ids:
            return None

        metrics_list = []
        for pid in patient_ids:
            m = self.compute_metrics(pid, drug_name, index_date)
            if m:
                metrics_list.append(m)

        if not metrics_list:
            return None

        n = len(metrics_list)
        adherent = sum(1 for m in metrics_list if m.adherence_tier == "adherent")
        partial = sum(1 for m in metrics_list if m.adherence_tier == "partially_adherent")
        non_adh = sum(1 for m in metrics_list if m.adherence_tier == "non_adherent")
        mean_pdc = sum(m.pdc for m in metrics_list) / n
        mean_mpr = sum(m.mpr for m in metrics_list) / n
        discontinued = sum(1 for m in metrics_list if m.discontinued)
        mean_pers = sum(m.persistence_days for m in metrics_list) / n

        return {
            "drug_name": drug_name,
            "n_patients": n,
            "pct_adherent": round(adherent / n * 100, 1),
            "pct_partially_adherent": round(partial / n * 100, 1),
            "pct_non_adherent": round(non_adh / n * 100, 1),
            "mean_pdc": round(mean_pdc, 4),
            "mean_mpr": round(mean_mpr, 4),
            "pct_discontinued": round(discontinued / n * 100, 1),
            "mean_persistence_days": round(mean_pers, 1),
        }

    def at_risk_patients(
        self,
        drug_name: str,
        index_date: date,
        gap_threshold_days: int = 30,
    ) -> List[Dict]:
        """Identify patients at risk of discontinuation based on recent refill gap.

        Args:
            drug_name: Drug to monitor.
            index_date: Observation index date.
            gap_threshold_days: Gap in days that flags a patient as at-risk. Default 30.

        Returns:
            List of dicts with patient_id, last_fill_date, days_since_last_fill,
            projected_run_out, days_gap for patients past threshold.
        """
        fills_by_patient: Dict[str, List[PrescriptionFill]] = {}
        for f in self.get_fills(drug_name=drug_name):
            fills_by_patient.setdefault(f.patient_id, []).append(f)

        at_risk = []
        for pid, fills in fills_by_patient.items():
            sorted_fills = sorted(fills, key=lambda x: x.fill_date)
            last_fill = sorted_fills[-1]
            run_out = last_fill.end_date
            days_since = (index_date - run_out).days
            if days_since > gap_threshold_days:
                at_risk.append({
                    "patient_id": pid,
                    "last_fill_date": last_fill.fill_date.isoformat(),
                    "days_since_run_out": days_since,
                    "projected_run_out": run_out.isoformat(),
                    "risk_level": "high" if days_since > self._disc_gap else "medium",
                })

        return sorted(at_risk, key=lambda x: -x["days_since_run_out"])
