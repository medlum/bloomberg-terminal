#yf_connector.py

from typing import Dict, Any, Optional
import pandas as pd
from yahooquery import Ticker
import re


class YFinanceConnector:
    """
    Connector for retrieving stock fundamentals, history, and technical indicators using yahooquery.
    """

    def __init__(self, ticker_symbol: str):
        self.ticker_symbol = ticker_symbol.upper()
        self.ticker = Ticker(self.ticker_symbol)

        # Cached raw data
        self.price_data = {}
        self.summary_data = {}
        self.financial_data = {}

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def get_stats(self, include_history: bool = False, period: str = "1y") -> Dict[str, Any]:
        """
        Returns cleaned and computed stock statistics.
        Optional: include_history=True to attach historical data for a specific period.
        """
        try:
            self._fetch_raw_data()

            current_price = self._safe_get(self.price_data, "regularMarketPrice")
            market_cap = self._safe_get(self.price_data, "marketCap")
            trailing_pe = self._safe_get(self.summary_data, "trailingPE")
            forward_pe = self._safe_get(self.summary_data, "forwardPE")
            price_to_book = self._safe_get(self.default_key_statistics(), "priceToBook")
            eps_ttm = self._safe_get(self.default_key_statistics(), "trailingEps")
            revenue_growth = self._safe_get(self.financial_data, "revenueGrowth")
            earnings_growth = self._safe_get(self.financial_data, "earningsGrowth")
            peg_ratio = self._compute_peg_ratio(trailing_pe, earnings_growth)
            roe = self._safe_get(self.financial_data, "returnOnEquity")
            debt_to_equity = self._safe_get(self.financial_data, "debtToEquity")
            profit_margin = self._safe_get(self.financial_data, "profitMargins")
            total_revenue = self._safe_get(self.financial_data, "totalRevenue")
            free_cashflow = self._safe_get(self.financial_data, "freeCashflow")
            shares_outstanding = self._safe_get(self.default_key_statistics(), "sharesOutstanding")

            fcf_per_share = self._compute_fcf_per_share(free_cashflow, shares_outstanding)
            bvps_derived = self._compute_bvps(current_price, price_to_book)

            stats = {
                "ticker": self.ticker_symbol,
                # Company Info
                "short_name": self._safe_get(self.price_data, "shortName"),
                "long_name": self._safe_get(self.price_data, "longName"),
                "sector": self._safe_get(self.summary_profile(), "sector"),
                "industry": self._safe_get(self.summary_profile(), "industry"),
                # Market Data
                "current_price": current_price,
                "market_cap": market_cap,
                "52w_high": self._safe_get(self.summary_data, "fiftyTwoWeekHigh"),
                "52w_low": self._safe_get(self.summary_data, "fiftyTwoWeekLow"),
                "dividend_yield": self._safe_get(self.summary_data, "dividendYield"),
                # Valuation
                "trailing_pe": trailing_pe,
                "forward_pe": forward_pe,
                "peg_ratio": peg_ratio,
                "price_to_book": price_to_book,
                "bvps_derived": bvps_derived,
                # Financial Quality
                "eps_ttm": eps_ttm,
                "roe": roe,
                "profit_margin": profit_margin,
                "debt_to_equity": debt_to_equity,
                # Growth
                "revenue_growth": revenue_growth,
                "market_growth_estimate": earnings_growth,
                # Revenue / Cash Flow
                "total_revenue": total_revenue,
                "fcf_per_share": fcf_per_share,
                "shares_outstanding": shares_outstanding,
            }

            if include_history:
                # REFACTORED: Pass the custom period variable down instead of using a hardcoded "1y" string
                stats["history"] = self.get_history(period=period, interval="1d")

            return stats

        except Exception as e:
            return {"ticker": self.ticker_symbol, "error": str(e)}

    def get_history(self, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        """
        Retrieves historical price data and returns it as a cleaned DataFrame.
        """
        df = self.ticker.history(period=period, interval=interval)
        
        if isinstance(df, pd.DataFrame) and not df.empty:
            df = df.reset_index()
            
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')
            
            if 'symbol' in df.columns:
                df = df.drop(columns=['symbol'])
                
            return df
            
        return pd.DataFrame()

    def get_technical_summary(self, period: str = "6mo") -> Dict[str, Any]:
        """
        Consolidated method for calculating technical trading signals and price indicators.
        Returns a structured dictionary of data and trends.
        """
        try:
            df = self.get_history(period=period, interval="1d")

            if df.empty or len(df) < 20:
                return {"ticker": self.ticker_symbol, "error": "Not enough data or invalid symbol for analysis."}

            # 1. Trend (50-day SMA)
            sma_window = min(len(df), 50)
            df['SMA_50'] = df['close'].rolling(window=sma_window).mean()
            current_price = float(df['close'].iloc[-1])
            sma_50 = float(df['SMA_50'].iloc[-1]) if not pd.isna(df['SMA_50'].iloc[-1]) else None
            trend = "Unknown" if sma_50 is None else ("Bullish" if current_price > sma_50 else "Bearish")

            # 2. RSI (14-day)
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            
            current_rsi = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else None
            rsi_signal = "Neutral"
            if current_rsi is not None:
                if current_rsi > 70:
                    rsi_signal = "Overbought"
                elif current_rsi < 30:
                    rsi_signal = "Oversold"

            # 3. MACD
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal_line = macd.ewm(span=9, adjust=False).mean()
            macd_signal = "Bullish Cross" if macd.iloc[-1] > signal_line.iloc[-1] else "Bearish Cross"

            # 4. Recent History Subset
            history_subset = df.tail(5)[['open', 'high', 'low', 'close', 'volume']]

            return {
                "ticker": self.ticker_symbol,
                "current_price": round(current_price, 2),
                "trend_50_sma": trend,
                "rsi_14": round(current_rsi, 2) if current_rsi else None,
                "rsi_signal": rsi_signal,
                "macd_signal": macd_signal,
                "last_5_days": history_subset
            }

        except Exception as e:
            return {"ticker": self.ticker_symbol, "error": f"Error in technical analysis: {str(e)}"}


    def get_financial_statement(self, statement_type):
        try:
            stock = self.ticker
            statement_method = getattr(stock, statement_type, None)

            if statement_method is None:
                return None

            # -----------------------------
            # IMPORTANT INVESTOR METRICS
            # -----------------------------
            IMPORTANT_METRICS = {
                "balance_sheet": [
                    "CashAndCashEquivalents",
                    "CurrentAssets",
                    "CurrentLiabilities",
                    "Inventory",
                    "WorkingCapital",
                    "TotalAssets",
                    "TotalDebt",
                    "CurrentDebt",
                    "LongTermDebt",
                    "NetDebt",
                    "StockholdersEquity",
                    "TotalEquityGrossMinorityInterest",
                    "RetainedEarnings",
                    "CommonStockEquity",
                    "NetTangibleAssets",
                    "TangibleBookValue",
                    "InvestedCapital",
                    "TotalCapitalization",
                    "AccountsReceivable",
                    "AccountsPayable",
                    "Goodwill",
                    "GoodwillAndOtherIntangibleAssets",
                ],

                "cash_flow": [
                    "OperatingCashFlow",
                    "FreeCashFlow",
                    "CapitalExpenditure",
                    "InvestingCashFlow",
                    "FinancingCashFlow",
                    "CashDividendsPaid",
                    "RepurchaseOfCapitalStock",
                    "NetIncome",
                    "DepreciationAndAmortization",
                    "ChangeInWorkingCapital",
                    "IssuanceOfDebt",
                    "RepaymentOfDebt",
                    "PurchaseOfPPE",
                    "StockBasedCompensation",
                    "BeginningCashPosition",
                    "EndCashPosition",
                ],

                "income_statement": [
                    "TotalRevenue",
                    "OperatingRevenue",
                    "CostOfRevenue",
                    "GrossProfit",
                    "OperatingIncome",
                    "EBIT",
                    "EBITDA",
                    "NormalizedEBITDA",
                    "NetIncome",
                    "NetIncomeCommonStockholders",
                    "PretaxIncome",
                    "OperatingExpense",
                    "TotalExpenses",
                    "ResearchAndDevelopment",
                    "SellingGeneralAndAdministration",
                    "InterestExpense",
                    "TaxProvision",
                    "BasicEPS",
                    "DilutedEPS",
                    "BasicAverageShares",
                    "DilutedAverageShares",
                ],
            }

            # Fetch raw statement data
            if callable(statement_method):
                df = statement_method(frequency="a")
            else:
                df = statement_method

            # Handle yahooquery dict return
            if isinstance(df, dict):
                df = df.get(self.ticker_symbol)

                if df is None or not isinstance(df, pd.DataFrame):
                    return None

            # Handle Series return
            if isinstance(df, pd.Series):
                df = df.to_frame().T

            if not isinstance(df, pd.DataFrame) or df.empty:
                return None

            # Filter yearly statements only
            if "periodType" in df.columns:
                df = df[df["periodType"] == "12M"].copy()

                if df.empty:
                    return None

            # Flatten MultiIndex columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # -----------------------------
            # KEEP ONLY IMPORTANT METRICS
            # -----------------------------
            selected_metrics = IMPORTANT_METRICS.get(statement_type, [])

            essential_cols = [
                col
                for col in ["symbol", "asOfDate", "date", "endDate", "periodType"]
                if col in df.columns
            ]

            available_metrics = [
                metric for metric in selected_metrics if metric in df.columns
            ]

            df = df[essential_cols + available_metrics].copy()

            # -----------------------------
            # CLEANUP / TRANSFORM
            # -----------------------------
            df = df.reset_index(drop=True)

            if "symbol" in df.columns:
                df.drop(columns=["symbol"], inplace=True)

            # Detect date column
            date_col = None
            for col_name in ["asOfDate", "date", "endDate"]:
                if col_name in df.columns:
                    date_col = col_name
                    break

            if date_col:
                df.set_index(date_col, inplace=True)

            # Transpose
            df = df.T
            df.reset_index(inplace=True)

            # Rename first column
            first_col = df.columns[0]
            df.rename(columns={first_col: "Metrics"}, inplace=True)

            # Remove metadata rows
            unwanted_metrics = ["periodType", "currencyCode"]
            df = df[~df["Metrics"].isin(unwanted_metrics)].copy()

            # -----------------------------
            # CLEAN METRIC NAMES
            # -----------------------------
            def clean_metric_name(name):
                if not isinstance(name, str):
                    return name

                s1 = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
                s2 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s1)

                return s2.strip()

            df["Metrics"] = df["Metrics"].apply(clean_metric_name)

            # Format column names
            df.columns = [
                col.strftime("%Y-%m-%d") if hasattr(col, "date") else str(col)
                for col in df.columns
            ]
            
            # -----------------------------
            # FORMAT NUMBERS
            # -----------------------------
            date_cols = [col for col in df.columns if col != "Metrics"]

            for col in date_cols:
                numeric_col = pd.to_numeric(df[col], errors="coerce")

                formatted_values = []

                for metric, val in zip(df["Metrics"], numeric_col):

                    if pd.isna(val):
                        formatted_values.append("-")

                    elif (
                        "EPS" in metric
                        or "Rate" in metric
                        or "Margin" in metric
                        or "Per Share" in metric
                    ):
                        formatted_values.append(f"{val:,.2f}")

                    else:
                        formatted_values.append(f"{val:,.0f}")

                df[col] = formatted_values

            df.fillna("-", inplace=True)

            # sort year in descending for display
            year_cols = sorted([c for c in df.columns if c != "Metrics"], reverse=True)
            df = df[["Metrics"] + year_cols]

            return df

        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f"DEBUGGING ERROR IN CONNECTOR: {str(e)}")
            return None

    # ---------------------------------------------------------
    # Raw Data Fetching & Helpers
    # ---------------------------------------------------------

    def _fetch_raw_data(self):
        self.price_data = self.ticker.price.get(self.ticker_symbol, {})
        self.summary_data = self.ticker.summary_detail.get(self.ticker_symbol, {})
        self.financial_data = self.ticker.financial_data.get(self.ticker_symbol, {})
     

    def summary_profile(self) -> Dict[str, Any]:
        return self.ticker.summary_profile.get(self.ticker_symbol, {})

    def default_key_statistics(self) -> Dict[str, Any]:
        return self.ticker.key_stats.get(self.ticker_symbol, {})

    @staticmethod
    def _safe_get(data: Dict, key: str) -> Optional[Any]:
        if not isinstance(data, dict):
            return None
        value = data.get(key)
        return None if value in ["", "N/A"] else value

    @staticmethod
    def _compute_bvps(current_price: Optional[float], price_to_book: Optional[float]) -> Optional[float]:
        if current_price and price_to_book and price_to_book > 0:
            return round(current_price / price_to_book, 2)
        return None

    @staticmethod
    def _compute_fcf_per_share(free_cashflow: Optional[float], shares_outstanding: Optional[float]) -> Optional[float]:
        if free_cashflow is not None and shares_outstanding and shares_outstanding > 0:
            return round(free_cashflow / shares_outstanding, 2)
        return None

    @staticmethod
    def _compute_peg_ratio(pe: Optional[float], growth: Optional[float]) -> Optional[float]:
        if pe is not None and growth and growth > 0:
            return round(pe / (growth * 100), 2)
        return None


