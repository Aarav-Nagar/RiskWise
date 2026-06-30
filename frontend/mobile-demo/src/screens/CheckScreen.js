import React, { useEffect, useMemo, useState } from "react";
import { Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as DocumentPicker from "expo-document-picker";
import * as FileSystem from "expo-file-system";
import * as ImagePicker from "expo-image-picker";
import { Card } from "../components/Card";
import { ErrorCard, Header, PrimaryButton, ScreenScroll, sharedText } from "../components/Shared";
import { extractContractFromAttachment, getMarketBundle, getOptionsChain, getOptionsExpirations, searchMarketSymbols } from "../services/apiClient";
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
    body: "Upload a real screenshot. RiskWise reads visible fields, then asks you to confirm before analysis."
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
  ["put", "Put", "Right to sell"]
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

export function CheckScreen({ user, draft, setDraft, onCheck, loading, error }) {
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
  const [extraction, setExtraction] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [extractionError, setExtractionError] = useState("");

  const calculations = useMemo(() => buildRiskMath(draft), [draft]);
  const optionValidation = useMemo(() => validateOptionContract(draft, selectedTicker, calculations), [draft, selectedTicker, calculations]);
  const missingDataWarnings = useMemo(() => buildMissingDataWarnings(draft, market), [draft, market]);
  const extractionStatus = useMemo(() => buildExtractionStatus(draft, extraction), [draft, extraction]);

  useEffect(() => {
    const query = tickerQuery.trim();
    let cancelled = false;

    if (!query) {
      setTickerResults([]);
      return undefined;
    }

    setSearching(true);
    setTickerResults(buildSearchResults(query, []));
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
      if (flow === "screenshot") {
        setFlow("screenshot");
        setExtractionStep(4);
      } else {
        setFlow("option");
        setStep(7);
      }
    }
  }

  async function startScreenshotUpload(source = "library") {
    setExtractionError("");
    setExtraction(null);
    let attachment = null;
    try {
      if (Platform.OS === "web" && typeof document !== "undefined") {
        attachment = await pickWebScreenshot(source);
      } else {
        attachment = await pickNativeScreenshot(source);
      }
      if (!attachment) {
        return;
      }
      setExtracting(true);
      setExtractionStep(2);
      const result = await extractContractFromAttachment({
        user,
        attachments: [attachment]
      });
      const fields = result.fields || {};
      setExtraction(result);
      if (fields.ticker) {
        setSelectedTicker(symbolToItem(fields.ticker, fields.tickerName || fields.ticker, fields.tickerExchange || "Uploaded"));
        setTickerQuery(fields.ticker);
      }
      const nextDraft = {
        ...fields,
        structure: fields.structure || fields.optionSide || draft.structure || "call",
        tradeType: fields.tradeType || tradeTypeFromStructure(fields.structure || fields.optionSide || draft.structure || "call"),
        expirationSource: "uploaded_screenshot",
        contracts: fields.contracts || draft.contracts || "1",
        amountAtRisk: estimateUploadedRisk(fields, draft),
        timeframe: draft.timeframe || "1-2 Weeks"
      };
      updateDraft(nextDraft);
      setExtractionStep(3);
    } catch (err) {
      setExtractionError(err?.message || "Could not extract this screenshot. Try a clearer image or enter the contract manually.");
      setExtractionStep(1);
    } finally {
      setExtracting(false);
    }
  }

  if (flow === "option") {
    return (
      <ScreenScroll>
        <FlowTopBar title="Build Your Trade" step={step} total={7} onBack={() => (step === 1 ? chooseFlow("start") : setStep(step - 1))} />
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
            onReview={() => setStep(7)}
            loading={loading}
            error={error}
          />
        )}
        {step === 7 && (
          <ReviewTradeStep
            draft={draft}
            calculations={calculations}
            validation={optionValidation}
            missingData={missingDataWarnings}
            onEditContract={() => setStep(5)}
            onEditSize={() => setStep(6)}
            onRun={runRiskCheck}
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
        {extractionStep === 1 && <UploadStep onUpload={startScreenshotUpload} extracting={extracting} error={extractionError} />}
        {extractionStep === 2 && <ExtractionStep extracting={extracting} extraction={extraction} onContinue={() => setExtractionStep(3)} />}
        {extractionStep === 3 && <ExtractedReviewStep draft={draft} extraction={extraction} status={extractionStatus} onEdit={() => { setFlow("option"); setStep(5); }} onContinue={() => setExtractionStep(4)} />}
        {extractionStep === 4 && (
          <ConfirmContractStep
            draft={draft}
            calculations={calculations}
            validation={optionValidation}
            missingData={missingDataWarnings}
            onEdit={() => { setFlow("option"); setStep(5); }}
            onContinue={() => setExtractionStep(5)}
          />
        )}
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
        {dayLabels.map((day, index) => <Text key={`${day}-${index}`} style={styles.weekLabel}>{day}</Text>)}
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
  const requiredReady = !validation.strike && !validation.premium && !validation.bidAsk && !validation.impliedVolatility && !validation.openInterest && !validation.contractVolume;
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
      <FieldRow label="Ask" value={draft.ask} onChangeText={(value) => setNumericField("ask", value)} prefix="$" error={validation.bidAsk} />
      <FieldRow label="IV (Implied Volatility)" value={draft.impliedVolatility} onChangeText={(value) => setNumericField("impliedVolatility", value)} suffix="%" error={validation.impliedVolatility} />
      <FieldRow label="Open Interest" value={draft.openInterest} onChangeText={(value) => setNumericField("openInterest", value)} error={validation.openInterest} />
      <FieldRow label="Volume" value={draft.contractVolume} onChangeText={(value) => setNumericField("contractVolume", value)} error={validation.contractVolume} />
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

function SizeStep({ draft, calculations, validation, setNumericField, setMaxRiskRule, adjustContracts, onReview, loading, error }) {
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
      <FieldRow label="Account Size" value={String(draft.accountSize || "")} onChangeText={(value) => setNumericField("accountSize", value)} prefix="$" error={validation.accountSize} />
      <FieldRow label="Max Risk Rule" value={String(riskRulePercent(draft))} onChangeText={setMaxRiskRule} suffix="%" error={validation.riskRule} />
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
      <ValidationSummary validation={validation} />
      {error ? <ErrorCard title="Check failed" message={errorMessage(error)} /> : null}
      <PrimaryButton label={loading ? "Reviewing..." : "Review Final Details"} onPress={onReview} disabled={!validation.ready || loading} />
    </View>
  );
}

function ReviewTradeStep({ draft, calculations, validation, missingData, onEditContract, onEditSize, onRun, loading, error }) {
  const tone = calculations.accountRiskPercent <= riskRulePercent(draft) ? "good" : calculations.accountRiskPercent <= riskRulePercent(draft) * 1.5 ? "warn" : "risk";
  return (
    <View>
      <StepTitle title="Final Review" subtitle="Confirm what RiskWise will use before analysis." />
      <Card style={styles.reviewHeroCard}>
        <View style={styles.rowBetween}>
          <View style={styles.flex}>
            <Text style={styles.bigSymbol}>{draft.ticker || "Ticker missing"}</Text>
            <Text style={styles.resultName}>{draft.tradeType || tradeTypeFromStructure(draft.structure || draft.optionSide || "call")}</Text>
          </View>
          <StatusPill label={draft.expirationSource === "uploaded_screenshot" ? "Uploaded" : "Manual"} tone="neutral" />
        </View>
        <View style={styles.reviewFacts}>
          <KeyValue label="Strike" value={calculations.strike ? `$${calculations.strike.toFixed(2)}` : "Missing"} />
          <KeyValue label="Expiration" value={displayDate(parseDate(draft.expiration))} />
          <KeyValue label="Premium" value={calculations.premium ? `$${calculations.premium.toFixed(2)}` : "Missing"} />
          <KeyValue label="Contracts" value={String(draft.contracts || "Missing")} />
        </View>
      </Card>
      <Card style={styles.mathCard}>
        <MetricGrid
          items={[
            ["Max Loss", formatMoney(calculations.maxLoss), tone],
            ["Account Risk", `${calculations.accountRiskPercent.toFixed(2)}%`, tone],
            ["Breakeven", calculations.breakeven ? `$${calculations.breakeven.toFixed(2)}` : "Missing", "neutral"],
            ["DTE", `${Math.max(calculations.daysToExpiration, 0)} days`, calculations.daysToExpiration < 7 ? "warn" : "neutral"]
          ]}
        />
        <StatusPill
          label={tone === "good" ? `Within ${riskRulePercent(draft)}% risk rule` : tone === "warn" ? "Near risk limit" : "Above risk limit"}
          tone={tone}
        />
      </Card>
      <MissingDataCard items={missingData} />
      <ValidationSummary validation={validation} />
      {error ? <ErrorCard title="Check failed" message={errorMessage(error)} /> : null}
      <View style={styles.reviewActions}>
        <Pressable style={[styles.secondaryButton, styles.reviewAction]} onPress={onEditContract}>
          <Text style={styles.secondaryButtonText}>Edit Contract</Text>
        </Pressable>
        <Pressable style={[styles.secondaryButton, styles.reviewAction]} onPress={onEditSize}>
          <Text style={styles.secondaryButtonText}>Edit Size</Text>
        </Pressable>
      </View>
      <PrimaryButton label={loading ? "Analyzing..." : "Run Risk Check"} onPress={onRun} disabled={!validation.ready || loading} />
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

function UploadStep({ onUpload, extracting, error }) {
  const uploadActions = [
    ["camera", "Take Photo", "Use camera", "camera-outline"],
    ["library", "Photo Library", "Choose saved", "images-outline"],
    ["files", "Files", "Image, TXT, or CSV", "folder-open-outline"]
  ];
  const tips = [
    ["Full frame", "Include ticker, strike, expiration, premium, and contracts."],
    ["Readable numbers", "Avoid blur, glare, or dark cropped screenshots."],
    ["Honest read", "RiskWise only uses fields it can actually see."]
  ];

  return (
    <View>
      <StepTitle title="Upload Screenshot" subtitle="Upload a real options contract screenshot. RiskWise will only use fields it can read." />
      <Pressable style={styles.uploadBox} onPress={() => onUpload("library")} disabled={extracting}>
        <View style={styles.uploadBoxTop}>
          <View style={styles.uploadIcon}>
            <Ionicons name={extracting ? "scan-outline" : "camera-outline"} size={27} color="#7C3AED" />
          </View>
          <View style={styles.uploadSignal}>
            <View style={styles.uploadSignalDot} />
            <Text style={styles.uploadSignalText}>{extracting ? "Reading" : "No guessing"}</Text>
          </View>
        </View>
        <View style={styles.uploadPreview}>
          <View style={styles.previewHeader}>
            <View style={styles.previewLogo} />
            <View style={styles.previewLineStrong} />
          </View>
          <View style={styles.previewRow}>
            <View style={styles.previewMetric} />
            <View style={styles.previewMetricSmall} />
            <View style={styles.previewMetric} />
          </View>
          <View style={styles.scanLine} />
          <View style={styles.previewFooter}>
            <View style={styles.previewPill} />
            <View style={styles.previewPillShort} />
          </View>
        </View>
        <Text style={styles.uploadTitle}>{extracting ? "Reading screenshot..." : "Upload contract screenshot"}</Text>
        <Text style={styles.uploadSub}>PNG, JPG, TXT, or CSV - Max 1.5MB</Text>
      </Pressable>
      <View style={styles.uploadActions}>
        {uploadActions.map(([source, title, subtitle, icon]) => (
          <Pressable key={source} style={styles.uploadActionButton} onPress={() => onUpload(source)} disabled={extracting}>
            <View style={styles.uploadActionIcon}>
              <Ionicons name={icon} size={16} color={palette.green} />
            </View>
            <Text style={styles.uploadActionText}>{title}</Text>
            <Text style={styles.uploadActionSub}>{subtitle}</Text>
          </Pressable>
        ))}
      </View>
      {error ? <ErrorCard title="Extraction failed" message={error} /> : null}
      <View style={styles.platformHeader}>
        <Text style={styles.miniLabel}>Supported platforms</Text>
        <Text style={styles.platformHint}>best-effort parsing</Text>
      </View>
      <View style={styles.platformGrid}>
        {platforms.map((platform) => (
          <View key={platform} style={styles.platformChip}>
            <View style={styles.platformDot} />
            <Text style={styles.platformText}>{platform}</Text>
          </View>
        ))}
      </View>
      <Card style={styles.uploadTipCard}>
        <View style={styles.tipHeader}>
          <View style={styles.tipHeaderIcon}>
            <Ionicons name="shield-checkmark-outline" size={17} color={palette.green} />
          </View>
          <View style={styles.flex}>
            <Text style={styles.tipHeaderTitle}>Clean screenshot checklist</Text>
            <Text style={styles.tipHeaderSub}>A clearer upload means fewer manual corrections.</Text>
          </View>
        </View>
        {tips.map(([label, tip]) => (
          <View key={label} style={styles.uploadTipRow}>
            <Ionicons name="checkmark-circle" size={17} color={palette.green} />
            <View style={styles.flex}>
              <Text style={styles.uploadTipTitle}>{label}</Text>
              <Text style={styles.uploadTipText}>{tip}</Text>
            </View>
          </View>
        ))}
      </Card>
    </View>
  );
}

function ExtractionStep({ extracting, extraction, onContinue }) {
  const missing = extraction?.missing_fields || [];
  const missingLive = extraction?.missing_live_fields || [];
  return (
    <View>
      <StepTitle title={extracting ? "Extracting Details..." : "Extraction Complete"} subtitle="We're reading the screenshot and extracting visible contract details." />
      <Card style={styles.extractCard}>
        <View style={styles.progressRing}>
          <Ionicons name="scan-outline" size={28} color="#7C3AED" />
        </View>
        <Text style={styles.extractTitle}>{extracting ? "Reading visible fields..." : extraction?.message || "Extraction finished."}</Text>
        {["Reading image", "Identifying contract fields", "Checking missing values"].map((item, index) => (
          <View key={item} style={styles.tipRow}>
            <Ionicons name={!extracting || index < 1 ? "checkmark-circle" : "ellipse-outline"} size={15} color={!extracting || index < 1 ? palette.green : palette.muted} />
            <Text style={styles.tipText}>{item}</Text>
          </View>
        ))}
        {!extracting && extraction ? (
          <View style={styles.extractionMeta}>
            <Text style={styles.uploadSub}>Provider: {extraction.provider || "none"} - Confidence: {Math.round((extraction.confidence || 0) * 100)}%</Text>
            {missing.length ? <Text style={styles.errorText}>Missing required: {missing.map(friendlyMissingField).join(", ")}</Text> : <Text style={styles.successText}>All required fields were found. Still confirm them manually.</Text>}
            {missingLive.length ? <Text style={styles.helperText}>Missing optional market fields: {missingLive.map(friendlyMissingField).join(", ")}</Text> : null}
          </View>
        ) : null}
      </Card>
      <PrimaryButton label="Review Extracted Details" onPress={onContinue} disabled={extracting} />
    </View>
  );
}

function ExtractedReviewStep({ draft, extraction, status, onEdit, onContinue }) {
  const requiredMissing = status?.requiredMissing || [];
  const optionalMissing = status?.optionalMissing || [];
  const rows = [
    ["Ticker", draft.ticker || "Missing"],
    ["Strategy", draft.tradeType || "Missing"],
    ["Expiration", draft.expiration ? displayDate(parseDate(draft.expiration)) : "Missing"],
    ["Strike Price", draft.strike ? `$${Number(draft.strike || 0).toFixed(2)}` : "Missing"],
    ["Premium", draft.premium ? `$${Number(draft.premium || 0).toFixed(2)}` : "Missing"],
    ["Contracts", draft.contracts || "Missing"],
    ["Underlying Price", draft.underlyingPrice ? `$${Number(draft.underlyingPrice || 0).toFixed(2)}` : "Optional"],
    ["Bid / Ask", draft.bid || draft.ask ? `${draft.bid || "?"} / ${draft.ask || "?"}` : "Missing"],
    ["IV", draft.impliedVolatility ? `${draft.impliedVolatility}%` : "Missing"],
    ["OI / Volume", draft.openInterest || draft.contractVolume ? `${draft.openInterest || "?"} / ${draft.contractVolume || "?"}` : "Missing"]
  ];
  return (
    <View>
      <StepTitle title="Review Extracted Details" subtitle="Confirm what the screenshot actually provided." />
      <Card>
        {rows.map(([label, value]) => <KeyValue key={label} label={label} value={value} />)}
      </Card>
      {requiredMissing.length ? (
        <Card style={styles.warningCard}>
          <Text style={styles.warningTitle}>Required fields need manual correction</Text>
          <Text style={styles.warningText}>RiskWise could not clearly read: {requiredMissing.join(", ")}. Edit these before analysis.</Text>
        </Card>
      ) : null}
      {!requiredMissing.length && optionalMissing.length ? (
        <Card style={styles.warningCard}>
          <Text style={styles.warningTitle}>Can continue with partial data</Text>
          <Text style={styles.warningText}>Missing optional market context: {optionalMissing.join(", ")}. RiskWise will label these as missing and will not invent them.</Text>
        </Card>
      ) : null}
      {!requiredMissing.length && !optionalMissing.length ? (
        <Card style={styles.successCard}>
          <Text style={styles.successText}>All core fields were found. Still confirm the numbers before analysis.</Text>
        </Card>
      ) : null}
      <Pressable style={styles.secondaryButton} onPress={onEdit}>
        <Text style={styles.secondaryButtonText}>Edit Manually</Text>
      </Pressable>
      <PrimaryButton label={requiredMissing.length ? "Fix Required Fields" : "Confirm & Continue"} onPress={requiredMissing.length ? onEdit : onContinue} />
    </View>
  );
}

function ConfirmContractStep({ draft, calculations, validation, missingData, onEdit, onContinue }) {
  return (
    <View>
      <StepTitle title="Confirm Contract" subtitle="Final check before the AI committee runs." />
      <Card>
        <Text style={styles.bigSymbol}>{draft.ticker}</Text>
        <Text style={styles.resultName}>{draft.tradeType}</Text>
        <KeyValue label="Strike" value={`$${Number(draft.strike || 0).toFixed(2)}`} />
        <KeyValue label="Expiration" value={displayDate(parseDate(draft.expiration))} />
        <KeyValue label="Premium" value={`$${Number(draft.premium || 0).toFixed(2)}`} />
        <KeyValue label="Contracts" value={draft.contracts} />
        <KeyValue label="Max Loss" value={formatMoney(calculations.maxLoss)} />
      </Card>
      <ValidationSummary validation={validation} />
      <MissingDataCard items={missingData} />
      <Card style={styles.successCard}>
        <Text style={styles.successText}>Looks good. RiskWise will still treat extracted values as user-confirmed, not live market data.</Text>
      </Card>
      {!validation.ready ? (
        <Pressable style={styles.secondaryButton} onPress={onEdit}>
          <Text style={styles.secondaryButtonText}>Fix Contract Details</Text>
        </Pressable>
      ) : null}
      <PrimaryButton label="Continue to Analysis" onPress={onContinue} disabled={!validation.ready} />
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
      {error ? <ErrorCard title="Check failed" message={errorMessage(error)} /> : null}
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

function ValidationSummary({ validation }) {
  if (!validation?.messages?.length) {
    return null;
  }
  return (
    <Card style={styles.warningCard}>
      <Text style={styles.warningTitle}>Fix before analysis</Text>
      {validation.messages.map((message) => (
        <View key={message} style={styles.tipRow}>
          <Ionicons name="alert-circle-outline" size={15} color={palette.red} />
          <Text style={styles.warningText}>{message}</Text>
        </View>
      ))}
    </Card>
  );
}

function MissingDataCard({ items = [] }) {
  if (!items.length) {
    return (
      <Card style={styles.successCard}>
        <Text style={styles.successText}>No optional data warnings from the current inputs.</Text>
      </Card>
    );
  }
  return (
    <Card style={styles.missingDataCard}>
      <View style={styles.rowBetween}>
        <View style={styles.flex}>
          <Text style={styles.warningTitle}>Missing data RiskWise will not invent</Text>
          <Text style={styles.warningText}>These fields can improve confidence, but absent values stay labeled as missing.</Text>
        </View>
        <Ionicons name="shield-checkmark-outline" size={20} color={palette.green} />
      </View>
      {items.map((item) => (
        <View key={item.label} style={styles.missingDataRow}>
          <View style={styles.missingDataIcon}>
            <Ionicons name="remove-circle-outline" size={14} color="#B7791F" />
          </View>
          <View style={styles.flex}>
            <Text style={styles.missingDataTitle}>{item.label}</Text>
            <Text style={styles.missingDataText}>{item.detail}</Text>
          </View>
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
  const bidProvided = hasText(draft.bid);
  const askProvided = hasText(draft.ask);
  const bid = Number(draft.bid || 0);
  const ask = Number(draft.ask || 0);
  const ivProvided = hasText(draft.impliedVolatility);
  const iv = Number(draft.impliedVolatility || 0);
  const accountSize = Number(draft.accountSize || 0);
  const rawRiskRule = accountSize > 0 ? Number(draft.riskBudget || 0) / accountSize * 100 : 0;
  const validation = {
    ticker: selectedTicker?.symbol ? "" : "Select a ticker from search results.",
    strike: calculations.strike > 0 ? "" : "Strike is required.",
    premium: calculations.premium > 0 ? "" : "Premium is required.",
    contracts: calculations.contracts > 0 ? "" : "At least one contract is required.",
    expiration: parseDate(draft.expiration) && calculations.daysToExpiration >= 0 ? "" : "Choose a future expiration.",
    bidAsk: bidAskValidationMessage(bidProvided, askProvided, bid, ask),
    impliedVolatility: ivProvided && (iv <= 0 || iv > 500) ? "IV must be between 0 and 500%, or left blank if unknown." : "",
    openInterest: hasText(draft.openInterest) && Number(draft.openInterest) < 0 ? "Open interest cannot be negative." : "",
    contractVolume: hasText(draft.contractVolume) && Number(draft.contractVolume) < 0 ? "Volume cannot be negative." : "",
    accountSize: accountSize > 0 ? "" : "Account size must be greater than zero.",
    riskRule: rawRiskRule > 0 && rawRiskRule <= 25 ? "" : "Risk rule must be above 0% and no more than 25%.",
    structure: isSupportedLongStructure(draft.structure || draft.optionSide || draft.tradeType) ? "" : "RiskWise v1 only supports single-leg long calls and long puts."
  };
  Object.values(validation).forEach((message) => message && messages.push(message));
  return { ...validation, messages, ready: messages.length === 0 };
}

function isSupportedLongStructure(value) {
  const lower = String(value || "").toLowerCase();
  if (["call", "put"].includes(lower)) return true;
  if (["call option (long)", "put option (long)", "long call", "long put"].includes(lower)) return true;
  return false;
}

function bidAskValidationMessage(bidProvided, askProvided, bid, ask) {
  if (bidProvided && bid <= 0) return "Bid must be greater than zero, or left blank if unknown.";
  if (askProvided && ask <= 0) return "Ask must be greater than zero, or left blank if unknown.";
  if (bidProvided && askProvided && bid > ask) return "Bid cannot be greater than ask.";
  return "";
}

function buildMissingDataWarnings(draft, market) {
  const warnings = [];
  if (!hasText(draft.bid) || !hasText(draft.ask)) {
    warnings.push({ label: "Bid/ask spread", detail: "Liquidity and realistic fill quality are unknown without both bid and ask." });
  }
  if (!hasText(draft.impliedVolatility)) {
    warnings.push({ label: "Implied volatility", detail: "IV crush and volatility richness cannot be measured from missing IV." });
  }
  warnings.push({ label: "Provider Greeks", detail: "Delta, theta, gamma, and vega are not live provider values in this check." });
  if (!hasText(draft.openInterest)) {
    warnings.push({ label: "Open interest", detail: "Contract depth is unknown without open interest." });
  }
  if (!hasText(draft.contractVolume)) {
    warnings.push({ label: "Volume", detail: "Today's trading activity is unknown without contract volume." });
  }
  if (!hasText(draft.underlyingPrice) && !market?.quote?.price) {
    warnings.push({ label: "Underlying quote", detail: "Required move uses the best available manual/reference value, not a confirmed live quote." });
  }
  if (!market?.earnings?.date) {
    warnings.push({ label: "Earnings date", detail: "RiskWise will not assume an earnings date when the provider does not attach one." });
  }
  if (!hasText(draft.bid) && !hasText(draft.ask)) {
    warnings.push({ label: "Current option price", detail: "The premium is user-entered or extracted; it is not a live option-chain price." });
  }
  return warnings;
}

function buildExtractionStatus(draft, extraction) {
  const missingSet = new Set((extraction?.missing_fields || []).map(normalizeMissingField));
  const missingLiveSet = new Set((extraction?.missing_live_fields || []).map(normalizeMissingField));
  const requiredChecks = [
    ["Ticker", ["ticker", "symbol"], draft.ticker],
    ["Option side", ["option_side", "side", "strategy", "type"], draft.optionSide || draft.structure || draft.tradeType],
    ["Expiration", ["expiration", "expiry", "expiration_date"], draft.expiration],
    ["Strike", ["strike", "strike_price"], draft.strike],
    ["Premium", ["premium", "price", "mid", "mark"], draft.premium],
    ["Contracts", ["contracts", "quantity", "qty"], draft.contracts]
  ];
  const requiredMissing = requiredChecks
    .filter(([, keys, value]) => !hasText(value) || keys.some((key) => missingSet.has(key)))
    .map(([label]) => label);
  const optionalMissing = Array.from(new Set([...missingSet, ...missingLiveSet]))
    .filter((key) => !requiredChecks.some(([, keys]) => keys.includes(key)))
    .map(friendlyMissingField)
    .filter(Boolean);
  return {
    requiredMissing: unique(requiredMissing),
    optionalMissing: unique(optionalMissing)
  };
}

function normalizeMissingField(value) {
  return String(value || "").trim().replace(/([a-z])([A-Z])/g, "$1_$2").replace(/[\s-]+/g, "_").toLowerCase();
}

function friendlyMissingField(value) {
  const labels = {
    bid: "Bid",
    ask: "Ask",
    bid_ask: "Bid/ask spread",
    implied_volatility: "Implied volatility",
    iv: "Implied volatility",
    greeks: "Greeks",
    open_interest: "Open interest",
    volume: "Volume",
    contract_volume: "Volume",
    earnings_date: "Earnings date",
    current_option_price: "Current option price",
    underlying_price: "Underlying price"
  };
  return labels[value] || value.replace(/_/g, " ");
}

function hasText(value) {
  return String(value ?? "").trim().length > 0;
}

function unique(items) {
  return Array.from(new Set(items));
}

function errorMessage(error) {
  if (!error) return "Could not generate this check. Try again.";
  if (typeof error === "string") return error;
  return error.message || "Could not generate this check. Try again.";
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
      whatHelps: weakest === "Liquidity Context" ? ["Add bid and ask", "Check open interest above 1,000", "Compare IV to normal levels"] : ["Reduce contracts", "Lower premium at risk", "Wait for a cheaper long option"],
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
  const aggressive = riskTolerance === "aggressive";
  const premiumBase = horizon === "short" ? 2.15 : horizon === "medium" ? 4.2 : 6.5;
  const choices = direction === "bearish" ? ["put"] : direction === "bullish" ? ["call"] : ["call", "put"];
  return choices.map((structure) => ({
    name: structure === "put" ? "Long Put" : "Long Call",
    structure,
    direction: structure === "put" ? "bearish" : "bullish",
    why: structure === "put"
      ? "Supported v1 structure for a directional downside thesis. Max loss is the premium paid."
      : "Supported v1 structure for a directional upside thesis. Max loss is the premium paid.",
    maxProfit: structure === "put" ? "High until stock approaches zero" : "High / uncapped",
    maxLoss: "Premium paid",
    risk: aggressive ? "Aggressive" : "Single-leg v1",
    tone: aggressive ? "warn" : "good",
    premium: premiumBase
  }));
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

function pickWebScreenshot(source) {
  return new Promise((resolve) => {
    const inputEl = document.createElement("input");
    inputEl.type = "file";
    inputEl.accept = source === "files" ? "image/*,.txt,.csv,text/plain,text/csv" : "image/*";
    if (source === "camera") {
      inputEl.capture = "environment";
    }
    inputEl.onchange = async () => {
      const file = Array.from(inputEl.files || [])[0];
      if (!file) {
        resolve(null);
        return;
      }
      resolve(await readScreenshotFile(file, source));
    };
    inputEl.click();
  });
}

async function pickNativeScreenshot(source) {
  if (source === "files") {
    return pickNativeDocumentAttachment();
  }
  const permission =
    source === "camera"
      ? await ImagePicker.requestCameraPermissionsAsync()
      : await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (permission.status !== "granted") {
    throw new Error(`${source === "camera" ? "Camera" : "Photo library"} permission was not granted.`);
  }
  const result =
    source === "camera"
      ? await ImagePicker.launchCameraAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.75, base64: true })
      : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.75, base64: true });
  if (result.canceled || !result.assets?.[0]) {
    return null;
  }
  return nativeScreenshotAttachment(result.assets[0], source);
}

function readScreenshotFile(file, source) {
  return new Promise((resolve, reject) => {
    const isText = file.type === "text/plain" || file.type === "text/csv" || /\.(txt|csv)$/i.test(file.name || "");
    const isImage = file.type?.startsWith("image/");
    if (!isImage && !isText) {
      reject(new Error("Upload a PNG/JPG screenshot or a readable TXT/CSV contract export."));
      return;
    }
    if (file.size > 1_500_000) {
      reject(new Error("Use a file under 1.5MB so RiskWise can process it."));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      resolve({
        name: file.name || (isText ? "contract.txt" : "contract-screenshot.jpg"),
        type: file.type || (isText ? "text/plain" : "image/jpeg"),
        size: file.size || 0,
        source,
        ...(isText ? { text: String(reader.result || "") } : { dataUrl: String(reader.result || "") })
      });
    };
    reader.onerror = () => reject(new Error("Could not read that upload."));
    if (isText) {
      reader.readAsText(file);
    } else {
      reader.readAsDataURL(file);
    }
  });
}

function nativeScreenshotAttachment(asset, source) {
  const mime = asset.mimeType || "image/jpeg";
  const extension = mime.includes("png") ? "png" : "jpg";
  return {
    name: asset.fileName || `${source}-contract-screenshot.${extension}`,
    type: mime,
    size: asset.fileSize || 0,
    source,
    uri: asset.uri,
    dataUrl: asset.base64 ? `data:${mime};base64,${asset.base64}` : ""
  };
}

async function pickNativeDocumentAttachment() {
  const result = await DocumentPicker.getDocumentAsync({
    type: ["image/*", "text/plain", "text/csv", "application/csv"],
    copyToCacheDirectory: true
  });
  if (result.canceled || !result.assets?.[0]) {
    return null;
  }
  const asset = result.assets[0];
  const isText = asset.mimeType === "text/plain" || asset.mimeType === "text/csv" || /\.(txt|csv)$/i.test(asset.name || "");
  const isImage = String(asset.mimeType || "").startsWith("image/");
  if (!isText && !isImage) {
    throw new Error("Upload a PNG/JPG screenshot or a readable TXT/CSV contract export.");
  }
  if (asset.size && asset.size > 1_500_000) {
    throw new Error("Use a file under 1.5MB so RiskWise can process it.");
  }
  if (isText) {
    const text = await FileSystem.readAsStringAsync(asset.uri, { encoding: FileSystem.EncodingType.UTF8 });
    return {
      name: asset.name || "contract.txt",
      type: asset.mimeType || "text/plain",
      size: asset.size || text.length,
      source: "files",
      text
    };
  }
  const base64 = await FileSystem.readAsStringAsync(asset.uri, { encoding: FileSystem.EncodingType.Base64 });
  const mime = asset.mimeType || "image/jpeg";
  return {
    name: asset.name || "contract-screenshot.jpg",
    type: mime,
    size: asset.size || 0,
    source: "files",
    uri: asset.uri,
    dataUrl: `data:${mime};base64,${base64}`
  };
}

function estimateUploadedRisk(fields, draft) {
  const premium = Number(fields.premium || draft.premium || 0);
  const contracts = Number(fields.contracts || draft.contracts || 1);
  const maxLoss = premium > 0 && contracts > 0 ? premium * contracts * 100 : Number(draft.amountAtRisk || 0);
  return maxLoss ? String(Math.round(maxLoss * 100) / 100) : draft.amountAtRisk;
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
  warningCard: { backgroundColor: "#FFF8E8", borderColor: "#FADFA2" },
  warningTitle: { color: palette.dark, fontSize: 12, fontWeight: "900", marginBottom: 6 },
  warningText: { flex: 1, color: "#6B5A32", fontSize: 10, lineHeight: 15, fontWeight: "800" },
  missingDataCard: { backgroundColor: "#FFFCF4", borderColor: "#FADFA2" },
  missingDataRow: { flexDirection: "row", alignItems: "flex-start", gap: 9, paddingTop: 9, marginTop: 8, borderTopWidth: 1, borderTopColor: "#F5E7C5" },
  missingDataIcon: { width: 24, height: 24, borderRadius: 12, backgroundColor: "#FFF1D6", alignItems: "center", justifyContent: "center" },
  missingDataTitle: { color: palette.dark, fontSize: 11, fontWeight: "900" },
  missingDataText: { color: "#6B5A32", fontSize: 9, lineHeight: 13, fontWeight: "800", marginTop: 2 },
  reviewHeroCard: { backgroundColor: "#FBFFFC", borderColor: "#CFEFD8" },
  reviewFacts: { marginTop: 10 },
  reviewActions: { flexDirection: "row", gap: 8, marginTop: 2 },
  reviewAction: { flex: 1 },
  strategyCard: { padding: 14 },
  strategyName: { color: palette.dark, fontSize: 14, fontWeight: "900" },
  strategyWhy: { color: palette.muted, fontSize: 10, lineHeight: 15, fontWeight: "700", marginTop: 4, maxWidth: 250 },
  strategyFacts: { flexDirection: "row", gap: 12, marginVertical: 12 },
  uploadBox: {
    minHeight: 220,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: "#D8C7FF",
    backgroundColor: "#FCFAFF",
    padding: 14,
    marginBottom: 12,
    overflow: "hidden",
    shadowColor: "#6D28D9",
    shadowOpacity: 0.13,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 14 }
  },
  uploadBoxTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 10 },
  uploadIcon: { width: 48, height: 48, borderRadius: 16, backgroundColor: "#F1E9FF", alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: "#E4D7FF" },
  uploadSignal: { minHeight: 27, borderRadius: 999, paddingHorizontal: 10, flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#ECE6FF" },
  uploadSignalDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: palette.green },
  uploadSignalText: { color: palette.dark, fontSize: 9, fontWeight: "900" },
  uploadPreview: { minHeight: 78, borderRadius: 16, borderWidth: 1, borderColor: "#E6DCFF", backgroundColor: "#FFFFFF", padding: 10, marginBottom: 11 },
  previewHeader: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 10 },
  previewLogo: { width: 20, height: 20, borderRadius: 10, backgroundColor: "#E8F8EF" },
  previewLineStrong: { flex: 1, height: 9, borderRadius: 999, backgroundColor: "#18233B" },
  previewRow: { flexDirection: "row", gap: 8, marginBottom: 10 },
  previewMetric: { flex: 1, height: 19, borderRadius: 8, backgroundColor: "#F1F5F9" },
  previewMetricSmall: { width: 50, height: 19, borderRadius: 8, backgroundColor: "#F1E9FF" },
  scanLine: { height: 2, borderRadius: 999, backgroundColor: "#8B5CF6", marginBottom: 8 },
  previewFooter: { flexDirection: "row", gap: 8 },
  previewPill: { width: 80, height: 9, borderRadius: 999, backgroundColor: "#E8F8EF" },
  previewPillShort: { width: 54, height: 9, borderRadius: 999, backgroundColor: "#EEF2F7" },
  uploadTitle: { color: palette.dark, fontSize: 15, fontWeight: "900", textAlign: "center" },
  uploadSub: { color: palette.muted, fontSize: 9, fontWeight: "800", marginTop: 4, textAlign: "center" },
  uploadActions: { flexDirection: "row", gap: 8, marginBottom: 12 },
  uploadActionButton: {
    flex: 1,
    minHeight: 73,
    borderRadius: 17,
    borderWidth: 1,
    borderColor: "#DDEBDD",
    backgroundColor: "#FFFFFF",
    padding: 8,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#12351B",
    shadowOpacity: 0.06,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 }
  },
  uploadActionIcon: { width: 26, height: 26, borderRadius: 13, backgroundColor: palette.greenSoft, alignItems: "center", justifyContent: "center", marginBottom: 5 },
  uploadActionText: { color: palette.dark, fontSize: 10, fontWeight: "900", textAlign: "center" },
  uploadActionSub: { color: palette.muted, fontSize: 8, fontWeight: "800", marginTop: 3, textAlign: "center" },
  platformHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 7 },
  platformHint: { color: "#8A63D2", fontSize: 9, fontWeight: "900" },
  platformGrid: { flexDirection: "row", flexWrap: "wrap", gap: 7, marginBottom: 10 },
  platformChip: { borderRadius: 999, backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#E6E1F5", paddingHorizontal: 9, paddingVertical: 6, flexDirection: "row", alignItems: "center", gap: 6 },
  platformDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: "#8B5CF6" },
  platformText: { color: palette.dark, fontSize: 9, fontWeight: "900" },
  uploadTipCard: { backgroundColor: "#FEFFFE", borderColor: "#D7F0DE", padding: 13 },
  tipHeader: { flexDirection: "row", alignItems: "center", gap: 9, marginBottom: 9 },
  tipHeaderIcon: { width: 31, height: 31, borderRadius: 16, backgroundColor: palette.greenSoft, alignItems: "center", justifyContent: "center" },
  tipHeaderTitle: { color: palette.dark, fontSize: 13, fontWeight: "900" },
  tipHeaderSub: { color: palette.muted, fontSize: 9, lineHeight: 12, fontWeight: "800", marginTop: 2 },
  uploadTipRow: { flexDirection: "row", alignItems: "flex-start", gap: 8, paddingTop: 8, borderTopWidth: 1, borderTopColor: "#EEF5F0" },
  uploadTipTitle: { color: palette.dark, fontSize: 11, fontWeight: "900" },
  uploadTipText: { color: palette.muted, fontSize: 9, lineHeight: 12, fontWeight: "800", marginTop: 1 },
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
