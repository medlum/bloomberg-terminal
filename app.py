# app.py

import os
import dash
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from plotly.subplots import make_subplots
from dash import dcc, html, Input, Output, State, no_update
from together import Together
from yahooquery import Ticker  # Added for Macro Indicators
import dash_ag_grid as dag

# Importing the connector containing your refactored method
from yf_connector import YFinanceConnector 
from financial_analyst import FinancialStatementAnalyzer
from macro_connector import fetch_macro_data
from configs import Config
import re

# --- BLOOMBERG STYLE CONSTANTS ---
BB_BG = "#111111"         # Main dark terminal background
BB_CONTAINER = "#1A1A1A"  # Dark gray card backgrounds
BB_TEXT = "#FFFFFF"       # White labels
BB_AMBER = "#FFB900"      # Bloomberg Amber Accent/Values
BB_MUTED = "#888888"      # Light gray for minor descriptions
BB_GREEN = "#00FF00"      # Dynamic positive signals
BB_RED = "#FF3333"        # Dynamic negative signals



# --- APP SETUP ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY, dbc.icons.BOOTSTRAP])
# 2. EXPOSE THE SERVER (Crucial for Render/Gunicorn)
server = app.server

# --- MACRO INDICATORS CONFIG & FUNCTIONS ---
MACRO_TICKERS = {
    "US Dollar Index": "DX-Y.NYB",
    "10Y Treasury Yield": "^TNX",
    "Gold": "GC=F",
    "Crude Oil": "CL=F"
}

def create_macro_figure(df):
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=list(MACRO_TICKERS.keys()),
        vertical_spacing=0.12,
        horizontal_spacing=0.08
    )
    positions = {
        "US Dollar Index": (1, 1),
        "10Y Treasury Yield": (1, 2),
        "Gold": (2, 1),
        "Crude Oil": (2, 2)
    }
    for asset_name in MACRO_TICKERS.keys():
        asset_df = df[df["asset"] == asset_name]
        row, col = positions[asset_name]
        fig.add_trace(
            go.Scatter(x=asset_df["date"], y=asset_df["close"], mode="lines", name=asset_name),
            row=row, col=col
        )
    fig.update_layout(
        height=800,
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        #title="Macro Indicators Dashboard",
        title_font_color=BB_AMBER,
        showlegend=False,
        margin=dict(l=40, r=40, t=50, b=10)
    )
    fig.update_yaxes(title_text="Price", gridcolor="#222222")
    fig.update_xaxes(gridcolor="#222222")
    return fig

# --- UI HELPERS ---
def create_metric_card(title, id_name):
    return dbc.Card(
        dbc.CardBody([
            html.H6(title, style={"color": BB_MUTED, "fontSize": "0.75rem", "textTransform": "uppercase"}),
            html.H4("---", id=id_name, style={"color": BB_AMBER, "fontWeight": "bold", "fontFamily": "Courier New", "marginBottom": "0"})
        ]),
        style={"backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}", "borderRadius": "0px"}
    )

def create_grouped_card(title, metric_list):
    rows = [
        html.Div([
            html.Span(m["label"], style={"color": BB_TEXT, "fontSize": "0.85rem"}),
            html.Span("---", id=m["id"], style={"color": BB_AMBER, "fontWeight": "bold", "fontFamily": "Courier New"})
        ], className="d-flex justify-content-between border-bottom py-2", style={"borderColor": f"{BB_MUTED} !important"})
        for m in metric_list
    ]
    return dbc.Card([
        dbc.CardHeader(title, style={"fontWeight": "bold", "color": BB_AMBER, "backgroundColor": "#222222", "borderRadius": "0px"}),
        dbc.CardBody(rows)
    ], style={"backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}", "borderRadius": "0px", "height": "100%"})

