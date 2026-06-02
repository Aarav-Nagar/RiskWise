import React, { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Card } from "../components/Card";
import { ErrorCard, Header, PrimaryButton, ScreenScroll, sharedText } from "../components/Shared";
import { getMarketBundle, getOptionsChain, getOptionsExpirations, searchMarketSymbols } from "../services/apiClient";
import { palette } from "../theme/theme";

const popularSymbols = ["AAPL", "NVDA", "SPY", "MSFT", "QQQ"];

const localSymbols = [
  ["AAPL", "Apple Inc.", "NASDAQ"],
  ["NVDA", "NVIDIA Corporation", "NASDAQ"],
  ["SPY", "SPDR S&P 500 ETF Trust", "NYSE Arca"],
  ["MSFT", "Microsoft Corporation", "NASDAQ"],
  ["QQQ", "Invesco QQQ Trust", "NASDAQ"],
  ["TSLA", "Tesla Inc.", "NASDAQ"],
  ["AMD", "Advanced Micro Devices Inc.", "NASDAQ"],
  ["AMZN", "Amazon.com Inc.", "NASDAQ"],
  ["META", "Meta Platforms Inc.", "NASDAQ"],
  ["GOOGL", "Alphabet Inc.", "NASDAQ"],
  ["ACHR", "Archer Aviation Inc.", "NYSE"],
  ["RKLB", "Rocket Lab USA Inc.", "NASDAQ"],
  ["SOFI", "SoFi Technologies Inc.", "NASDAQ"],
  ["HOOD", "Robinhood Markets Inc.", "NASDAQ"],
  ["PLTR", "Palantir Technologies Inc.", "NASDAQ"],
  ["RIVN", "Rivian Automotive Inc.", "NASDAQ"],
  ["COIN", "Coinbase Global Inc.", "NASDAQ"],
  ["SMCI", "Super Micro Computer Inc.", "NASDAQ"],
  ["MARA", "MARA Holdings Inc.", "NASDAQ"],
  ["IONQ", "IonQ Inc.", "NYSE"],
  ["QBTS", "D-Wave Quantum Inc.", "NYSE"],
  ["ASTS", "AST SpaceMobile Inc.", "NASDAQ"]
].map(([symbol, name, exchange]) => ({ symbol, name, exchange, source: "local" }));

const flowChoices = [
  {
    key: "option",
    accent: palette.green,
    icon: "document-text-outline",
    title: "Option Contract",
    subtitle: "I know the contract details and want to evaluate it.",
    body: "Use this when strike, expiration, premium, and size are already known."
  },
  {
    key: "stock",
    accent: palette.blue,
    icon: "trending-up-outline",
    title: "Stock Idea",
    subtitle: "I have a ticker idea and want to explore option structures.",
    body: "RiskWise suggests structures first, then moves into contract details."
  },
  {
    key: "screenshot",
    accent: "#7C3AED",
    icon: "camera-outline",
    title: "Screenshot",
    subtitle: "I have a contract screenshot from a trading platform.",
    body: "Mock extraction reads the image, asks you to confirm, then runs the same check."
  }
];

const directions = [
  ["bullish", "Bullish", "I expect the price to go up", "thumbs-up-outline"],
  ["bearish", "Bearish", "I expect the price to go down", "trending-down-outline"],
  ["neutral", "Neutral", "I expect sideways / no big move", "remove-circle-outline"],
  ["not_sure", "Not sure", "I'm unsure about direction", "help-circle-outline"]
];

const optionStructures = [
  ["call", "Call", "Right to buy"],
  ["put", "Put", "Right to sell"],
  ["call_spread", "Call Spread", "Buy a call, sell a call"],
  ["put_spread", "Put Spread", "Buy a put, sell a put"]
];

const horizons = [
  ["short", "Short term", "1-4 weeks"],
  ["medium", "Medium term", "1-3 months"],
  ["long", "Long term", "3+ months"]
];

const tolerances = [
  ["conservative", "Conservative", "Lower risk, smaller potential return"],
  ["balanced", "Balanced", "Moderate risk and reward"],
  ["aggressive", "Aggressive", "Higher risk, higher potential return"]
];

const platforms = ["Robinhood", "Webull", "Thinkorswim", "Fidelity"];
const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const dayLabels = ["S", "M", "T", "W", "T", "F", "S"];

