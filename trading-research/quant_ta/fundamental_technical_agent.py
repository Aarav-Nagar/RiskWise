from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
import yfinance as yf

from quant_ta.config import CONFIG, ResearchConfig
from quant_ta.features import load_features
from quant_ta.io import read_frame, write_frame


@dataclass(frozen=True)
class FundamentalAgentConfig:
    initial_capital: float = 1000.0
    reporting_lag_days: int = 45
    rebalance_frequency: str = "W-FRI"
    top_n: int = 5
    transaction_cost: float = 0.001
    test_start: str = "2024-01-01"


AGENT_CONFIG = FundamentalAgentConfig()


def _safe_get(frame: pd.DataFrame, item: str) -> pd.Series:
    if frame.empty or item not in frame.index:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame.loc[item], errors="coerce")


def _statement_features(ticker: str, lag_days: int) -> pd.DataFrame:
    stock = yf.Ticker(ticker)
    income = stock.quarterly_financials
    balance = stock.quarterly_balance_sheet
    cashflow = stock.quarterly_cashflow
    if income.empty:
        return pd.DataFrame()

    columns = pd.to_datetime(income.columns)
    rows = []
    revenue = _safe_get(income, "Total Revenue")
    net_income = _safe_get(income, "Net Income")
    ebitda = _safe_get(income, "Normalized EBITDA")
    total_assets = _safe_get(balance, "Total Assets")
    total_debt = _safe_get(balance, "Total Debt")
    stockholder_equity = _safe_get(balance, "Stockholders Equity")
    fcf = _safe_get(cashflow, "Free Cash Flow")
    operating_cashflow = _safe_get(cashflow, "Operating Cash Flow")

    for period in columns:
        key = period.to_pydatetime()
        rev = revenue.get(key, np.nan)
        ni = net_income.get(key, np.nan)
        ebit = ebitda.get(key, np.nan)
        assets = total_assets.get(key, np.nan)
        debt = total_debt.get(key, np.nan)
        equity = stockholder_equity.get(key, np.nan)
        free_cf = fcf.get(key, np.nan)
        ocf = operating_cashflow.get(key, np.nan)
        prev_year = key - pd.DateOffset(years=1)
        prior_revenue = revenue.get(prev_year.to_pydatetime(), np.nan)
        prior_income = net_income.get(prev_year.to_pydatetime(), np.nan)

        rows.append(
            {
                "ticker": ticker,
                "period_end": period,
                "date": period + pd.Timedelta(days=lag_days),
                "revenue": rev,
                "net_income": ni,
                "ebitda": ebit,
                "free_cash_flow": free_cf,
                "operating_cash_flow": ocf,
                "total_assets": assets,
                "total_debt": debt,
                "stockholder_equity": equity,
                "net_margin": ni / rev if rev and rev > 0 else np.nan,
                "fcf_margin": free_cf / rev if rev and rev > 0 else np.nan,
                "roa": ni / assets if assets and assets > 0 else np.nan,
                "roe": ni / equity if equity and equity > 0 else np.nan,
                "debt_to_assets": debt / assets if assets and assets > 0 else np.nan,
                "revenue_yoy": rev / prior_revenue - 1 if prior_revenue and prior_revenue > 0 else np.nan,
                "net_income_yoy": ni / abs(prior_income) - 1 if prior_income and prior_income != 0 else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values("date")


def build_fundamental_panel(config: ResearchConfig = CONFIG, agent_config: FundamentalAgentConfig = AGENT_CONFIG) -> pd.DataFrame:
    config.ensure_dirs()
    frames = []
    for ticker in config.tickers:
        try:
            frame = _statement_features(ticker, agent_config.reporting_lag_days)
            if not frame.empty:
                frames.append(frame)
        except Exception as error:
            frames.append(pd.DataFrame([{"ticker": ticker, "error": str(error)}]))
    panel = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    write_frame(panel, config.processed_dir / "fundamental_panel.csv")
    return panel


def load_fundamental_panel(config: ResearchConfig = CONFIG, agent_config: FundamentalAgentConfig = AGENT_CONFIG) -> pd.DataFrame:
    path = config.processed_dir / "fundamental_panel.csv"
    if path.exists():
        return read_frame(path, parse_dates=["date", "period_end"])
    return build_fundamental_panel(config, agent_config)


def _rank_percentile(series: pd.Series, ascending: bool = True) -> pd.Series:
    return series.rank(pct=True, ascending=ascending)


def _prepare_agent_panel(config: ResearchConfig, agent_config: FundamentalAgentConfig) -> pd.DataFrame:
    features = load_features(config)
    fundamentals = load_fundamental_panel(config, agent_config)
    fundamentals = fundamentals[fundamentals.get("error").isna() if "error" in fundamentals else fundamentals.index == fundamentals.index].copy()
    features = features[features["ticker"].isin(config.tickers)].sort_values(["ticker", "date"]).copy()
    merged = []
    for ticker, prices in features.groupby("ticker"):
        fund = fundamentals[fundamentals["ticker"] == ticker].sort_values("date")
        if fund.empty:
            continue
        merged.append(pd.merge_asof(prices.sort_values("date"), fund, on="date", by="ticker", direction="backward"))
    panel = pd.concat(merged, ignore_index=True) if merged else pd.DataFrame()
    panel = panel[panel["date"] >= pd.Timestamp(agent_config.test_start)].copy()
    panel["daily_return"] = panel.groupby("ticker")["close"].pct_change()
    return panel


def _score_cross_section(day: pd.DataFrame) -> pd.DataFrame:
    day = day.copy()
    day["quality_score"] = (
        _rank_percentile(day["net_margin"])
        + _rank_percentile(day["fcf_margin"])
        + _rank_percentile(day["roa"])
        + _rank_percentile(day["debt_to_assets"], ascending=False)
    ) / 4
    day["growth_score"] = (
        _rank_percentile(day["revenue_yoy"].replace([np.inf, -np.inf], np.nan))
        + _rank_percentile(day["net_income_yoy"].replace([np.inf, -np.inf], np.nan))
    ) / 2
    day["technical_score"] = (
        _rank_percentile(day["return_20d"])
        + _rank_percentile(day["return_60d"])
        + _rank_percentile(day["price_to_sma_50d"])
        + _rank_percentile(day["price_to_sma_200d"])
        + _rank_percentile(day["volatility_20d"], ascending=False)
    ) / 5
    day["agent_score"] = 0.45 * day["quality_score"] + 0.25 * day["growth_score"] + 0.30 * day["technical_score"]
    return day


def run_fundamental_technical_agent(
    config: ResearchConfig = CONFIG,
    agent_config: FundamentalAgentConfig = AGENT_CONFIG,
) -> pd.DataFrame:
    config.ensure_dirs()
    panel = _prepare_agent_panel(config, agent_config)
    if panel.empty:
        raise RuntimeError("No merged fundamental+technical panel was available.")
    panel = panel.dropna(subset=["agent_score"] if "agent_score" in panel else ["close"])
    scored_days = []
    for _, day in panel.groupby("date"):
        scored_days.append(_score_cross_section(day))
    scored = pd.concat(scored_days, ignore_index=True)
    scored = scored.dropna(subset=["agent_score", "daily_return"])

    rebalance_dates = pd.Series(sorted(scored["date"].unique()))
    rebalance_dates = rebalance_dates.groupby(rebalance_dates.dt.to_period("W")).max().to_list()
    weights_by_date: dict[pd.Timestamp, dict[str, float]] = {}
    selections = []
    current_weights: dict[str, float] = {}
    for date in sorted(scored["date"].unique()):
        date = pd.Timestamp(date)
        if date in rebalance_dates:
            day = scored[scored["date"] == date].sort_values("agent_score", ascending=False)
            selected = day.head(agent_config.top_n)
            current_weights = {ticker: 1 / len(selected) for ticker in selected["ticker"]} if not selected.empty else {}
            selections.append(selected.assign(selection_date=date))
        weights_by_date[date] = current_weights.copy()

    equity = agent_config.initial_capital
    previous_weights: dict[str, float] = {}
    equity_rows = []
    for date in sorted(scored["date"].unique()):
        day = scored[scored["date"] == date]
        returns = day.set_index("ticker")["daily_return"].fillna(0).to_dict()
        weights = weights_by_date.get(pd.Timestamp(date), {})
        turnover = sum(abs(weights.get(t, 0) - previous_weights.get(t, 0)) for t in set(weights) | set(previous_weights))
        portfolio_return = sum(weights.get(ticker, 0) * returns.get(ticker, 0) for ticker in weights)
        equity *= 1 + portfolio_return
        equity -= equity * agent_config.transaction_cost * turnover
        previous_weights = weights
        equity_rows.append(
            {
                "date": date,
                "equity": equity,
                "portfolio_return": portfolio_return,
                "turnover": turnover,
                "holdings": json.dumps(weights),
            }
        )

    equity_curve = pd.DataFrame(equity_rows)
    selections_df = pd.concat(selections, ignore_index=True) if selections else pd.DataFrame()
    equity_curve = _attach_benchmarks(equity_curve, config, agent_config)
    summary = _summarize(equity_curve, agent_config)
    write_frame(scored, config.processed_dir / "fundamental_technical_scored_panel.csv")
    write_frame(selections_df, config.backtest_dir / "fundamental_technical_selections.csv")
    write_frame(equity_curve, config.backtest_dir / "fundamental_technical_equity.csv")
    write_frame(summary, config.backtest_dir / "fundamental_technical_results.csv")
    _write_report(summary, selections_df, config)
    return summary


def _summarize(curve: pd.DataFrame, agent_config: FundamentalAgentConfig) -> pd.DataFrame:
    returns = curve["equity"].pct_change().fillna(0)
    cumulative = curve["equity"].iloc[-1] / agent_config.initial_capital - 1
    spy_return = curve["spy_equity"].iloc[-1] / agent_config.initial_capital - 1
    basket_return = curve["basket_equity"].iloc[-1] / agent_config.initial_capital - 1
    drawdown = curve["equity"] / curve["equity"].cummax() - 1
    return pd.DataFrame(
        [
            {
                "strategy": "FundamentalTechnicalAgent",
                "starting_capital": agent_config.initial_capital,
                "ending_value": curve["equity"].iloc[-1],
                "profit_loss": curve["equity"].iloc[-1] - agent_config.initial_capital,
                "cumulative_return": cumulative,
                "spy_ending_value": curve["spy_equity"].iloc[-1],
                "spy_return": spy_return,
                "basket_ending_value": curve["basket_equity"].iloc[-1],
                "basket_return": basket_return,
                "return_vs_spy": cumulative - spy_return,
                "return_vs_basket": cumulative - basket_return,
                "sharpe": returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else np.nan,
                "max_drawdown": drawdown.min(),
                "average_turnover": curve["turnover"].mean(),
                "evaluation_start": curve["date"].min(),
                "evaluation_end": curve["date"].max(),
                "point_in_time_caveat": "Uses yfinance quarterly statements with 45-day reporting lag; not restatement-proof institutional point-in-time data.",
            }
        ]
    )


def _attach_benchmarks(curve: pd.DataFrame, config: ResearchConfig, agent_config: FundamentalAgentConfig) -> pd.DataFrame:
    features = load_features(config)
    dates = pd.to_datetime(curve["date"])
    bench = features[features["date"].isin(dates)].copy()
    spy_returns = (
        bench[bench["ticker"] == config.benchmark][["date", "return_1d"]]
        .rename(columns={"return_1d": "spy_return"})
        .sort_values("date")
    )
    basket_returns = (
        bench[bench["ticker"].isin(config.tickers)]
        .groupby("date", as_index=False)["return_1d"]
        .mean()
        .rename(columns={"return_1d": "basket_return"})
    )
    out = curve.merge(spy_returns, on="date", how="left").merge(basket_returns, on="date", how="left")
    out["spy_return"] = out["spy_return"].fillna(0)
    out["basket_return"] = out["basket_return"].fillna(0)
    out["spy_equity"] = agent_config.initial_capital * (1 + out["spy_return"]).cumprod()
    out["basket_equity"] = agent_config.initial_capital * (1 + out["basket_return"]).cumprod()
    return out


def _write_report(summary: pd.DataFrame, selections: pd.DataFrame, config: ResearchConfig) -> None:
    top_recent = selections.sort_values("selection_date").tail(20) if not selections.empty else selections
    lines = [
        "# Fundamental + Technical Agent Study",
        "",
        "This experiment combines quarterly business fundamentals with daily technical features. Fundamentals are lagged by 45 days after quarter end to reduce lookahead bias, but the data source is free yfinance and is not a true institutional point-in-time feed.",
        "",
        "## Results",
        "",
        "```text",
        summary.to_string(index=False, float_format=lambda value: f"{value:,.6f}"),
        "```",
        "",
        "## Recent Agent Selections",
        "",
        "```text",
        top_recent[["selection_date", "ticker", "agent_score", "quality_score", "growth_score", "technical_score"]].to_string(index=False, float_format=lambda value: f"{value:,.6f}")
        if not top_recent.empty
        else "No selections.",
        "```",
        "",
        "## Financial Interpretation",
        "",
        "This agent is designed for swing allocation, not intraday scalping. A valid positive result would require beating SPY and the equal-weight basket after turnover costs while keeping drawdown controlled.",
        "",
    ]
    (config.reports_dir / "fundamental_technical_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    run_fundamental_technical_agent(CONFIG, AGENT_CONFIG)


if __name__ == "__main__":
    main()