def create_news_card(item):
    return dbc.Card([
        dbc.CardBody([
            html.H6(item['title'], style={"color": BB_AMBER, "fontWeight": "bold", "marginBottom": "4px"}),
            html.Small(f"{item.get('date', 'Recent')}", style={"color": BB_MUTED, "display": "block", "marginBottom": "8px"}),
            html.P(item['summary'], style={"color": BB_TEXT, "fontSize": "0.85rem", "lineHeight": "1.8", "letterSpacing": "0.03rem","wordSpacing": "0.08rem","marginBottom": "12px"}),
            dbc.Button("» READ SOURCE", href=item['url'], target="_blank", size="sm", color="link", style={"color": BB_MUTED, "padding": "0", "fontSize": "0.75rem"})
        ])
    ], style={"backgroundColor": BB_CONTAINER, "borderLeft": f"4px solid {BB_AMBER}", "borderTop": "0", "borderRight": "0", "borderBottom": "0", "marginBottom": "15px", "borderRadius": "0px", "height":"100%"})


# --- LAYOUT ---
app.layout = dbc.Container([
    dcc.Store(id="stock-store"),

    # Header Panel
    dbc.Row([
        dbc.Col(html.H2("⚡ BLOOMBERG EQUITY INTELLIGENCE TERMINAL", 
                        style={"color": BB_AMBER, "fontFamily": "Courier New", "letterSpacing": "1px"}, 
                        className="text-center my-4"))
    ]),

    dbc.Row([
        # ---------------- SIDEBAR CONTROLS ----------------
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("TERMINAL COMMANDS", style={"fontWeight": "bold", "color": BB_AMBER, "backgroundColor": "#222222"}),
                dbc.CardBody([
                    dbc.Label("TICKER SYMBOL", style={"color": BB_TEXT, "fontSize": "0.8rem"}),
                    dbc.Input(id="ticker-input", value="", type="text", placeholder = "Enter a NYSE ticker", style={"backgroundColor": "#000000", "color": BB_GREEN, "fontFamily": "Courier New", "border": f"1px solid {BB_MUTED}"}, className="mb-3"),
                    dbc.Button("RUN ANALYSIS <GO>", id="submit-btn", color="warning", style={"fontWeight": "bold", "borderRadius": "0px"}, className="w-100"),
                    html.Hr(style={"borderColor": BB_MUTED}),
                    html.Div(id="score-container", className="text-center"),
                ])
            ], style={"backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}", "borderRadius": "0px"}),
            
            # Investment Analysis Summary Panel
            dbc.Card([
                dbc.CardHeader("INVESTMENT PROFILES", style={"fontWeight": "bold", "color": BB_AMBER, "backgroundColor": "#222222"}),
                dbc.ListGroup([
                    dbc.ListGroupItem([html.Div("VALUATION", style={"fontWeight": "bold", "fontSize": "0.75rem", "color": BB_MUTED}), html.P("---", id="analysis-valuation", style={"color": BB_TEXT, "margin": "0"})], style={"backgroundColor": BB_CONTAINER}),
                    dbc.ListGroupItem([html.Div("QUALITY", style={"fontWeight": "bold", "fontSize": "0.75rem", "color": BB_MUTED}), html.P("---", id="analysis-quality", style={"color": BB_TEXT, "margin": "0"})], style={"backgroundColor": BB_CONTAINER}),
                    dbc.ListGroupItem([html.Div("RISK", style={"fontWeight": "bold", "fontSize": "0.75rem", "color": BB_MUTED}), html.P("---", id="analysis-risk", style={"color": BB_TEXT, "margin": "0"})], style={"backgroundColor": BB_CONTAINER}),
                    dbc.ListGroupItem([html.Div("GROWTH", style={"fontWeight": "bold", "fontSize": "0.75rem", "color": BB_MUTED}), html.P("---", id="analysis-growth", style={"color": BB_TEXT, "margin": "0"})], style={"backgroundColor": BB_CONTAINER})
                ], flush=True, style={"fontSize": "0.85rem"})
            ], style={"backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}", "borderRadius": "0px"} , className="mt-3"),
            
            dbc.Card([
                dbc.CardHeader("SECURITY CLASSIFICATION", style={"fontWeight": "bold", "color": BB_AMBER, "backgroundColor": "#222222"}),
                dbc.ListGroup([
                    dbc.ListGroupItem([
                        html.Div("SECTOR", style={"fontWeight": "bold", "fontSize": "0.75rem", "color": BB_MUTED}), 
                        html.P("---", id="card-sector", style={"color": BB_TEXT, "margin": "0", "fontSize": "0.85rem"})
                    ], style={"backgroundColor": BB_CONTAINER}),
                    dbc.ListGroupItem([
                        html.Div("INDUSTRY", style={"fontWeight": "bold", "fontSize": "0.75rem", "color": BB_MUTED}), 
                        html.P("---", id="card-industry", style={"color": BB_TEXT, "margin": "0", "fontSize": "0.85rem"})
                    ], style={"backgroundColor": BB_CONTAINER})
                ], flush=True)
            ], style={"backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}", "borderRadius": "0px"}, className="mt-3"),
        ], width=3),

        # ---------------- MAIN FIVE-TAB DESK ----------------
        dbc.Col([
            dbc.Tabs([
                
                # TAB 1: CORE MARKET METRICS & CHARTS
                dbc.Tab(label="1 <GO> CORE METRICS", tab_style={"marginLeft": "auto"}, children=[
                    html.Div([
                        dbc.Row([
                            dbc.Col(create_metric_card("COMPANY", "card-name"), width=4),
                            dbc.Col(create_metric_card("PRICE", "card-price"), width=4),
                            dbc.Col(create_metric_card("MARKET CAP", "card-mktcap"), width=4),
                        ], className="mb-4 mt-3"),

                        dbc.Row([
                            dbc.Col(create_grouped_card("VALUATION MATRIX", [
                                {"label": "Trailing P/E", "id": "val-pe"},
                                {"label": "Forward P/E", "id": "val-fwd-pe"},
                                {"label": "PEG Ratio", "id": "val-peg"},
                                {"label": "Price/Book", "id": "val-pb"},
                            ]), width=4),
                            dbc.Col(create_grouped_card("QUALITY & GROWTH", [
                                {"label": "ROE", "id": "fin-roe"},
                                {"label": "Profit Margin", "id": "fin-margin"},
                                {"label": "Rev Growth", "id": "fin-rev-growth"},
                                {"label": "D/E Ratio", "id": "fin-de"},
                            ]), width=4),
                            dbc.Col(create_grouped_card("CASH FLOW & MARKET", [
                                {"label": "FCF / Share", "id": "cf-fcf"},
                                {"label": "Div Yield", "id": "mkt-div"},
                                {"label": "52W High", "id": "mkt-high"},
                                {"label": "52W Low", "id": "mkt-low"},
                            ]), width=4),
                        ], className="mb-4"),

                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader([
                                        html.Div([
                                            html.Span("HISTORICAL MARKET CANDLESTICKS", style={"fontWeight": "bold", "color": BB_AMBER}),
                                            dcc.Dropdown(
                                                id="period-dropdown",
                                                options=[
                                                    {"label": "1 Month", "value": "1mo"},
                                                    {"label": "3 Months", "value": "3mo"},
                                                    {"label": "6 Months", "value": "6mo"},
                                                    {"label": "1 Year", "value": "1y"},
                                                    {"label": "5 Years", "value": "5y"},
                                                ],
                                                value="6mo",
                                                clearable=False,
                                                style={
                                                    "width": "150px", 
                                                    "backgroundColor": "#000000", 
                                                    "color": BB_AMBER, 
                                                    "border": f"1px solid {BB_MUTED}",
                                                    "fontFamily": "Courier New"
                                                }
                                            )
                                        ], className="d-flex justify-content-between align-items-center")
                                    ], style={"backgroundColor": "#222222"}),
                                    dbc.CardBody(dcc.Graph(id="price-chart", style={"height": "400px"}))
                                ], style={"backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}", "borderRadius": "0px"})
                            ], width=12),
                        ])
                    ])
                ], active_label_style={"color": BB_AMBER, "backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}"}, label_style={"color": BB_TEXT}),

                # TAB 2: LIVE COMPANY NEWS FEEDS
                dbc.Tab(label="2 <GO> WIRE NEWS", children=[
                    html.Div([
                        dbc.Card([
                            dbc.CardHeader([
                                html.Div([
                                    html.Span("REALTIME NEWS FEED BROADCAST", style={"fontWeight": "bold", "color": BB_AMBER}),
                                    dbc.Switch(id="news-toggle", label="ENABLE FEED", value=False, className="mb-0", style={"color": BB_TEXT})
                                ], className="d-flex justify-content-between align-items-center")
                            ], style={"backgroundColor": "#222222"}),
                            dbc.CardBody([
                                dcc.Loading(id="loading-news", type="dot", children=html.Div(id="news-feed", style={"maxHeight": "600px", "overflowY": "auto"}))
                            ])
                        ], style={"backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}", "borderRadius": "0px", "marginTop": "20px"})
                    ])
                ], active_label_style={"color": BB_AMBER, "backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}"}, label_style={"color": BB_TEXT}),
                
                # TAB 3: TECHNICAL DESK ANALYSIS
                dbc.Tab(label="3 <GO> TECHNICALS", children=[
                    html.Div([
                        dbc.Card([
                            dbc.CardHeader("QUANTITATIVE TECHNICAL MATRIX INDICATORS", style={"fontWeight": "bold", "color": BB_AMBER, "backgroundColor": "#222222"}),
                            dbc.CardBody([
                                dbc.Row([
                                    dbc.Col([
                                        html.Div("TRENDING MATRIX (50-DAY SMA)", style={"fontWeight": "bold", "fontSize": "0.85rem", "color": BB_MUTED}),
                                        html.H3("---", id="tech-trend", style={"color": BB_TEXT, "fontFamily": "Courier New", "padding": "10px 0"})
                                    ], width=4, className="text-center border-end", style={"borderColor": BB_MUTED}),
                                    dbc.Col([
                                        html.Div("MOMENTUM (RSI 14-DAY)", style={"fontWeight": "bold", "fontSize": "0.85rem", "color": BB_MUTED}),
                                        html.H3("---", id="tech-rsi", style={"color": BB_TEXT, "fontFamily": "Courier New", "padding": "10px 0"})
                                    ], width=4, className="text-center border-end", style={"borderColor": BB_MUTED}),
                                    dbc.Col([
                                        html.Div("MACD TRIGGER STRATEGY", style={"fontWeight": "bold", "fontSize": "0.85rem", "color": BB_MUTED}),
                                        html.H3("---", id="tech-macd", style={"color": BB_TEXT, "fontFamily": "Courier New", "padding": "10px 0"})
                                    ], width=4, className="text-center"),
                                ]), 
                            ])
                        ], style={"backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}", "borderRadius": "0px", "marginTop": "20px"})
                    ])
                ], active_label_style={"color": BB_AMBER, "backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}"}, label_style={"color": BB_TEXT}),

                # TAB 4: FINANCIAL STATEMENTS
                dbc.Tab(label="4 <GO> FINANCIALS", children=[
                    html.Div([
                        dbc.Card([
                            dbc.CardHeader([
                                        html.Div([
                                            html.Span("FINANCIAL STATEMENTS", style={"fontWeight": "bold", "color": BB_AMBER}),
                                            dcc.Dropdown(
                                                id="statement-dropdown",
                                                options=[
                                                    {"label": "Balance Sheet", "value": "balance_sheet"},
                                                    {"label": "Income Statement", "value": "income_statement"},
                                                    {"label": "Cash Flow", "value": "cash_flow"}
                                                ],
                                                value="balance_sheet",  
                                                clearable=False,
                                                style={
                                                    "width": "250px", 
                                                    "backgroundColor": "#000000", 
                                                    "color": BB_AMBER, 
                                                    "border": f"1px solid {BB_MUTED}",
                                                    "fontFamily": "Courier New"
                                                }
                                            )
                                        ], className="d-flex justify-content-between align-items-center")
                                    ], style={"backgroundColor": "#222222"}),
                            
                            dbc.CardBody([
                                dag.AgGrid(
                                    id="financials-grid",
                                    rowData=[],
                                    columnDefs=[],
                                    className="ag-theme-alpine",
                                    style={"height": "300px", "width": "100%"}
                                ),
                                html.Hr(style={"borderColor": BB_MUTED, "marginTop": "20px", "marginBottom": "20px"}),
                                
                                # NEW: Reactive Growth & Summary Panels
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Card([
                                            dbc.CardHeader("📈 YOY GROWTH RATES", style={"fontWeight": "bold", "color": BB_AMBER, "backgroundColor": "#222222"}),
                                            dbc.CardBody(dcc.Loading(id="loading-growth", type="circle", children=html.Div(id="growth-rates-container")))
                                        ], style={"backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}", "borderRadius": "0px"})
                                    ], width=6),
                                    dbc.Col([
                                        dbc.Card([
                                            dbc.CardHeader("💡 KEY INSIGHTS", style={"fontWeight": "bold", "color": BB_AMBER, "backgroundColor": "#222222"}),
                                            dbc.CardBody(dcc.Loading(id="loading-summary", type="circle", children=html.Div(id="financial-summary-container")))
                                        ], style={"backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}", "borderRadius": "0px"})
                                    ], width=6)
                                ], className="mt-3")
                            ]),
                            
                        ], style={"backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}", "borderRadius": "0px", "marginTop": "20px"})
                    ])
                ], active_label_style={"color": BB_AMBER, "backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}"}, label_style={"color": BB_TEXT}),

                # TAB 5: MACRO INDICATORS (NEW)
                dbc.Tab(label="5 <GO> MACRO INDICATORS", children=[
                    html.Div([
                        dbc.Card([
                            dbc.CardHeader([
                                html.Div([
                                    html.Span("MACRO ECONOMIC & COMMODITY TRACKER", style={"fontWeight": "bold", "color": BB_AMBER}),
                                    dcc.Dropdown(
                                        id="macro-period-dropdown",  # Renamed to avoid collision with Tab 1 dropdown
                                        options=[
                                            {"label": "1 Year", "value": "1y"},
                                            {"label": "3 Years", "value": "3y"},
                                            {"label": "5 Years", "value": "5y"},
                                        ],
                                        value="1y",
                                        clearable=False,
                                        style={
                                            "width": "150px", 
                                            "backgroundColor": "#000000", 
                                            "color": BB_AMBER, 
                                            "border": f"1px solid {BB_MUTED}",
                                            "fontFamily": "Courier New"
                                        }
                                    )
                                ], className="d-flex justify-content-between align-items-center")
                            ], style={"backgroundColor": "#222222"}),
                            dbc.CardBody(dcc.Graph(id="macro-chart", style={"height": "500px"}))
                        ], style={"backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}", "borderRadius": "0px", "marginTop": "20px"})
                    ])
                ], active_label_style={"color": BB_AMBER, "backgroundColor": BB_CONTAINER, "border": f"1px solid {BB_MUTED}"}, label_style={"color": BB_TEXT}),

            ], id="terminal-tabs", style={"borderBottom": f"1px solid {BB_MUTED}"})
        ], width=9)
    ])
], fluid=True, style={"backgroundColor": BB_BG, "minHeight": "100vh", "padding": "20px"})

