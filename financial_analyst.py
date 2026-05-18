

import pandas as pd
import numpy as np


# --- FINANCIAL ANALYZER CLASS ---
class FinancialStatementAnalyzer:
    """Encapsulates cleaning, growth calculation, and automated summary generation."""
    
    DEFAULT_INCOME_METRICS = [
        "Total Revenue", "Gross Profit", "Operating Income", 
        "Net Income", "Basic EPS", "Research And Development"
    ]
    DEFAULT_BALANCE_METRICS = [
        "Total Assets", "Stockholders Equity", "Current Assets", "Total Debt"
    ]
    DEFAULT_CASHFLOW_METRICS = [
        "Operating Cash Flow", "Free Cash Flow", "Capital Expenditure", "End Cash Position"
    ]

    def __init__(self, ticker: str, connector):
        self.ticker = ticker
        self.connector = connector
        self.cleaned_data = {}

    @staticmethod
    def clean_statement(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if "Metrics" not in df.columns:
            raise ValueError("DataFrame must contain a 'Metrics' column.")
        year_cols = sorted([c for c in df.columns if c != "Metrics"])
        df = df[["Metrics"] + year_cols]
        for col in year_cols:
            df[col] = (df[col].astype(str).str.replace(",", "", regex=False).replace("-", np.nan))
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    @staticmethod
    def _safe_extract(df: pd.DataFrame, metric_name: str) -> pd.Series:
        row = df[df["Metrics"] == metric_name]
        if row.empty:
            return pd.Series(dtype=float)
        return row.iloc[0, 1:]

    @staticmethod
    def _safe_growth(series: pd.Series):
        if series.empty or series.isna().all():
            return None
        growth = series.pct_change().iloc[-1] * 100
        return growth if not pd.isna(growth) else None

    def calculate_growth(self, df: pd.DataFrame, metrics: list) -> pd.DataFrame:
        insights = []
        for metric in metrics:
            series = self._safe_extract(df, metric)
            growth = self._safe_growth(series)
            insights.append({
                "Metric": metric,
                "Latest Value": series.iloc[-1] if not series.empty else np.nan,
                "YoY Growth %": round(growth, 2) if growth is not None else "N/A"
            })
        return pd.DataFrame(insights)

    def generate_income_summary(self, df: pd.DataFrame) -> list:
        summaries = []
        rev, ni, gp, oi, eps, rnd = (self._safe_extract(df, m) for m in [
            "Total Revenue", "Net Income", "Gross Profit", "Operating Income", "Basic EPS", "Research And Development"
        ])
        rev_g, ni_g, eps_g, rnd_g = (self._safe_growth(s) for s in [rev, ni, eps, rnd])

        if rev_g is not None:
            summaries.append(f"Revenue growth is {'extremely strong' if rev_g > 30 else 'healthy' if rev_g > 10 else '⚠️ slowing'} at {rev_g:.1f}% YoY.")
        if ni_g is not None and rev_g is not None:
            summaries.append("Earnings are growing faster than revenue, indicating expanding profitability." if ni_g > rev_g else "⚠️ Earnings growth is lagging revenue growth.")
        if not gp.empty and not rev.empty and pd.notna(gp.iloc[-1]) and pd.notna(rev.iloc[-1]) and rev.iloc[-1] != 0:
            summaries.append(f"Latest gross margin is {(gp.iloc[-1] / rev.iloc[-1]) * 100:.1f}%.")
        if not oi.empty and not rev.empty and pd.notna(oi.iloc[-1]) and pd.notna(rev.iloc[-1]) and rev.iloc[-1] != 0:
            op_m = (oi.iloc[-1] / rev.iloc[-1]) * 100
            summaries.append(f"Operating margin is {'exceptionally high' if op_m > 25 else 'stable'} at {op_m:.1f}%.")
        if eps_g is not None: summaries.append(f"EPS grew by {eps_g:.1f}% YoY.")
        if rnd_g is not None: summaries.append(f"R&D investment {'increased' if rnd_g > 0 else 'decreased'} by {rnd_g:.1f}% YoY.")
        return summaries

    def generate_balance_summary(self, df: pd.DataFrame) -> list:
        summaries = []
        ca, cl, td, eq, ta = (self._safe_extract(df, m) for m in ["Current Assets", "Current Liabilities", "Total Debt", "Stockholders Equity", "Total Assets"])
        ta_g, eq_g = (self._safe_growth(s) for s in [ta, eq])

        if not ca.empty and not cl.empty and pd.notna(cl.iloc[-1]) and cl.iloc[-1] != 0:
            curr = ca.iloc[-1] / cl.iloc[-1]
            summaries.append(f"{'Strong' if curr > 2.0 else 'Adequate' if curr > 1.0 else '⚠️ Concerning'} liquidity with a current ratio of {curr:.2f}x.")
        if not td.empty and not eq.empty and pd.notna(eq.iloc[-1]) and eq.iloc[-1] != 0:
            de = td.iloc[-1] / eq.iloc[-1]
            summaries.append(f"{'Conservative' if de < 0.5 else 'Moderate' if de < 1.0 else '⚠️ High'} leverage with a Debt-to-Equity ratio of {de:.2f}x.")
        if ta_g is not None: summaries.append(f"Total assets grew by {ta_g:.1f}% YoY.")
        if eq_g is not None: summaries.append(f"Shareholders' equity grew by {eq_g:.1f}% YoY.")
        return summaries

    def generate_cashflow_summary(self, df: pd.DataFrame) -> list:
        summaries = []
        ocf, fcf, capex, ni, cash = (self._safe_extract(df, m) for m in ["Operating Cash Flow", "Free Cash Flow", "Capital Expenditure", "Net Income", "End Cash Position"])
        ocf_g, fcf_g, cash_g = (self._safe_growth(s) for s in [ocf, fcf, cash])

        if ocf_g is not None: summaries.append(f"Operating cash flow growth is {'robust' if ocf_g > 20 else 'steady'} at {ocf_g:.1f}% YoY.")
        if fcf_g is not None: summaries.append(f"Free cash flow growth is {'robust' if fcf_g > 20 else 'steady'} at {fcf_g:.1f}% YoY.")
        if not fcf.empty and not ni.empty and pd.notna(ni.iloc[-1]) and ni.iloc[-1] != 0:
            summaries.append(f"FCF conversion rate stands at {(fcf.iloc[-1] / ni.iloc[-1]) * 100:.1f}% of net income.")
        if not capex.empty and pd.notna(capex.iloc[-1]):
            summaries.append(f"Capital expenditures were {abs(capex.iloc[-1]):,.0f}.")
        if cash_g is not None: summaries.append(f"Ending cash position changed by {cash_g:.1f}% YoY.")
        return summaries
