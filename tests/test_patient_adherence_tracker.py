"""Unit tests for src.patient_adherence_tracker.

Covers: PrescriptionFill validation, PatientAdherenceTracker construction,
add/get fills, PDC/MPR computation, adherence tiers, gap analysis,
persistence, population summary, at-risk identification, and edge cases.
"""

import pytest
from datetime import date, timedelta
from src.patient_adherence_tracker import (
    PrescriptionFill,
    AdherenceMetrics,
    PatientAdherenceTracker,
    PDC_ADHERENCE_THRESHOLD,
    DISCONTINUATION_GAP_DAYS,
)


# ---------------------------------------------------------------------------
# PrescriptionFill tests
# ---------------------------------------------------------------------------


class TestPrescriptionFill:
    def test_basic_creation(self):
        f = PrescriptionFill("P001", "Metformin", date(2025, 1, 1), 30)
        assert f.patient_id == "P001"
        assert f.days_supply == 30

    def test_end_date_calculation(self):
        f = PrescriptionFill("P001", "Metformin", date(2025, 1, 1), 30)
        # 30 days from Jan 1 = Jan 30 (1 + 29 = 30th)
        assert f.end_date == date(2025, 1, 30)

    def test_end_date_single_day(self):
        f = PrescriptionFill("P001", "DrugA", date(2025, 6, 1), 1)
        assert f.end_date == date(2025, 6, 1)

    def test_empty_patient_id_raises(self):
        with pytest.raises(ValueError, match="patient_id"):
            PrescriptionFill("", "Drug", date(2025, 1, 1), 30)

    def test_empty_drug_name_raises(self):
        with pytest.raises(ValueError, match="drug_name"):
            PrescriptionFill("P001", "", date(2025, 1, 1), 30)

    def test_zero_days_supply_raises(self):
        with pytest.raises(ValueError, match="days_supply"):
            PrescriptionFill("P001", "Drug", date(2025, 1, 1), 0)

    def test_negative_days_supply_raises(self):
        with pytest.raises(ValueError, match="days_supply"):
            PrescriptionFill("P001", "Drug", date(2025, 1, 1), -5)

    def test_zero_quantity_raises(self):
        with pytest.raises(ValueError, match="quantity"):
            PrescriptionFill("P001", "Drug", date(2025, 1, 1), 30, quantity=0)


# ---------------------------------------------------------------------------
# PatientAdherenceTracker construction
# ---------------------------------------------------------------------------


class TestTrackerInit:
    def test_default_creation(self):
        t = PatientAdherenceTracker()
        assert t._window == 365
        assert t._threshold == PDC_ADHERENCE_THRESHOLD

    def test_custom_window(self):
        t = PatientAdherenceTracker(observation_window_days=180)
        assert t._window == 180

    def test_invalid_window_raises(self):
        with pytest.raises(ValueError, match="observation_window_days"):
            PatientAdherenceTracker(observation_window_days=10)

    def test_invalid_threshold_raises(self):
        with pytest.raises(ValueError, match="adherence_threshold"):
            PatientAdherenceTracker(adherence_threshold_pdc=0.0)

    def test_invalid_gap_raises(self):
        with pytest.raises(ValueError, match="discontinuation_gap"):
            PatientAdherenceTracker(discontinuation_gap_days=3)


# ---------------------------------------------------------------------------
# Fill management
# ---------------------------------------------------------------------------


def make_fill(patient_id, drug, fill_date, days_supply):
    return PrescriptionFill(patient_id, drug, fill_date, days_supply)


class TestFillManagement:
    def test_add_fill(self):
        t = PatientAdherenceTracker()
        t.add_fill(make_fill("P1", "Drug", date(2025, 1, 1), 30))
        assert len(t.get_fills()) == 1

    def test_add_wrong_type_raises(self):
        t = PatientAdherenceTracker()
        with pytest.raises(TypeError):
            t.add_fill({"patient": "P1"})

    def test_add_fills_batch(self):
        t = PatientAdherenceTracker()
        fills = [make_fill("P1", "Drug", date(2025, 1 + i, 1), 30) for i in range(3)]
        count = t.add_fills(fills)
        assert count == 3

    def test_filter_by_patient(self):
        t = PatientAdherenceTracker()
        t.add_fill(make_fill("P1", "Drug", date(2025, 1, 1), 30))
        t.add_fill(make_fill("P2", "Drug", date(2025, 1, 1), 30))
        assert len(t.get_fills("P1")) == 1

    def test_filter_by_drug(self):
        t = PatientAdherenceTracker()
        t.add_fill(make_fill("P1", "Metformin", date(2025, 1, 1), 30))
        t.add_fill(make_fill("P1", "Lisinopril", date(2025, 1, 1), 30))
        assert len(t.get_fills(drug_name="Metformin")) == 1

    def test_get_fills_sorted_by_date(self):
        t = PatientAdherenceTracker()
        t.add_fill(make_fill("P1", "Drug", date(2025, 3, 1), 30))
        t.add_fill(make_fill("P1", "Drug", date(2025, 1, 1), 30))
        fills = t.get_fills("P1")
        assert fills[0].fill_date < fills[1].fill_date


