from __future__ import annotations

from datetime import date, datetime, timezone

from .models import TradeCheckRequest, TradeCheckResponse


def parse_expiration_date(value: str) -> date | None:
    clean = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%m/%d/%Y"):
        try:
            parsed = datetime.strptime(clean, fmt).date()
            return parsed if parsed >= date.today() else None
        except ValueError:
            continue
    return None


def score_trade_check(request: TradeCheckRequest) -> TradeCheckResponse:
    ticker = request.ticker.upper().strip()
    is_option = "Option" in request.trade_type
    option_side = normalize_option_side(request.option_side, request.trade_type)
    premium = float(request.premium or 0)
    contracts = int(request.contracts or 1)
    if is_option:
        if request.strike <= 0:
            raise ValueError("Strike must be greater than zero for an option check.")
        if premium < 0:
            raise ValueError("Premium cannot be negative.")
        if contracts < 1:
            raise ValueError("Contracts must be at least 1.")
        calculated_risk = round(premium * contracts * 100, 2) if premium else None
        if calculated_risk is not None and calculated_risk > 0:
            drift = abs(calculated_risk - request.amount_at_risk)
            if drift > max(10, calculated_risk * 0.25):
                raise ValueError("Amount at risk should be close to premium x contracts x 100 for long options.")
    risk_percent = request.amount_at_risk / request.account_size * 100
    expiration_date = parse_expiration_date(request.expiration)
    if expiration_date is None:
        raise ValueError("Choose a valid future expiration date.")
    calendar_days = max(0, (expiration_date - date.today()).days)
    expiration_trading_days = max(1, round(calendar_days * 5 / 7))
    selected_hold_days = {"Intraday": 1, "1-3 Days": 3, "1-2 Weeks": 9, "1 Month+": 22}.get(request.timeframe, 9)
    option_risk = 1.0 if is_option else 0.4
    timeframe_adjustment = {
        "Intraday": 0.9,
        "1-3 Days": 0.7,
        "1-2 Weeks": 0.45,
        "1 Month+": 0.35,
    }.get(request.timeframe, 0.55)
    expiry_pressure = 1.2 if expiration_trading_days <= 3 else 0.8 if expiration_trading_days <= 7 else 0.45 if expiration_trading_days <= 15 else 0.2

    risk_score = min(9.4, round(2.4 + risk_percent * 0.75 + option_risk + timeframe_adjustment + expiry_pressure, 1))
    setup_score = max(48, min(84, round(76 - max(0, risk_percent - 1.5) * 5 - timeframe_adjustment * 3 - max(0, 7 - expiration_trading_days) * 0.6)))
    options_structure = max(35, min(88, round(84 - risk_score * 5.0 - timeframe_adjustment * 6 - max(0, selected_hold_days - expiration_trading_days) * 1.4)))
    behavior_score = max(38, min(84, round(76 - max(0, risk_percent - 1.0) * 7)))
    market_context = max(45, min(78, round(64 + (setup_score - 65) * 0.2)))
    agent_agreement = max(52, min(88, round(setup_score + 8 - risk_score * 2.2)))
    profile_limit = 2.0
    amount_above_profile = max(0.0, request.amount_at_risk - request.account_size * profile_limit / 100)
    required_move = round(2.4 + risk_score * 0.42 + timeframe_adjustment * 1.2 + max(0, 10 - expiration_trading_days) * 0.18, 1)
    trading_days = expiration_trading_days
    hold_vs_expiration = "Too tight" if selected_hold_days >= trading_days else "Room available" if trading_days - selected_hold_days >= 5 else "Tight"
    if is_option and premium:
        breakeven = round(request.strike + premium, 2) if option_side == "call" else round(request.strike - premium, 2)
        breakeven_basis = "premium"
    else:
        breakeven = round(request.strike * (1 + required_move / 100), 2) if option_side == "call" else round(request.strike * (1 - required_move / 100), 2)
        breakeven_basis = "modeled_move"
    mid_price = midpoint(request.bid, request.ask)
    spread_pct = round(((request.ask or 0) - (request.bid or 0)) / mid_price * 100, 1) if mid_price else None
    liquidity_risk = "Unknown"
    if request.open_interest is not None or request.contract_volume is not None or spread_pct is not None:
        open_interest = request.open_interest or 0
        volume = request.contract_volume or 0
        if (spread_pct is not None and spread_pct > 12) or open_interest < 100 or volume < 20:
            liquidity_risk = "Elevated"
        elif open_interest >= 500 and volume >= 100 and (spread_pct is None or spread_pct <= 6):
            liquidity_risk = "Better"
        else:
            liquidity_risk = "Mixed"
    theta_risk = "High" if trading_days <= 3 else "Medium" if trading_days <= 10 else "Lower"
    event_risk = "Elevated" if request.timeframe in {"Intraday", "1-3 Days", "1-2 Weeks"} else "Moderate"
    difficulty = "Advanced" if risk_percent > 3 or trading_days <= 3 else "Intermediate" if trading_days <= 10 else "Beginner-aware"

    if risk_percent > 3:
        badge = "High Risk"
        risk_posture = "Elevated"
        weakest_link = "Position sizing"
        overall_read = "Reviewable only after reducing size"
        insight = (
            "The planned risk is large relative to the demo account. This review suggests reducing size or waiting for a "
            "cleaner setup before making any real-world decision."
        )
    elif setup_score >= 70 and risk_score <= 5.5:
        badge = "Constructive Setup"
        risk_posture = "Controlled"
        weakest_link = "Contract timing" if option_risk else "Entry timing"
        overall_read = "Constructive, but still needs an exit plan"
        insight = (
            "The check has constructive technical context and controlled sizing. Treat this as a structured risk review, "
            "not a directional prediction."
        )
    else:
        badge = "Needs Review"
        risk_posture = "Mixed"
        weakest_link = "Signal clarity"
        overall_read = "Mixed evidence; clarify the thesis before acting"
        insight = (
            "The setup has mixed evidence. The app would flag this for more review rather than treating it as a high-quality setup."
        )

    return TradeCheckResponse(
        id=f"api-{int(datetime.now(timezone.utc).timestamp())}",
        ticker=ticker,
        trade_type=request.trade_type,
        title=f"{ticker} {request.trade_type}",
        subtitle=f"${request.strike:g} Strike - {request.expiration} - {request.timeframe}",
        badge=badge,
        setup_score=setup_score,
        risk_score=risk_score,
        agent_agreement=agent_agreement,
        methodology_label="Backend educational score",
        insight=insight,
        strike=request.strike,
        expiration=request.expiration,
        amount_at_risk=request.amount_at_risk,
        timeframe=request.timeframe,
        checks=[
            ["Trend Context", "good" if setup_score >= 65 else "warn"],
            ["Volatility Context", "good" if risk_score <= 6 else "warn"],
            ["Sizing Discipline", "good" if risk_percent <= 2 else "warn"],
            ["Risk Review", "warn" if risk_percent > 2 else "good"],
        ],
        agents=[
            ["Risk-Managed", min(92, agent_agreement + 10), "good"],
            ["Neutral", agent_agreement, "good"],
            ["Aggressive", max(45, agent_agreement - 18), "risk"],
        ],
        scenarios=[
            ["Bear Case", "-50%", f"-${request.amount_at_risk * 0.5:.0f}", "risk"],
            ["Base Case", "+15%", f"+${request.amount_at_risk * 0.15:.0f}", "good"],
            ["Bull Case", "+75%", f"+${request.amount_at_risk * 0.75:.0f}", "good"],
        ],
        overall_read=overall_read,
        weakest_link=weakest_link,
        risk_posture=risk_posture,
        decision_snapshot={
            "setup_quality": setup_score,
            "options_structure": options_structure,
            "risk_budget_used": round(risk_percent, 2),
            "profile_risk_limit": profile_limit,
            "agent_disagreement": "High" if agent_agreement < 62 else "Medium" if agent_agreement < 78 else "Low",
            "review_status": badge,
            "calendar_days_to_expiration": calendar_days,
            "selected_hold_days": selected_hold_days,
            "hold_vs_expiration": hold_vs_expiration,
            "modeled_breakeven": breakeven,
            "option_side": option_side,
            "premium": premium or None,
            "contracts": contracts if is_option else None,
            "liquidity_risk": liquidity_risk,
        },
        risk_math={
            "capital_at_risk": round(request.amount_at_risk, 2),
            "max_loss": round(request.amount_at_risk, 2),
            "half_premium_drawdown": -round(request.amount_at_risk * 0.5, 2),
            "amount_above_profile": round(amount_above_profile, 2),
            "required_move_to_breakeven_pct": required_move,
            "trading_days_left": trading_days,
            "calendar_days_left": calendar_days,
            "planned_hold_days": selected_hold_days,
            "risk_percent_of_account": round(risk_percent, 2),
            "dollars_until_profile_limit": round(max(0.0, request.account_size * profile_limit / 100 - request.amount_at_risk), 2),
            "premium_per_contract": premium or None,
            "contracts": contracts if is_option else None,
            "notional_premium": round(premium * contracts * 100, 2) if is_option and premium else None,
            "breakeven_basis": breakeven_basis,
        },
        agent_docket=[
            {
                "name": "Setup Agent",
                "score": setup_score,
                "read": "Constructive" if setup_score >= 70 else "Incomplete",
                "focus": "Is the trade idea clear enough to review?",
                "evidence": "The current check can evaluate structure and sizing, but it does not yet see a live chart trend, support/resistance, or volume confirmation.",
                "why_it_matters": "A contract can look attractive because of payoff convexity, but the setup still needs an invalidation level. Without that, losses become emotional instead of rule-based.",
                "next_question": "What exact stock price, indicator break, or thesis failure would make this setup no longer valid?",
            },
            {
                "name": "Options Risk Agent",
                "score": options_structure,
                "read": "Fragile" if options_structure < 60 else "Usable",
                "focus": "Can the contract survive time, breakeven, and volatility pressure?",
                "evidence": f"The contract has {calendar_days} calendar day(s), about {trading_days} trading day(s), and a breakeven near ${breakeven:g}. Liquidity is marked {liquidity_risk.lower()} from the available contract fields.",
                "why_it_matters": "For a long option, being directionally right is not enough. The move has to be large enough and fast enough to outrun theta decay and any IV compression.",
                "next_question": "What premium, bid/ask spread, implied volatility, and earnings date should be attached before trusting this read?",
            },
            {
                "name": "Sizing Agent",
                "score": behavior_score,
                "read": "Personal warning" if risk_percent > profile_limit else "Aligned",
                "focus": "Does this fit the user's guardrails?",
                "evidence": f"The planned risk uses {risk_percent:.1f}% of the account versus a {profile_limit:.1f}% profile limit. That is ${amount_above_profile:.0f} above the profile limit." if amount_above_profile else f"The planned risk uses {risk_percent:.1f}% of the account and stays inside the {profile_limit:.1f}% profile limit.",
                "why_it_matters": "Sizing is the part the user controls most. Good analysis does not matter if one trade can damage the account enough to change future decisions.",
                "next_question": "Would this same idea still be worth reviewing at half size?",
            },
            {
                "name": "Event/IV Agent",
                "score": market_context,
                "read": "Missing live context",
                "focus": "Could an event or volatility regime dominate the option price?",
                "evidence": "Live IV rank, option chain, earnings date, sector trend, and index context are not attached yet, so this agent refuses to pretend it knows the volatility setup.",
                "why_it_matters": "Earnings and high-IV environments can make an option lose value even when the stock moves in the expected direction.",
                "next_question": "Is this trade near earnings or another catalyst, and is IV unusually high compared with its own history?",
            },
            {
                "name": "Risk Manager",
                "score": max(35, min(90, round((setup_score + options_structure + behavior_score + market_context) / 4))),
                "read": "Reduce size" if risk_percent > profile_limit else "Plan first",
                "focus": "What should slow the user down before committing?",
                "evidence": f"The main tension is {weakest_link.lower()}. Agreement is {agent_agreement}/100 because the setup score, option structure, and sizing score do not all say the same thing.",
                "why_it_matters": "A useful risk review should expose disagreement. If every agent sounds confident, the app is probably hiding uncertainty.",
                "next_question": "What is the plan if the option drops 50% before the stock thesis is clearly invalidated?",
            },
        ],
        agreement_map={
            "agree": [
                f"The maximum defined loss is ${request.amount_at_risk:.0f}, so the downside is measurable before the trade is considered.",
                f"The contract has {calendar_days} calendar day(s) left, which makes time pressure visible instead of hidden.",
            ],
            "disagree": [
                f"The modeled breakeven requires about a {required_move}% move, but live premium and IV are not connected yet.",
                f"Sizing uses {risk_percent:.1f}% of the account; that can be the limiting factor even if the direction thesis is reasonable.",
            ],
            "main_conflict": f"{weakest_link} is the current weakest link.",
        },
        questions=[
            "What exact price or condition invalidates this trade?",
            "Would the trade still make sense at half the size?",
            "Are you comfortable with the full premium going to zero?",
            f"Does the planned hold ({selected_hold_days} day(s)) fit the expiration window ({calendar_days} calendar day(s))?",
        ],
        contract_label={
            "max_loss": round(request.amount_at_risk, 2),
            "account_risk_pct": round(risk_percent, 2),
            "breakeven": breakeven,
            "days_left": trading_days,
            "required_move_pct": required_move,
            "theta_risk": theta_risk,
            "iv_event_risk": event_risk,
            "difficulty": difficulty,
            "premium": premium or None,
            "contracts": contracts if is_option else None,
            "spread_pct": spread_pct,
            "liquidity_risk": liquidity_risk,
        },
        setup_debate={
            "bull_case": "The setup can be worth reviewing if price context, timing, and risk budget are aligned.",
            "bear_case": f"The contract still needs a clean move through the ${breakeven:g} breakeven area while time decay, spread cost, and volatility changes can work against the premium.",
            "risk_judge": f"{weakest_link} matters most here. A reasonable thesis can still be a poor structure if max loss or timing is uncomfortable.",
        },
        contract_snapshot={
            "option_side": option_side,
            "strike": request.strike,
            "expiration": request.expiration,
            "expiration_source": request.expiration_source,
            "premium": premium or None,
            "contracts": contracts if is_option else None,
            "bid": request.bid,
            "ask": request.ask,
            "mid": mid_price,
            "spread_pct": spread_pct,
            "implied_volatility": request.implied_volatility,
            "open_interest": request.open_interest,
            "volume": request.contract_volume,
            "underlying_price": request.underlying_price,
        },
        data_quality={
            "has_underlying_quote": request.underlying_price is not None,
            "has_real_premium": bool(premium),
            "has_bid_ask": request.bid is not None and request.ask is not None,
            "has_iv": request.implied_volatility is not None,
            "has_liquidity": request.open_interest is not None or request.contract_volume is not None,
            "missing": [
                label
                for label, missing in [
                    ("underlying quote", request.underlying_price is None),
                    ("premium", not bool(premium)),
                    ("bid/ask", request.bid is None or request.ask is None),
                    ("implied volatility", request.implied_volatility is None),
                    ("open interest/volume", request.open_interest is None and request.contract_volume is None),
                ]
                if missing
            ],
        },
    )


def normalize_option_side(option_side: str | None, trade_type: str) -> str:
    clean = str(option_side or "").strip().lower()
    if clean in {"call", "put"}:
        return clean
    return "put" if "Put" in trade_type else "call"


def midpoint(bid: float | None, ask: float | None) -> float | None:
    if bid is None or ask is None or ask <= 0:
        return None
    if bid < 0 or ask < bid:
        return None
    return round((bid + ask) / 2, 4)
