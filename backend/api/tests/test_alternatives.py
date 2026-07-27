from datetime import date, timedelta

from fastapi.testclient import TestClient

from api.app import app
from api.services.alternatives import build_alternatives
from api.services.alternatives.engine import fit_weights


client = TestClient(app)

ORIGINAL_EXPIRATION = (date.today() + timedelta(days=60)).isoformat()
LATER_EXPIRATION = (date.today() + timedelta(days=120)).isoformat()


def long_call_report(**overrides) -> dict:
    report = {
        "ticker": "AAPL",
        "tradeType": "Call Option (Long)",
        "strike": 100,
        "expiration": ORIGINAL_EXPIRATION,
        "riskMath": {
            "max_loss": 1000,
            "breakeven": 105,
            "calendar_days_left": 60,
            "risk_percent_of_account": 4.0,
        },
        "contractSnapshot": {
            "option_side": "call",
            "strike": 100,
            "expiration": ORIGINAL_EXPIRATION,
            "premium": 5.0,
            "contracts": 2,
            "underlying_price": 102.0,
            "implied_volatility": 0.30,
        },
    }
    report.update(overrides)
    return report


def chain_rows() -> list[dict]:
    return [
        # Later expiration, same strike/side, priced.
        {
            "contract_type": "call",
            "expiration_date": LATER_EXPIRATION,
            "strike_price": 100,
            "bid": 6.8,
            "ask": 7.2,
            "mid": 7.0,
            "last": 6.9,
            "implied_volatility": 0.32,
        },
        # Short-leg candidate at the original expiration, further OTM, cheaper.
        {
            "contract_type": "call",
            "expiration_date": ORIGINAL_EXPIRATION,
            "strike_price": 110,
            "bid": 1.9,
            "ask": 2.1,
            "mid": 2.0,
            "last": 2.0,
            "implied_volatility": 0.29,
        },
        # Wrong side row that must be ignored.
        {
            "contract_type": "put",
            "expiration_date": LATER_EXPIRATION,
            "strike_price": 100,
            "mid": 4.0,
        },
    ]


def candidates_by_type(result: dict) -> dict:
    return {item["type"]: item for item in result["candidates"]}


def test_full_candidate_set_with_market_data() -> None:
    result = build_alternatives(
        report=long_call_report(),
        user_profile={"riskStyle": "Balanced", "riskRules": {"maxRiskPerTradePercent": 2.0}},
        market_contracts=chain_rows(),
    )
    assert result["status"] == "ok"
    by_type = candidates_by_type(result)
    assert set(by_type) == {"later_expiration", "vertical_spread", "reduced_size", "wait"}

    later = by_type["later_expiration"]
    assert later["status"] == "ok"
    # 2 contracts x $7.00 premium x 100 = $1400 via long_option_metrics
    assert later["metrics"]["max_loss"] == 1400.0
    assert later["metrics"]["breakeven"] == 107.0
    assert later["metrics"]["days_to_expiry"] == 120
    assert later["probability"]["status"] == "ok"
    assert later["probability"]["basis"] == "delayed_iv_black_scholes"

    spread = by_type["vertical_spread"]
    assert spread["status"] == "ok"
    # Net debit 5.0 - 2.0 = 3.0, width 10 -> max loss 600, max profit 1400 for 2 contracts
    assert spread["metrics"]["max_loss"] == 600.0
    assert spread["metrics"]["max_profit"] == 1400.0
    assert spread["metrics"]["breakeven"] == 103.0
    assert spread["probability"]["status"] == "ok"
    assert spread["probability"]["p_max_profit"] is not None

    reduced = by_type["reduced_size"]
    assert reduced["status"] == "ok"
    assert reduced["metrics"]["contracts"] == 1
    assert reduced["metrics"]["max_loss"] == 500.0
    assert reduced["probability"]["status"] == "ok"

    wait = by_type["wait"]
    assert wait["metrics"]["max_loss"] == 0.0
    assert wait["probability"]["status"] == "not_applicable"

    # Every candidate got a fit score with named, transparent sub-scores.
    for candidate in result["candidates"]:
        assert candidate["fit"]["score"] is not None
        assert all({"name", "value", "weight", "weighted"} <= set(sub) for sub in candidate["fit"]["sub_scores"])


def test_time_relief_never_applies_to_same_expiration_candidates() -> None:
    result = build_alternatives(report=long_call_report(), market_contracts=chain_rows())
    by_type = candidates_by_type(result)
    for candidate_type in ("reduced_size", "vertical_spread", "wait"):
        names = {sub["name"] for sub in by_type[candidate_type]["fit"]["sub_scores"]}
        assert "time_relief" not in names, candidate_type
    later_names = {sub["name"] for sub in by_type["later_expiration"]["fit"]["sub_scores"]}
    assert "time_relief" in later_names


def test_missing_market_data_never_invents_premiums() -> None:
    result = build_alternatives(report=long_call_report(), market_contracts=[])
    by_type = candidates_by_type(result)
    assert by_type["later_expiration"]["status"] == "needs_live_premium"
    assert by_type["later_expiration"]["metrics"] == {}
    assert by_type["vertical_spread"]["status"] == "needs_live_premium"
    assert by_type["vertical_spread"]["metrics"] == {}
    # Wait and reduced-size never need market data.
    assert by_type["wait"]["status"] == "ok"
    assert by_type["reduced_size"]["status"] == "ok"


