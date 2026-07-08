const API_RE = /\/(market|trade-check|saved-checks|chat|extract-contract)(\/|\?|$)/;

async function installBackendMocks(page) {
  await page.route(API_RE, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === "/market/providers") {
      return fulfill(route, {
        status: "partial",
        strategy: "qa_manual_delayed",
        capabilities: [
          {
            provider: "qa-market",
            configured: true,
            status: "active",
            fields: ["Quote", "News", "Reference-only options", "Manual upload"],
            missing: ["Live OPRA options", "Provider Greeks"],
            notes: "QA mode uses delayed/manual context."
          }
        ],
        data_quality_labels: ["Full", "Delayed", "Estimated", "Manual", "Missing"],
        message: "QA mode labels delayed, estimated, manual, and missing fields explicitly."
      });
    }

    if (path === "/market/search") {
      return fulfill(route, {
        items: [
          { symbol: "ACHR", name: "Archer Aviation Inc.", exchange: "NYSE", type: "stock", source: "qa" },
          { symbol: "AAPL", name: "Apple Inc.", exchange: "NASDAQ", type: "stock", source: "qa" }
        ]
      });
    }

    if (path.startsWith("/market/quote/")) {
      return fulfill(route, {
        symbol: symbolFromPath(path),
        price: 9.84,
        change: 0.18,
        changePercentage: 1.86,
        dataQuality: "qa-delayed"
      });
    }

    if (path.startsWith("/market/profile/")) {
      return fulfill(route, {
        symbol: symbolFromPath(path),
        companyName: "Archer Aviation Inc.",
        sector: "Industrials",
        industry: "Aerospace"
      });
    }

    if (path.startsWith("/market/news/")) {
      return fulfill(route, { items: [] });
    }

    if (path.startsWith("/market/earnings/")) {
      return fulfill(route, {
        symbol: symbolFromPath(path),
        date: null,
        status: "missing",
        message: "No earnings date attached in QA smoke mode."
      });
    }

    if (path.startsWith("/market/options/expirations/")) {
      return fulfill(route, {
        ticker: symbolFromPath(path),
        status: "reference",
        message: "QA reference expirations only.",
        expirations: [futureIso(21), futureIso(35), futureIso(63)]
      });
    }

    if (path.startsWith("/market/options/chain/")) {
      const ticker = symbolFromPath(path);
      const expiration = url.searchParams.get("expiration") || futureIso(35);
      return fulfill(route, {
        ticker,
        status: "reference",
        message: "Reference contract symbols only. Premium, IV, bid/ask, OI, and volume remain user-entered.",
        contracts: [
          {
            contract_symbol: `${ticker}${expiration.replaceAll("-", "").slice(2)}C00010000`,
            contract_type: "call",
            strike_price: 10,
            expiration_date: expiration,
            moneynessLabel: "near"
          },
          {
            contract_symbol: `${ticker}${expiration.replaceAll("-", "").slice(2)}C00012000`,
            contract_type: "call",
            strike_price: 12,
            expiration_date: expiration,
            moneynessLabel: "otm"
          },
          {
            contract_symbol: `${ticker}${expiration.replaceAll("-", "").slice(2)}P00009000`,
            contract_type: "put",
            strike_price: 9,
            expiration_date: expiration,
            moneynessLabel: "near"
          }
        ]
      });
    }

    if (path.startsWith("/market/options-context/")) {
      return fulfill(route, {
        ticker: symbolFromPath(path),
        status: "partial",
        provider: "qa-reference",
        fields_pending: ["implied_volatility", "greeks", "bid_ask", "open_interest", "volume", "earnings_date", "live_premium"],
        message: "QA smoke mode has no live options feed attached."
      });
    }

    if (path === "/trade-check" && request.method() === "POST") {
      const body = JSON.parse(request.postData() || "{}");
      return fulfill(route, buildTradeCheckResponse(body));
    }

    if (path === "/saved-checks" && request.method() === "POST") {
      const body = JSON.parse(request.postData() || "{}");
      return fulfill(route, {
        id: "saved-qa-check",
        userId: body.user_id || "preview-user",
        tradeCheckId: body.trade_check_id || "qa-check",
        report: body.report || {},
        note: body.note || "",
        createdAt: new Date().toISOString()
      });
    }

    if (path.startsWith("/saved-checks/")) {
      return fulfill(route, []);
    }

    if (path.startsWith("/chat/threads/")) {
      return fulfill(route, []);
    }

    if (path === "/chat" && request.method() === "POST") {
      const body = JSON.parse(request.postData() || "{}");
      const report = body.current_report || {};
      const ticker = String(report.ticker || report.contractSnapshot?.ticker || "").toUpperCase();
      const strike = report.strike || report.contractSnapshot?.strike || report.decisionSnapshot?.strike;
      const expiration = report.expiration || report.contractSnapshot?.expiration;
      const tradeType = report.tradeType || report.trade_type || report.decisionSnapshot?.option_side || "selected option contract";
      const selectedSummary = ticker
        ? `QA smoke response: You selected ${ticker}${strike ? ` $${strike}` : ""} ${tradeType}${expiration ? ` expiring ${expiration}` : ""}. I can review that selected check, but live IV, Greeks, bid/ask, open interest, volume, earnings date, and current option price are missing unless the report supplies them.`
        : "QA smoke response: I can review the selected check, but live IV, Greeks, bid/ask, open interest, volume, earnings date, and current option price are missing unless the report supplies them.";
      return fulfill(route, {
        thread_id: "qa-thread",
        answer: selectedSummary,
        analysis_depth: "standard",
        mode: "qa",
        confidence: 0.74,
        missing_data: ["IV", "Greeks", "bid/ask", "open interest", "volume", "earnings date", "current option price"],
        risk_flags: ["missing live options data"],
        tools_used: [{ name: "retrieve_selected_trade" }, { name: "detect_missing_data" }],
        what_used: ["selected-trade retriever", "missing-data detector"],
        provider: "fallback",
        used_fallback: true,
        summary_cards: [
          { label: "Weakest link", value: "Liquidity Context", tone: "warn" },
          { label: "Max loss", value: "$125", tone: "risk" },
          { label: "DTE", value: "35d", tone: "neutral" }
        ],
        visual_blocks: [
          {
            type: "mini_table",
            title: "Watch next",
            rows: [
              ["First pressure", "Liquidity Context"],
              ["Missing proof", "bid/ask, IV, open interest"],
              ["Sizing test", "2% of account"]
            ]
          }
        ],
        suggested_prompts: ["Debate this setup", "What can break this trade?", "Check my position size"]
      });
    }

    if (path === "/extract-contract" && request.method() === "POST") {
      return fulfill(route, {
        status: "ok",
        provider: "qa-text-parser",
        model: "",
        message: "QA extraction read visible contract fields. Confirm before analysis.",
        confidence: 0.86,
        fields: {
          ticker: "ACHR",
          tickerName: "Archer Aviation Inc.",
          optionSide: "call",
          strike: "10",
          expiration: futureIso(35),
          premium: "1.25",
          contracts: "1"
        },
        missing_fields: [],
        missing_live_fields: ["bid", "ask", "implied_volatility", "open_interest", "contract_volume", "Greeks"],
        attachments: [["contract.png", "image/png"]]
      });
    }

    return fulfill(route, {});
  });
}

