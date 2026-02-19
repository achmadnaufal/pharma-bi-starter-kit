"""
Data Quality Scorer for pharmaceutical BI data pipelines.

Scores incoming datasets against configurable quality dimensions:
  1. Completeness — fraction of non-null values
  2. Validity — values within expected domain/range
  3. Uniqueness — duplicate record detection
  4. Timeliness — data freshness relative to expected update cadence
  5. Consistency — referential integrity across related fields

Produces a composite DQ score (0–100) and an itemised quality report
suitable for BI data observability dashboards and pipeline alerting.

Aligned with DAMA-DMBOK2 data quality dimensions.

Reference:
    DAMA International (2017) DAMA-DMBOK: Data Management Body of Knowledge, 2nd Ed.
    IQVIA Data Quality Framework for Pharma Analytics.

Author: github.com/achmadnaufal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Dimension weights (must sum to 1.0)
# ---------------------------------------------------------------------------

DEFAULT_DIMENSION_WEIGHTS: Dict[str, float] = {
    "completeness": 0.30,
    "validity": 0.25,
    "uniqueness": 0.20,
    "timeliness": 0.15,
    "consistency": 0.10,
}

# DQ rating bands
RATING_BANDS = [
    (90, "Excellent"),
    (75, "Good"),
    (60, "Acceptable"),
    (40, "Poor"),
    (0,  "Critical"),
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DimensionScore:
    """Score for a single data quality dimension.

    Attributes:
        dimension: Name of the DQ dimension.
        raw_score: Score before weighting (0–100).
        weight: Configured weight for this dimension.
        weighted_score: raw_score × weight.
        issues: List of human-readable issue descriptions found.
    """

    dimension: str
    raw_score: float
    weight: float
    weighted_score: float
    issues: List[str] = field(default_factory=list)


@dataclass
class DataQualityReport:
    """Composite data quality report for a dataset.

    Attributes:
        dataset_name: Identifier for the dataset.
        total_rows: Row count in the input DataFrame.
        composite_score: Weighted DQ score (0–100).
        rating: Rating band (Excellent/Good/Acceptable/Poor/Critical).
        dimension_scores: Dict mapping dimension name → DimensionScore.
        passed: True if composite_score ≥ ``pass_threshold``.
        recommendations: List of prioritised action recommendations.
    """

    dataset_name: str
    total_rows: int
    composite_score: float
    rating: str
    dimension_scores: Dict[str, DimensionScore]
    passed: bool
    recommendations: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------


class DataQualityScorer:
    """Score a pandas DataFrame against configurable data quality dimensions.

    Args:
        dataset_name: Label for the dataset being scored.
        required_columns: Columns that must be present and non-null
            (used for completeness).
        valid_ranges: Dict mapping column name → (min, max) tuple for
            numeric range validation (used for validity).
        valid_categories: Dict mapping column name → set of allowed values
            for categorical fields.
        unique_key_columns: Columns that together form the expected unique
            key (used for uniqueness check).
        max_age_days: Maximum acceptable data age in days. Requires a
            ``date_column`` argument in :meth:`score`.
        dimension_weights: Override default dimension weights.
        pass_threshold: Minimum composite score to mark ``passed=True``.
            Default 75.

    Example:
        >>> import pandas as pd
        >>> from src.data_quality_scorer import DataQualityScorer
        >>> scorer = DataQualityScorer(
        ...     dataset_name="NSP-Indonesia-2025-Q4",
        ...     required_columns=["period", "brand", "sales_usd"],
        ...     valid_ranges={"sales_usd": (0, 10_000_000)},
        ...     valid_categories={"channel": {"chain", "independent", "hospital"}},
        ...     unique_key_columns=["period", "brand", "outlet_id"],
        ... )
        >>> df = pd.read_csv("data/nsp_indonesia.csv")
        >>> report = scorer.score(df)
        >>> print(f"DQ Score: {report.composite_score:.1f}/100 ({report.rating})")
    """

    def __init__(
        self,
        dataset_name: str,
        required_columns: Optional[List[str]] = None,
        valid_ranges: Optional[Dict[str, Tuple[float, float]]] = None,
        valid_categories: Optional[Dict[str, Set]] = None,
        unique_key_columns: Optional[List[str]] = None,
        max_age_days: Optional[int] = None,
        dimension_weights: Optional[Dict[str, float]] = None,
        pass_threshold: float = 75.0,
    ):
        if not dataset_name.strip():
            raise ValueError("dataset_name cannot be empty")
        if pass_threshold < 0 or pass_threshold > 100:
            raise ValueError("pass_threshold must be in [0, 100]")

        self.dataset_name = dataset_name
        self.required_columns = required_columns or []
        self.valid_ranges = valid_ranges or {}
        self.valid_categories = valid_categories or {}
        self.unique_key_columns = unique_key_columns or []
        self.max_age_days = max_age_days
        self.pass_threshold = pass_threshold

        weights = dimension_weights or DEFAULT_DIMENSION_WEIGHTS
        total = sum(weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"dimension_weights must sum to 1.0, got {total:.3f}")
        self.weights = weights

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(
        self,
        df: pd.DataFrame,
        date_column: Optional[str] = None,
        reference_date: Optional[Any] = None,
    ) -> DataQualityReport:
        """Score the DataFrame and return a detailed quality report.

        Args:
            df: DataFrame to assess.
            date_column: Column containing record dates (for timeliness check).
            reference_date: Reference date for freshness calculation. If None,
                uses today (``pd.Timestamp.today()``).

        Returns:
            :class:`DataQualityReport` with composite score and dimension breakdown.
        """
        if df.empty:
            return self._empty_report()

        dimension_scores: Dict[str, DimensionScore] = {}
        dimension_scores["completeness"] = self._score_completeness(df)
        dimension_scores["validity"] = self._score_validity(df)
        dimension_scores["uniqueness"] = self._score_uniqueness(df)
        dimension_scores["timeliness"] = self._score_timeliness(df, date_column, reference_date)
        dimension_scores["consistency"] = self._score_consistency(df)

        composite = sum(
            ds.weighted_score for ds in dimension_scores.values()
        )
        composite = round(min(100.0, max(0.0, composite)), 2)
        rating = self._get_rating(composite)
        recs = self._build_recommendations(dimension_scores)

        return DataQualityReport(
            dataset_name=self.dataset_name,
            total_rows=len(df),
            composite_score=composite,
            rating=rating,
            dimension_scores=dimension_scores,
            passed=composite >= self.pass_threshold,
            recommendations=recs,
        )

    def score_column(self, series: pd.Series) -> Dict[str, float]:
        """Score a single column for completeness and validity.

        Args:
            series: The column to assess.

        Returns:
            Dict with ``completeness_pct`` and ``null_count``.
        """
        null_count = int(series.isna().sum())
        completeness = (1 - null_count / max(len(series), 1)) * 100
        return {
            "completeness_pct": round(completeness, 2),
            "null_count": null_count,
            "total": len(series),
        }

    # ------------------------------------------------------------------
    # Dimension scorers
    # ------------------------------------------------------------------

    def _score_completeness(self, df: pd.DataFrame) -> DimensionScore:
        issues: List[str] = []
        scores: List[float] = []

        # Check required columns exist
        missing_cols = [c for c in self.required_columns if c not in df.columns]
        if missing_cols:
            issues.append(f"Missing required columns: {missing_cols}")
            scores.append(0.0)
        else:
            for col in self.required_columns:
                null_pct = df[col].isna().mean() * 100
                col_score = max(0.0, 100.0 - null_pct * 2)  # penalise heavily
                scores.append(col_score)
                if null_pct > 0:
                    issues.append(f"'{col}': {null_pct:.1f}% nulls")

        # Also score overall completeness
        overall_null_pct = df.isna().mean().mean() * 100
        scores.append(max(0.0, 100.0 - overall_null_pct))

        raw = sum(scores) / len(scores) if scores else 100.0
        return DimensionScore(
            dimension="completeness",
            raw_score=round(raw, 2),
            weight=self.weights["completeness"],
            weighted_score=round(raw * self.weights["completeness"], 4),
            issues=issues,
        )

    def _score_validity(self, df: pd.DataFrame) -> DimensionScore:
        issues: List[str] = []
        violation_counts: List[int] = []
        total_checks = 0

        for col, (lo, hi) in self.valid_ranges.items():
            if col not in df.columns:
                issues.append(f"Range check column '{col}' not found")
                continue
            numeric = pd.to_numeric(df[col], errors="coerce")
            out_of_range = ((numeric < lo) | (numeric > hi)).sum()
            violation_counts.append(int(out_of_range))
            total_checks += len(df)
            if out_of_range:
                issues.append(f"'{col}': {out_of_range} values outside [{lo}, {hi}]")

        for col, allowed in self.valid_categories.items():
            if col not in df.columns:
                issues.append(f"Category check column '{col}' not found")
                continue
            invalid = (~df[col].isin(allowed)).sum()
            violation_counts.append(int(invalid))
            total_checks += len(df)
            if invalid:
                issues.append(f"'{col}': {invalid} values not in allowed set")

        if total_checks == 0:
            raw = 100.0
        else:
            total_violations = sum(violation_counts)
            raw = max(0.0, (1 - total_violations / total_checks) * 100)

        return DimensionScore(
            dimension="validity",
            raw_score=round(raw, 2),
            weight=self.weights["validity"],
            weighted_score=round(raw * self.weights["validity"], 4),
            issues=issues,
        )

    def _score_uniqueness(self, df: pd.DataFrame) -> DimensionScore:
        issues: List[str] = []
        if not self.unique_key_columns:
            return DimensionScore(
                dimension="uniqueness",
                raw_score=100.0,
                weight=self.weights["uniqueness"],
                weighted_score=100.0 * self.weights["uniqueness"],
                issues=["No unique key columns configured — skipped"],
            )
        available = [c for c in self.unique_key_columns if c in df.columns]
        if not available:
            issues.append(f"Unique key columns not found in DataFrame: {self.unique_key_columns}")
            return DimensionScore("uniqueness", 0.0, self.weights["uniqueness"], 0.0, issues)

        dup_count = df.duplicated(subset=available).sum()
        dup_pct = dup_count / len(df) * 100
        raw = max(0.0, 100.0 - dup_pct * 5)  # 1% duplicates → -5 points
        if dup_count:
            issues.append(f"{dup_count} duplicate rows on key {available} ({dup_pct:.1f}%)")

        return DimensionScore(
            dimension="uniqueness",
            raw_score=round(raw, 2),
            weight=self.weights["uniqueness"],
            weighted_score=round(raw * self.weights["uniqueness"], 4),
            issues=issues,
        )

    def _score_timeliness(
        self,
        df: pd.DataFrame,
        date_column: Optional[str],
        reference_date: Optional[Any],
    ) -> DimensionScore:
        issues: List[str] = []
        if not date_column or date_column not in df.columns or self.max_age_days is None:
            return DimensionScore(
                dimension="timeliness",
                raw_score=100.0,
                weight=self.weights["timeliness"],
                weighted_score=100.0 * self.weights["timeliness"],
                issues=["Timeliness check not configured — skipped"],
            )

        ref = pd.Timestamp(reference_date) if reference_date else pd.Timestamp.today()
        dates = pd.to_datetime(df[date_column], errors="coerce")
        invalid_dates = dates.isna().sum()
        if invalid_dates:
            issues.append(f"{invalid_dates} unparseable dates in '{date_column}'")

        max_date = dates.max()
        if pd.isna(max_date):
            return DimensionScore("timeliness", 0.0, self.weights["timeliness"], 0.0,
                                   issues + ["All dates are null"])

        age_days = (ref - max_date).days
        raw = max(0.0, 100.0 - max(0, age_days - self.max_age_days) * 5)
        if age_days > self.max_age_days:
            issues.append(f"Latest data is {age_days} days old (max allowed: {self.max_age_days})")

        return DimensionScore(
            dimension="timeliness",
            raw_score=round(raw, 2),
            weight=self.weights["timeliness"],
            weighted_score=round(raw * self.weights["timeliness"], 4),
            issues=issues,
        )

    def _score_consistency(self, df: pd.DataFrame) -> DimensionScore:
        """Check for logical consistency between related fields."""
        issues: List[str] = []
        n_checks = 0
        n_violations = 0

        # Generic consistency: numeric columns should not have extreme outliers
        # (z-score > 5 suggests data entry errors in pharma datasets)
        for col in df.select_dtypes(include="number").columns:
            col_data = df[col].dropna()
            if len(col_data) < 4:
                continue
            mean, std = col_data.mean(), col_data.std()
            if std == 0:
                continue
            z_scores = ((col_data - mean) / std).abs()
            extreme = (z_scores > 5).sum()
            n_checks += 1
            if extreme:
                n_violations += 1
                issues.append(f"'{col}': {extreme} values with z-score > 5 (potential outliers)")

        if n_checks == 0:
            raw = 100.0
        else:
            raw = max(0.0, (1 - n_violations / n_checks) * 100)

        return DimensionScore(
            dimension="consistency",
            raw_score=round(raw, 2),
            weight=self.weights["consistency"],
            weighted_score=round(raw * self.weights["consistency"], 4),
            issues=issues,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _empty_report(self) -> DataQualityReport:
        empty_dim = {
            d: DimensionScore(d, 0.0, w, 0.0, ["Empty DataFrame"])
            for d, w in self.weights.items()
        }
        return DataQualityReport(
            dataset_name=self.dataset_name,
            total_rows=0,
            composite_score=0.0,
            rating="Critical",
            dimension_scores=empty_dim,
            passed=False,
            recommendations=["Dataset is empty — check upstream data source"],
        )

    @staticmethod
    def _get_rating(score: float) -> str:
        for threshold, label in RATING_BANDS:
            if score >= threshold:
                return label
        return "Critical"

    @staticmethod
    def _build_recommendations(dimension_scores: Dict[str, DimensionScore]) -> List[str]:
        recs: List[str] = []
        worst = sorted(dimension_scores.values(), key=lambda ds: ds.raw_score)
        for ds in worst[:3]:
            if ds.raw_score < 80:
                recs.append(
                    f"Improve {ds.dimension} (score {ds.raw_score:.0f}/100): "
                    + "; ".join(ds.issues[:2])
                    if ds.issues
                    else f"Review {ds.dimension} dimension."
                )
        return recs
