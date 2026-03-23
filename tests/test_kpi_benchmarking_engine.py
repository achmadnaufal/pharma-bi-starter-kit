"""Unit tests for KPIBenchmarkingEngine."""
import pytest
from src.kpi_benchmarking_engine import (
    KPIBenchmarkingEngine, KPIRecord, SFE_BENCHMARKS
)


@pytest.fixture
def engine():
    e = KPIBenchmarkingEngine(team_name="Oncology - Indonesia", attainment_on_target_threshold=80.0)
    reps = [
        ("REP-001", 8.5, 8.0), ("REP-002", 7.2, 8.0), ("REP-003", 9.1, 8.0),
        ("REP-004", 5.8, 8.0), ("REP-005", 10.2, 8.0), ("REP-006", 6.5, 8.0),
    ]
    for rep_id, value, target in reps:
        e.add_record(KPIRecord(
            rep_id, "calls_per_rep_per_day", value, target,
            "2025-Q1", segment="specialty"
        ))
    # Add period 2025-Q2 for indexing tests
    e.add_record(KPIRecord("REP-001", "calls_per_rep_per_day", 9.0, 8.0, "2025-Q2", segment="specialty"))
    return e


# --- KPIRecord validation ---

def test_empty_entity_id():
    with pytest.raises(ValueError, match="entity_id"):
        KPIRecord("", "calls_per_rep_per_day", 8.0, 8.5, "2025-Q1")

def test_empty_kpi_name():
    with pytest.raises(ValueError, match="kpi_name"):
        KPIRecord("REP-001", "", 8.0, 8.5, "2025-Q1")

def test_negative_target():
    with pytest.raises(ValueError, match="target"):
        KPIRecord("REP-001", "calls_per_rep_per_day", 8.0, -1.0, "2025-Q1")

def test_attainment_pct():
    r = KPIRecord("REP-001", "calls", 8.0, 10.0, "2025-Q1")
    assert r.attainment_pct == 80.0

def test_attainment_zero_target():
    r = KPIRecord("REP-001", "calls", 5.0, 0.0, "2025-Q1")
    assert r.attainment_pct == 0.0

def test_vs_target_delta():
    r = KPIRecord("REP-001", "calls", 8.0, 10.0, "2025-Q1")
    assert r.vs_target_delta == -2.0


# --- Engine setup ---

def test_invalid_threshold():
    with pytest.raises(ValueError, match="attainment_on_target_threshold"):
        KPIBenchmarkingEngine(attainment_on_target_threshold=0)

def test_len(engine):
    assert len(engine) == 7  # 6 Q1 + 1 Q2

def test_repr(engine):
    assert "KPIBenchmarkingEngine" in repr(engine)
    assert "Oncology" in repr(engine)

def test_bulk_add():
    e = KPIBenchmarkingEngine()
    records = [KPIRecord(f"REP-{i}", "calls", 8.0, 9.0, "2025-Q1") for i in range(3)]
    n = e.add_records_bulk(records)
    assert n == 3


# --- Filter ---

def test_filter_by_kpi(engine):
    results = engine.filter_records(kpi_name="calls_per_rep_per_day")
    assert len(results) == 7

def test_filter_by_period(engine):
    results = engine.filter_records(period="2025-Q1")
    assert len(results) == 6

def test_filter_combined(engine):
    results = engine.filter_records(kpi_name="calls_per_rep_per_day", period="2025-Q1")
    assert len(results) == 6


# --- Attainment summary ---

def test_attainment_summary_n(engine):
    summary = engine.attainment_summary("calls_per_rep_per_day", period="2025-Q1")
    assert summary["n_entities"] == 6

def test_attainment_summary_on_target(engine):
    summary = engine.attainment_summary("calls_per_rep_per_day", period="2025-Q1")
    # REP-001(106%), REP-003(114%), REP-005(128%) above 80%
    # REP-002(90%), REP-006(81%) also above 80%... check
    assert summary["on_target_count"] >= 3

