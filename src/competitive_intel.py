"""Competitive intelligence and market positioning analysis for pharma."""

from typing import Dict, List, Optional


class CompetitiveIntelligence:
    """
    Analyze competitive landscape and market positioning.
    
    Supports:
    - Competitor product portfolio tracking
    - Market share analysis
    - Pricing intelligence
    - Product launch timeline monitoring
    """
    
    def __init__(self):
        """Initialize competitive intelligence system."""
        self.competitors = {}
        self.market_data = {}
    
    def add_competitor(
        self,
        competitor_name: str,
        therapeutic_areas: List[str],
        products: Dict[str, Dict],  # {product_name: {sales, market_share, launch_date}}
        market_position: str = "follower"  # leader, challenger, follower, niche
    ) -> Dict:
        """
        Register competitor and portfolio.
        
        Args:
            competitor_name: Competitor company name
            therapeutic_areas: List of therapy areas (Oncology, Cardio, etc.)
            products: Dictionary of products with sales and dates
            market_position: Competitive position
        
        Returns:
            Competitor profile record
        """
        if not competitor_name:
            raise ValueError("competitor_name required")
        
        total_sales = sum(p.get('sales_usd', 0) for p in products.values())
        
        profile = {
            "competitor_name": competitor_name,
            "therapeutic_areas": therapeutic_areas,
            "product_count": len(products),
            "total_sales_usd": total_sales,
            "market_position": market_position,
            "products": products,
            "market_share_pct": 0,  # Updated in analysis
        }
        
        self.competitors[competitor_name] = profile
        return profile
    
    def calculate_market_dynamics(
        self,
        therapeutic_area: str
    ) -> Dict:
        """
        Analyze competitive dynamics in a therapeutic area.
        
        Args:
            therapeutic_area: e.g., "Oncology", "Cardiology"
        
        Returns:
            Market analysis with HHI, concentration, and positioning
        """
        # Filter competitors in this TA
        ta_competitors = [
            c for c in self.competitors.values()
            if therapeutic_area in c.get('therapeutic_areas', [])
        ]
        
        if not ta_competitors:
            return {"error": f"No competitors in {therapeutic_area}"}
        
        # Calculate market shares
        total_market_sales = sum(c['total_sales_usd'] for c in ta_competitors)
        
        market_shares = {}
        hhi = 0  # Herfindahl-Hirschman Index
        
        for competitor in ta_competitors:
            share_pct = (competitor['total_sales_usd'] / total_market_sales * 100) if total_market_sales > 0 else 0
            market_shares[competitor['competitor_name']] = round(share_pct, 1)
            hhi += share_pct ** 2
        
        # Classify market concentration
        if hhi > 2500:
            concentration = "highly_concentrated"
        elif hhi > 1500:
            concentration = "moderately_concentrated"
        else:
            concentration = "competitive"
        
        return {
            "therapeutic_area": therapeutic_area,
            "competitor_count": len(ta_competitors),
            "total_market_sales_usd": round(total_market_sales, 2),
            "market_shares": market_shares,
            "hhi_index": round(hhi, 0),
            "concentration": concentration,
            "market_leaders": sorted(
                [(k, v) for k, v in market_shares.items()],
                key=lambda x: x[1],
                reverse=True
            )[:3],
        }
    
    def identify_competitive_gaps(
        self,
        our_products: List[str],
        our_therapeutic_areas: List[str]
    ) -> Dict:
        """
        Identify market opportunities and competitive gaps.
        
        Args:
            our_products: Our product portfolio
            our_therapeutic_areas: Therapeutic areas we serve
        
        Returns:
            Gaps and opportunities analysis
        """
        all_tas = set()
        for competitor in self.competitors.values():
            all_tas.update(competitor.get('therapeutic_areas', []))
        
        our_tas = set(our_therapeutic_areas)
        
        # Calculate gap analysis
        underserved_tas = all_tas - our_tas
        dominant_tas = our_tas - (all_tas - our_tas)
        
        # Competitor portfolio analysis
        competitors_per_ta = {}
        for ta in all_tas:
            count = sum(
                1 for c in self.competitors.values()
                if ta in c.get('therapeutic_areas', [])
            )
            competitors_per_ta[ta] = count
        
        return {
            "current_coverage": our_tas,
            "underserved_areas": underserved_tas,
            "our_strongholds": dominant_tas,
            "competitor_density": competitors_per_ta,
            "recommendations": self._generate_strategy_recommendations(
                our_tas, underserved_tas, competitors_per_ta
            ),
        }
    
    def _generate_strategy_recommendations(
        self,
        our_tas: set,
        underserved: set,
        density: Dict
    ) -> List[str]:
        """Generate strategic recommendations."""
        recommendations = []
        
        if underserved:
            lowest_density = min(density.get(ta, 10) for ta in underserved)
            if lowest_density < 3:
                recommendations.append(
                    f"Explore underserved areas with <3 competitors: {underserved}"
                )
        
        for ta in our_tas:
            if density.get(ta, 0) > 5:
                recommendations.append(
                    f"Differentiate in competitive area: {ta} (6+ competitors)"
                )
        
        if len(our_tas) < 3:
            recommendations.append("Consider portfolio expansion into adjacent areas")
        
        return recommendations
    
    def forecast_product_maturity(
        self,
        product_name: str,
        sales_history: List[float],
        years_on_market: int
    ) -> Dict:
        """
        Forecast product life cycle stage and revenue trajectory.
        
        Args:
            product_name: Product identifier
            sales_history: Historical sales (e.g., last 4 quarters)
            years_on_market: Years since launch
        
        Returns:
            Lifecycle stage assessment and forecast
        """
        if len(sales_history) < 2:
            raise ValueError("Need at least 2 historical data points")
        
        # Calculate growth rate
        growth_rates = [
            (sales_history[i+1] - sales_history[i]) / max(sales_history[i], 1)
            for i in range(len(sales_history) - 1)
        ]
        avg_growth = sum(growth_rates) / len(growth_rates)
        
        # Determine lifecycle stage
        if years_on_market < 1:
            stage = "launch"
        elif avg_growth > 0.15:
            stage = "growth"
        elif avg_growth > -0.05:
            stage = "maturity"
        else:
            stage = "decline"
        
        # Forecast next 4 quarters
        last_sales = sales_history[-1]
        forecast = [
            last_sales * ((1 + avg_growth) ** (i + 1))
            for i in range(4)
        ]
        
        return {
            "product_name": product_name,
            "lifecycle_stage": stage,
            "years_on_market": years_on_market,
            "average_growth_rate": round(avg_growth * 100, 1),
            "current_sales": sales_history[-1],
            "next_4_quarters_forecast": [round(x, 0) for x in forecast],
            "health_score": self._calculate_product_health(stage, avg_growth),
        }
    
    def _calculate_product_health(self, stage: str, growth: float) -> str:
        """Rate product health (healthy, caution, at_risk)."""
        if stage == "launch" and growth > 0.2:
            return "healthy"
        elif stage == "growth" and growth > 0.05:
            return "healthy"
        elif stage == "maturity" and growth > -0.05:
            return "healthy"
        elif stage == "decline" and growth > -0.20:
            return "caution"
        else:
            return "at_risk"
