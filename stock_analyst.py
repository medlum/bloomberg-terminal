#stock_analyst.py

from typing import Dict, Any, List

class StockAnalyzer:
    """
    Analyzes stock data provided by YFinanceConnector to provide 
    investment insights and scoring.
    """

    def __init__(self, stock_data: Dict[str, Any]):
        self.data = stock_data
        self.ticker = stock_data.get("ticker", "Unknown")
        
        # Handle cases where the connector returned an error
        if "error" in self.data:
            raise ValueError(f"Cannot analyze data for {self.ticker}: {self.data['error']}")

    # ---------------------------------------------------------
    # Analysis Methods
    # ---------------------------------------------------------

    def get_valuation_analysis(self) -> str:
        pe = self.data.get("trailing_pe")
        fwd_pe = self.data.get("forward_pe")
        peg = self.data.get("peg_ratio")
        growth = self.data.get("market_growth_estimate")

        insights = []

        # P/E Logic
        if pe and fwd_pe:
            if fwd_pe < pe:
                insights.append("Earnings are expected to grow (Forward P/E < Trailing P/E).")
            if pe > 40 and (growth is None or growth < 0.10):
                insights.append("Warning: Valuation appears stretched relative to growth.")

        # PEG Logic
        if peg:
            if peg < 1.0:
                insights.append(f"Undervalued relative to growth (PEG: {peg}).")
            elif peg > 2.0:
                insights.append(f"Expensive relative to growth (PEG: {peg}).")

        return " | ".join(insights) if insights else "Neutral valuation signals."

    def get_quality_rating(self) -> str:
        roe = self.data.get("roe")
        margin = self.data.get("profit_margin")
        fcf_ps = self.data.get("fcf_per_share")
        eps = self.data.get("eps_ttm")

        if roe is None: return "Insufficient data for quality analysis."

        if roe > 0.20:
            rating = "Excellent capital efficiency (ROE > 20%)"
        elif roe > 0.10:
            rating = "Good capital efficiency (ROE 10-20%)"
        else:
            rating = "Weak capital efficiency"

        if margin and margin > 0.25:
            rating += " with very strong profit margins."
        
        if fcf_ps and eps and fcf_ps < eps:
            rating += " Note: Cash flow is trailing accounting earnings."

        return rating

    def get_risk_profile(self) -> str:
        de = self.data.get("debt_to_equity")
        if de is None: return "Risk profile unknown (missing D/E data)."

        if de < 50:
            return "Healthy balance sheet (Low Leverage)."
        elif de <= 150:
            return "Moderate leverage."
        else:
            return "High financial risk (Highly Leveraged)."

    def get_growth_category(self) -> str:
        rev_growth = self.data.get("revenue_growth")
        if rev_growth is None: return "Data N/A"

        if rev_growth > 0.30: return "Hypergrowth"
        if rev_growth > 0.15: return "Strong Growth"
        if rev_growth > 0.05: return "Moderate Growth"
        return "Mature / Slow Growth"

    # ---------------------------------------------------------
    # Scoring System
    # ---------------------------------------------------------

    def calculate_composite_score(self) -> Dict[str, Any]:
        """
        Calculates an investment score out of 10.
        """
        score = 0
        breakdown = {}

        # 1. Growth (2 pts)
        rev_growth = self.data.get("revenue_growth") or 0
        if rev_growth > 0.20: 
            score += 2
            breakdown["growth"] = 2
        
        # 2. Profitability (2 pts)
        roe = self.data.get("roe") or 0
        if roe > 0.20: 
            score += 2
            breakdown["profitability"] = 2

        # 3. Valuation (2 pts)
        peg = self.data.get("peg_ratio")
        if peg and peg < 1.5: 
            score += 2
            breakdown["valuation"] = 2

        # 4. Debt (2 pts)
        de = self.data.get("debt_to_equity")
        if de is not None and de < 80: 
            score += 2
            breakdown["solvency"] = 2

        # 5. Cash Flow (2 pts)
        fcf_yield = 0
        if self.data.get("fcf_per_share") and self.data.get("current_price"):
            fcf_yield = self.data["fcf_per_share"] / self.data["current_price"]
        
        if fcf_yield > 0.05:
            score += 2
            breakdown["cash_flow"] = 2

        return {
            "total_score": score,
            "max_score": 10,
            "breakdown": breakdown,
            "recommendation": "Strong Watchlist" if score >= 8 else "Neutral/Research"
        }

    def generate_report(self):
        """Prints a formatted summary report."""
        score_data = self.calculate_composite_score()
        
        print(f"--- Investment Analysis: {self.ticker} ---")
        print(f"Name:         {self.data.get('long_name')}")
        print(f"Industry:     {self.data.get('industry')}")
        print(f"Score:        {score_data['total_score']}/{score_data['max_score']}")
        print(f"Verdict:      {score_data['recommendation']}")
        print("-" * 30)
        print(f"Valuation:    {self.get_valuation_analysis()}")
        print(f"Quality:      {self.get_quality_rating()}")
        print(f"Risk:         {self.get_risk_profile()}")
        print(f"Growth Stage: {self.get_growth_category()}")
        print("-" * 30)