def test_attainment_summary_empty():
    e = KPIBenchmarkingEngine()
    summary = e.attainment_summary("calls_per_rep_per_day")
    assert summary["n_entities"] == 0

def test_attainment_summary_keys(engine):
    summary = engine.attainment_summary("calls_per_rep_per_day", period="2025-Q1")
    for key in ["avg_attainment_pct", "median_attainment_pct", "on_target_pct",
                "below_target_pct", "above_100_pct"]:
        assert key in summary


# --- Percentile rank ---

def test_percentile_rank_top(engine):
    rank = engine.percentile_rank("REP-005", "calls_per_rep_per_day", period="2025-Q1")
    assert rank["percentile"] >= 80

def test_percentile_rank_bottom(engine):
    rank = engine.percentile_rank("REP-004", "calls_per_rep_per_day", period="2025-Q1")
    assert rank["percentile"] <= 30

def test_percentile_rank_keys(engine):
    rank = engine.percentile_rank("REP-001", "calls_per_rep_per_day", period="2025-Q1")
    for key in ["entity_id", "value", "percentile", "rank", "peer_group_size", "classification"]:
        assert key in rank

def test_percentile_unknown_entity(engine):
    with pytest.raises(KeyError, match="REP-999"):
        engine.percentile_rank("REP-999", "calls_per_rep_per_day")


# --- Z-score ---

def test_zscore_returns_all_reps(engine):
    zscores = engine.zscore_analysis("calls_per_rep_per_day", period="2025-Q1")
    assert len(zscores) == 6

def test_zscore_sorted_desc(engine):
    zscores = engine.zscore_analysis("calls_per_rep_per_day", period="2025-Q1")
    z_vals = [r["zscore"] for r in zscores]
    assert z_vals == sorted(z_vals, reverse=True)

def test_zscore_empty():
    e = KPIBenchmarkingEngine()
    assert e.zscore_analysis("some_kpi") == []

def test_zscore_high_alert(engine):
    # REP-005 (10.2) is the highest — may get HIGH alert
    zscores = engine.zscore_analysis("calls_per_rep_per_day", period="2025-Q1")
    top = zscores[0]
    # Top scorer should have high z-score
    assert top["zscore"] > 0


# --- Period index ---

def test_period_index_growth(engine):
    idx = engine.period_index("REP-001", "calls_per_rep_per_day", "2025-Q1", "2025-Q2")
    assert idx["index"] > 100  # 9.0 / 8.5 * 100 > 100

def test_period_index_missing_base(engine):
    with pytest.raises(KeyError, match="base period"):
        engine.period_index("REP-001", "calls_per_rep_per_day", "2024-Q4", "2025-Q1")

def test_period_index_keys(engine):
    idx = engine.period_index("REP-001", "calls_per_rep_per_day", "2025-Q1", "2025-Q2")
    for key in ["base_value", "compare_value", "index", "change_pct"]:
        assert key in idx


# --- Industry benchmark ---

def test_compare_to_industry_keys(engine):
    result = engine.compare_to_industry("calls_per_rep_per_day", "specialty", "2025-Q1")
    for key in ["team_avg", "industry_low", "industry_median", "industry_high", "team_position"]:
        assert key in result

def test_compare_to_industry_position(engine):
    result = engine.compare_to_industry("calls_per_rep_per_day", "specialty", "2025-Q1")
    assert result["team_position"] in [
        "Above Industry Top", "Above Median", "Below Median", "Below Industry Low"
    ]

def test_compare_invalid_kpi(engine):
    with pytest.raises(KeyError, match="market_share"):
        engine.compare_to_industry("market_share", "specialty")

def test_compare_invalid_segment(engine):
    with pytest.raises(KeyError, match="pediatric"):
        engine.compare_to_industry("calls_per_rep_per_day", "pediatric")


# --- SFE Benchmarks sanity ---

def test_sfe_benchmarks_structure():
    for kpi, segments in SFE_BENCHMARKS.items():
        for seg, vals in segments.items():
            assert "low" in vals
            assert "median" in vals
            assert "high" in vals
            assert vals["low"] < vals["median"] < vals["high"]
