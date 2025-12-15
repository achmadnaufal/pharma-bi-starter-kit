"""
Starter kit for pharma BI analysts with templates, SQL queries, and best practices.

Provides reusable analysis components for pharmaceutical business intelligence:
sales force effectiveness (SFE), sales rep performance, territory analysis,
and KPI reporting aligned with common pharma BI frameworks.

Author: github.com/achmadnaufal
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List


class PharmaBIStarterKit:
    """
    Pharma BI analyst starter kit.

    Provides ready-to-use components for common pharma BI use cases:
    rep performance, territory KPIs, target attainment, and call activity analysis.

    Args:
        config: Optional dict with keys:
            - target_attainment_threshold: % for "on-target" classification (default 80)
            - top_performers_pct: Top performer percentile (default 20)

    Example:
        >>> kit = PharmaBIStarterKit(config={"target_attainment_threshold": 80})
        >>> df = kit.load_data("data/rep_sales.csv")
        >>> report = kit.sales_performance_report(df)
        >>> print(report["top_performers"])
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.target_threshold = self.config.get("target_attainment_threshold", 80.0)
        self.top_pct = self.config.get("top_performers_pct", 20.0)

    def load_data(self, filepath: str) -> pd.DataFrame:
        """
        Load sales rep data from CSV or Excel.

        Args:
            filepath: Path to file. Expected columns: rep_id, territory,
                      actual_sales, target_sales, call_count, period.

        Returns:
            DataFrame with rep performance data.

        Raises:
            FileNotFoundError: If file does not exist.
        """
        p = Path(filepath)
        if not p.exists():
            raise FileNotFoundError(f"Data file not found: {filepath}")
        if p.suffix in (".xlsx", ".xls"):
            return pd.read_excel(filepath)
        return pd.read_csv(filepath)

    def validate(self, df: pd.DataFrame) -> bool:
        """
        Validate rep performance data.

        Args:
            df: DataFrame to validate.

        Returns:
            True if valid.

        Raises:
            ValueError: If empty or missing required columns.
        """
        if df.empty:
            raise ValueError("Input DataFrame is empty")
        df_cols = [c.lower().strip().replace(" ", "_") for c in df.columns]
        required = ["rep_id", "actual_sales", "target_sales"]
        missing = [c for c in required if c not in df_cols]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        return True

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names and fill missing values."""
        df = df.copy()
        df.dropna(how="all", inplace=True)
        df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]
        num_cols = df.select_dtypes(include="number").columns
        for col in num_cols:
            if df[col].isnull().any():
                df[col].fillna(df[col].median(), inplace=True)
        return df

    def sales_performance_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate sales rep performance KPI report.

        Calculates target attainment %, performance tier (top/on-track/below),
        call-to-sales efficiency, and territory ranking.

        Args:
            df: Rep performance DataFrame with rep_id, actual_sales,
                target_sales, and optionally call_count, territory.

        Returns:
            Dict with:
                - rep_summary: DataFrame with per-rep KPIs
                - top_performers: List of top performers (top N%)
                - below_target: Reps below attainment threshold
                - team_attainment_pct: Team-level target attainment
                - total_actual_vs_target: {actual, target, gap}

        Raises:
            ValueError: If required columns missing.
        """
        df = self.preprocess(df)
        required = ["rep_id", "actual_sales", "target_sales"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing columns: {missing}")

        if (df["target_sales"] <= 0).any():
            df.loc[df["target_sales"] <= 0, "target_sales"] = 1  # avoid div by zero

        agg_cols = ["rep_id"] + (["territory"] if "territory" in df.columns else [])
        rep_agg = df.groupby(agg_cols).agg(
            actual_sales=("actual_sales", "sum"),
            target_sales=("target_sales", "sum"),
        )
        if "call_count" in df.columns:
            rep_agg["call_count"] = df.groupby(agg_cols)["call_count"].sum()
        rep_agg = rep_agg.reset_index()

        rep_agg["attainment_pct"] = (
            rep_agg["actual_sales"] / rep_agg["target_sales"] * 100
        ).round(2)

        top_threshold = rep_agg["attainment_pct"].quantile(1 - self.top_pct / 100)
        rep_agg["performance_tier"] = pd.cut(
            rep_agg["attainment_pct"],
            bins=[-np.inf, self.target_threshold, top_threshold, np.inf],
            labels=["Below Target", "On Track", "Top Performer"],
        ).astype(str)

        if "call_count" in rep_agg.columns:
            rep_agg["sales_per_call"] = (
                rep_agg["actual_sales"] / rep_agg["call_count"].replace(0, np.nan)
            ).round(2)

        rep_agg["rank"] = rep_agg["attainment_pct"].rank(ascending=False, method="min").astype(int)
        rep_agg = rep_agg.sort_values("rank")

        team_attainment = float(
            rep_agg["actual_sales"].sum() / rep_agg["target_sales"].sum() * 100
        )
        top_performers = rep_agg[rep_agg["performance_tier"] == "Top Performer"]["rep_id"].tolist()
        below_target = rep_agg[rep_agg["attainment_pct"] < self.target_threshold]["rep_id"].tolist()

        return {
            "rep_summary": rep_agg,
            "top_performers": top_performers,
            "below_target": below_target,
            "team_attainment_pct": round(team_attainment, 2),
            "total_actual_vs_target": {
                "actual": round(rep_agg["actual_sales"].sum(), 2),
                "target": round(rep_agg["target_sales"].sum(), 2),
                "gap": round(rep_agg["target_sales"].sum() - rep_agg["actual_sales"].sum(), 2),
            },
        }

    def territory_heatmap_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate performance metrics by territory for heatmap visualization.

        Args:
            df: Rep performance DataFrame with territory column.

        Returns:
            DataFrame with territory-level KPIs: total sales, attainment %,
            rep count, avg call count.

        Raises:
            ValueError: If territory column not present.
        """
        df = self.preprocess(df)
        if "territory" not in df.columns:
            raise ValueError("Column 'territory' required for territory heatmap")

        agg = df.groupby("territory").agg(
            total_actual=("actual_sales", "sum"),
            total_target=("target_sales", "sum"),
            rep_count=("rep_id", "nunique"),
        )
        if "call_count" in df.columns:
            agg["avg_calls"] = df.groupby("territory")["call_count"].mean().round(1)
        agg["territory_attainment_pct"] = (
            agg["total_actual"] / agg["total_target"] * 100
        ).round(2)
        return agg.reset_index().sort_values("territory_attainment_pct", ascending=False)

    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Run descriptive analysis and return summary metrics."""
        df = self.preprocess(df)
        result = {
            "total_records": len(df),
            "columns": list(df.columns),
            "missing_pct": (df.isnull().sum() / len(df) * 100).round(1).to_dict(),
        }
        numeric_df = df.select_dtypes(include="number")
        if not numeric_df.empty:
            result["summary_stats"] = numeric_df.describe().round(3).to_dict()
            result["totals"] = numeric_df.sum().round(2).to_dict()
            result["means"] = numeric_df.mean().round(3).to_dict()
        return result

    def run(self, filepath: str) -> Dict[str, Any]:
        """Full pipeline: load → validate → analyze."""
        df = self.load_data(filepath)
        self.validate(df)
        return self.analyze(df)

    def to_dataframe(self, result: Dict) -> pd.DataFrame:
        """Convert result dict to flat DataFrame for export."""
        rows = []
        for k, v in result.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    rows.append({"metric": f"{k}.{kk}", "value": vv})
            else:
                rows.append({"metric": k, "value": v})
        return pd.DataFrame(rows)


    def territory_performance_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build a territory performance matrix with attainment, call efficiency,
        and opportunity score for sales force effectiveness (SFE) analysis.

        Performance matrix quadrants (based on attainment and call efficiency):
            - Star: high attainment + high call efficiency
            - Underperformer: low attainment + high calls (low conversion)
            - Efficient: high attainment + low calls (high conversion)
            - At Risk: low attainment + low calls

        Args:
            df: Sales DataFrame with rep_id, territory, actual_sales,
                target_sales, and call_count columns.

        Returns:
            DataFrame with territory, attainment_pct, calls_per_sale,
            quadrant label, and opportunity_score.

        Raises:
            ValueError: If required columns are missing.
        """
        df = self.preprocess(df)
        required = ["actual_sales", "target_sales", "call_count"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing columns for territory matrix: {missing}")

        group_col = "territory" if "territory" in df.columns else "rep_id" if "rep_id" in df.columns else None
        if group_col is None:
            raise ValueError("Need 'territory' or 'rep_id' column for grouping")

        agg = df.groupby(group_col).agg(
            total_actual=("actual_sales", "sum"),
            total_target=("target_sales", "sum"),
            total_calls=("call_count", "sum"),
        ).reset_index()

        agg["attainment_pct"] = (agg["total_actual"] / agg["total_target"].replace(0, np.nan) * 100).round(2)
        agg["calls_per_sale"] = (agg["total_calls"] / agg["total_actual"].replace(0, np.nan)).round(3)

        att_median = agg["attainment_pct"].median()
        cps_median = agg["calls_per_sale"].median()

        def quadrant(row: pd.Series) -> str:
            """Assign SFE quadrant based on attainment and call efficiency."""
            high_att = row["attainment_pct"] >= att_median
            low_cps = row["calls_per_sale"] <= cps_median  # lower calls_per_sale = more efficient
            if high_att and low_cps:
                return "Star"
            if high_att and not low_cps:
                return "Underperformer"
            if not high_att and low_cps:
                return "Efficient"
            return "At Risk"

        agg["quadrant"] = agg.apply(quadrant, axis=1)
        agg["opportunity_score"] = (
            (agg["attainment_pct"] / 100).clip(0, 2) * 0.6
            + (1 / agg["calls_per_sale"].replace(0, np.nan)).fillna(0).clip(0, 1) * 0.4
        ).round(3)

        return agg.sort_values("attainment_pct", ascending=False).reset_index(drop=True)

    def kpi_summary_card(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate a KPI summary card for pharma BI dashboard display.

        Returns top-line metrics suitable for a Power BI card visual or
        Streamlit metric widget.

        Args:
            df: Sales DataFrame.

        Returns:
            Dict with keys: total_actual_sales, total_target_sales,
            overall_attainment_pct, reps_on_target, reps_at_risk, periods_covered.
        """
        df = self.preprocess(df)
        result: Dict[str, Any] = {}
        if "actual_sales" in df.columns:
            result["total_actual_sales"] = round(float(df["actual_sales"].sum()), 2)
        if "target_sales" in df.columns:
            result["total_target_sales"] = round(float(df["target_sales"].sum()), 2)
        if "actual_sales" in df.columns and "target_sales" in df.columns:
            tot = float(df["target_sales"].sum())
            result["overall_attainment_pct"] = round(
                float(df["actual_sales"].sum()) / tot * 100 if tot > 0 else 0, 2
            )
            if "rep_id" in df.columns:
                rep_att = df.groupby("rep_id").apply(
                    lambda g: g["actual_sales"].sum() / max(g["target_sales"].sum(), 1) * 100
                )
                result["reps_on_target"] = int((rep_att >= self.target_threshold).sum())
                result["reps_at_risk"] = int((rep_att < self.target_threshold).sum())
        if "period" in df.columns:
            result["periods_covered"] = df["period"].nunique()
        return result