# --- SAFE STRING HELPER (ADD THIS) ---
def safe_upper(value, default='N/A'):
    """Safely convert value to uppercase, handling None/missing/empty values"""
    return (value or default).upper()

# --- CALLBACK 1: METRICS, CANDLESTICKS, RATINGS & PERSISTENT DATA ---
@app.callback(
    [
        Output("card-name", "children"), Output("card-sector", "children"),    
        Output("card-industry", "children"), Output("card-price", "children"),
        Output("card-mktcap", "children"), Output("val-pe", "children"),
        Output("val-fwd-pe", "children"), Output("val-peg", "children"),
        Output("val-pb", "children"), Output("fin-roe", "children"),
        Output("fin-margin", "children"), Output("fin-rev-growth", "children"),
        Output("fin-de", "children"), Output("cf-fcf", "children"),
        Output("mkt-div", "children"), Output("mkt-high", "children"),
        Output("mkt-low", "children"), Output("price-chart", "figure"),
        Output("score-container", "children"), Output("analysis-valuation", "children"),
        Output("analysis-quality", "children"), Output("analysis-risk", "children"),
        Output("analysis-growth", "children"), Output("tech-trend", "children"),
        Output("tech-rsi", "children"), Output("tech-macd", "children"),
        Output("stock-store", "data")
    ],
    Input("submit-btn", "n_clicks"),
    Input("period-dropdown", "value"),
    State("ticker-input", "value")
)
def update_stock_dashboard(n_clicks, selected_period, ticker):
    if not ticker:
        return [dash.no_update] * 27

    yf_conn = YFinanceConnector(ticker)
    raw_tech_data = yf_conn.get_technical_summary(period=selected_period)
    stats = yf_conn.get_stats(include_history=True, period=selected_period)

    if "error" in stats:
        return ([f"ERROR: {stats['error']}"] + ["---"] * 14 +
                [go.Figure(), "", "", "", "", "", "ERROR", "ERROR", "ERROR", {}])

    from stock_analyst import StockAnalyzer
    analyzer = StockAnalyzer(stats)
    score_data = analyzer.calculate_composite_score()

    fmt_p = lambda v: f"${v:,.2f}" if v else "N/A"
    fmt_pct = lambda v: f"{v*100:.1f}%" if v else "N/A"
    fmt_num = lambda v: f"{v:.2f}" if isinstance(v, (int, float)) else "N/A"

    df = stats.get("history", pd.DataFrame())
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Price", increasing_line_color=BB_GREEN, decreasing_line_color=BB_RED), row=1, col=1)
    
    volume_colors = [BB_GREEN if row['close'] >= row['open'] else BB_RED for _, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['volume'], name="Volume", marker_color=volume_colors, opacity=0.8), row=2, col=1)
    
    fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=40, r=40, t=10, b=10), showlegend=False,
                      xaxis2={"title": "Date", "gridcolor": "#222222"}, xaxis={"rangeslider": {"visible": False}, "gridcolor": "#222222"},
                      yaxis={"gridcolor": "#222222", "title": "Price ($)"}, yaxis2={"gridcolor": "#222222", "title": "Volume"})

    score_ui = [html.H3(f"{score_data['total_score']} / 10", style={"color": BB_AMBER, "fontFamily": "Courier New", "fontWeight": "bold"}),
                dbc.Badge(score_data['recommendation'].upper(), color="success" if score_data['total_score'] >= 8 else "info", style={"borderRadius": "0px"})]

    if isinstance(df, pd.DataFrame):
        stats["history"] = df.reset_index().to_dict("records")
    stats["ticker"] = ticker

    if "error" not in raw_tech_data:
        trend_val = raw_tech_data.get('trend_50_sma', 'N/A').upper()
        rsi_val = f"{raw_tech_data['rsi_14']:.2f} ({raw_tech_data['rsi_signal'].upper()})" if raw_tech_data.get('rsi_14') else "N/A"
        macd_val = raw_tech_data.get('macd_signal', 'N/A').upper()
    else:
        trend_val, rsi_val, macd_val = "DATA ERROR", "DATA ERROR", "DATA ERROR"

    return (
        safe_upper(stats.get('long_name')),      # ✅ was: stats['long_name'].upper()
        safe_upper(stats.get('sector')),         # ✅ was: stats.get('sector', 'N/A').upper()
        safe_upper(stats.get('industry')),       # ✅ was: stats.get('industry', 'N/A').upper()
        fmt_p(stats['current_price']), f"${stats['market_cap']/1e9:.1f}B",
        fmt_num(stats['trailing_pe']), fmt_num(stats['forward_pe']), fmt_num(stats['peg_ratio']), fmt_num(stats['price_to_book']),
        fmt_pct(stats['roe']), fmt_pct(stats['profit_margin']), fmt_pct(stats['revenue_growth']), stats['debt_to_equity'],
        fmt_p(stats['fcf_per_share']), fmt_pct(stats['dividend_yield']), fmt_p(stats['52w_high']), fmt_p(stats['52w_low']),
        fig, score_ui, analyzer.get_valuation_analysis(), analyzer.get_quality_rating(), analyzer.get_risk_profile(),
        analyzer.get_growth_category(), trend_val, rsi_val, macd_val, stats
    )