# ---------------------------------------------------------
# Optional: Standalone Helper for Legacy String Formatting
# ---------------------------------------------------------

def format_technical_summary_report(tech_data: Dict[str, Any]) -> str:
    """
    Optional helper function to replicate the exact string print-out style 
    of the original code using data from YFinanceConnector.get_technical_summary.
    """
    if "error" in tech_data:
        return f"Error: {tech_data['error']}"

    output = [
        f"TECHNICAL SUMMARY FOR {tech_data['ticker']}",
        f"Current Price: ${tech_data['current_price']:.2f}",
        f"Trend (50-day SMA): {tech_data['trend_50_sma']}",
        f"RSI (14-day): {tech_data['rsi_14']:.2f} ({tech_data['rsi_signal']})" if tech_data['rsi_14'] else "RSI (14-day): N/A",
        f"MACD Signal: {tech_data['macd_signal']}",
        "\nLAST 5 DAYS PRICE ACTION:",
        tech_data['last_5_days'].to_string()
    ]
    return "\n".join(output)



connector = YFinanceConnector("NVDA")
income_df = connector.get_financial_statement("income_statement")
cashflow_df =  connector.get_financial_statement("cash_flow")
balance_df =  connector.get_financial_statement("balance_sheet")
#print(income_df.to_dict())
#print(cashflow_df.to_dict())
#print(balance_df.to_dict())





#print(connector.get_technical_summary())
#print(data.get('short_name'))
#
#for key, value in data.items():
#    print(f"{key.upper()}: {value}")
#
#history = connector.get_history()
#print(history.columns)