def test_risk_style_shifts_weights_and_over_limit_boosts_risk_reduction() -> None:
    conservative = fit_weights("Conservative", over_profile_limit=False)
    aggressive = fit_weights("Aggressive", over_profile_limit=False)
    assert conservative["risk_reduction"] > aggressive["risk_reduction"]
    assert aggressive["thesis_preservation"] > conservative["thesis_preservation"]

    over_limit = fit_weights("Balanced", over_profile_limit=True)
    base = fit_weights("Balanced", over_profile_limit=False)
    assert over_limit["risk_reduction"] > base["risk_reduction"]
    assert over_limit["thesis_preservation"] < base["thesis_preservation"]
    assert abs(sum(over_limit.values()) - sum(base.values())) < 1e-9

    unknown_style = fit_weights("Degenerate", over_profile_limit=False)
    assert unknown_style == base


def test_over_limit_profile_is_reported_in_context() -> None:
    result = build_alternatives(
        report=long_call_report(),
        user_profile={"riskStyle": "Balanced", "riskRules": {"maxRiskPerTradePercent": 2.0}},
        market_contracts=[],
    )
    assert result["profile_context"]["over_profile_limit"] is True
    assert result["profile_context"]["max_risk_per_trade_percent"] == 2.0

    within = build_alternatives(
        report=long_call_report(),
        user_profile={"riskStyle": "Balanced", "riskBudgetPercent": 10},
        market_contracts=[],
    )
    assert within["profile_context"]["over_profile_limit"] is False
    # riskBudgetPercent is the fallback when riskRules.maxRiskPerTradePercent is absent.
    assert within["profile_context"]["max_risk_per_trade_percent"] == 10


# --- division guards: every candidate-type combination that could divide by zero ---


def test_zero_and_missing_denominators_do_not_crash() -> None:
    report = long_call_report()
    report["riskMath"] = {"max_loss": 0, "calendar_days_left": 0, "risk_percent_of_account": 0}
    report["contractSnapshot"]["contracts"] = 0
    report["contractSnapshot"]["premium"] = None
    report["strike"] = 0
    result = build_alternatives(report=report, market_contracts=chain_rows())
    assert result["status"] == "ok"
    for candidate in result["candidates"]:
        fit = candidate["fit"]
        # Score may be None when nothing is computable, but nothing may raise
        # and no sub-score may be NaN/inf.
        for sub in fit["sub_scores"]:
            if sub["value"] is not None:
                assert 0.0 <= sub["value"] <= 1.0


def test_single_contract_trade_has_no_reduced_size_candidate() -> None:
    report = long_call_report()
    report["contractSnapshot"]["contracts"] = 1
    report["riskMath"]["max_loss"] = 500
    result = build_alternatives(report=report, market_contracts=[])
    assert "reduced_size" not in candidates_by_type(result)
    assert "wait" in candidates_by_type(result)


def test_empty_report_still_returns_wait_baseline() -> None:
    result = build_alternatives(report={}, market_contracts=[])
    by_type = candidates_by_type(result)
    assert "wait" in by_type
    assert by_type["wait"]["fit"]["score"] is not None


def test_original_vertical_spread_only_gets_size_and_wait_candidates() -> None:
    report = {
        "ticker": "MSFT",
        "tradeType": "Call Spread",
        "strike": 100,
        "expiration": ORIGINAL_EXPIRATION,
        "riskMath": {"max_loss": 400, "breakeven": 102, "calendar_days_left": 60, "risk_percent_of_account": 1.6},
        "contractSnapshot": {
            "option_side": "call",
            "premium": 2.0,
            "contracts": 2,
            "underlying_price": 101.0,
            "implied_volatility": 0.28,
            "structure": {
                "kind": "vertical_spread",
                "label": "Call Debit Spread $100/$110",
                "primary_strike": 100,
                "short_strike": 110,
                "quantity": 2,
                "max_loss": 400,
                "max_profit": 1600,
                "breakeven": 102,
                "spread_orientation": "call_debit",
            },
        },
    }
    result = build_alternatives(report=report, market_contracts=[])
    by_type = candidates_by_type(result)
    assert set(by_type) == {"reduced_size", "wait"}
    reduced = by_type["reduced_size"]
    assert reduced["status"] == "ok"
    assert reduced["metrics"]["max_loss"] == 200.0
    assert reduced["metrics"]["max_profit"] == 800.0
    assert reduced["probability"]["status"] == "ok"


def test_alternatives_endpoint_returns_scored_candidates() -> None:
    user = client.post(
        "/auth/clerk-sync",
        json={
            "clerkId": "clerk_alternatives",
            "name": "Alt Tester",
            "email": "alt-tester@example.com",
            "accountSize": 25000,
            "riskBudgetPercent": 2,
            "riskStyle": "Conservative",
            "experienceLevel": "Some experience",
            "purpose": [],
            "tradeFocus": [],
            "struggles": [],
            "reminders": [],
            "sectors": [],
            "marketCaps": [],
            "events": [],
            "safetyAccepted": True,
        },
    ).json()
    response = client.post(
        "/alternatives",
        json={
            "user_id": user["id"],
            "report": long_call_report(),
            "market_contracts": chain_rows(),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["fit_basis"] == "profile_weighted_subscores_v1"
    assert body["probability_basis"] == "delayed_iv_black_scholes"
    assert body["profile_context"]["risk_style"] == "Conservative"
    assert {item["type"] for item in body["candidates"]} == {"later_expiration", "vertical_spread", "reduced_size", "wait"}
    # Candidates come back ranked by fit score, best first.
    scores = [item["fit"]["score"] for item in body["candidates"] if item["fit"]["score"] is not None]
    assert scores == sorted(scores, reverse=True)