export function CheckScreen({ draft, setDraft, onCheck, loading, error }) {
  const [flow, setFlow] = useState("start");
  const [step, setStep] = useState(1);
  const [selectedTicker, setSelectedTicker] = useState(() => symbolToItem(draft.ticker, draft.tickerName, draft.tickerExchange));
  const [tickerQuery, setTickerQuery] = useState(draft.ticker || "");
  const [tickerResults, setTickerResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [market, setMarket] = useState(null);
  const [expirations, setExpirations] = useState([]);
  const [contractReferences, setContractReferences] = useState([]);
  const [contractProviderMessage, setContractProviderMessage] = useState("");
  const [visibleMonth, setVisibleMonth] = useState(startOfMonth(parseDate(draft.expiration) || addDays(new Date(), 30)));
  const [runningProgress, setRunningProgress] = useState(0);
  const [localReport, setLocalReport] = useState(null);
  const [extractionStep, setExtractionStep] = useState(1);

  const calculations = useMemo(() => buildRiskMath(draft), [draft]);
  const optionValidation = useMemo(() => validateOptionContract(draft, selectedTicker, calculations), [draft, selectedTicker, calculations]);

  useEffect(() => {
    const query = tickerQuery.trim();
    let cancelled = false;

    if (!query) {
      setTickerResults([]);
      return undefined;
    }

    setSearching(true);
    const timeout = setTimeout(async () => {
      try {
        const remoteRows = await searchMarketSymbols(query);
        if (!cancelled) {
          setTickerResults(buildSearchResults(query, remoteRows));
        }
      } catch {
        if (!cancelled) {
          setTickerResults(buildSearchResults(query, []));
        }
      } finally {
        if (!cancelled) {
          setSearching(false);
        }
      }
    }, 160);

    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [tickerQuery]);

  useEffect(() => {
    const symbol = selectedTicker?.symbol;
    if (!symbol) {
      setMarket(null);
      setExpirations([]);
      return undefined;
    }

    let cancelled = false;
    Promise.allSettled([getMarketBundle(symbol), getOptionsExpirations(symbol)]).then(([bundleResult, expirationsResult]) => {
      if (cancelled) return;
      const bundle = bundleResult.status === "fulfilled" ? bundleResult.value : null;
      const options = expirationsResult.status === "fulfilled" ? expirationsResult.value : null;
      setMarket(bundle);
      setExpirations(Array.isArray(options?.expirations) ? options.expirations.slice(0, 8) : []);
      if (bundle?.quote?.price) {
        updateDraft({ underlyingPrice: String(bundle.quote.price) });
      }
    });

    return () => {
      cancelled = true;
    };
  }, [selectedTicker?.symbol]);

  useEffect(() => {
    const symbol = selectedTicker?.symbol;
    if (!symbol || !draft.expiration) {
      setContractReferences([]);
      setContractProviderMessage("");
      return undefined;
    }
    let cancelled = false;
    getOptionsChain({ ticker: symbol, expiration: draft.expiration })
      .then((chain) => {
        if (cancelled) return;
        const rows = Array.isArray(chain?.contracts) ? chain.contracts : [];
        setContractReferences(rows.slice(0, 80));
        setContractProviderMessage(chain?.message || "");
      })
      .catch(() => {
        if (!cancelled) {
          setContractReferences([]);
          setContractProviderMessage("");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedTicker?.symbol, draft.expiration]);

  function updateDraft(updates) {
    setDraft((current) => ({ ...current, ...updates }));
  }

  function chooseFlow(nextFlow) {
    setFlow(nextFlow);
    setStep(1);
    setLocalReport(null);
    setRunningProgress(0);
    setExtractionStep(1);
  }

  function selectTicker(item) {
    const normalized = {
      symbol: normalizeSymbol(item.symbol),
      name: item.name || `${normalizeSymbol(item.symbol)} selected ticker`,
      exchange: item.exchange || "US",
      source: item.source || "search"
    };
    setSelectedTicker(normalized);
    setTickerQuery(normalized.symbol);
    setTickerResults([]);
    updateDraft({
      ticker: normalized.symbol,
      tickerName: normalized.name,
      tickerExchange: normalized.exchange,
      tickerSource: normalized.source
    });
  }

  function chooseStructure(structure) {
    updateDraft({
      structure,
      optionSide: structure.includes("put") ? "put" : "call",
      tradeType: tradeTypeFromStructure(structure)
    });
  }

  function chooseStrategy(strategy) {
    const nextExpiration = estimateExpirationFromHorizon(draft.timeHorizon || "medium");
    const price = Number(draft.underlyingPrice || market?.quote?.price || 100);
    const side = strategy.structure.includes("put") ? "put" : "call";
    const strike = side === "put" ? Math.round(price * 0.97) : Math.round(price * 1.03);
    updateDraft({
      direction: strategy.direction,
      structure: strategy.structure,
      optionSide: side,
      tradeType: tradeTypeFromStructure(strategy.structure),
      expiration: nextExpiration,
      expirationSource: "strategy_estimate",
      strike: String(strike),
      premium: String(strategy.premium),
      bid: "",
      ask: "",
      impliedVolatility: "",
      openInterest: "",
      contractVolume: "",
      contracts: "1",
      amountAtRisk: String(Math.round(Number(strategy.premium) * 100)),
      timeframe: horizonToTimeframe(draft.timeHorizon || "medium")
    });
    setFlow("option");
    setStep(4);
  }

  function setNumericField(field, value) {
    const clean = String(value || "").replace(/[^0-9.]/g, "");
    const updates = { [field]: clean };
    const premium = Number(field === "premium" ? clean : draft.premium || 0);
    const contracts = Number(field === "contracts" ? clean : draft.contracts || 0);
    if (premium > 0 && contracts > 0) {
      updates.amountAtRisk = String(Math.round(premium * contracts * 100));
    }
    updateDraft(updates);
  }

  function adjustContracts(delta) {
    const next = Math.max(1, Number(draft.contracts || 1) + delta);
    setNumericField("contracts", String(next));
  }

  async function runRiskCheck() {
    if (!validateOptionContract(draft, selectedTicker, calculations).ready || loading) {
      return;
    }
    setFlow("running");
    setRunningProgress(28);
    try {
      const report = await onCheck({ stayOnCheck: true });
      setRunningProgress(100);
      setLocalReport(buildLocalResult(report, draft, selectedTicker, calculations));
      setTimeout(() => setFlow("results"), 250);
    } catch {
      setFlow("option");
      setStep(6);
    }
  }

  function mockScreenshotUpload() {
    const extracted = {
      ticker: "AAPL",
      tickerName: "Apple Inc.",
      tickerExchange: "NASDAQ",
      direction: "bullish",
      structure: "call",
      optionSide: "call",
      tradeType: "Call Option (Long)",
      expiration: estimateExpirationFromHorizon("short"),
      expirationSource: "screenshot_mock",
      strike: "200",
      premium: "2.15",
      bid: "2.10",
      ask: "2.20",
      impliedVolatility: "22.4",
      openInterest: "12345",
      contractVolume: "8210",
      contracts: "1",
      underlyingPrice: "197.02",
      amountAtRisk: "215",
      timeframe: "1-2 Weeks"
    };
    setSelectedTicker(symbolToItem("AAPL", "Apple Inc.", "NASDAQ"));
    setTickerQuery("AAPL");
    updateDraft(extracted);
    setExtractionStep(2);
  }

  if (flow === "option") {
    return (
      <ScreenScroll>
        <FlowTopBar title="Build Your Trade" step={step} total={6} onBack={() => (step === 1 ? chooseFlow("start") : setStep(step - 1))} />
        {step === 1 && (
          <TickerStep
            title="Select Ticker"
            subtitle="Enter the underlying stock or ETF."
            query={tickerQuery}
            setQuery={(text) => {
              setTickerQuery(text);
              setSelectedTicker(null);
            }}
            results={tickerResults}
            searching={searching}
            selectedTicker={selectedTicker}
            market={market}
            onSelect={selectTicker}
            onContinue={() => setStep(2)}
          />
        )}
        {step === 2 && (
          <ChoiceStep
            title="Choose Direction"
            subtitle="What direction is your trade based on?"
            value={draft.direction || "bullish"}
            options={directions}
            onSelect={(direction) => updateDraft({ direction })}
            onContinue={() => setStep(3)}
          />
        )}
        {step === 3 && (
          <ChoiceStep
            title="Select Option Type"
            subtitle="What type of option are you considering?"
            value={draft.structure || "call"}
            options={optionStructures}
            onSelect={chooseStructure}
            onContinue={() => setStep(4)}
          />
        )}
        {step === 4 && (
          <ExpirationStep
            draft={draft}
            expirations={expirations}
            visibleMonth={visibleMonth}
            setVisibleMonth={setVisibleMonth}
            onSelect={(expiration, source = "calendar") => updateDraft({ expiration, expirationSource: source })}
            onContinue={() => setStep(5)}
          />
        )}
        {step === 5 && (
          <ContractDetailsStep
            draft={draft}
            setNumericField={setNumericField}
            validation={optionValidation}
            contractReferences={contractReferences}
            providerMessage={contractProviderMessage}
            onSelectContract={(contract) => {
              if (!contract) return;
              updateDraft({
                strike: String(contract.strike_price || contract.strike || draft.strike || ""),
                optionSide: contract.contract_type || draft.optionSide,
                structure: contract.contract_type || draft.structure,
                tradeType: tradeTypeFromStructure(contract.contract_type || draft.structure),
                contractSymbol: contract.contract_symbol || contract.ticker || "",
                expiration: contract.expiration_date || draft.expiration,
                expirationSource: "market_contract_reference"
              });
            }}
            onContinue={() => setStep(6)}
          />
        )}
        {step === 6 && (
          <SizeStep
            draft={draft}
            calculations={calculations}
            validation={optionValidation}
            setNumericField={setNumericField}
            setMaxRiskRule={(value) => {
              const percent = Number(String(value || "").replace(/[^0-9.]/g, ""));
              if (percent > 0) {
                updateDraft({ riskBudget: Math.round(Number(draft.accountSize || 0) * percent / 100) });
              }
            }}
            adjustContracts={adjustContracts}
            onSubmit={runRiskCheck}
            loading={loading}
            error={error}
          />
        )}
      </ScreenScroll>
    );
  }

  if (flow === "stock") {
    return (
      <ScreenScroll>
        <FlowTopBar title="Explore An Idea" step={step} total={5} onBack={() => (step === 1 ? chooseFlow("start") : setStep(step - 1))} />
        {step === 1 && (
          <TickerStep
            title="What's the stock?"
            subtitle="Enter the stock or ETF you want to explore."
            query={tickerQuery}
            setQuery={(text) => {
              setTickerQuery(text);
              setSelectedTicker(null);
            }}
            results={tickerResults}
            searching={searching}
            selectedTicker={selectedTicker}
            market={market}
            onSelect={selectTicker}
            onContinue={() => setStep(2)}
          />
        )}
        {step === 2 && (
          <ChoiceStep
            title="What's your outlook?"
            subtitle="Help us understand your main expectation."
            value={draft.direction || "bullish"}
            options={directions}
            onSelect={(direction) => updateDraft({ direction })}
            onContinue={() => setStep(3)}
          />
        )}
        {step === 3 && (
          <ChoiceStep
            title="Time Horizon"
            subtitle="What's your expected timeframe?"
            value={draft.timeHorizon || "medium"}
            options={horizons}
            onSelect={(timeHorizon) => updateDraft({ timeHorizon, timeframe: horizonToTimeframe(timeHorizon) })}
            onContinue={() => setStep(4)}
          />
        )}
        {step === 4 && (
          <ChoiceStep
            title="Risk Tolerance"
            subtitle="How much risk are you comfortable with?"
            value={draft.riskTolerance || "balanced"}
            options={tolerances}
            onSelect={(riskTolerance) => updateDraft({ riskTolerance })}
            onContinue={() => setStep(5)}
          />
        )}
        {step === 5 && (
          <StrategyStep
            ticker={selectedTicker?.symbol || draft.ticker}
            direction={draft.direction || "bullish"}
            riskTolerance={draft.riskTolerance || "balanced"}
            horizon={draft.timeHorizon || "medium"}
            onSelect={chooseStrategy}
          />
        )}
      </ScreenScroll>
    );
  }

  if (flow === "screenshot") {
    return (
      <ScreenScroll>
        <FlowTopBar title="Screenshot Flow" step={extractionStep} total={5} onBack={() => (extractionStep === 1 ? chooseFlow("start") : setExtractionStep(extractionStep - 1))} />
        {extractionStep === 1 && <UploadStep onUpload={mockScreenshotUpload} />}
        {extractionStep === 2 && <ExtractionStep onContinue={() => setExtractionStep(3)} />}
        {extractionStep === 3 && <ExtractedReviewStep draft={draft} onEdit={() => { setFlow("option"); setStep(5); }} onContinue={() => setExtractionStep(4)} />}
        {extractionStep === 4 && <ConfirmContractStep draft={draft} calculations={calculations} onContinue={() => setExtractionStep(5)} />}
        {extractionStep === 5 && <RunningStep progress={82} onContinue={runRiskCheck} loading={loading} error={error} buttonLabel="View Investigation Results" />}
      </ScreenScroll>
    );
  }

  if (flow === "running") {
    return (
      <ScreenScroll>
        <RunningStep progress={runningProgress} loading={loading} error={error} buttonLabel="Finalizing..." />
      </ScreenScroll>
    );
  }

  if (flow === "results") {
    return (
      <ScreenScroll>
        <InvestigationResults
          result={localReport || buildLocalResult(null, draft, selectedTicker, calculations)}
          onBack={() => chooseFlow("start")}
          onDebate={() => setFlow("debate")}
          onIssue={() => setFlow("issue")}
        />
      </ScreenScroll>
    );
  }

  if (flow === "debate") {
    return (
      <ScreenScroll>
        <CommitteeResults result={localReport || buildLocalResult(null, draft, selectedTicker, calculations)} onBack={() => setFlow("results")} />
      </ScreenScroll>
    );
  }

  if (flow === "issue") {
    return (
      <ScreenScroll>
        <IssueDeepDive result={localReport || buildLocalResult(null, draft, selectedTicker, calculations)} onBack={() => setFlow("results")} />
      </ScreenScroll>
    );
  }

  return (
    <ScreenScroll>
      <Header title={`Good morning, ${draft.user}`} subtitle="Choose how much information you already have." />
      <Card style={styles.snapshot}>
        <View style={styles.rowBetween}>
          <Text style={sharedText.cardLabel}>Account Snapshot</Text>
          <StatusPill label="OK" tone="good" />
        </View>
        <View style={styles.snapshotGrid}>
          <MiniStat label="Account Size" value={formatMoney(draft.accountSize)} />
          <MiniStat label="Risk Rule" value={`${riskRulePercent(draft)}% max`} />
        </View>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${Math.min(Number(draft.riskBudget || 0) / Number(draft.accountSize || 1) * 100 * 20, 100)}%` }]} />
        </View>
        <Text style={sharedText.microcopy}>RiskWise checks the contract before the story convinces you.</Text>
      </Card>
      <Card>
        <Text style={sharedText.sectionTitle}>How would you like to check a trade?</Text>
        {flowChoices.map((choice) => (
          <Pressable key={choice.key} style={styles.flowChoice} onPress={() => chooseFlow(choice.key)}>
            <View style={[styles.flowIcon, { backgroundColor: `${choice.accent}16` }]}>
              <Ionicons name={choice.icon} size={19} color={choice.accent} />
            </View>
            <View style={styles.flex}>
              <Text style={styles.flowTitle}>{choice.title}</Text>
              <Text style={styles.flowSubtitle}>{choice.subtitle}</Text>
              <Text style={styles.flowBody}>{choice.body}</Text>
            </View>
            <Ionicons name="chevron-forward" size={17} color={palette.muted} />
          </Pressable>
        ))}
      </Card>
    </ScreenScroll>
  );
}

function FlowTopBar({ title, step, total, onBack }) {
  return (
    <View style={styles.topBar}>
      <Pressable style={styles.roundButton} onPress={onBack}>
        <Ionicons name="chevron-back" size={18} color={palette.dark} />
      </Pressable>
      <View style={styles.topCenter}>
        <Text style={styles.stepCount}>{step} of {total}</Text>
        <Text style={styles.flowHeading}>{title}</Text>
      </View>
      <View style={styles.roundButtonGhost} />
    </View>
  );
}

function TickerStep({ title, subtitle, query, setQuery, results, searching, selectedTicker, market, onSelect, onContinue }) {
  const ready = Boolean(selectedTicker?.symbol);
  return (
    <View>
      <StepTitle title={title} subtitle={subtitle} />
      <SearchBox query={query} setQuery={setQuery} results={results} searching={searching} selectedTicker={selectedTicker} onSelect={onSelect} />
      <Text style={styles.miniLabel}>Popular</Text>
      <View style={styles.chipRow}>
        {popularSymbols.map((symbol) => (
          <Pressable key={symbol} style={styles.chip} onPress={() => onSelect(localSymbols.find((item) => item.symbol === symbol) || { symbol })}>
            <Text style={styles.chipText}>{symbol}</Text>
          </Pressable>
        ))}
      </View>
      {ready ? <TickerCard ticker={selectedTicker} market={market} /> : null}
      <PrimaryButton label="Continue" onPress={onContinue} disabled={!ready} />
    </View>
  );
}

function SearchBox({ query, setQuery, results, searching, selectedTicker, onSelect }) {
  const showResults = query.trim().length > 0 && (!selectedTicker || selectedTicker.symbol !== normalizeSymbol(query));
  return (
    <View style={styles.searchWrap}>
      <View style={styles.searchBox}>
        <Ionicons name="search-outline" size={17} color={palette.muted} />
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="Search ticker, e.g. AAPL"
          placeholderTextColor="#9AA5A0"
          autoCapitalize="characters"
          style={styles.searchInput}
        />
        {selectedTicker?.symbol ? <Ionicons name="checkmark-circle" size={18} color={palette.green} /> : null}
      </View>
      {showResults ? (
        <View style={styles.searchResults}>
          {searching ? <Text style={styles.dropdownEmpty}>Searching...</Text> : null}
          {!searching && results.length === 0 ? <Text style={styles.dropdownEmpty}>No matches yet. Try the exact ticker.</Text> : null}
          {results.map((item) => (
            <Pressable key={`${item.symbol}-${item.name}-${item.source}`} style={styles.resultRow} onPress={() => onSelect(item)}>
              <View style={styles.symbolAvatar}>
                <Text style={styles.symbolAvatarText}>{item.symbol.slice(0, 1)}</Text>
              </View>
              <View style={styles.flex}>
                <Text style={styles.resultSymbol}>{item.symbol}</Text>
                <Text style={styles.resultName} numberOfLines={1}>{item.name}</Text>
              </View>
              <Text style={styles.resultExchange}>{item.exchange || "US"}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function TickerCard({ ticker, market }) {
  const quote = market?.quote;
  const price = quote?.price || mockPrice(ticker.symbol);
  const change = quote?.changePercentage ?? quote?.change_percent ?? mockChange(ticker.symbol);
  return (
    <Card style={styles.tickerCard}>
      <View style={styles.symbolLogo}>
        <Text style={styles.symbolLogoText}>{ticker.symbol.slice(0, 1)}</Text>
      </View>
      <View style={styles.flex}>
        <Text style={styles.bigSymbol}>{ticker.symbol}</Text>
        <Text style={styles.resultName}>{ticker.name}</Text>
      </View>
      <View style={styles.priceBox}>
        <Text style={styles.priceText}>${Number(price).toFixed(2)}</Text>
        <Text style={styles.changeText}>{Number(change) >= 0 ? "+" : ""}{Number(change).toFixed(2)}%</Text>
      </View>
    </Card>
  );
}

function ChoiceStep({ title, subtitle, options, value, onSelect, onContinue }) {
  return (
    <View>
      <StepTitle title={title} subtitle={subtitle} />
      {options.map(([key, label, text, icon]) => (
        <SelectableRow key={key} active={value === key} title={label} subtitle={text} icon={icon || "ellipse-outline"} onPress={() => onSelect(key)} />
      ))}
      <PrimaryButton label="Continue" onPress={onContinue} />
    </View>
  );
}

function SelectableRow({ active, title, subtitle, icon, onPress }) {
  return (
    <Pressable style={[styles.selectable, active && styles.selectableActive]} onPress={onPress}>
      <View style={[styles.radio, active && styles.radioActive]}>
        <Ionicons name={active ? "checkmark" : icon} size={14} color={active ? "#FFFFFF" : palette.muted} />
      </View>
      <View style={styles.flex}>
        <Text style={styles.selectableTitle}>{title}</Text>
        <Text style={styles.selectableSubtitle}>{subtitle}</Text>
      </View>
      {active ? <Ionicons name="checkmark-circle" size={18} color={palette.green} /> : null}
    </Pressable>
  );
}

function ExpirationStep({ draft, expirations, visibleMonth, setVisibleMonth, onSelect, onContinue }) {
  const selected = parseDate(draft.expiration);
  const dte = selected ? dayDiff(new Date(), selected) : null;
  return (
    <View>
      <StepTitle title="Expiration" subtitle="Choose the expiration date." />
      <Pressable style={styles.dateSelector}>
        <View style={styles.rowCenter}>
          <Ionicons name="calendar-outline" size={17} color={palette.dark} />
          <View>
            <Text style={styles.dateText}>{selected ? displayDate(selected) : "Choose expiration"}</Text>
            <Text style={styles.dateSub}>{dte !== null ? `${Math.max(dte, 0)} calendar days left` : "Future dates only"}</Text>
          </View>
        </View>
        <Ionicons name="chevron-down" size={16} color={palette.muted} />
      </Pressable>
      {expirations.length ? (
        <View style={styles.suggestedDates}>
          {expirations.slice(0, 4).map((expiration) => (
            <Pressable key={expiration} style={[styles.dateChip, expiration === draft.expiration && styles.dateChipActive]} onPress={() => onSelect(expiration, "market_expiration")}>
              <Text style={[styles.dateChipText, expiration === draft.expiration && styles.dateChipTextActive]}>{shortDate(expiration)}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
      <MiniCalendar visibleMonth={visibleMonth} selected={selected} setVisibleMonth={setVisibleMonth} onSelect={(date) => onSelect(toIsoDate(date), "calendar")} />
      <PrimaryButton label="Continue" onPress={onContinue} disabled={!selected || dte < 0} />
    </View>
  );
}

function MiniCalendar({ visibleMonth, selected, setVisibleMonth, onSelect }) {
  const cells = buildCalendar(visibleMonth);
  const today = stripTime(new Date());
  return (
    <Card style={styles.calendarCard}>
      <View style={styles.calendarHeader}>
        <Pressable style={styles.calendarNav} onPress={() => setVisibleMonth(addMonths(visibleMonth, -1))}>
          <Ionicons name="chevron-back" size={15} color={palette.dark} />
        </Pressable>
        <Text style={styles.calendarTitle}>{monthNames[visibleMonth.getMonth()]} {visibleMonth.getFullYear()}</Text>
        <Pressable style={styles.calendarNav} onPress={() => setVisibleMonth(addMonths(visibleMonth, 1))}>
          <Ionicons name="chevron-forward" size={15} color={palette.dark} />
        </Pressable>
      </View>
      <View style={styles.weekRow}>
        {dayLabels.map((day) => <Text key={day} style={styles.weekLabel}>{day}</Text>)}
      </View>
      <View style={styles.daysGrid}>
        {cells.map(({ date, inMonth }) => {
          const disabled = date < today || !inMonth;
          const active = selected && toIsoDate(selected) === toIsoDate(date);
          return (
            <Pressable
              key={date.toISOString()}
              style={[styles.dayCell, active && styles.dayCellActive, disabled && styles.dayCellDisabled]}
              disabled={disabled}
              onPress={() => onSelect(date)}
            >
              <Text style={[styles.dayText, active && styles.dayTextActive]}>{date.getDate()}</Text>
            </Pressable>
          );
        })}
      </View>
    </Card>
  );
}

function ContractDetailsStep({ draft, setNumericField, validation, contractReferences = [], providerMessage = "", onSelectContract, onContinue }) {
  const requiredReady = !validation.strike && !validation.premium;
  const side = draft.optionSide || (draft.structure?.includes("put") ? "put" : "call");
  const referenceRows = contractReferences
    .filter((contract) => !side || contract.contract_type === side)
    .slice(0, 8);
  return (
    <View>
      <StepTitle title="Contract Details" subtitle="Enter the contract price and key details." />
      {referenceRows.length ? (
        <Card style={styles.referenceCard}>
          <View style={styles.rowBetween}>
            <View style={styles.flex}>
              <Text style={styles.referenceTitle}>Real contract references</Text>
              <Text style={styles.referenceSub}>Tap a strike to attach the exchange contract symbol. Premium and IV still need live quote access or manual entry.</Text>
            </View>
            <Ionicons name="shield-checkmark-outline" size={19} color={palette.green} />
          </View>
          <View style={styles.referenceGrid}>
            {referenceRows.map((contract) => {
              const active = Number(contract.strike_price) === Number(draft.strike) && contract.contract_type === side;
              return (
                <Pressable
                  key={contract.contract_symbol || `${contract.contract_type}-${contract.strike_price}`}
                  style={[styles.referenceChip, active && styles.referenceChipActive]}
                  onPress={() => onSelectContract?.(contract)}
                >
                  <Text style={[styles.referenceChipText, active && styles.referenceChipTextActive]}>
                    {contract.contract_type === "put" ? "P" : "C"} ${Number(contract.strike_price || 0).toFixed(0)}
                  </Text>
                  <Text style={[styles.referenceChipSub, active && styles.referenceChipTextActive]}>{contract.moneynessLabel || "reference"}</Text>
                </Pressable>
              );
            })}
          </View>
        </Card>
      ) : providerMessage ? (
        <Card style={styles.referenceCard}>
          <Text style={styles.referenceTitle}>Contract reference status</Text>
          <Text style={styles.referenceSub}>{providerMessage}</Text>
        </Card>
      ) : null}
      <FieldRow label="Strike Price" value={draft.strike} onChangeText={(value) => setNumericField("strike", value)} prefix="$" error={validation.strike} />
      <FieldRow label="Premium (Mid)" value={draft.premium} onChangeText={(value) => setNumericField("premium", value)} prefix="$" error={validation.premium} />
      <FieldRow label="Bid" value={draft.bid} onChangeText={(value) => setNumericField("bid", value)} prefix="$" />
      <FieldRow label="Ask" value={draft.ask} onChangeText={(value) => setNumericField("ask", value)} prefix="$" />
      <FieldRow label="IV (Implied Volatility)" value={draft.impliedVolatility} onChangeText={(value) => setNumericField("impliedVolatility", value)} suffix="%" />
      <FieldRow label="Open Interest" value={draft.openInterest} onChangeText={(value) => setNumericField("openInterest", value)} />
      <FieldRow label="Volume" value={draft.contractVolume} onChangeText={(value) => setNumericField("contractVolume", value)} />
      <Text style={styles.helperText}>Bid/ask helps us check liquidity and estimated cost. IV, open interest, and volume make the risk read stronger.</Text>
      <PrimaryButton label="Continue" onPress={onContinue} disabled={!requiredReady} />
    </View>
  );
}

function FieldRow({ label, value, onChangeText, prefix, suffix, error }) {
  const hasValue = String(value || "").length > 0;
  return (
    <View style={styles.fieldRow}>
      <View style={styles.fieldLabelWrap}>
        <Text style={styles.fieldLabel}>{label}</Text>
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </View>
      <View style={[styles.compactInput, error && styles.inputError]}>
        {prefix && hasValue ? <Text style={styles.inputAdornment}>{prefix}</Text> : null}
        <TextInput value={String(value || "")} onChangeText={onChangeText} keyboardType="decimal-pad" style={styles.compactTextInput} placeholder="Optional" placeholderTextColor="#9AA5A0" />
        {suffix && hasValue ? <Text style={styles.inputAdornment}>{suffix}</Text> : null}
      </View>
    </View>
  );
}

function SizeStep({ draft, calculations, validation, setNumericField, setMaxRiskRule, adjustContracts, onSubmit, loading, error }) {
  const tone = calculations.accountRiskPercent <= riskRulePercent(draft) ? "good" : calculations.accountRiskPercent <= riskRulePercent(draft) * 1.5 ? "warn" : "risk";
  return (
    <View>
      <StepTitle title="Size & Guardrails" subtitle="Set position size and review risk." />
      <View style={styles.stepperRow}>
        <View>
          <Text style={styles.fieldLabel}>Contracts</Text>
          <Text style={styles.helperText}>Each options contract controls 100 shares.</Text>
        </View>
        <View style={styles.stepper}>
          <Pressable style={styles.stepperButton} onPress={() => adjustContracts(-1)}><Text style={styles.stepperText}>-</Text></Pressable>
          <TextInput value={String(draft.contracts || "1")} onChangeText={(value) => setNumericField("contracts", value)} keyboardType="numeric" style={styles.stepperInput} />
          <Pressable style={styles.stepperButton} onPress={() => adjustContracts(1)}><Text style={styles.stepperText}>+</Text></Pressable>
        </View>
      </View>
      <FieldRow label="Account Size" value={String(draft.accountSize || "")} onChangeText={(value) => setNumericField("accountSize", value)} prefix="$" />
      <FieldRow label="Max Risk Rule" value={String(riskRulePercent(draft))} onChangeText={setMaxRiskRule} suffix="%" />
      <Card style={styles.mathCard}>
        <MetricGrid
          items={[
            ["Max Loss", formatMoney(calculations.maxLoss), tone],
            ["Account Risk", `${calculations.accountRiskPercent.toFixed(2)}%`, tone],
            ["Breakeven", `$${calculations.breakeven.toFixed(2)}`, "neutral"],
            ["DTE", `${Math.max(calculations.daysToExpiration, 0)} days`, calculations.daysToExpiration < 7 ? "warn" : "neutral"]
          ]}
        />
        <StatusPill
          label={tone === "good" ? `Within your ${riskRulePercent(draft)}% risk rule` : tone === "warn" ? "Slightly above your risk rule" : "Above your risk rule"}
          tone={tone}
        />
      </Card>
      <InsightList calculations={calculations} validation={validation} />
      {error ? <ErrorCard message="Could not generate this check. Try again." /> : null}
      <PrimaryButton label={loading ? "Reviewing..." : "Review Trade Check"} onPress={onSubmit} disabled={!validation.ready || loading} />
    </View>
  );
}

function StrategyStep({ ticker, direction, riskTolerance, horizon, onSelect }) {
  const strategies = buildStrategies(direction, riskTolerance, horizon);
  return (
    <View>
      <StepTitle title="Suggested Strategies" subtitle={`Based on your outlook for ${ticker || "the selected stock"}.`} />
      {strategies.map((strategy) => (
        <Card key={strategy.name} style={styles.strategyCard}>
          <View style={styles.rowBetween}>
            <View>
              <Text style={styles.strategyName}>{strategy.name}</Text>
              <Text style={styles.strategyWhy}>{strategy.why}</Text>
            </View>
            <StatusPill label={strategy.risk} tone={strategy.tone} />
          </View>
          <View style={styles.strategyFacts}>
            <MiniStat label="Max Profit" value={strategy.maxProfit} />
            <MiniStat label="Max Loss" value={strategy.maxLoss} />
          </View>
          <PrimaryButton label="Explore Strategy" onPress={() => onSelect(strategy)} />
        </Card>
      ))}
    </View>
  );
}

function UploadStep({ onUpload }) {
  return (
    <View>
      <StepTitle title="Upload Screenshot" subtitle="Upload a screenshot of your options contract." />
      <Pressable style={styles.uploadBox} onPress={onUpload}>
        <View style={styles.uploadIcon}>
          <Ionicons name="camera-outline" size={27} color="#7C3AED" />
        </View>
        <Text style={styles.uploadTitle}>Tap to upload</Text>
        <Text style={styles.uploadSub}>PNG, JPG - Max 10MB</Text>
      </Pressable>
      <Text style={styles.miniLabel}>Supported platforms</Text>
      <View style={styles.chipRow}>
        {platforms.map((platform) => <View key={platform} style={styles.platformChip}><Text style={styles.platformText}>{platform}</Text></View>)}
      </View>
      <Card style={styles.tipCard}>
        {["Include full contract details", "Make sure strike, expiration, and premium are visible", "Avoid blurry or cropped images"].map((tip) => (
          <View key={tip} style={styles.tipRow}>
            <Ionicons name="checkmark-circle-outline" size={15} color={palette.green} />
            <Text style={styles.tipText}>{tip}</Text>
          </View>
        ))}
      </Card>
    </View>
  );
}

function ExtractionStep({ onContinue }) {
  return (
    <View>
      <StepTitle title="Extracting Details..." subtitle="We're reading the screenshot and extracting contract details." />
      <Card style={styles.extractCard}>
        <View style={styles.progressRing}>
          <Ionicons name="scan-outline" size={28} color="#7C3AED" />
        </View>
        <Text style={styles.extractTitle}>Extracting...</Text>
        {["Reading text", "Identifying fields", "Verifying values"].map((item, index) => (
          <View key={item} style={styles.tipRow}>
            <Ionicons name={index < 2 ? "checkmark-circle" : "ellipse-outline"} size={15} color={index < 2 ? palette.green : palette.muted} />
            <Text style={styles.tipText}>{item}</Text>
          </View>
        ))}
      </Card>
      <PrimaryButton label="Review Extracted Details" onPress={onContinue} />
    </View>
  );
}

function ExtractedReviewStep({ draft, onEdit, onContinue }) {
  const rows = [
    ["Ticker", draft.ticker],
    ["Strategy", draft.tradeType],
    ["Expiration", displayDate(parseDate(draft.expiration))],
    ["Strike Price", `$${Number(draft.strike || 0).toFixed(2)}`],
    ["Premium", `$${Number(draft.premium || 0).toFixed(2)}`],
    ["Contracts", draft.contracts],
    ["Underlying Price", `$${Number(draft.underlyingPrice || 0).toFixed(2)}`]
  ];
  return (
    <View>
      <StepTitle title="Review Extracted Details" subtitle="Please confirm the extracted details." />
      <Card>
        {rows.map(([label, value]) => <KeyValue key={label} label={label} value={value} />)}
      </Card>
      <Pressable style={styles.secondaryButton} onPress={onEdit}>
        <Text style={styles.secondaryButtonText}>Edit Manually</Text>
      </Pressable>
      <PrimaryButton label="Confirm & Continue" onPress={onContinue} />
    </View>
  );
}

function ConfirmContractStep({ draft, calculations, onContinue }) {
  return (
    <View>
      <StepTitle title="Confirm Contract" subtitle="Everything looks good?" />
      <Card>
        <Text style={styles.bigSymbol}>{draft.ticker}</Text>
        <Text style={styles.resultName}>{draft.tradeType}</Text>
        <KeyValue label="Strike" value={`$${Number(draft.strike || 0).toFixed(2)}`} />
        <KeyValue label="Expiration" value={displayDate(parseDate(draft.expiration))} />
        <KeyValue label="Premium" value={`$${Number(draft.premium || 0).toFixed(2)}`} />
        <KeyValue label="Contracts" value={draft.contracts} />
        <KeyValue label="Max Loss" value={formatMoney(calculations.maxLoss)} />
      </Card>
      <Card style={styles.successCard}>
        <Text style={styles.successText}>Looks good. RiskWise will still treat extracted values as user-confirmed, not live market data.</Text>
      </Card>
      <PrimaryButton label="Continue to Analysis" onPress={onContinue} />
    </View>
  );
}

function RunningStep({ progress, onContinue, loading, error, buttonLabel }) {
  return (
    <View>
      <StepTitle title="Running Risk Check" subtitle="We're analyzing your trade with our AI committee." />
      <Card>
        {["Calculating key metrics", "Checking risk & liquidity", "AI agents analyzing", "Building investigation report", "Finalizing insights"].map((item, index) => (
          <View key={item} style={styles.timelineRow}>
            <View style={[styles.timelineDot, index <= Math.floor(progress / 22) && styles.timelineDotActive]} />
            <Text style={styles.tipText}>{item}</Text>
            {index <= Math.floor(progress / 22) ? <Ionicons name="checkmark" size={14} color={palette.green} /> : null}
          </View>
        ))}
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${Math.min(progress, 100)}%` }]} />
        </View>
        <Text style={sharedText.microcopy}>{Math.min(progress, 100)}%</Text>
      </Card>
      {error ? <ErrorCard message="Could not generate this check. Try again." /> : null}
      {onContinue ? <PrimaryButton label={loading ? "Analyzing..." : buttonLabel} onPress={onContinue} disabled={loading} /> : null}
    </View>
  );
}

function InvestigationResults({ result, onBack, onDebate, onIssue }) {
  return (
    <View>
      <FlowTopBar title="Trade Investigation" step={1} total={1} onBack={onBack} />
      <Card style={styles.heroCard}>
        <View style={styles.rowBetween}>
          <View>
            <Text style={styles.heroTitle}>{result.title}</Text>
            <Text style={styles.heroSub}>{result.subtitle}</Text>
          </View>
          <ScoreCircle value={result.score} />
        </View>
        <View style={styles.verdictBox}>
          <StatusDot tone={result.tone} />
          <View>
            <Text style={styles.verdictTitle}>{result.verdict}</Text>
            <Text style={styles.verdictSub}>{result.verdictSub}</Text>
          </View>
        </View>
      </Card>
      <MetricGrid
        items={[
          ["Max Loss", formatMoney(result.maxLoss), result.tone],
          ["Breakeven", `$${result.breakeven.toFixed(2)}`, "neutral"],
          ["Required Move", `${result.requiredMovePercent.toFixed(2)}%`, result.requiredMovePercent > 8 ? "warn" : "neutral"],
          ["Acct Risk", `${result.accountRiskPercent.toFixed(2)}%`, result.tone]
        ]}
      />
      <Card>
        <Text style={sharedText.sectionTitle}>Why RiskWise is hesitating</Text>
        {result.issues.map((issue) => (
          <Pressable key={issue.title} style={styles.issueRow} onPress={onIssue}>
            <View style={[styles.issueIcon, issue.tone === "risk" && styles.issueIconRisk, issue.tone === "warn" && styles.issueIconWarn]}>
              <Ionicons name={issue.icon} size={16} color={toneColor(issue.tone)} />
            </View>
            <View style={styles.flex}>
              <Text style={styles.issueTitle}>{issue.title}</Text>
              <Text style={styles.issueSub}>{issue.detail}</Text>
            </View>
            <StatusPill label={issue.label} tone={issue.tone} />
          </Pressable>
        ))}
      </Card>
      <Pressable style={styles.debateEntry} onPress={onDebate}>
        <View>
          <Text style={styles.strategyName}>Open Committee Debate</Text>
          <Text style={styles.resultName}>Bull, skeptic, risk judge, and risk manager discuss the setup.</Text>
        </View>
        <Ionicons name="chevron-forward" size={17} color={palette.green} />
      </Pressable>
      <Card style={styles.successCard}>
        <Text style={styles.successText}>Saved checks and coaching context can use this report. Educational only, not financial advice.</Text>
      </Card>
    </View>
  );
}

function CommitteeResults({ result, onBack }) {
  const agents = [
    ["Bull Analyst", "Structure aligns with the thesis, but only if price confirmation appears before theta eats the premium."],
    ["Skeptic", `${result.issues[0].title} is the weak link. A correct direction can still lose if the contract is too expensive.`],
    ["Risk Judge", `Account risk is ${result.accountRiskPercent.toFixed(2)}%. Sizing must be judged before conviction.`],
    ["Risk Manager", "The cleanest next step is defining what would invalidate the setup, not increasing exposure."]
  ];
  return (
    <View>
      <FlowTopBar title="Committee Debate" step={1} total={1} onBack={onBack} />
      <View style={styles.levelRow}>
        {["Easy", "Moderate", "Advanced"].map((level) => <StatusPill key={level} label={level} tone={level === "Moderate" ? "good" : "neutral"} />)}
      </View>
      <Card>
        <View style={styles.rowBetween}>
          <Text style={sharedText.sectionTitle}>Live Discussion</Text>
          <StatusPill label="Live" tone="risk" />
        </View>
        {agents.map(([name, text], index) => (
          <View key={name} style={styles.agentRow}>
            <View style={[styles.agentAvatar, { backgroundColor: ["#DDF8E6", "#DDEAFF", "#EFE5FF", "#FFF0CC"][index] }]}>
              <Text style={styles.agentInitials}>{name.split(" ").map((word) => word[0]).join("")}</Text>
            </View>
            <View style={styles.flex}>
              <Text style={styles.agentName}>{name}</Text>
              <Text style={styles.agentText}>{text}</Text>
            </View>
          </View>
        ))}
      </Card>
    </View>
  );
}

function IssueDeepDive({ result, onBack }) {
  const issue = result.issues[0];
  return (
    <View>
      <FlowTopBar title={issue.title} step={1} total={1} onBack={onBack} />
      <Card>
        <View style={styles.rowBetween}>
          <View>
            <Text style={styles.strategyName}>{issue.title}</Text>
            <Text style={styles.resultName}>Detailed breakdown</Text>
          </View>
          <Text style={[styles.deepScore, { color: toneColor(issue.tone) }]}>{issue.score}/100</Text>
        </View>
        <Block title="Evidence" lines={issue.evidence} />
        <Block title="Why it matters" lines={[issue.why]} />
        <Block title="What would help" lines={issue.whatHelps} />
        <View style={styles.nextQuestion}>
          <Text style={styles.blockTitle}>Next question</Text>
          <Text style={styles.tipText}>{issue.nextQuestion}</Text>
        </View>
      </Card>
    </View>
  );
}

function Block({ title, lines }) {
  return (
    <View style={styles.block}>
      <Text style={styles.blockTitle}>{title}</Text>
      {lines.map((line) => <Text key={line} style={styles.blockText}>- {line}</Text>)}
    </View>
  );
}

function StepTitle({ title, subtitle }) {
  return (
    <View style={styles.stepTitleBlock}>
      <Text style={styles.screenTitle}>{title}</Text>
      <Text style={styles.screenSubtitle}>{subtitle}</Text>
    </View>
  );
}

function StatusPill({ label, tone }) {
  return (
    <View style={[styles.pill, tone === "good" && styles.pillGood, tone === "warn" && styles.pillWarn, tone === "risk" && styles.pillRisk]}>
      <Text style={[styles.pillText, tone === "good" && styles.pillTextGood, tone === "warn" && styles.pillTextWarn, tone === "risk" && styles.pillTextRisk]}>{label}</Text>
    </View>
  );
}

function StatusDot({ tone }) {
  return <View style={[styles.statusDot, { backgroundColor: toneColor(tone) }]} />;
}

function ScoreCircle({ value }) {
  return (
    <View style={styles.scoreCircle}>
      <Text style={styles.scoreValue}>{value}</Text>
      <Text style={styles.scoreOutOf}>/100</Text>
    </View>
  );
}

function MetricGrid({ items }) {
  return (
    <View style={styles.metricGrid}>
      {items.map(([label, value, tone]) => (
        <Card key={label} style={styles.metricCard}>
          <Text style={sharedText.cardLabel}>{label}</Text>
          <Text style={[styles.metricValue, { color: toneColor(tone) }]}>{value}</Text>
        </Card>
      ))}
    </View>
  );
}

function MiniStat({ label, value }) {
  return (
    <View style={styles.miniStat}>
      <Text style={sharedText.cardLabel}>{label}</Text>
      <Text style={styles.miniStatValue}>{value}</Text>
    </View>
  );
}

function KeyValue({ label, value }) {
  return (
    <View style={styles.keyValue}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <Text style={styles.keyValueText}>{value}</Text>
    </View>
  );
}

function InsightList({ calculations, validation }) {
  const rows = [
    validation.strike || validation.premium ? "Strike and premium are required before the check can run." : "Max loss is calculated from premium x contracts x 100.",
    calculations.bidAskSpreadPercent !== null ? `Bid/ask spread is ${calculations.bidAskSpreadPercent.toFixed(1)}% of premium.` : "Bid/ask is optional, but missing liquidity data lowers confidence.",
    calculations.requiredMovePercent > 0 ? `Underlying needs about ${calculations.requiredMovePercent.toFixed(2)}% before breakeven at expiration.` : "Breakeven move is close to current price."
  ];
  return (
    <Card style={styles.tipCard}>
      {rows.map((row) => (
        <View key={row} style={styles.tipRow}>
          <Ionicons name="information-circle-outline" size={15} color={palette.green} />
          <Text style={styles.tipText}>{row}</Text>
        </View>
      ))}
    </Card>
  );
}

function buildRiskMath(draft) {
  const premium = Number(draft.premium || 0);
  const contracts = Math.max(0, Number(draft.contracts || 0));
  const strike = Number(draft.strike || 0);
  const accountSize = Math.max(1, Number(draft.accountSize || 1));
  const underlying = Number(draft.underlyingPrice || 0) || strike;
  const side = draft.optionSide || (String(draft.tradeType || "").toLowerCase().includes("put") ? "put" : "call");
  const maxLoss = premium * contracts * 100;
  const accountRiskPercent = maxLoss / accountSize * 100;
  const breakeven = side === "put" ? strike - premium : strike + premium;
  const requiredMovePercent = underlying > 0
    ? side === "put"
      ? Math.max(0, (underlying - breakeven) / underlying * 100)
      : Math.max(0, (breakeven - underlying) / underlying * 100)
    : 0;
  const bid = Number(draft.bid || 0);
  const ask = Number(draft.ask || 0);
  const bidAskSpreadPercent = bid > 0 && ask > bid && premium > 0 ? (ask - bid) / premium * 100 : null;
  const expiration = parseDate(draft.expiration);
  const daysToExpiration = expiration ? dayDiff(new Date(), expiration) : 0;
  return { premium, contracts, strike, maxLoss, accountRiskPercent, breakeven, requiredMovePercent, bidAskSpreadPercent, daysToExpiration };
}

function validateOptionContract(draft, selectedTicker, calculations) {
  const messages = [];
  const validation = {
    ticker: selectedTicker?.symbol ? "" : "Select a ticker from search results.",
    strike: calculations.strike > 0 ? "" : "Strike is required.",
    premium: calculations.premium > 0 ? "" : "Premium is required.",
    contracts: calculations.contracts > 0 ? "" : "At least one contract is required.",
    expiration: parseDate(draft.expiration) && calculations.daysToExpiration >= 0 ? "" : "Choose a future expiration."
  };
  Object.values(validation).forEach((message) => message && messages.push(message));
  return { ...validation, messages, ready: messages.length === 0 };
}

function buildLocalResult(report, draft, selectedTicker, calculations) {
  const rule = riskRulePercent(draft);
  const liquidityKnown = Number(draft.openInterest || 0) > 0 || Number(draft.contractVolume || 0) > 0 || calculations.bidAskSpreadPercent !== null;
  const riskTone = calculations.accountRiskPercent <= rule ? "good" : calculations.accountRiskPercent <= rule * 1.5 ? "warn" : "risk";
  const score = Math.max(28, Math.min(92, Math.round(
    (report?.setupScore || 62)
    - (riskTone === "risk" ? 18 : riskTone === "warn" ? 8 : 0)
    - (!liquidityKnown ? 10 : 0)
    - (calculations.daysToExpiration < 7 ? 8 : 0)
    - (calculations.requiredMovePercent > 8 ? 7 : 0)
  )));
  const weakest = !liquidityKnown ? "Liquidity Context" : riskTone !== "good" ? "Position Size" : calculations.requiredMovePercent > 8 ? "Signal Clarity" : "Volatility Context";
  const title = `${draft.ticker || selectedTicker?.symbol || "Contract"} $${draft.strike || "?"} ${draft.optionSide === "put" ? "Put" : "Call"}`;
  const subtitle = `${displayDate(parseDate(draft.expiration))} - ${draft.contracts || 1} Contract${Number(draft.contracts || 1) === 1 ? "" : "s"}`;
  const issues = [
    {
      title: weakest,
      score: weakest === "Liquidity Context" ? 48 : weakest === "Position Size" ? 52 : 61,
      label: weakest === "Position Size" ? "Size Risk" : weakest === "Signal Clarity" ? "Needs Proof" : "Unknown",
      tone: weakest === "Position Size" && riskTone === "risk" ? "risk" : "warn",
      icon: weakest === "Position Size" ? "shield-outline" : weakest === "Signal Clarity" ? "analytics-outline" : "water-outline",
      detail: weakest === "Liquidity Context" ? "Bid/ask, volume, open interest, or IV are missing." : weakest === "Position Size" ? "Risk is high relative to the account rule." : "The contract needs a clearer price thesis.",
      evidence: weakest === "Liquidity Context"
        ? ["Bid/ask spread is missing or unclear.", "Open interest and volume may be unknown.", "IV context is not confirmed."]
        : [`Account risk is ${calculations.accountRiskPercent.toFixed(2)}%.`, `Your rule is ${rule}% max risk per trade.`, "Sizing should be decided before conviction."],
      why: weakest === "Liquidity Context" ? "Options can look attractive but become hard to exit when liquidity is weak." : "A good thesis can still hurt the account if the premium risk is too large.",
      whatHelps: weakest === "Liquidity Context" ? ["Add bid and ask", "Check open interest above 1,000", "Compare IV to normal levels"] : ["Reduce contracts", "Lower premium at risk", "Use a spread to define risk"],
      nextQuestion: weakest === "Liquidity Context" ? "Is this contract liquid enough to enter and exit cleanly?" : "What position size keeps the trade survivable if it expires worthless?"
    },
    {
      title: "Contract Structure",
      score: report?.setupScore || 70,
      label: calculations.maxLoss > 0 ? "Defined" : "Missing",
      tone: calculations.maxLoss > 0 ? "good" : "risk",
      icon: "document-text-outline",
      detail: "Premium paid defines max loss for long options."
    },
    {
      title: "Breakeven Hurdle",
      score: calculations.requiredMovePercent > 8 ? 54 : 72,
      label: calculations.requiredMovePercent > 8 ? "High Move" : "Manageable",
      tone: calculations.requiredMovePercent > 8 ? "warn" : "good",
      icon: "trending-up-outline",
      detail: `Required move is about ${calculations.requiredMovePercent.toFixed(2)}% by expiration.`
    }
  ];
  return {
    title,
    subtitle,
    score,
    tone: riskTone,
    verdict: score >= 75 ? "Clearer Setup" : score >= 55 ? "Mixed Conviction" : "Needs Review",
    verdictSub: score >= 75 ? "Main risks are visible." : "Wait for the weak area to improve.",
    maxLoss: calculations.maxLoss,
    breakeven: calculations.breakeven,
    requiredMovePercent: calculations.requiredMovePercent,
    accountRiskPercent: calculations.accountRiskPercent,
    issues
  };
}

function buildStrategies(direction, riskTolerance, horizon) {
  const bullish = direction !== "bearish";
  const aggressive = riskTolerance === "aggressive";
  const premiumBase = horizon === "short" ? 2.15 : horizon === "medium" ? 4.2 : 6.5;
  return [
    {
      name: bullish ? "Long Call" : "Long Put",
      structure: bullish ? "call" : "put",
      direction,
      why: "Best for strong directional moves where the thesis needs convex upside.",
      maxProfit: bullish ? "High / uncapped" : "High until stock approaches zero",
      maxLoss: "Premium paid",
      risk: aggressive ? "Aggressive" : "Most Direct",
      tone: aggressive ? "warn" : "good",
      premium: premiumBase
    },
    {
      name: bullish ? "Bull Call Spread" : "Bear Put Spread",
      structure: bullish ? "call_spread" : "put_spread",
      direction,
      why: "Best for a moderate move where lower premium risk matters more than unlimited upside.",
      maxProfit: "Limited",
      maxLoss: "Defined",
      risk: "Balanced",
      tone: "good",
      premium: Math.max(1.15, premiumBase * 0.55).toFixed(2)
    },
    {
      name: bullish ? "Cash Secured Put" : "Covered Call",
      structure: bullish ? "put" : "call",
      direction: bullish ? "neutral" : "neutral",
      why: "Best for income-style thinking, but only if assignment risk is understood.",
      maxProfit: "Premium received",
      maxLoss: bullish ? "Stock purchase risk" : "Opportunity cost / stock downside",
      risk: "Conservative",
      tone: "neutral",
      premium: Math.max(0.85, premiumBase * 0.35).toFixed(2)
    }
  ];
}

function buildSearchResults(query, remoteRows = []) {
  const clean = normalizeSymbol(query);
  const normalizedRemote = remoteRows
    .map((item) => ({
      symbol: normalizeSymbol(item.symbol),
      name: item.name || `${normalizeSymbol(item.symbol)} ticker`,
      exchange: item.exchange || "US",
      source: item.source || "api"
    }))
    .filter((item) => item.symbol);
  const localMatches = localSymbols.filter((item) =>
    item.symbol.includes(clean) || item.name.toUpperCase().includes(clean)
  );
  const exactManual = clean && /^[A-Z0-9.-]{1,8}$/.test(clean)
    ? [{ symbol: clean, name: `${clean} exact ticker - verify quote`, exchange: "Manual", source: "manual" }]
    : [];
  const combined = [...normalizedRemote, ...localMatches, ...exactManual];
  const seen = new Set();
  return combined.filter((item) => {
    const key = item.symbol;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(0, 8);
}

function symbolToItem(symbol, name, exchange) {
  return { symbol: normalizeSymbol(symbol), name: name || recentName(symbol), exchange: exchange || "US" };
}

function tradeTypeFromStructure(structure) {
  if (structure === "put") return "Put Option (Long)";
  if (structure === "call_spread") return "Call Option Spread";
  if (structure === "put_spread") return "Put Option Spread";
  return "Call Option (Long)";
}

function horizonToTimeframe(horizon) {
  if (horizon === "short") return "1-2 Weeks";
  if (horizon === "long") return "1 Month+";
  return "1-3 Months";
}

function estimateExpirationFromHorizon(horizon) {
  return toIsoDate(addDays(new Date(), horizon === "short" ? 21 : horizon === "long" ? 120 : 60));
}

function riskRulePercent(draft) {
  const account = Number(draft.accountSize || 1);
  const budget = Number(draft.riskBudget || 0);
  return Math.max(0.5, Math.round((budget / account * 100 || 2) * 10) / 10);
}

function normalizeSymbol(value) {
  return String(value || "").trim().toUpperCase().replace("/", "-");
}

function recentName(symbol) {
  const found = localSymbols.find((item) => item.symbol === normalizeSymbol(symbol));
  return found?.name || `${normalizeSymbol(symbol)} ticker`;
}

function mockPrice(symbol) {
  return { AAPL: 197.02, NVDA: 113.5, SPY: 602.1, MSFT: 442.7, QQQ: 531.4, ACHR: 8.26 }[normalizeSymbol(symbol)] || 50;
}

function mockChange(symbol) {
  return { AAPL: 0.63, NVDA: 1.1, SPY: 0.24, MSFT: 0.42, QQQ: 0.36, ACHR: -1.8 }[normalizeSymbol(symbol)] || 0.15;
}

function parseDate(value) {
  if (!value) return null;
  const date = /^\d{4}-\d{2}-\d{2}$/.test(String(value)) ? new Date(`${value}T00:00:00`) : new Date(value);
  return Number.isNaN(date.getTime()) ? null : stripTime(date);
}

function displayDate(date) {
  if (!date) return "Choose date";
  return `${monthNames[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
}

function shortDate(value) {
  const date = parseDate(value);
  return date ? `${monthNames[date.getMonth()]} ${date.getDate()}` : value;
}

function buildCalendar(monthDate) {
  const first = startOfMonth(monthDate);
  const start = addDays(first, -first.getDay());
  return Array.from({ length: 42 }, (_, index) => {
    const date = addDays(start, index);
    return { date, inMonth: date.getMonth() === first.getMonth() };
  });
}

function stripTime(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addDays(date, days) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return stripTime(next);
}

function addMonths(date, months) {
  return new Date(date.getFullYear(), date.getMonth() + months, 1);
}

function toIsoDate(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function dayDiff(start, end) {
  return Math.ceil((stripTime(end).getTime() - stripTime(start).getTime()) / 86400000);
}

function formatMoney(value) {
  return `$${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function toneColor(tone) {
  if (tone === "risk") return palette.red;
  if (tone === "warn") return "#F59E0B";
  if (tone === "good") return palette.green;
  return palette.dark;
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  rowCenter: { flexDirection: "row", alignItems: "center", gap: 10 },
  snapshot: { backgroundColor: "#FEFFFE" },
  snapshotGrid: { flexDirection: "row", gap: 12, marginTop: 12 },
  progressTrack: { height: 8, backgroundColor: "#EEF2EF", borderRadius: 999, overflow: "hidden", marginTop: 12 },
  progressFill: { height: "100%", backgroundColor: palette.green, borderRadius: 999 },
  flowChoice: {
    minHeight: 92,
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 18,
    padding: 13,
    marginBottom: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: "#FFFFFF"
  },
  flowIcon: { width: 42, height: 42, borderRadius: 21, alignItems: "center", justifyContent: "center" },
  flowTitle: { color: palette.dark, fontSize: 14, fontWeight: "900" },
  flowSubtitle: { color: palette.dark, fontSize: 11, lineHeight: 15, fontWeight: "800", marginTop: 3 },
  flowBody: { color: palette.muted, fontSize: 10, lineHeight: 14, fontWeight: "700", marginTop: 5 },
  topBar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingTop: 8, paddingBottom: 14 },
  topCenter: { alignItems: "center", flex: 1 },
  roundButton: { width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center", backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: palette.border },
  roundButtonGhost: { width: 38, height: 38 },
  stepCount: { color: palette.dark, fontSize: 10, fontWeight: "900", marginBottom: 5 },
  flowHeading: { color: palette.dark, fontSize: 14, fontWeight: "900" },
  stepTitleBlock: { alignItems: "center", marginBottom: 16 },
  screenTitle: { color: palette.dark, fontSize: 18, fontWeight: "900", textAlign: "center" },
  screenSubtitle: { color: palette.muted, fontSize: 11, lineHeight: 16, fontWeight: "700", textAlign: "center", marginTop: 5 },
  searchWrap: { position: "relative", zIndex: 5, marginBottom: 12 },
  searchBox: { minHeight: 48, borderWidth: 1, borderColor: palette.border, borderRadius: 14, backgroundColor: "#FBFCFB", flexDirection: "row", alignItems: "center", gap: 9, paddingHorizontal: 12 },
  searchInput: { flex: 1, color: palette.dark, fontWeight: "800", outlineStyle: "none" },
  searchResults: { borderWidth: 1, borderColor: palette.border, borderRadius: 16, backgroundColor: "#FFFFFF", overflow: "hidden", marginTop: 8 },
  dropdownEmpty: { color: palette.muted, fontSize: 11, fontWeight: "800", padding: 12 },
  resultRow: { minHeight: 54, flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 12, borderTopWidth: 1, borderTopColor: "#F0F3F0" },
  symbolAvatar: { width: 31, height: 31, borderRadius: 16, backgroundColor: palette.greenSoft, alignItems: "center", justifyContent: "center" },
  symbolAvatarText: { color: palette.green, fontSize: 12, fontWeight: "900" },
  resultSymbol: { color: palette.dark, fontSize: 13, fontWeight: "900" },
  resultName: { color: palette.muted, fontSize: 10, fontWeight: "800", marginTop: 2 },
  resultExchange: { color: palette.muted, fontSize: 9, fontWeight: "900" },
  miniLabel: { color: palette.muted, fontSize: 10, fontWeight: "900", marginBottom: 8 },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 12 },
  chip: { borderRadius: 999, borderWidth: 1, borderColor: palette.border, paddingHorizontal: 13, paddingVertical: 8, backgroundColor: "#FFFFFF" },
  chipText: { color: palette.dark, fontSize: 10, fontWeight: "900" },
  tickerCard: { flexDirection: "row", alignItems: "center", gap: 12, marginTop: 4 },
  symbolLogo: { width: 38, height: 38, borderRadius: 19, backgroundColor: "#101828", alignItems: "center", justifyContent: "center" },
  symbolLogoText: { color: "#FFFFFF", fontSize: 15, fontWeight: "900" },
  bigSymbol: { color: palette.dark, fontSize: 18, fontWeight: "900" },
  priceBox: { alignItems: "flex-end" },
  priceText: { color: palette.dark, fontSize: 13, fontWeight: "900" },
  changeText: { color: palette.green, fontSize: 10, fontWeight: "900", marginTop: 3 },
  selectable: { minHeight: 70, borderWidth: 1, borderColor: palette.border, borderRadius: 16, backgroundColor: "#FFFFFF", padding: 13, flexDirection: "row", alignItems: "center", gap: 12, marginBottom: 10 },
  selectableActive: { borderColor: palette.green, backgroundColor: "#F4FFF7" },
  radio: { width: 26, height: 26, borderRadius: 13, borderWidth: 1, borderColor: palette.border, alignItems: "center", justifyContent: "center", backgroundColor: "#FFFFFF" },
  radioActive: { backgroundColor: palette.green, borderColor: palette.green },
  selectableTitle: { color: palette.dark, fontSize: 13, fontWeight: "900" },
  selectableSubtitle: { color: palette.muted, fontSize: 10, lineHeight: 15, fontWeight: "700", marginTop: 2 },
  dateSelector: { minHeight: 58, borderRadius: 16, borderWidth: 1, borderColor: palette.border, paddingHorizontal: 13, backgroundColor: "#FFFFFF", flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 10 },
  dateText: { color: palette.dark, fontSize: 13, fontWeight: "900" },
  dateSub: { color: palette.muted, fontSize: 10, fontWeight: "800", marginTop: 2 },
  suggestedDates: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 10 },
  dateChip: { borderRadius: 999, borderWidth: 1, borderColor: palette.border, paddingHorizontal: 11, paddingVertical: 7, backgroundColor: "#FFFFFF" },
  dateChipActive: { backgroundColor: palette.green, borderColor: palette.green },
  dateChipText: { color: palette.dark, fontSize: 10, fontWeight: "900" },
  dateChipTextActive: { color: "#FFFFFF" },
  calendarCard: { padding: 10 },
  calendarHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  calendarNav: { width: 28, height: 28, borderRadius: 14, borderWidth: 1, borderColor: palette.border, alignItems: "center", justifyContent: "center" },
  calendarTitle: { color: palette.dark, fontSize: 13, fontWeight: "900" },
  weekRow: { flexDirection: "row", marginBottom: 5 },
  weekLabel: { width: `${100 / 7}%`, textAlign: "center", color: palette.muted, fontSize: 9, fontWeight: "900" },
  daysGrid: { flexDirection: "row", flexWrap: "wrap" },
  dayCell: { width: `${100 / 7}%`, height: 31, alignItems: "center", justifyContent: "center", borderRadius: 12 },
  dayCellActive: { backgroundColor: palette.green },
  dayCellDisabled: { opacity: 0.25 },
  dayText: { color: palette.dark, fontSize: 10, fontWeight: "900" },
  dayTextActive: { color: "#FFFFFF" },
  fieldRow: { width: "100%", borderBottomWidth: 1, borderBottomColor: "#EEF2EF", paddingVertical: 6 },
  fieldLabelWrap: { width: "100%", marginBottom: 4 },
  referenceCard: { backgroundColor: "#FBFFFC", borderColor: "#D7F0DE", padding: 12 },
  referenceTitle: { color: palette.dark, fontSize: 12, fontWeight: "900" },
  referenceSub: { color: palette.muted, fontSize: 10, lineHeight: 15, fontWeight: "800", marginTop: 3 },
  referenceGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 11 },
  referenceChip: { width: "23%", minHeight: 54, borderRadius: 14, borderWidth: 1, borderColor: palette.border, backgroundColor: "#FFFFFF", alignItems: "center", justifyContent: "center", padding: 6 },
  referenceChipActive: { backgroundColor: palette.green, borderColor: palette.green },
  referenceChipText: { color: palette.dark, fontSize: 11, fontWeight: "900" },
  referenceChipSub: { color: palette.muted, fontSize: 8, fontWeight: "800", marginTop: 2, textAlign: "center" },
  referenceChipTextActive: { color: "#FFFFFF" },
  fieldLabel: { color: palette.muted, fontSize: 11, fontWeight: "900" },
  compactInput: { width: "100%", minHeight: 38, borderRadius: 13, borderWidth: 1, borderColor: palette.border, backgroundColor: "#FBFCFB", flexDirection: "row", alignItems: "center", paddingHorizontal: 10 },
  inputError: { borderColor: palette.red, backgroundColor: "#FFFBFB" },
  compactTextInput: { flex: 1, minWidth: 0, color: palette.dark, textAlign: "left", fontWeight: "900", outlineStyle: "none" },
  inputAdornment: { color: palette.muted, fontSize: 11, fontWeight: "900" },
  errorText: { color: palette.red, fontSize: 9, fontWeight: "800", marginTop: 3 },
  helperText: { color: palette.muted, fontSize: 10, lineHeight: 15, fontWeight: "700", marginVertical: 9 },
  stepperRow: { minHeight: 62, flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 8 },
  stepper: { flexDirection: "row", alignItems: "center", borderRadius: 14, borderWidth: 1, borderColor: palette.border, overflow: "hidden", backgroundColor: "#FFFFFF" },
  stepperButton: { width: 42, height: 40, alignItems: "center", justifyContent: "center", backgroundColor: "#F7FBF8" },
  stepperText: { color: palette.green, fontSize: 18, fontWeight: "900" },
  stepperInput: { width: 44, height: 40, color: palette.dark, textAlign: "center", fontWeight: "900", outlineStyle: "none" },
  mathCard: { backgroundColor: "#FBFFFC", borderColor: "#CFEFD8" },
  metricGrid: { flexDirection: "row", flexWrap: "wrap", gap: 9, marginBottom: 10 },
  metricCard: { width: "48%", marginBottom: 0, padding: 12 },
  metricValue: { fontSize: 17, fontWeight: "900" },
  miniStat: { flex: 1 },
  miniStatValue: { color: palette.dark, fontSize: 17, fontWeight: "900" },
  pill: { borderRadius: 999, borderWidth: 1, borderColor: palette.border, backgroundColor: "#FFFFFF", paddingHorizontal: 10, paddingVertical: 6, alignSelf: "flex-start" },
  pillGood: { backgroundColor: palette.greenSoft, borderColor: "#CFEFD8" },
  pillWarn: { backgroundColor: "#FFF8E8", borderColor: "#FADFA2" },
  pillRisk: { backgroundColor: "#FFF1F1", borderColor: "#F8CACA" },
  pillText: { color: palette.dark, fontSize: 9, fontWeight: "900" },
  pillTextGood: { color: palette.green },
  pillTextWarn: { color: "#B7791F" },
  pillTextRisk: { color: palette.red },
  tipCard: { backgroundColor: "#FBFFFC" },
  tipRow: { flexDirection: "row", alignItems: "flex-start", gap: 8, marginBottom: 7 },
  tipText: { flex: 1, color: palette.dark, fontSize: 11, lineHeight: 16, fontWeight: "800" },
  strategyCard: { padding: 14 },
  strategyName: { color: palette.dark, fontSize: 14, fontWeight: "900" },
  strategyWhy: { color: palette.muted, fontSize: 10, lineHeight: 15, fontWeight: "700", marginTop: 4, maxWidth: 250 },
  strategyFacts: { flexDirection: "row", gap: 12, marginVertical: 12 },
  uploadBox: { minHeight: 185, borderRadius: 18, borderWidth: 1, borderColor: "#CBB9FF", borderStyle: "dashed", backgroundColor: "#FBF9FF", alignItems: "center", justifyContent: "center", marginBottom: 14 },
  uploadIcon: { width: 58, height: 58, borderRadius: 29, backgroundColor: "#EFE7FF", alignItems: "center", justifyContent: "center" },
  uploadTitle: { color: palette.dark, fontSize: 14, fontWeight: "900", marginTop: 12 },
  uploadSub: { color: palette.muted, fontSize: 10, fontWeight: "800", marginTop: 4 },
  platformChip: { borderRadius: 999, backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: palette.border, paddingHorizontal: 9, paddingVertical: 6 },
  platformText: { color: palette.dark, fontSize: 9, fontWeight: "900" },
  extractCard: { alignItems: "center" },
  progressRing: { width: 82, height: 82, borderRadius: 41, borderWidth: 7, borderColor: "#CBB9FF", alignItems: "center", justifyContent: "center", marginBottom: 12 },
  extractTitle: { color: palette.dark, fontSize: 13, fontWeight: "900", marginBottom: 12 },
  secondaryButton: { minHeight: 48, borderRadius: 15, borderWidth: 1, borderColor: palette.green, alignItems: "center", justifyContent: "center", backgroundColor: "#FFFFFF", marginBottom: 8 },
  secondaryButtonText: { color: palette.green, fontWeight: "900" },
  keyValue: { flexDirection: "row", justifyContent: "space-between", gap: 12, borderBottomWidth: 1, borderBottomColor: "#EEF2EF", paddingVertical: 10 },
  keyValueText: { color: palette.dark, fontSize: 12, fontWeight: "900", textAlign: "right", flex: 1 },
  successCard: { backgroundColor: "#F2FFF6", borderColor: "#CFEFD8" },
  successText: { color: palette.dark, fontSize: 11, lineHeight: 16, fontWeight: "800", textAlign: "center" },
  timelineRow: { flexDirection: "row", alignItems: "center", gap: 10, minHeight: 36 },
  timelineDot: { width: 12, height: 12, borderRadius: 6, borderWidth: 1, borderColor: palette.border, backgroundColor: "#FFFFFF" },
  timelineDotActive: { backgroundColor: palette.green, borderColor: palette.green },
  heroCard: { backgroundColor: "#F7FFF9", borderColor: "#CFEFD8" },
  heroTitle: { color: palette.dark, fontSize: 21, fontWeight: "900" },
  heroSub: { color: palette.muted, fontSize: 11, fontWeight: "800", marginTop: 3 },
  scoreCircle: { width: 76, height: 76, borderRadius: 38, borderWidth: 7, borderColor: palette.green, alignItems: "center", justifyContent: "center", backgroundColor: "#FFFFFF" },
  scoreValue: { color: palette.dark, fontSize: 20, fontWeight: "900" },
  scoreOutOf: { color: palette.muted, fontSize: 9, fontWeight: "900" },
  verdictBox: { minHeight: 62, marginTop: 14, borderRadius: 16, borderWidth: 1, borderColor: "#DDEBDD", backgroundColor: "#FFFFFF", padding: 12, flexDirection: "row", alignItems: "center", gap: 11 },
  statusDot: { width: 13, height: 13, borderRadius: 7 },
  verdictTitle: { color: palette.dark, fontSize: 14, fontWeight: "900" },
  verdictSub: { color: palette.muted, fontSize: 10, fontWeight: "800", marginTop: 2 },
  issueRow: { minHeight: 58, flexDirection: "row", alignItems: "center", gap: 10, borderTopWidth: 1, borderTopColor: "#EEF2EF", paddingVertical: 9 },
  issueIcon: { width: 32, height: 32, borderRadius: 16, backgroundColor: palette.greenSoft, alignItems: "center", justifyContent: "center" },
  issueIconWarn: { backgroundColor: "#FFF7E6" },
  issueIconRisk: { backgroundColor: "#FEEEEE" },
  issueTitle: { color: palette.dark, fontSize: 12, fontWeight: "900" },
  issueSub: { color: palette.muted, fontSize: 9, lineHeight: 13, fontWeight: "800", marginTop: 2 },
  debateEntry: { minHeight: 70, borderRadius: 18, borderWidth: 1, borderColor: "#CFEFD8", backgroundColor: "#FFFFFF", padding: 14, marginBottom: 12, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  levelRow: { flexDirection: "row", gap: 8, marginBottom: 12 },
  agentRow: { flexDirection: "row", gap: 10, paddingVertical: 12, borderTopWidth: 1, borderTopColor: "#EEF2EF" },
  agentAvatar: { width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center" },
  agentInitials: { color: palette.green, fontSize: 10, fontWeight: "900" },
  agentName: { color: palette.dark, fontSize: 12, fontWeight: "900" },
  agentText: { color: palette.dark, fontSize: 10, lineHeight: 15, fontWeight: "800", marginTop: 4 },
  deepScore: { fontSize: 22, fontWeight: "900" },
  block: { borderTopWidth: 1, borderTopColor: "#EEF2EF", paddingTop: 12, marginTop: 12 },
  blockTitle: { color: palette.green, fontSize: 11, fontWeight: "900", marginBottom: 7 },
  blockText: { color: palette.dark, fontSize: 11, lineHeight: 17, fontWeight: "800", marginBottom: 4 },
  nextQuestion: { borderRadius: 16, backgroundColor: "#F7FFF9", borderWidth: 1, borderColor: "#CFEFD8", padding: 12, marginTop: 14 }
});