# REPLACE THIS ENTIRE CALLBACK:
# --- CALLBACK 2: WIRE NEWS DECK ---
@app.callback(
    Output("news-feed", "children"), 
    Input("stock-store", "data"), 
    Input("news-toggle", "value")
)
def update_news(stats, news_enabled):
    if not stats:
        return html.Div("TERMINAL IDLE. ENTER TICKER TO LISTEN FOR WIRE UPDATES.", style={"color": BB_MUTED, "fontFamily": "Courier New", "textAlign": "center", "padding": "20px"})
    
    # 🛑 GATEKEEPER: Skip API calls if toggle is OFF (default)
    if not news_enabled:
        return html.Div("⛔ NEWS FEED DISABLED. TOGGLE ON TO FETCH LIVE WIRES & CONSERVE API CREDITS.", style={"color": BB_MUTED, "fontFamily": "Courier New", "textAlign": "center", "padding": "20px"})
        
    try:
        from news_connector import BraveNewsAnalyst
        client = Together(api_key=Config.TOGETHER_API_KEY)
        news_analyst = BraveNewsAnalyst(client=client)
        raw_news = news_analyst.fetch_company_news(stats['long_name'], stats['ticker'])
        if not raw_news:
            return html.Div("NO REALTIME WIRE TICKERS FOR ASSIGNED ASSET.", style={"color": BB_MUTED, "fontFamily": "Courier New"})
        return [create_news_card(n) for n in raw_news]
    except Exception as e:
        return html.Div(f"WIRE FEED ERROR: {str(e).upper()}", style={"color": BB_RED, "fontFamily": "Courier New"})


