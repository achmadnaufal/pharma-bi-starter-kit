"""End-to-end demo for pharma-bi-starter-kit.

Runs each analyzer module against the shipped sample_data and prints a
compact summary suitable for README usage examples.

Modules exercised:
    - HCPTargetingOptimizer (LP-based call planning)
    - SalesForceEffectivenessScorer (IQVIA APAC SFE)
    - KPIBenchmarkingEngine (attainment + percentile)
    - PatientAdherenceTracker (MPR / PDC / persistence)

Run from the repo root:

    python demo/demo.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Ensure `src` package is importable when run from repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.hcp_targeting import HCPProfile, HCPTargetingOptimizer
from src.kpi_benchmarking_engine import KPIBenchmarkingEngine, KPIRecord
from src.patient_adherence_tracker import (
    PatientAdherenceTracker,
    PrescriptionFill,
)
from src.sales_force_effectiveness_scorer import (
    RepPerformanceRecord,
    SalesForceEffectivenessScorer,
    Specialty,
)


SECTION = "=" * 60


def banner(title: str) -> None:
    """Print a section banner."""
    print(f"\n{SECTION}\n  {title}\n{SECTION}")


def demo_hcp_targeting() -> None:
    """HCP segmentation + LP call allocation + next-best-action."""
    banner("HCP TARGETING OPTIMIZER (LP-based call planning)")
    profiles = (
        HCPProfile("H001", "Cardiology", "Jawa Barat", 350, 15.0, 45.0, 45, 6.5),
        HCPProfile("H002", "Cardiology", "Jawa Barat", 220, 8.0, 30.0, 60, 4.2),
        HCPProfile("H003", "Oncology",   "Bangkok",    480, 22.0, 38.0, 20, 7.8),
        HCPProfile("H004", "Oncology",   "Bangkok",    150, 12.0, 20.0, 90, 3.5),
        HCPProfile("H005", "Cardiology", "Manila",     300, 18.0, 40.0, 30, 6.0),
    )
    optimizer = HCPTargetingOptimizer(total_call_capacity=40)
    segments = optimizer.segment_hcps(list(profiles))
    allocation = optimizer.optimize_reach(list(profiles), total_calls=40)

    print(f"  HCPs analysed        : {len(profiles)}")
    print(f"  High-potential count : {int((segments['segment'] == 'high').sum())}")
    print(f"  Medium-potential ct. : {int((segments['segment'] == 'medium').sum())}")
    print(f"  Low-potential count  : {int((segments['segment'] == 'low').sum())}")
    print(f"  Total calls allocated: {sum(allocation.values())}")
    print(f"  Top allocation (H003): {allocation['H003']} calls")
    action = optimizer.next_best_action(profiles[0])
    print(f"  H001 next-best-action: {action.value}")


def demo_sfe_scorer() -> None:
    """IQVIA-aligned SFE scoring for a single rep."""
    banner("SALES FORCE EFFECTIVENESS SCORER (IQVIA APAC)")
    record = RepPerformanceRecord(
        rep_id="REP_001",
        rep_name="Ahmad Solikhin",
        territory_id="JKT_WEST",
        specialty=Specialty.SPECIALTY,
        period="Q1 2026",
        target_prescribers=120,
        prescribers_visited=96,
        total_calls=480,
        total_working_days=65,
        avg_call_quality_score=7.5,
        ntb_prescribers=14,
        revenue_actual_usd=285_000,
        revenue_quota_usd=300_000,
    )
    scorer = SalesForceEffectivenessScorer()
    score = scorer.score(record)
    print(f"  Rep                  : {record.rep_name} ({record.rep_id})")
    print(f"  Composite SFE Score  : {score.composite_score:.1f} / 100")
    print(f"  Tier                 : {score.tier.value}")
    print(f"  Coverage pct         : {record.coverage_pct:.1f}%")
    print(f"  Revenue attainment   : {record.revenue_attainment_pct:.1f}%")
    if score.strengths:
        print(f"  Top strength         : {score.strengths[0]}")
    if score.coaching_priorities:
        print(f"  Coaching priority    : {score.coaching_priorities[0]}")


def demo_kpi_benchmarker() -> None:
    """Team-wide attainment benchmarking."""
    banner("KPI BENCHMARKING ENGINE")
    engine = KPIBenchmarkingEngine(team_name="Cardiovascular APAC")
    engine.add_records_bulk([
        KPIRecord("REP_001", "calls_per_rep_per_day", 7.8, 8.5, "Q1 2026", "specialty"),
        KPIRecord("REP_002", "calls_per_rep_per_day", 6.2, 8.5, "Q1 2026", "specialty"),
        KPIRecord("REP_003", "calls_per_rep_per_day", 9.1, 8.5, "Q1 2026", "specialty"),
        KPIRecord("REP_004", "calls_per_rep_per_day", 5.4, 8.5, "Q1 2026", "specialty"),
        KPIRecord("REP_005", "calls_per_rep_per_day", 8.7, 8.5, "Q1 2026", "specialty"),
    ])
    summary = engine.attainment_summary("calls_per_rep_per_day", period="Q1 2026")
    ranking = engine.percentile_rank("REP_003", "calls_per_rep_per_day", period="Q1 2026")
    print(f"  Team                 : {engine.team_name}")
    print(f"  Reps evaluated       : {summary['n_entities']}")
    print(f"  Avg attainment       : {summary['avg_attainment_pct']}%")
    print(f"  On-target reps       : {summary['on_target_count']} ({summary['on_target_pct']}%)")
    print(f"  REP_003 percentile   : P{ranking['percentile']:.0f} ({ranking['classification']})")


def demo_patient_adherence() -> None:
    """Population-level MPR / PDC / persistence summary."""
    banner("PATIENT ADHERENCE TRACKER (MPR / PDC / Persistence)")
    tracker = PatientAdherenceTracker(observation_window_days=180)
    # Patient A: fully adherent (monthly refills with no gaps)
    for month_idx in range(6):
        tracker.add_fill(PrescriptionFill(
            patient_id="P001",
            drug_name="Atorvastatin",
            fill_date=date(2025, month_idx + 1, 1),
            days_supply=31,
        ))
    # Patient B: partially adherent (gaps)
    tracker.add_fill(PrescriptionFill("P002", "Atorvastatin", date(2025, 1, 1), 30))
    tracker.add_fill(PrescriptionFill("P002", "Atorvastatin", date(2025, 3, 15), 30))
    tracker.add_fill(PrescriptionFill("P002", "Atorvastatin", date(2025, 5, 1), 30))
    # Patient C: discontinued
    tracker.add_fill(PrescriptionFill("P003", "Atorvastatin", date(2025, 1, 1), 30))
    tracker.add_fill(PrescriptionFill("P003", "Atorvastatin", date(2025, 2, 1), 30))

    summary = tracker.population_adherence_summary("Atorvastatin", date(2025, 1, 1))
    if summary is None:
        print("  No adherence data available.")
        return
    print(f"  Drug                 : {summary['drug_name']}")
    print(f"  Patients analysed    : {summary['n_patients']}")
    print(f"  Mean PDC             : {summary['mean_pdc']:.2f}")
    print(f"  Mean MPR             : {summary['mean_mpr']:.2f}")
    print(f"  Adherent pct         : {summary['pct_adherent']}%")
    print(f"  Discontinued pct     : {summary['pct_discontinued']}%")
    print(f"  Mean persistence     : {summary['mean_persistence_days']} days")


def main() -> int:
    """Run the full demo. Returns 0 on success."""
    print("PHARMA BI STARTER KIT — LIVE DEMO")
    print(f"Repo root: {REPO_ROOT}")
    demo_hcp_targeting()
    demo_sfe_scorer()
    demo_kpi_benchmarker()
    demo_patient_adherence()
    print(f"\n{SECTION}\n  Demo complete.\n{SECTION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