# ---------------------------------------------------------------------------
# PDC/MPR computation
# ---------------------------------------------------------------------------


class TestComputeMetrics:
    def _make_tracker_with_fills(self, fills):
        t = PatientAdherenceTracker(observation_window_days=365)
        t.add_fills(fills)
        return t

    def test_no_fills_returns_none(self):
        t = PatientAdherenceTracker()
        result = t.compute_metrics("P1", "Drug", date(2025, 1, 1))
        assert result is None

    def test_single_fill_pdc(self):
        # 30 days supply in 365-day window → PDC ≈ 30/365
        t = self._make_tracker_with_fills([
            make_fill("P1", "Drug", date(2025, 1, 1), 30)
        ])
        m = t.compute_metrics("P1", "Drug", date(2025, 1, 1))
        assert m is not None
        assert m.pdc == pytest.approx(30 / 365, abs=0.001)

    def test_full_coverage_adherent(self):
        # 12 fills × 30 days = 360 / 365 ≈ 0.986 → adherent
        fills = [
            make_fill("P1", "Drug", date(2025, 1, 1) + timedelta(days=30 * i), 30)
            for i in range(12)
        ]
        t = self._make_tracker_with_fills(fills)
        m = t.compute_metrics("P1", "Drug", date(2025, 1, 1))
        assert m.pdc >= 0.80
        assert m.adherence_tier == "adherent"

    def test_low_coverage_non_adherent(self):
        # Only 1 fill of 30 days in 365 → PDC = 30/365 ≈ 8% → non_adherent
        fills = [make_fill("P1", "Drug", date(2025, 1, 1), 30)]
        t = self._make_tracker_with_fills(fills)
        m = t.compute_metrics("P1", "Drug", date(2025, 1, 1))
        assert m.adherence_tier == "non_adherent"

    def test_pdc_no_overlap_credit(self):
        # Overlapping fills: same day_supply shouldn't double-count
        fills = [
            make_fill("P1", "Drug", date(2025, 1, 1), 60),
            make_fill("P1", "Drug", date(2025, 1, 15), 60),  # overlaps
        ]
        t = self._make_tracker_with_fills(fills)
        m = t.compute_metrics("P1", "Drug", date(2025, 1, 1))
        # PDC should not exceed 1.0
        assert m.pdc <= 1.0
        # Max covered = 75 days (Jan 1 to Mar 16), not 120

    def test_mpr_capped_at_1(self):
        # 2 fills of 200 days each in 365-day window → raw MPR > 1 → capped
        fills = [
            make_fill("P1", "Drug", date(2025, 1, 1), 200),
            make_fill("P1", "Drug", date(2025, 1, 1), 200),
        ]
        t = self._make_tracker_with_fills(fills)
        m = t.compute_metrics("P1", "Drug", date(2025, 1, 1))
        assert m.mpr <= 1.0

    def test_n_fills_correct(self):
        fills = [make_fill("P1", "Drug", date(2025, 1 + i, 1), 30) for i in range(3)]
        t = self._make_tracker_with_fills(fills)
        m = t.compute_metrics("P1", "Drug", date(2025, 1, 1))
        assert m.n_fills == 3

    def test_invalid_observation_end_raises(self):
        t = PatientAdherenceTracker()
        t.add_fill(make_fill("P1", "Drug", date(2025, 1, 1), 30))
        with pytest.raises(ValueError, match="observation_end"):
            t.compute_metrics(
                "P1", "Drug", date(2025, 6, 1),
                observation_end=date(2025, 1, 1)
            )