function collectBrowserErrors(page) {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

function filteredErrors(errors) {
  return errors
    .filter((message) => !message.includes("favicon"))
    .filter((message) => !message.includes("File not found"))
    .filter((message) => !message.includes("Expo Webpack"))
    .join("\n");
}

function fulfill(route, body, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body)
  });
}

function symbolFromPath(path) {
  return decodeURIComponent(path.split("/").filter(Boolean).pop() || "ACHR").toUpperCase();
}

function futureIso(days) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function buildTradeCheckResponse(body) {
  const ticker = String(body.ticker || "ACHR").toUpperCase();
  const premium = Number(body.premium || 5);
  const contracts = Number(body.contracts || 1);
  const strike = Number(body.strike || 10);
  const amountAtRisk = Number(body.amount_at_risk || premium * contracts * 100);
  const expiration = body.expiration || futureIso(35);
  const maxLoss = Math.round(amountAtRisk * 100) / 100;

  return {
    id: "qa-risk-check",
    ticker,
    trade_type: body.trade_type || "Call Option (Long)",
    title: `${ticker} QA Options Check`,
    subtitle: `$${strike} Strike - ${expiration} - ${body.timeframe || "1-2 Weeks"}`,
    badge: "Needs Review",
    setup_score: 68,
    risk_score: 5.8,
    agent_agreement: 64,
    methodology_label: "QA deterministic educational score",
    insight: "The structure has defined max loss, but the smoke data intentionally omits live options fields so the UI must stay honest.",
    strike,
    expiration,
    amount_at_risk: maxLoss,
    timeframe: body.timeframe || "1-2 Weeks",
    checks: [
      ["Sizing Discipline", "good"],
      ["Liquidity Context", "warn"],
      ["Volatility Context", "warn"],
      ["Risk Review", "warn"]
    ],
    agents: [
      ["Rule Coverage", 72, "good"],
      ["Evidence Completeness", 64, "good"],
      ["Unresolved Risk", 49, "risk"]
    ],
    scenarios: [
      ["Premium stress", "-50%", `-$${Math.round(maxLoss * 0.5)}`, "risk"],
      ["Small recovery", "+15%", `+$${Math.round(maxLoss * 0.15)}`, "good"],
      ["Upside sketch", "+75%", `+$${Math.round(maxLoss * 0.75)}`, "good"]
    ],
    overall_read: "Mixed evidence; missing live contract data limits coverage",
    weakest_link: "Liquidity Context",
    risk_posture: "Mixed",
    decision_snapshot: {
      setup_quality: 68,
      options_structure: 56,
      risk_budget_used: 2,
      profile_risk_limit: 2,
      review_gap: "Medium",
      agent_disagreement: "Medium",
      review_status: "Needs Review",
      calendar_days_to_expiration: 35,
      selected_hold_days: 9,
      hold_vs_expiration: "Room available",
      modeled_breakeven: strike + premium,
      option_side: body.option_side || "call",
      premium,
      contracts,
      liquidity_risk: "Unknown"
    },
    risk_math: {
      capital_at_risk: maxLoss,
      max_loss: maxLoss,
      half_premium_drawdown: -Math.round(maxLoss * 0.5),
      amount_above_profile: 0,
      breakeven: strike + premium,
      breakeven_price: strike + premium,
      required_move_to_breakeven_pct: 4.2,
      required_move_basis: "underlying_to_breakeven",
      trading_days_left: 25,
      calendar_days_left: 35,
      planned_hold_days: 9,
      risk_percent_of_account: 2,
      dollars_until_profile_limit: 0,
      premium_per_contract: premium,
      contracts,
      notional_premium: maxLoss,
      breakeven_basis: "premium"
    },
    agent_docket: [
      {
        name: "Setup Agent",
        score: 68,
        read: "Incomplete",
        focus: "Is the trade idea clear enough to review?",
        evidence: "QA smoke mode supplies structure and sizing but not live chart context.",
        why_it_matters: "A defined loss still needs an invalidation plan.",
        next_question: "What price action would prove this thesis wrong?"
      },
      {
        name: "Options Risk Agent",
        score: 56,
        read: "Fragile",
        focus: "Can the contract survive time, breakeven, and volatility pressure?",
        evidence: "Live IV, Greeks, bid/ask, open interest, volume, earnings date, and current option price are intentionally missing.",
        why_it_matters: "The option can lose value even if the stock moves in the expected direction.",
        next_question: "What live chain fields can you attach before trusting this read?"
      },
      {
        name: "Risk Manager",
        score: 64,
        read: "Plan first",
        focus: "What should slow the user down before committing?",
        evidence: "The main tension is liquidity context.",
        why_it_matters: "The app should surface uncertainty instead of hiding it.",
        next_question: "Would this idea still be acceptable at half size?"
      }
    ],
    agreement_map: {
      agree: ["The maximum loss is defined by premium paid.", "The expiration is visible."],
      disagree: ["Live options fields are missing.", "Liquidity cannot be verified from QA data."],
      main_conflict: "Liquidity Context is the current weakest link."
    },
    questions: [
      "What invalidates this trade?",
      "Would this still make sense at half size?",
      "Can you confirm bid/ask, IV, open interest, volume, and earnings date?"
    ],
    contract_label: {
      max_loss: maxLoss,
      account_risk_pct: 2,
      breakeven: strike + premium,
      days_left: 25,
      required_move_pct: 4.2,
      theta_risk: "Medium",
      iv_event_risk: "Missing",
      difficulty: "Intermediate",
      premium,
      contracts,
      spread_pct: null,
      liquidity_risk: "Unknown"
    },
    setup_debate: {
      bull_case: "The defined-risk structure makes the downside measurable.",
      bear_case: "The contract still lacks live IV, Greeks, bid/ask, open interest, volume, earnings date, and current option price.",
      risk_judge: "This is reviewable only as partial-data education until live contract fields are attached."
    },
    contract_snapshot: {
      option_side: body.option_side || "call",
      strike,
      expiration,
      expiration_source: body.expiration_source || "manual",
      premium,
      contracts,
      bid: null,
      ask: null,
      mid: null,
      spread_pct: null,
      implied_volatility: null,
      open_interest: null,
      volume: null,
      underlying_price: body.underlying_price || null
    },
    data_quality: {
      has_underlying_quote: Boolean(body.underlying_price),
      has_real_premium: Boolean(premium),
      has_bid_ask: false,
      has_iv: false,
      has_liquidity: false,
      missing: ["bid/ask", "implied volatility", "Greeks", "open interest", "volume", "earnings date", "current option price"]
    }
  };
}

module.exports = {
  collectBrowserErrors,
  filteredErrors,
  installBackendMocks
};
