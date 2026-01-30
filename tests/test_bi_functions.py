"""Tests for Pharma BI analytical functions."""
import pytest
import pandas as pd

class TestBIFunctions:
    """Test suite for BI functions."""
    
    @pytest.fixture
    def sample_sales_data(self):
        return pd.DataFrame({
            'month': ['2025-01', '2025-02', '2025-03'],
            'revenue': [100000, 120000, 115000],
            'units_sold': [1000, 1200, 1150],
            'region': ['NA', 'NA', 'NA']
        })
    
    def test_data_loading(self, sample_sales_data):
        assert len(sample_sales_data) == 3
        assert 'revenue' in sample_sales_data.columns
    
    def test_revenue_calculation(self, sample_sales_data):
        total = sample_sales_data['revenue'].sum()
        assert total == 335000
    
    def test_growth_rate_calculation(self, sample_sales_data):
        df = sample_sales_data.copy()
        df['growth_pct'] = df['revenue'].pct_change() * 100
        assert pd.notna(df['growth_pct'].iloc[1])
    
    def test_regional_aggregation(self):
        df = pd.DataFrame({
            'region': ['NA', 'EU', 'APAC', 'NA'],
            'revenue': [100, 200, 150, 90]
        })
        regional = df.groupby('region')['revenue'].sum()
        assert regional['NA'] == 190
    
    def test_kpi_calculation(self, sample_sales_data):
        avg_revenue = sample_sales_data['revenue'].mean()
        assert avg_revenue > 0