# ---------------------------------------------------------------------------
# Refill gap and discontinuation
# ---------------------------------------------------------------------------


class TestGapAndDiscontinuation:
    def test_gap_detected(self):
        # Gap of 90 days between fills
        t = PatientAdherenceTracker()
        t.add_fill(make_fill("P1", "Drug", date(2025, 1, 1), 30))  # runs to Jan 30
        t.add_fill(make_fill("P1", "Drug", date(2025, 5, 1), 30))  # gap of ~90 days
        m = t.compute_metrics("P1", "Drug", date(2025, 1, 1))
        assert m.days_gap_max > 60
        assert m.discontinued is True

    def test_no_gap_no_discontinuation(self):
        t = PatientAdherenceTracker()
        t.add_fill(make_fill("P1", "Drug", date(2025, 1, 1), 30))
        t.add_fill(make_fill("P1", "Drug", date(2025, 1, 31), 30))  # no gap
        m = t.compute_metrics("P1", "Drug", date(2025, 1, 1))
        assert m.discontinued is False

    def test_persistence_shorter_when_discontinued(self):
        t = PatientAdherenceTracker()
        t.add_fill(make_fill("P1", "Drug", date(2025, 1, 1), 30))  # 30 days
        t.add_fill(make_fill("P1", "Drug", date(2025, 6, 1), 30))  # after big gap
        m = t.compute_metrics("P1", "Drug", date(2025, 1, 1))
        assert m.persistence_days < 365


# ---------------------------------------------------------------------------
# Population summary
# ---------------------------------------------------------------------------


class TestPopulationSummary:
    def _make_3_patient_tracker(self):
        t = PatientAdherenceTracker(observation_window_days=365)
        # Patient 1: adherent (12 fills)
        for i in range(12):
            t.add_fill(make_fill("P1", "Metformin",
                                  date(2025, 1, 1) + timedelta(days=30 * i), 30))
        # Patient 2: partially adherent (5 fills)
        for i in range(5):
            t.add_fill(make_fill("P2", "Metformin",
                                  date(2025, 1, 1) + timedelta(days=60 * i), 30))
        # Patient 3: non-adherent (1 fill)
        t.add_fill(make_fill("P3", "Metformin", date(2025, 1, 1), 30))
        return t

    def test_summary_structure(self):
        t = self._make_3_patient_tracker()
        summary = t.population_adherence_summary("Metformin", date(2025, 1, 1))
        assert summary is not None
        assert summary["n_patients"] == 3
        assert "pct_adherent" in summary
        assert "mean_pdc" in summary

    def test_no_data_returns_none(self):
        t = PatientAdherenceTracker()
        result = t.population_adherence_summary("UnknownDrug", date(2025, 1, 1))
        assert result is None

    def test_adherent_patient_counted(self):
        t = self._make_3_patient_tracker()
        summary = t.population_adherence_summary("Metformin", date(2025, 1, 1))
        assert summary["pct_adherent"] > 0


# ---------------------------------------------------------------------------
# At-risk patients
# ---------------------------------------------------------------------------


class TestAtRiskPatients:
    def test_at_risk_detected(self):
        t = PatientAdherenceTracker()
        # Patient ran out of medication 40 days ago
        run_out_date = date(2025, 10, 1)
        t.add_fill(make_fill("P1", "Drug", run_out_date - timedelta(days=29), 30))
        check_date = run_out_date + timedelta(days=40)
        at_risk = t.at_risk_patients("Drug", check_date, gap_threshold_days=30)
        assert len(at_risk) == 1
        assert at_risk[0]["patient_id"] == "P1"

    def test_not_at_risk_recent_fill(self):
        t = PatientAdherenceTracker()
        today = date(2025, 10, 1)
        t.add_fill(make_fill("P1", "Drug", today - timedelta(days=10), 30))
        at_risk = t.at_risk_patients("Drug", today, gap_threshold_days=30)
        assert len(at_risk) == 0

    def test_high_risk_label(self):
        t = PatientAdherenceTracker(discontinuation_gap_days=60)
        run_out = date(2025, 8, 1)
        t.add_fill(make_fill("P1", "Drug", run_out - timedelta(days=29), 30))
        check_date = run_out + timedelta(days=70)  # 70 days past run-out
        at_risk = t.at_risk_patients("Drug", check_date, gap_threshold_days=30)
        assert at_risk[0]["risk_level"] == "high"