# --- CALLBACK 3: FINANCIAL STATEMENTS DESK (AG-GRID + SUMMARY) ---
@app.callback(
    [
        Output("financials-grid", "rowData"),
        Output("financials-grid", "columnDefs"),
        Output("growth-rates-container", "children"),
        Output("financial-summary-container", "children")
    ],
    [
        Input("submit-btn", "n_clicks"),          
        Input("statement-dropdown", "value")     
    ],
    [State("ticker-input", "value")]
)
def update_financial_statements(n_clicks, statement_type, ticker):
    fallback_info = html.Div("ENTER TICKER & HIT <GO> TO INITIATE FINANCIAL ANALYSIS.", 
                             style={"color": BB_MUTED, "fontFamily": "Courier New", "textAlign": "center", "padding": "20px"})
    
    if not ticker:
        return [], [], fallback_info, fallback_info
    
    try:
        yf_conn = YFinanceConnector(ticker)
        df = yf_conn.get_financial_statement(statement_type)
        
        if df is None or isinstance(df, str) or (isinstance(df, pd.DataFrame) and df.empty):
            return [{"Metrics": "ERROR: No data returned."}], [{"field": "Metrics"}], fallback_info, fallback_info
            
        analyzer = FinancialStatementAnalyzer(ticker, yf_conn)
        cleaned_df = FinancialStatementAnalyzer.clean_statement(df)
        
        row_data = df.to_dict("records")
        column_defs = []
        for col in df.columns:
            style_cfg = {"color": BB_AMBER, "backgroundColor": "#000000", "fontFamily": "Courier New"}
            col_def = {"field": col, "type": "rightAligned" if col != "Metrics" else None, "cellStyle": style_cfg}
            if col == "Metrics":
                col_def.update({"pinned": "left", "filter": True})
            column_defs.append(col_def)
            
        metrics_map = {
            "income_statement": (analyzer.DEFAULT_INCOME_METRICS, analyzer.generate_income_summary),
            "balance_sheet": (analyzer.DEFAULT_BALANCE_METRICS, analyzer.generate_balance_summary),
            "cash_flow": (analyzer.DEFAULT_CASHFLOW_METRICS, analyzer.generate_cashflow_summary)
        }
        metrics, summary_fn = metrics_map.get(statement_type, ([], lambda x: ["Unknown statement type."]))
        
        growth_df = analyzer.calculate_growth(cleaned_df, metrics)
        summary_list = summary_fn(cleaned_df)
        
        growth_rows = [html.Tr([
            html.Th("METRIC", style={"color": BB_MUTED, "fontSize": "0.7rem", "padding": "8px"}),
            html.Th("LATEST VALUE", style={"color": BB_MUTED, "fontSize": "0.7rem", "padding": "8px", "textAlign": "right"}),
            html.Th("YOY GROWTH %", style={"color": BB_MUTED, "fontSize": "0.7rem", "padding": "8px", "textAlign": "right"})
        ], style={"borderBottom": f"1px solid {BB_MUTED}"})]
        
        for _, row in growth_df.iterrows():
            val = row["Latest Value"]
            g_val = row["YoY Growth %"]
            g_color = BB_GREEN if g_val != "N/A" and float(g_val) > 0 else (BB_RED if g_val != "N/A" and float(g_val) < 0 else BB_MUTED)
            
            growth_rows.append(html.Tr([
                html.Td(row["Metric"], style={"color": BB_TEXT, "padding": "8px"}),
                html.Td(f"{val:,.2f}" if isinstance(val, (int, float)) else str(val), style={"color": BB_AMBER, "padding": "8px", "textAlign": "right", "fontFamily": "Courier New"}),
                html.Td(f"{g_val}%" if g_val != "N/A" else "N/A", style={"color": g_color, "padding": "8px", "textAlign": "right", "fontFamily": "Courier New"})
            ], style={"borderBottom": f"1px solid {BB_MUTED}"}))
            
        growth_ui = dbc.Table(growth_rows, className="table-sm", style={"backgroundColor": "transparent", "fontSize": "0.8rem"})
        summary_ui = html.Ul([html.Li(bullet, style={"color": BB_TEXT, "fontSize": "0.85rem", "marginBottom": "6px", "listStyleType": "square", "marginLeft": "15px"}) for bullet in summary_list], 
                             style={"paddingLeft": "15px", "marginBottom": "0"})
        
        return row_data, column_defs, growth_ui, summary_ui

    except Exception as e:
        return [{"Metrics": f"DESK ERROR: {str(e).upper()}"}], [{"field": "Metrics"}], html.Div(str(e).upper(), style={"color": BB_RED}), html.Div(str(e).upper(), style={"color": BB_RED})


# --- CALLBACK 4: MACRO INDICATORS DASHBOARD ---
@app.callback(
    Output("macro-chart", "figure"),
    Input("macro-period-dropdown", "value")
)
def update_macro_chart(selected_period):
    df = fetch_macro_data(tickers_dict=MACRO_TICKERS, period=selected_period, interval="1d")
    fig = create_macro_figure(df)
    return fig


if __name__ == "__main__":
    app.run(debug=True)