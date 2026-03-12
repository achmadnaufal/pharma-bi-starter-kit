"""Tests for competitive intelligence module."""

import pytest
from src.competitive_intel import CompetitiveIntelligence


class TestCompetitiveIntelligence:
    """Test competitive intelligence analysis."""
    
    @pytest.fixture
    def intel(self):
        ci = CompetitiveIntelligence()
        ci.add_competitor(
            "Pfizer",
            ["Oncology", "Cardio"],
            {"Drug A": {"sales_usd": 500000}, "Drug B": {"sales_usd": 300000}}
        )
        ci.add_competitor(
            "Roche",
            ["Oncology"],
            {"Drug C": {"sales_usd": 400000}}
        )
        return ci
    
    def test_add_competitor(self, intel):
        """Test competitor registration."""
        assert "Pfizer" in intel.competitors
        assert len(intel.competitors["Pfizer"]["products"]) == 2
    
    def test_market_dynamics(self, intel):
        """Test market dynamics analysis."""
        result = intel.calculate_market_dynamics("Oncology")
        
        assert "Pfizer" in result["market_shares"]
        assert "Roche" in result["market_shares"]
        assert result["hhi_index"] > 0
    
    def test_competitive_gaps(self, intel):
        """Test gap identification."""
        result = intel.identify_competitive_gaps(
            ["MyDrug"],
            ["Cardio"]
        )
        
        assert "Oncology" in result["underserved_areas"]
        assert "Cardio" in result["our_coverage"]
    
    def test_product_maturity(self, intel):
        """Test product lifecycle forecasting."""
        result = intel.forecast_product_maturity(
            "TestDrug",
            [100, 120, 140, 160],
            years_on_market=1
        )
        
        assert result["lifecycle_stage"] == "growth"
        assert len(result["next_4_quarters_forecast"]) == 4
