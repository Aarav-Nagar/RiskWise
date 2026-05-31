import React, { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Card } from "../components/Card";
import { ConfidenceRing, IntelligenceStrip, MiniLineChart } from "../components/InsightVisuals";
import { Metric } from "../components/Metric";
import { ErrorCard, Field, Header, money, PrimaryButton, ScreenScroll, SelectLike, sharedText } from "../components/Shared";
import { getMarketBundle, getOptionContractContext, getOptionsExpirations, searchMarketSymbols } from "../services/apiClient";
import { palette } from "../theme/theme";

const tradeTypes = ["Call Option (Long)", "Put Option (Long)", "Stock Position (Long)", "Watchlist Only"];
const timeframes = ["Intraday", "1-3 Days", "1-2 Weeks", "1 Month+"];
const optionSides = [
  { label: "Call", value: "call" },
  { label: "Put", value: "put" }
];
const startChoices = [
  {
    key: "stock",
    title: "Stock Idea",
    text: "I have a stock idea and want to explore it.",
    icon: "trending-up"
  },
  {
    key: "option",
    title: "Option Contract",
    text: "I know contract details and want to evaluate it.",
    icon: "document-text"
  },
  {
    key: "screenshot",
    title: "Screenshot",
    text: "Upload a contract screenshot from a trading platform.",
    icon: "camera"
  }
];
const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const dayLabels = ["S", "M", "T", "W", "T", "F", "S"];

export function CheckScreen({ draft, setDraft, onCheck, loading, error }) {
  const [stage, setStage] = useState("start");
  const [openStep, setOpenStep] = useState(1);
  const [tickerQuery, setTickerQuery] = useState(draft.ticker || "");
  const [tickerOpen, setTickerOpen] = useState(false);
  const [tickerResults, setTickerResults] = useState([]);
  const [tickerLoading, setTickerLoading] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState(() => ({
    symbol: draft.ticker || "",
    name: draft.tickerName || "",
    exchange: draft.tickerExchange || ""
  }));
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [visibleMonth, setVisibleMonth] = useState(startOfMonth(parseDate(draft.expiration) || addDays(new Date(), 30)));
  const [marketContext, setMarketContext] = useState(null);
  const [optionContext, setOptionContext] = useState(null);
  const [optionExpirations, setOptionExpirations] = useState([]);
  const [marketLoading, setMarketLoading] = useState(false);
  const [investigationReport, setInvestigationReport] = useState(null);
  const [selectedIssue, setSelectedIssue] = useState(null);
  const [debateLevel, setDebateLevel] = useState("Moderate");

  const isOption = draft.tradeType.includes("Option");
  const amountAtRisk = numberFromMoney(draft.amountAtRisk);
  const premium = numberFromMoney(draft.premium);
  const contracts = Number(String(draft.contracts || "").replace(/[^0-9]/g, "") || 0);
  const calculatedRisk = isOption && premium > 0 && contracts > 0 ? Math.round(premium * contracts * 100) : 0;
  const accountSize = Number(draft.accountSize || 1);
  const riskPercentNumber = amountAtRisk / accountSize * 100;
  const expirationDate = parseDate(draft.expiration);
  const daysToExpiration = expirationDate ? dayDiff(stripTime(new Date()), expirationDate) : null;
  const validation = useMemo(
    () => validateDraft({ draft, selectedTicker, tickerQuery, amountAtRisk, riskPercentNumber, expirationDate }),
    [draft, selectedTicker, tickerQuery, amountAtRisk, riskPercentNumber, expirationDate]
  );
  const investigation = useMemo(
    () => buildInvestigation({ draft, report: investigationReport, selectedTicker, marketContext, optionContext, validation, riskPercentNumber, daysToExpiration, calculatedRisk }),
    [draft, investigationReport, selectedTicker, marketContext, optionContext, validation, riskPercentNumber, daysToExpiration, calculatedRisk]
  );

  useEffect(() => {
    const clean = tickerQuery.trim();
    if (clean.length < 1 || selectedTicker?.symbol === clean.toUpperCase()) {
      setTickerResults([]);
      return undefined;
    }
    let cancelled = false;
    const timeout = setTimeout(async () => {
      setTickerLoading(true);
      try {
        const rows = await searchMarketSymbols(clean);
        if (!cancelled) {
          setTickerResults(withExactSymbolFallback(clean, rows).slice(0, 10));
          setTickerOpen(true);
        }
      } catch (err) {
        if (!cancelled) {
          setTickerResults(withExactSymbolFallback(clean, []));
          setTickerOpen(true);
        }
      } finally {
        if (!cancelled) {
          setTickerLoading(false);
        }
      }
    }, 180);
    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [tickerQuery, selectedTicker?.symbol]);

  useEffect(() => {
    const symbol = selectedTicker?.symbol;
    if (!symbol) {
      setMarketContext(null);
      setOptionContext(null);
      setOptionExpirations([]);
      return undefined;
    }
    let cancelled = false;
    setMarketLoading(true);
    Promise.allSettled([getMarketBundle(symbol), getOptionsExpirations(symbol)])
      .then(([bundleResult, expirationsResult]) => {
        if (cancelled) return;
        const bundle = bundleResult.status === "fulfilled" ? bundleResult.value : null;
        const expirations = expirationsResult.status === "fulfilled" ? expirationsResult.value : null;
        setMarketContext(bundle);
        setOptionExpirations(Array.isArray(expirations?.expirations) ? expirations.expirations.slice(0, 6) : []);
        if (bundle?.quote?.price) {
          setDraft((current) => ({ ...current, underlyingPrice: String(bundle.quote.price) }));
        }
      })
      .finally(() => {
        if (!cancelled) setMarketLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedTicker?.symbol, setDraft]);

  useEffect(() => {
    const symbol = selectedTicker?.symbol;
    if (!symbol || !isOption || !draft.expiration || !draft.strike) {
      setOptionContext(null);
      return undefined;
    }
    let cancelled = false;
    getOptionContractContext({
      ticker: symbol,
      expiration: draft.expiration,
      strike: draft.strike,
      optionSide: draft.optionSide
    })
      .then((context) => {
        if (!cancelled) setOptionContext(context);
      })
      .catch(() => {
        if (!cancelled) setOptionContext(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedTicker?.symbol, isOption, draft.expiration, draft.strike, draft.optionSide]);

  function selectTicker(item) {
    const symbol = normalizeSymbol(item.symbol);
    const normalizedItem = {
      ...item,
      symbol,
      name: item.name || `${symbol} selected ticker`,
      exchange: item.exchange || "US"
    };
    setSelectedTicker(normalizedItem);
    setTickerQuery(symbol);
    setTickerOpen(false);
    setDraft({
      ...draft,
      ticker: symbol,
      tickerName: normalizedItem.name,
      tickerExchange: normalizedItem.exchange,
      tickerSource: item.source || "search"
    });
  }

  function updateTicker(text) {
    setTickerQuery(text);
    setSelectedTicker(null);
  }

  function selectExpiration(date) {
    const iso = toIsoDate(date);
    setDraft({ ...draft, expiration: iso, expirationSource: "calendar" });
    setCalendarOpen(false);
  }

  function selectExpirationValue(expiration) {
    setDraft({ ...draft, expiration, expirationSource: "estimated_market_calendar" });
    setCalendarOpen(false);
  }

  function updateOptionSizing(field, value) {
    const clean = field === "contracts" ? value.replace(/[^0-9]/g, "") : value.replace(/[^0-9.]/g, "");
    const next = { ...draft, [field]: clean };
    const nextPremium = Number(String(field === "premium" ? clean : draft.premium || "").replace(/[^0-9.]/g, "") || 0);
    const nextContracts = Number(String(field === "contracts" ? clean : draft.contracts || "").replace(/[^0-9]/g, "") || 0);
    if (nextPremium > 0 && nextContracts > 0 && isOption) {
      next.amountAtRisk = String(Math.round(nextPremium * nextContracts * 100));
    }
    setDraft(next);
  }

  async function reviewTrade() {
    if (!validation.ready || loading) {
      return;
    }
    try {
      const report = await onCheck({ stayOnCheck: true });
      setInvestigationReport(report);
      setSelectedIssue(null);
      setStage("summary");
    } catch {
      // The error card below receives the message from app state.
    }
  }

  if (stage === "wizard") {
    return (
      <ScreenScroll>
        <WizardHeader onBack={() => setStage("start")} />
        <ProgressDots current={openStep} total={6} />
        <WizardStep number={1} title="Choose Ticker" open={openStep === 1} onPress={() => setOpenStep(1)} complete={Boolean(selectedTicker?.symbol)}>
          <TickerPicker
            query={tickerQuery}
            setQuery={updateTicker}
            open={tickerOpen}
            setOpen={setTickerOpen}
            results={tickerResults}
            loading={tickerLoading}
            selectedTicker={selectedTicker}
            onSelect={selectTicker}
            error={validation.ticker}
          />
          <RecentTickers onSelect={(symbol) => selectTicker({ symbol, name: recentName(symbol), exchange: "US", source: "recent" })} />
        </WizardStep>
        <WizardStep number={2} title="Direction" open={openStep === 2} onPress={() => setOpenStep(2)} complete={Boolean(draft.optionSide)}>
          <SegmentedOptions
            label="Option Side"
            value={draft.optionSide || "call"}
            options={optionSides}
            onSelect={(optionSide) => setDraft({ ...draft, optionSide, tradeType: optionSide === "put" ? "Put Option (Long)" : "Call Option (Long)" })}
          />
          <SelectLike
            label="Trade Type"
            value={draft.tradeType}
            options={tradeTypes}
            onSelect={(tradeType) => setDraft({ ...draft, tradeType, optionSide: tradeType.includes("Put") ? "put" : "call" })}
          />
        </WizardStep>
        <WizardStep number={3} title="Structure" open={openStep === 3} onPress={() => setOpenStep(3)} complete={isOption}>
          <ContractContext context={marketContext} optionContext={optionContext} loading={marketLoading} selectedTicker={selectedTicker} />
        </WizardStep>
        <WizardStep number={4} title="Expiration" open={openStep === 4} onPress={() => setOpenStep(4)} complete={!validation.expiration}>
          <ExpirationShortcuts expirations={optionExpirations} selected={draft.expiration} onSelect={selectExpirationValue} />
          <ExpirationPicker
            value={draft.expiration}
            date={expirationDate}
            daysToExpiration={daysToExpiration}
            open={calendarOpen}
            setOpen={setCalendarOpen}
            visibleMonth={visibleMonth}
            setVisibleMonth={setVisibleMonth}
            onSelect={selectExpiration}
            error={validation.expiration}
          />
        </WizardStep>
        <WizardStep number={5} title="Strike & Premium" open={openStep === 5} onPress={() => setOpenStep(5)} complete={!validation.strike && !validation.premium}>
          <View style={styles.inputRow}>
            <Field
              label="Strike"
              value={draft.strike}
              onChangeText={(strike) => setDraft({ ...draft, strike: strike.replace(/[^0-9.]/g, "") })}
              keyboardType="decimal-pad"
              error={validation.strike}
            />
            <Field
              label="Premium"
              value={draft.premium || ""}
              onChangeText={(premiumValue) => updateOptionSizing("premium", premiumValue)}
              keyboardType="decimal-pad"
              error={validation.premium}
              helper="Per share. One option contract controls 100 shares."
            />
          </View>
        </WizardStep>
        <WizardStep number={6} title="Contracts & Size" open={openStep === 6} onPress={() => setOpenStep(6)} complete={!validation.contracts && !validation.amount}>
          <View style={styles.inputRow}>
            <Field
              label="Contracts"
              value={draft.contracts || ""}
              onChangeText={(contractsValue) => updateOptionSizing("contracts", contractsValue)}
              keyboardType="numeric"
              error={validation.contracts}
            />
            <Field
              label="Risk"
              value={`$${draft.amountAtRisk}`}
              onChangeText={(amount) => setDraft({ ...draft, amountAtRisk: amount.replace(/[^0-9.]/g, "") })}
              suffix={`${riskPercentNumber.toFixed(1)}%`}
              keyboardType="numeric"
              error={validation.amount}
            />
          </View>
          <SelectLike label="Timeframe" value={draft.timeframe} options={timeframes} onSelect={(timeframe) => setDraft({ ...draft, timeframe })} />
          <SizingStrip amountAtRisk={amountAtRisk} calculatedRisk={calculatedRisk} riskPercentNumber={riskPercentNumber} />
        </WizardStep>
        <IntelligenceStrip
          agreement={validation.ready ? 74 : 49}
          agents={5}
          pattern={validation.ready ? "Ready for investigation" : "Missing contract details"}
          missing={validation.messages.length}
        />
        {!validation.ready ? <InlineWarning items={validation.messages} /> : null}
        {error ? <ErrorCard message="Could not generate this check. Try again." /> : null}
        <PrimaryButton label={loading ? "Reviewing..." : "Review Trade"} onPress={reviewTrade} disabled={loading || !validation.ready} />
      </ScreenScroll>
    );
  }

  if (stage === "summary") {
    return <InvestigationSummary investigation={investigation} draft={draft} selectedTicker={selectedTicker} onBack={() => setStage("wizard")} onDebate={() => setStage("debate")} onIssue={(issue) => { setSelectedIssue(issue); setStage("issue"); }} />;
  }

  if (stage === "debate") {
    return <CommitteeDebate investigation={investigation} level={debateLevel} setLevel={setDebateLevel} onBack={() => setStage("summary")} />;
  }

  if (stage === "issue") {
    return <IssueCard issue={selectedIssue || investigation.issues[0]} onBack={() => setStage("summary")} />;
  }

  return (
    <ScreenScroll>
      <Header
        title={`Good morning, ${draft.user}`}
        subtitle="Check the contract before the story convinces you."
        right={<Text style={styles.bell}>!</Text>}
      />
      <Card style={styles.snapshot}>
        <View style={styles.rowBetween}>
          <Text style={sharedText.cardLabel}>Account Snapshot</Text>
          <View style={[styles.statusPill, riskPercentNumber > 3 && styles.statusPillRisk]}>
            <Text style={[styles.statusText, riskPercentNumber > 3 && styles.statusTextRisk]}>{riskPercentNumber > 3 ? "High" : "OK"}</Text>
          </View>
        </View>
        <View style={styles.twoCols}>
          <Metric label="Account Size" value={money(draft.accountSize)} />
          <Metric label="Risk Budget" value={`${money(draft.riskBudget)} (${Number(draft.riskBudget || 0) / accountSize * 100 || 0}%)`} />
        </View>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, riskPercentNumber > 3 && styles.progressRisk, { width: `${Math.min(riskPercentNumber * 24, 100)}%` }]} />
        </View>
        <Text style={sharedText.microcopy}>{riskPercentNumber.toFixed(1)}% of account planned for this check</Text>
      </Card>
      <Card>
        <Text style={sharedText.sectionTitle}>How would you like to check a trade?</Text>
        {startChoices.map((choice) => (
          <Pressable key={choice.key} style={[styles.choiceCard, choice.key === "option" && styles.choiceCardActive]} onPress={() => setStage("wizard")}>
            <View style={[styles.choiceIcon, choice.key === "option" && styles.choiceIconActive]}>
              <Ionicons name={choice.icon} size={18} color={choice.key === "option" ? "#FFFFFF" : palette.green} />
            </View>
            <View style={styles.choiceCopy}>
              <Text style={styles.choiceTitle}>{choice.title}</Text>
              <Text style={styles.choiceText}>{choice.text}</Text>
            </View>
            <Ionicons name="chevron-forward" size={17} color={palette.muted} />
          </Pressable>
        ))}
      </Card>
    </ScreenScroll>
  );
}

function WizardHeader({ onBack }) {
  return (
    <View style={styles.wizardHeader}>
      <Pressable style={styles.backButton} onPress={onBack}>
        <Ionicons name="chevron-back" size={18} color={palette.dark} />
      </Pressable>
      <View>
        <Text style={styles.wizardTitle}>Build Your Trade</Text>
        <Text style={styles.wizardSub}>Step-by-step contract builder</Text>
      </View>
    </View>
  );
}

function ProgressDots({ current, total }) {
  return (
    <View style={styles.stepTrack}>
      {Array.from({ length: total }, (_, index) => (
        <View key={index} style={[styles.stepDot, index + 1 <= current && styles.stepDotActive]} />
      ))}
    </View>
  );
}

function WizardStep({ number, title, open, complete, onPress, children }) {
  return (
    <Card style={styles.stepCard}>
      <Pressable style={styles.stepHeader} onPress={onPress}>
        <View style={styles.stepTitleWrap}>
          <Text style={styles.stepNumber}>{number}.</Text>
          <Text style={styles.stepTitle}>{title}</Text>
        </View>
        <View style={styles.stepRight}>
          {complete ? <Ionicons name="checkmark-circle" size={16} color={palette.green} /> : null}
          <Ionicons name={open ? "chevron-up" : "chevron-forward"} size={16} color={palette.muted} />
        </View>
      </Pressable>
      {open ? <View style={styles.stepBody}>{children}</View> : null}
    </Card>
  );
}

function TickerPicker({ query, setQuery, open, setOpen, results, loading, selectedTicker, onSelect, error }) {
  return (
    <View style={styles.fieldWrap}>
      <Text style={styles.inputLabel}>Ticker</Text>
      <View style={[styles.searchBox, error && styles.fieldError]}>
        <Ionicons name="search" size={16} color={palette.muted} />
        <TextInput
          value={query}
          onChangeText={setQuery}
          onFocus={() => setOpen(true)}
          placeholder="Search ticker or company"
          placeholderTextColor="#9AA5A0"
          autoCapitalize="characters"
          style={styles.searchInput}
        />
        {selectedTicker?.symbol ? <Ionicons name="checkmark-circle" size={17} color={palette.green} /> : null}
      </View>
      {selectedTicker?.name ? (
        <View style={styles.selectedTickerCard}>
          <Text style={styles.selectedTickerSymbol}>{selectedTicker.symbol}</Text>
          <Text style={styles.selectedTickerName} numberOfLines={1}>{selectedTicker.name}</Text>
        </View>
      ) : null}
      {error ? <Text style={styles.fieldErrorText}>{error}</Text> : null}
      {open && (query.trim().length > 0 || results.length > 0) ? (
        <View style={styles.dropdown}>
          {loading ? <Text style={styles.dropdownEmpty}>Searching...</Text> : null}
          {!loading && results.length === 0 ? <Text style={styles.dropdownEmpty}>Type a symbol, then select a match.</Text> : null}
          {results.map((item) => (
            <Pressable key={`${item.symbol}-${item.name}`} style={styles.tickerOption} onPress={() => onSelect(item)}>
              <View style={styles.tickerLogo}>
                <Text style={styles.tickerLogoText}>{item.symbol.slice(0, 1)}</Text>
              </View>
              <View style={styles.tickerCopy}>
                <Text style={styles.tickerSymbol}>{item.symbol}</Text>
                <Text style={styles.tickerName} numberOfLines={1}>{item.name}</Text>
              </View>
              <Text style={styles.exchangeText}>{item.exchange || "US"}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function RecentTickers({ onSelect }) {
  return (
    <View style={styles.recentWrap}>
      <Text style={styles.miniLabel}>Recent</Text>
      <View style={styles.recentRow}>
        {["AAPL", "MSFT", "SPY", "NVDA", "AMZN"].map((symbol) => (
          <Pressable key={symbol} style={styles.recentChip} onPress={() => onSelect(symbol)}>
            <Text style={styles.recentText}>{symbol}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function ContractContext({ context, optionContext, loading, selectedTicker }) {
  if (!selectedTicker?.symbol) {
    return <Text style={styles.emptyHint}>Choose a ticker first so RiskWise can attach market context.</Text>;
  }
  const quote = context?.quote;
  const selected = optionContext?.selected || {};
  const price = quote?.price;
  const chartData = price ? [price * 0.985, price * 0.99, price * 0.997, price * 0.992, price * 1.004, price * 1.01] : [42, 45, 44, 48, 47, 50];
  return (
    <View style={styles.contextBox}>
      <View style={styles.rowBetween}>
        <View>
          <Text style={styles.contextTitle}>{selectedTicker.symbol} structure context</Text>
          <Text style={styles.contextSub} numberOfLines={1}>{loading ? "Loading quote..." : context?.profile?.companyName || selectedTicker.name || "Selected ticker"}</Text>
        </View>
        <View style={styles.priceBadge}>
          <Text style={styles.priceText}>{price ? `$${Number(price).toFixed(2)}` : "Quote"}</Text>
        </View>
      </View>
      <MiniLineChart data={chartData} height={54} />
      <View style={styles.contextChips}>
        <Text style={styles.contextChip}>{context?.profile?.sector || "Sector pending"}</Text>
        <Text style={styles.contextChip}>{selected.moneynessLabel || "Moneyness pending"}</Text>
        <Text style={styles.contextChip}>{optionContext?.status?.replaceAll("_", " ") || "Options data later"}</Text>
      </View>
    </View>
  );
}

function SegmentedOptions({ label, value, options, onSelect }) {
  return (
    <View style={styles.fieldWrap}>
      <Text style={styles.inputLabel}>{label}</Text>
      <View style={styles.segmentRow}>
        {options.map((option) => (
          <Pressable key={option.value} style={[styles.segmentButton, value === option.value && styles.segmentButtonActive]} onPress={() => onSelect(option.value)}>
            <Text style={[styles.segmentText, value === option.value && styles.segmentTextActive]}>{option.label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function ExpirationShortcuts({ expirations, selected, onSelect }) {
  if (!expirations?.length) {
    return null;
  }
  return (
    <View style={styles.expirationStrip}>
      <Text style={styles.miniLabel}>Estimated monthly expirations</Text>
      <View style={styles.expirationChips}>
        {expirations.slice(0, 4).map((expiration) => (
          <Pressable key={expiration} style={[styles.expirationChip, selected === expiration && styles.expirationChipActive]} onPress={() => onSelect(expiration)}>
            <Text style={[styles.expirationChipText, selected === expiration && styles.expirationChipTextActive]}>{shortDate(expiration)}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function ExpirationPicker({ value, date, daysToExpiration, open, setOpen, visibleMonth, setVisibleMonth, onSelect, error }) {
  const dates = buildCalendar(visibleMonth);
  const today = stripTime(new Date());
  return (
    <View style={styles.fieldWrap}>
      <Text style={styles.inputLabel}>Expiration</Text>
      <Pressable style={[styles.dateButton, error && styles.fieldError]} onPress={() => setOpen(!open)}>
        <View>
          <Text style={styles.dateText}>{date ? displayDate(date) : value || "Choose date"}</Text>
          <Text style={styles.dateSub}>{daysToExpiration !== null && daysToExpiration >= 0 ? `${daysToExpiration} calendar days left` : "Future dates only"}</Text>
        </View>
        <Ionicons name="calendar-outline" size={18} color={palette.green} />
      </Pressable>
      {error ? <Text style={styles.fieldErrorText}>{error}</Text> : null}
      {open ? (
        <View style={styles.calendarPanel}>
          <View style={styles.calendarHeader}>
            <Pressable style={styles.calendarNav} onPress={() => setVisibleMonth(startOfMonth(addMonths(visibleMonth, -1)))}>
              <Ionicons name="chevron-back" size={14} color={palette.dark} />
            </Pressable>
            <Text style={styles.calendarTitle}>{monthNames[visibleMonth.getMonth()]} {visibleMonth.getFullYear()}</Text>
            <Pressable style={styles.calendarNav} onPress={() => setVisibleMonth(startOfMonth(addMonths(visibleMonth, 1)))}>
              <Ionicons name="chevron-forward" size={14} color={palette.dark} />
            </Pressable>
          </View>
          <View style={styles.weekRow}>
            {dayLabels.map((label, index) => <Text key={`${label}-${index}`} style={styles.weekLabel}>{label}</Text>)}
          </View>
          <View style={styles.daysGrid}>
            {dates.map((item) => {
              const disabled = item.date < today || !item.inMonth;
              const selected = date && toIsoDate(item.date) === toIsoDate(date);
              return (
                <Pressable
                  key={toIsoDate(item.date)}
                  style={[styles.dayCell, selected && styles.dayCellSelected, disabled && styles.dayCellDisabled]}
                  disabled={disabled}
                  onPress={() => onSelect(item.date)}
                >
                  <Text style={[styles.dayText, selected && styles.dayTextSelected, disabled && styles.dayTextDisabled]}>{item.date.getDate()}</Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      ) : null}
    </View>
  );
}

function SizingStrip({ amountAtRisk, calculatedRisk, riskPercentNumber }) {
  const items = [
    ["Max loss", money(amountAtRisk)],
    ["Calc risk", calculatedRisk ? money(calculatedRisk) : "Pending"],
    ["Account", `${riskPercentNumber.toFixed(1)}%`]
  ];
  return (
    <View style={styles.sizingStrip}>
      {items.map(([label, value]) => (
        <View key={label} style={styles.sizingItem}>
          <Text style={styles.miniLabel}>{label}</Text>
          <Text style={styles.sizingValue}>{value}</Text>
        </View>
      ))}
    </View>
  );
}

function InvestigationSummary({ investigation, draft, selectedTicker, onBack, onDebate, onIssue }) {
  return (
    <ScreenScroll>
      <View style={styles.wizardHeader}>
        <Pressable style={styles.backButton} onPress={onBack}>
          <Ionicons name="chevron-back" size={18} color={palette.dark} />
        </Pressable>
        <View style={styles.flex}>
          <Text style={styles.wizardTitle}>Trade Investigation</Text>
          <Text style={styles.wizardSub}>High-level snapshot before the debate</Text>
        </View>
        <Ionicons name="share-outline" size={18} color={palette.dark} />
      </View>
      <Card style={styles.summaryHero}>
        <View style={styles.rowBetween}>
          <View style={styles.flex}>
            <Text style={styles.heroTicker}>{selectedTicker?.symbol || draft.ticker} ${draft.strike} {titleCase(draft.optionSide || "call")}</Text>
            <Text style={styles.heroSub}>{displayDate(parseDate(draft.expiration))} - {draft.contracts || 1} Contract</Text>
          </View>
          <ConfidenceRing value={investigation.score} label="/100" sublabel={investigation.verdict} size={84} />
        </View>
        <View style={styles.convictionBox}>
          <View>
            <Text style={styles.convictionTitle}>{investigation.conviction}</Text>
            <Text style={styles.convictionSub}>{investigation.verdict}</Text>
          </View>
          <View style={styles.signalDot} />
        </View>
        <View style={styles.summaryGrid}>
          {investigation.summaryCards.map((item) => (
            <View key={item.label} style={styles.summaryMini}>
              <Ionicons name={item.icon} size={15} color={item.tone === "good" ? palette.green : item.tone === "risk" ? palette.red : palette.amber} />
              <Text style={styles.summaryMiniLabel}>{item.label}</Text>
              <Text style={[styles.summaryMiniValue, item.tone === "risk" && styles.riskText, item.tone === "warn" && styles.warnText]}>{item.value}</Text>
            </View>
          ))}
        </View>
      </Card>
      <Card>
        <Text style={sharedText.sectionTitle}>Why RiskWise is hesitating</Text>
        <Text style={styles.smallSub}>{investigation.issues.length} key areas evaluated</Text>
        {investigation.issues.map((issue) => (
          <IssueRow key={issue.id} issue={issue} onPress={() => onIssue(issue)} />
        ))}
        <PrimaryButton label="Open Committee Debate" onPress={onDebate} style={styles.debateButton} />
      </Card>
    </ScreenScroll>
  );
}

function IssueRow({ issue, onPress }) {
  return (
    <Pressable style={styles.issueRow} onPress={onPress}>
      <View style={[styles.issueIcon, issue.tone === "risk" && styles.issueIconRisk, issue.tone === "warn" && styles.issueIconWarn]}>
        <Ionicons name={issue.icon} size={14} color={issue.tone === "risk" ? palette.red : issue.tone === "warn" ? palette.amber : palette.green} />
      </View>
      <View style={styles.flex}>
        <Text style={styles.issueTitle}>{issue.title}</Text>
        <Text style={styles.issueSub}>{issue.oneLine}</Text>
      </View>
      <Text style={[styles.issueBadge, issue.tone === "risk" && styles.issueBadgeRisk, issue.tone === "warn" && styles.issueBadgeWarn]}>{issue.status}</Text>
      <Ionicons name="chevron-forward" size={15} color={palette.muted} />
    </Pressable>
  );
}

function CommitteeDebate({ investigation, level, setLevel, onBack }) {
  const messages = buildDebateMessages(investigation, level);
  return (
    <ScreenScroll>
      <View style={styles.wizardHeader}>
        <Pressable style={styles.backButton} onPress={onBack}>
          <Ionicons name="chevron-back" size={18} color={palette.dark} />
        </Pressable>
        <View style={styles.flex}>
          <Text style={styles.wizardTitle}>Committee Debate</Text>
          <Text style={styles.wizardSub}>Multi-agent risk conversation</Text>
        </View>
        <View style={styles.liveBadge}><Text style={styles.liveText}>Live</Text></View>
      </View>
      <View style={styles.levelRow}>
        {["Easy", "Moderate", "Advanced"].map((item) => (
          <Pressable key={item} style={[styles.levelChip, level === item && styles.levelChipActive]} onPress={() => setLevel(item)}>
            <Text style={[styles.levelText, level === item && styles.levelTextActive]}>{item}</Text>
          </Pressable>
        ))}
      </View>
      <Card>
        <Text style={sharedText.sectionTitle}>Live Discussion</Text>
        <Text style={styles.smallSub}>4 agents - based on the current check</Text>
        {messages.map((message) => (
          <View key={message.name} style={styles.debateRow}>
            <View style={[styles.agentAvatar, { backgroundColor: message.color }]}>
              <Text style={styles.agentInitial}>{message.initials}</Text>
            </View>
            <View style={styles.flex}>
              <View style={styles.rowBetween}>
                <Text style={styles.agentName}>{message.name}</Text>
                <Text style={styles.agentTime}>{message.time}</Text>
              </View>
              {message.points.map((point) => (
                <Text key={point} style={styles.agentPoint}>- {point}</Text>
              ))}
            </View>
          </View>
        ))}
      </Card>
    </ScreenScroll>
  );
}

function IssueCard({ issue, onBack }) {
  if (!issue) {
    return null;
  }
  return (
    <ScreenScroll>
      <View style={styles.wizardHeader}>
        <Pressable style={styles.backButton} onPress={onBack}>
          <Ionicons name="chevron-back" size={18} color={palette.dark} />
        </Pressable>
        <View style={styles.flex}>
          <Text style={styles.wizardTitle}>{issue.title}</Text>
          <Text style={styles.wizardSub}>Detailed technical breakdown</Text>
        </View>
        <Text style={[styles.scoreText, issue.tone === "risk" && styles.riskText, issue.tone === "warn" && styles.warnText]}>{issue.score}/100</Text>
      </View>
      <Card style={styles.deepDiveCard}>
        <View style={styles.rowBetween}>
          <View>
            <Text style={styles.deepStatus}>{issue.status}</Text>
            <Text style={styles.deepSub}>{issue.headline}</Text>
          </View>
          <Text style={[styles.deepScore, issue.tone === "risk" && styles.riskText, issue.tone === "warn" && styles.warnText]}>{issue.score}</Text>
        </View>
        <SectionBlock title="Evidence" rows={issue.evidence} />
        <SectionBlock title="Why it matters" rows={[issue.why]} />
        <SectionBlock title="What would help" rows={issue.whatWouldHelp} />
        <View style={styles.nextQuestion}>
          <Text style={styles.blockTitle}>Next question</Text>
          <Text style={styles.blockText}>{issue.nextQuestion}</Text>
        </View>
      </Card>
    </ScreenScroll>
  );
}

function SectionBlock({ title, rows }) {
  return (
    <View style={styles.block}>
      <Text style={styles.blockTitle}>{title}</Text>
      {rows.map((row) => <Text key={row} style={styles.blockText}>- {row}</Text>)}
    </View>
  );
}

function InlineWarning({ items }) {
  if (!items.length) {
    return null;
  }
  return (
    <Card style={styles.warningCard}>
      <Text style={styles.warningTitle}>Before RiskWise can check it</Text>
      {items.map((item) => (
        <View key={item} style={styles.warningRow}>
          <Ionicons name="alert-circle-outline" size={15} color={palette.teal} />
          <Text style={styles.warningText}>{item}</Text>
        </View>
      ))}
    </Card>
  );
}

function validateDraft({ draft, selectedTicker, tickerQuery, amountAtRisk, riskPercentNumber, expirationDate }) {
  const messages = [];
  const isOption = draft.tradeType.includes("Option");
  const ticker = !selectedTicker?.symbol || selectedTicker.symbol !== tickerQuery.trim().toUpperCase()
    ? "Select a ticker from the dropdown instead of typing a loose symbol."
    : "";
  const strikeNumber = Number(draft.strike || 0);
  const premiumNumber = Number(String(draft.premium || "").replace(/[^0-9.]/g, "") || 0);
  const contractsNumber = Number(String(draft.contracts || "").replace(/[^0-9]/g, "") || 0);
  const calculatedRisk = premiumNumber * contractsNumber * 100;
  const strike = isOption && strikeNumber <= 0 ? "Strike is required for option checks." : "";
  const premium = isOption && premiumNumber <= 0 ? "Premium is required for option checks." : "";
  const contracts = isOption && contractsNumber < 1 ? "Contracts must be at least 1." : "";
  const today = stripTime(new Date());
  const expiration = !expirationDate
    ? "Choose an expiration date."
    : expirationDate < today
      ? "Expiration cannot be in the past."
      : "";
  const amount = amountAtRisk <= 0
    ? "Amount at risk must be greater than zero."
    : isOption && calculatedRisk > 0 && Math.abs(calculatedRisk - amountAtRisk) > Math.max(10, calculatedRisk * 0.25)
      ? "Amount at risk should match premium x contracts x 100."
      : riskPercentNumber > 10
        ? "This risks more than 10% of the account. Lower it before checking."
        : "";
  [ticker, strike, premium, contracts, expiration, amount].forEach((item) => item && messages.push(item));
  return { ticker, strike, premium, contracts, expiration, amount, messages, ready: messages.length === 0 };
}

function buildInvestigation({ draft, report, selectedTicker, marketContext, optionContext, validation, riskPercentNumber, daysToExpiration, calculatedRisk }) {
  const score = Math.max(30, Math.min(92, Math.round(report?.setupScore || 78 - validation.messages.length * 9 - (riskPercentNumber > 3 ? 12 : 0) - (daysToExpiration !== null && daysToExpiration < 7 ? 10 : 0))));
  const moneyness = optionContext?.selected?.moneynessLabel || "Moneyness unknown";
  const dataMissing = !optionContext?.selected?.impliedVolatility && !draft.impliedVolatility;
  const signalScore = score < 65 ? 45 : 68;
  const issues = [
    {
      id: "signal",
      title: "Signal Clarity",
      icon: "analytics-outline",
      status: signalScore < 60 ? "Weak" : "Mixed",
      score: signalScore,
      tone: signalScore < 60 ? "risk" : "warn",
      oneLine: signalScore < 60 ? "Needs price confirmation." : "Thesis is plausible but not fully confirmed.",
      headline: "Needs Review",
      evidence: [
        `${selectedTicker?.symbol || draft.ticker} context is attached, but price confirmation is still separate from contract math.`,
        `${moneyness} based on the current strike and underlying context.`,
        "No live technical confirmation is being inferred from future data."
      ],
      why: "Options punish unclear timing because premium can decay even if the broad thesis is directionally reasonable.",
      whatWouldHelp: ["Clear entry condition", "Defined invalidation level", "Volume or trend confirmation"],
      nextQuestion: "What exact condition would invalidate this trade idea?"
    },
    {
      id: "contract",
      title: "Contract Structure",
      icon: "document-text-outline",
      status: calculatedRisk > 0 ? "Defined" : "Incomplete",
      score: calculatedRisk > 0 ? 76 : 50,
      tone: calculatedRisk > 0 ? "good" : "warn",
      oneLine: calculatedRisk > 0 ? "Max loss is mechanically defined." : "Premium and contract count need tightening.",
      headline: calculatedRisk > 0 ? "Acceptable" : "Needs Inputs",
      evidence: [
        `Premium x contracts x 100 implies about ${money(calculatedRisk || 0)} at risk.`,
        `Selected structure: ${draft.tradeType}.`,
        `Expiration: ${draft.expiration || "not selected"}.`
      ],
      why: "A good idea can still be a poor option contract if premium, expiration, or strike create too much required movement.",
      whatWouldHelp: ["Compare a closer/farther expiration", "Compare long option vs debit spread", "Check breakeven against realistic move"],
      nextQuestion: "Is this contract chosen for liquidity, conviction, or just price?"
    },
    {
      id: "volatility",
      title: "Volatility Context",
      icon: "pulse-outline",
      status: dataMissing ? "Unknown" : "Attached",
      score: dataMissing ? 42 : 70,
      tone: dataMissing ? "risk" : "good",
      oneLine: dataMissing ? "Live IV, Greeks, and chain quality are not attached yet." : "Volatility fields are attached.",
      headline: dataMissing ? "Missing Data" : "Visible",
      evidence: [
        marketContext?.earnings?.date ? `Next earnings context: ${marketContext.earnings.date}.` : "Earnings date is not confirmed in this check.",
        "Live IV crush risk requires a real options chain provider.",
        "Bid/ask, open interest, and volume are not guaranteed from the current fallback."
      ],
      why: "Around events, implied volatility can fall after uncertainty clears, so the option can lose even when direction is only slightly right.",
      whatWouldHelp: ["IV percentile or IV rank", "Bid/ask spread", "Open interest and volume", "Known earnings/event date"],
      nextQuestion: "Is this trade trying to benefit from movement, volatility, or both?"
    },
    {
      id: "size",
      title: "Position Size",
      icon: "shield-checkmark-outline",
      status: riskPercentNumber <= 2 ? "Good" : riskPercentNumber <= 5 ? "Elevated" : "Too High",
      score: riskPercentNumber <= 2 ? 84 : riskPercentNumber <= 5 ? 63 : 35,
      tone: riskPercentNumber <= 2 ? "good" : riskPercentNumber <= 5 ? "warn" : "risk",
      oneLine: `${riskPercentNumber.toFixed(1)}% of account is planned for this check.`,
      headline: riskPercentNumber <= 2 ? "Within Rules" : "Needs Guardrail",
      evidence: [
        `Account size: ${money(draft.accountSize)}.`,
        `Amount at risk: ${money(draft.amountAtRisk)}.`,
        `Risk budget: ${money(draft.riskBudget)}.`
      ],
      why: "Sizing controls whether a wrong thesis is a learning cost or an account-damaging event.",
      whatWouldHelp: ["Keep loss inside risk budget", "Predefine max loss", "Avoid increasing size to compensate for uncertainty"],
      nextQuestion: "Would this trade still feel reasonable if it immediately went to max loss?"
    },
    {
      id: "behavior",
      title: "Behavior Match",
      icon: "person-circle-outline",
      status: "No Issues",
      score: 74,
      tone: "good",
      oneLine: "No obvious rule conflict from the current inputs.",
      headline: "Aligned",
      evidence: ["Timeframe is declared.", "Max loss is visible.", "No leverage is assumed."],
      why: "Most option losses become worse when the trader changes the plan mid-trade.",
      whatWouldHelp: ["Write the exit condition", "Decide whether this is a thesis trade or a volatility trade", "Save the check before acting"],
      nextQuestion: "What would make you not take this trade?"
    }
  ];
  const weakest = issues.reduce((low, item) => item.score < low.score ? item : low, issues[0]);
  return {
    score,
    conviction: score >= 78 ? "High Conviction" : score >= 62 ? "Mixed Conviction" : "Low Conviction",
    verdict: score >= 78 ? "Strong Setup" : score >= 62 ? "Needs Review" : "Weak Setup",
    weakest,
    issues,
    summaryCards: [
      { label: "Strength", value: riskPercentNumber <= 2 ? "Risk Size" : "Defined Loss", tone: "good", icon: "checkmark-circle" },
      { label: "Main Risk", value: weakest.title, tone: weakest.tone === "good" ? "warn" : weakest.tone, icon: "warning" },
      { label: "Missing", value: dataMissing ? "Volatility" : "Less", tone: dataMissing ? "risk" : "good", icon: "close-circle" }
    ]
  };
}

function buildDebateMessages(investigation, level) {
  const detailed = level === "Advanced";
  const simple = level === "Easy";
  return [
    {
      name: "Bull Analyst",
      initials: "BA",
      color: "#BAE7C7",
      time: "2m ago",
      points: simple
        ? ["The loss is defined.", "The trade idea is organized enough to review."]
        : ["Structure aligns with a defined-risk thesis.", detailed ? "Premium loss is capped, but expected move still needs support." : "Max loss is visible, and timing is at least declared.", "Entry needs price confirmation."]
    },
    {
      name: "Skeptic",
      initials: "SK",
      color: "#CFE2FF",
      time: "1m ago",
      points: simple
        ? ["The weak part is confirmation.", "Unknown volatility can hurt options."]
        : [`${investigation.weakest.title} is the weakest part of the check.`, detailed ? "If IV is elevated, breakeven may understate the real hurdle after volatility contracts." : "IV rank unknown adds risk.", "Time decay can make a slow correct thesis lose."]
    },
    {
      name: "Risk Judge",
      initials: "RJ",
      color: "#E5D8FF",
      time: "30s ago",
      points: ["Position size is judged before direction.", `${investigation.weakest.title} score is ${investigation.weakest.score}/100.`, simple ? "Fix the weakest issue first." : "The committee wants one clear invalidation rule."]
    },
    {
      name: "Risk Manager",
      initials: "RM",
      color: "#FDE7B0",
      time: "10s ago",
      points: ["No trade instruction is being given.", "The check is useful only if the missing data is resolved.", detailed ? "Final confidence should drop when liquidity, IV, or catalyst data is unavailable." : "Upside path is unclear until evidence improves."]
    }
  ];
}

function withExactSymbolFallback(query, rows) {
  const clean = normalizeSymbol(query);
  const items = Array.isArray(rows) ? rows.map((item) => ({ ...item, symbol: normalizeSymbol(item.symbol) })) : [];
  if (!clean || clean.length > 8 || !/^[A-Z0-9.-]+$/.test(clean)) {
    return items;
  }
  if (items.some((item) => item.symbol === clean)) {
    return items;
  }
  return [
    ...items,
    {
      symbol: clean,
      name: `${clean} exact symbol`,
      exchange: "Verify quote",
      sector: "Manual selection",
      source: "exact_symbol"
    }
  ];
}

function normalizeSymbol(value) {
  return String(value || "").trim().toUpperCase().replace("/", "-");
}

function buildCalendar(monthDate) {
  const first = startOfMonth(monthDate);
  const start = addDays(first, -first.getDay());
  return Array.from({ length: 42 }, (_, index) => {
    const date = addDays(start, index);
    return { date, inMonth: date.getMonth() === first.getMonth() };
  });
}

function parseDate(value) {
  if (!value) return null;
  const isoMatch = /^\d{4}-\d{2}-\d{2}$/.test(String(value));
  const date = isoMatch ? new Date(`${value}T00:00:00`) : new Date(value);
  return Number.isNaN(date.getTime()) ? null : stripTime(date);
}

function displayDate(date) {
  if (!date) return "Choose date";
  return `${monthNames[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
}

function toIsoDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
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

function dayDiff(start, end) {
  return Math.round((end.getTime() - start.getTime()) / 86400000);
}

function shortDate(value) {
  const date = parseDate(value);
  return date ? `${monthNames[date.getMonth()]} ${date.getDate()}` : value;
}

function titleCase(value) {
  return String(value || "").slice(0, 1).toUpperCase() + String(value || "").slice(1);
}

function numberFromMoney(value) {
  return Number(String(value || "").replace(/[^0-9.]/g, "") || 0);
}

function recentName(symbol) {
  return {
    AAPL: "Apple Inc.",
    MSFT: "Microsoft Corporation",
    SPY: "SPDR S&P 500 ETF",
    NVDA: "NVIDIA Corporation",
    AMZN: "Amazon.com Inc."
  }[symbol] || `${symbol} ticker`;
}

const styles = StyleSheet.create({
  flex: {
    flex: 1
  },
  snapshot: {
    backgroundColor: "#FEFFFE"
  },
  rowBetween: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12
  },
  twoCols: {
    flexDirection: "row",
    gap: 16,
    marginTop: 12
  },
  progressTrack: {
    height: 9,
    backgroundColor: "#EEF2EF",
    borderRadius: 999,
    marginTop: 14,
    overflow: "hidden"
  },
  progressFill: {
    height: "100%",
    backgroundColor: palette.green,
    borderRadius: 999
  },
  progressRisk: {
    backgroundColor: palette.teal
  },
  statusPill: {
    borderRadius: 999,
    backgroundColor: palette.greenSoft,
    paddingHorizontal: 10,
    paddingVertical: 6
  },
  statusPillRisk: {
    backgroundColor: palette.amberSoft
  },
  statusText: {
    color: palette.green,
    fontWeight: "900",
    fontSize: 10
  },
  statusTextRisk: {
    color: palette.teal
  },
  bell: {
    color: palette.dark,
    fontSize: 20,
    fontWeight: "900"
  },
  choiceCard: {
    minHeight: 70,
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 17,
    padding: 12,
    marginBottom: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: "#FFFFFF"
  },
  choiceCardActive: {
    borderColor: palette.green,
    backgroundColor: "#FBFFFC"
  },
  choiceIcon: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: palette.greenSoft
  },
  choiceIconActive: {
    backgroundColor: palette.green
  },
  choiceCopy: {
    flex: 1
  },
  choiceTitle: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900"
  },
  choiceText: {
    color: palette.muted,
    fontSize: 11,
    lineHeight: 16,
    fontWeight: "700",
    marginTop: 3
  },
  wizardHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingTop: 10,
    paddingBottom: 12
  },
  backButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: palette.border
  },
  wizardTitle: {
    color: palette.dark,
    fontSize: 16,
    fontWeight: "900"
  },
  wizardSub: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 2
  },
  stepTrack: {
    flexDirection: "row",
    gap: 7,
    marginBottom: 12,
    paddingHorizontal: 4
  },
  stepDot: {
    flex: 1,
    height: 5,
    borderRadius: 999,
    backgroundColor: "#E4EAE4"
  },
  stepDotActive: {
    backgroundColor: palette.green
  },
  stepCard: {
    paddingVertical: 10,
    marginBottom: 9
  },
  stepHeader: {
    minHeight: 34,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10
  },
  stepTitleWrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6
  },
  stepNumber: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "900"
  },
  stepTitle: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900"
  },
  stepRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6
  },
  stepBody: {
    marginTop: 10
  },
  inputRow: {
    flexDirection: "row",
    gap: 10,
    alignItems: "flex-start"
  },
  fieldWrap: {
    flex: 1,
    minWidth: 0,
    marginBottom: 10,
    position: "relative"
  },
  inputLabel: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "800",
    marginBottom: 5
  },
  searchBox: {
    minHeight: 45,
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 14,
    paddingHorizontal: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: "#FBFCFB"
  },
  searchInput: {
    flex: 1,
    color: palette.dark,
    fontWeight: "900",
    outlineStyle: "none"
  },
  fieldError: {
    borderColor: palette.red,
    backgroundColor: "#FFFBFB"
  },
  fieldErrorText: {
    color: palette.red,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 5
  },
  dropdown: {
    marginTop: 7,
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    overflow: "hidden"
  },
  dropdownEmpty: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "800",
    padding: 12
  },
  tickerOption: {
    minHeight: 54,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 12,
    borderTopWidth: 1,
    borderTopColor: "#F0F3F0"
  },
  tickerLogo: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: palette.greenSoft,
    alignItems: "center",
    justifyContent: "center"
  },
  tickerLogoText: {
    color: palette.green,
    fontSize: 12,
    fontWeight: "900"
  },
  tickerCopy: {
    flex: 1
  },
  tickerSymbol: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900"
  },
  tickerName: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 2
  },
  exchangeText: {
    color: palette.muted,
    fontSize: 9,
    fontWeight: "900"
  },
  selectedTickerCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 7,
    borderRadius: 12,
    backgroundColor: palette.greenSoft,
    paddingHorizontal: 10,
    paddingVertical: 8
  },
  selectedTickerSymbol: {
    color: palette.green,
    fontSize: 12,
    fontWeight: "900"
  },
  selectedTickerName: {
    flex: 1,
    color: palette.dark,
    fontSize: 11,
    fontWeight: "800"
  },
  recentWrap: {
    marginTop: 2
  },
  miniLabel: {
    color: palette.muted,
    fontSize: 9,
    fontWeight: "900",
    marginBottom: 7
  },
  recentRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 7
  },
  recentChip: {
    borderRadius: 999,
    paddingHorizontal: 13,
    paddingVertical: 8,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: palette.border
  },
  recentText: {
    color: palette.dark,
    fontSize: 10,
    fontWeight: "900"
  },
  contextBox: {
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "rgba(207,239,216,0.9)",
    backgroundColor: "#FBFFFC",
    padding: 12
  },
  contextTitle: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900"
  },
  contextSub: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 2
  },
  priceBadge: {
    borderRadius: 15,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: palette.border,
    paddingHorizontal: 9,
    paddingVertical: 6,
    alignItems: "flex-end"
  },
  priceText: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  contextChips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 7
  },
  contextChip: {
    color: palette.green,
    backgroundColor: palette.greenSoft,
    borderRadius: 999,
    overflow: "hidden",
    paddingHorizontal: 8,
    paddingVertical: 5,
    fontSize: 9,
    fontWeight: "900"
  },
  emptyHint: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "800",
    lineHeight: 17
  },
  segmentRow: {
    flexDirection: "row",
    gap: 8,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FBFCFB",
    padding: 4
  },
  segmentButton: {
    flex: 1,
    minHeight: 34,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center"
  },
  segmentButtonActive: {
    backgroundColor: palette.green
  },
  segmentText: {
    color: palette.muted,
    fontSize: 12,
    fontWeight: "900"
  },
  segmentTextActive: {
    color: "#FFFFFF"
  },
  expirationStrip: {
    borderRadius: 16,
    backgroundColor: "#F8FCF8",
    borderWidth: 1,
    borderColor: "#E1ECE2",
    padding: 10,
    marginBottom: 10
  },
  expirationChips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 7
  },
  expirationChip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 10,
    paddingVertical: 7
  },
  expirationChipActive: {
    backgroundColor: palette.green,
    borderColor: palette.green
  },
  expirationChipText: {
    color: palette.dark,
    fontSize: 10,
    fontWeight: "900"
  },
  expirationChipTextActive: {
    color: "#FFFFFF"
  },
  dateButton: {
    minHeight: 49,
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 14,
    paddingHorizontal: 11,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#FBFCFB"
  },
  dateText: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  dateSub: {
    color: palette.muted,
    fontSize: 9,
    fontWeight: "800",
    marginTop: 3
  },
  calendarPanel: {
    width: 238,
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    padding: 8,
    marginTop: 8,
    alignSelf: "flex-end",
    shadowColor: "#16351D",
    shadowOpacity: 0.12,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 8 }
  },
  calendarHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 7
  },
  calendarNav: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 1,
    borderColor: palette.border,
    alignItems: "center",
    justifyContent: "center"
  },
  calendarTitle: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  weekRow: {
    flexDirection: "row",
    marginBottom: 4
  },
  weekLabel: {
    width: `${100 / 7}%`,
    textAlign: "center",
    color: palette.muted,
    fontSize: 8,
    fontWeight: "900"
  },
  daysGrid: {
    flexDirection: "row",
    flexWrap: "wrap"
  },
  dayCell: {
    width: `${100 / 7}%`,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 9
  },
  dayCellSelected: {
    backgroundColor: palette.green
  },
  dayCellDisabled: {
    opacity: 0.25
  },
  dayText: {
    color: palette.dark,
    fontSize: 9,
    fontWeight: "900"
  },
  dayTextSelected: {
    color: "#FFFFFF"
  },
  dayTextDisabled: {
    color: palette.muted
  },
  sizingStrip: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 10
  },
  sizingItem: {
    flex: 1,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FBFDFB",
    padding: 10
  },
  sizingValue: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900"
  },
  warningCard: {
    backgroundColor: "#F6FCFF",
    borderColor: "#CFEFFF"
  },
  warningTitle: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900",
    marginBottom: 8
  },
  warningRow: {
    flexDirection: "row",
    gap: 8,
    alignItems: "flex-start",
    marginBottom: 6
  },
  warningText: {
    flex: 1,
    color: palette.dark,
    fontSize: 11,
    lineHeight: 16,
    fontWeight: "800"
  },
  summaryHero: {
    backgroundColor: "#F7FFF9",
    borderColor: "#CFEFD8"
  },
  heroTicker: {
    color: palette.dark,
    fontSize: 22,
    fontWeight: "900"
  },
  heroSub: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "800",
    marginTop: 3
  },
  convictionBox: {
    marginTop: 12,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#E1ECE2",
    backgroundColor: "#FFFFFF",
    padding: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  convictionTitle: {
    color: palette.dark,
    fontSize: 14,
    fontWeight: "900"
  },
  convictionSub: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 2
  },
  signalDot: {
    width: 13,
    height: 13,
    borderRadius: 7,
    backgroundColor: palette.amber
  },
  summaryGrid: {
    flexDirection: "row",
    gap: 8,
    marginTop: 12
  },
  summaryMini: {
    flex: 1,
    borderRadius: 15,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E6EFE7",
    padding: 10,
    alignItems: "center"
  },
  summaryMiniLabel: {
    color: palette.muted,
    fontSize: 9,
    fontWeight: "900",
    marginTop: 5
  },
  summaryMiniValue: {
    color: palette.green,
    fontSize: 10,
    fontWeight: "900",
    marginTop: 3,
    textAlign: "center"
  },
  smallSub: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: -6,
    marginBottom: 8
  },
  issueRow: {
    minHeight: 52,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderTopWidth: 1,
    borderTopColor: "#EEF2EF",
    paddingVertical: 9
  },
  issueIcon: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: palette.greenSoft,
    alignItems: "center",
    justifyContent: "center"
  },
  issueIconRisk: {
    backgroundColor: "#FEEEEE"
  },
  issueIconWarn: {
    backgroundColor: "#FFF7E6"
  },
  issueTitle: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  issueSub: {
    color: palette.muted,
    fontSize: 9,
    fontWeight: "800",
    marginTop: 2
  },
  issueBadge: {
    color: palette.green,
    backgroundColor: palette.greenSoft,
    borderRadius: 999,
    overflow: "hidden",
    paddingHorizontal: 8,
    paddingVertical: 5,
    fontSize: 8,
    fontWeight: "900"
  },
  issueBadgeRisk: {
    color: palette.red,
    backgroundColor: "#FEEEEE"
  },
  issueBadgeWarn: {
    color: palette.amber,
    backgroundColor: "#FFF7E6"
  },
  debateButton: {
    marginTop: 10
  },
  levelRow: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 12
  },
  levelChip: {
    flex: 1,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FFFFFF",
    paddingVertical: 9,
    alignItems: "center"
  },
  levelChipActive: {
    backgroundColor: palette.green,
    borderColor: palette.green
  },
  levelText: {
    color: palette.dark,
    fontSize: 10,
    fontWeight: "900"
  },
  levelTextActive: {
    color: "#FFFFFF"
  },
  liveBadge: {
    borderRadius: 999,
    backgroundColor: "#FEEEEE",
    paddingHorizontal: 9,
    paddingVertical: 5
  },
  liveText: {
    color: palette.red,
    fontSize: 9,
    fontWeight: "900"
  },
  debateRow: {
    flexDirection: "row",
    gap: 10,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: "#EEF2EF"
  },
  agentAvatar: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: "center",
    justifyContent: "center"
  },
  agentInitial: {
    color: palette.green,
    fontSize: 10,
    fontWeight: "900"
  },
  agentName: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  agentTime: {
    color: palette.muted,
    fontSize: 8,
    fontWeight: "800"
  },
  agentPoint: {
    color: palette.dark,
    fontSize: 10,
    lineHeight: 15,
    fontWeight: "800",
    marginTop: 4
  },
  deepDiveCard: {
    backgroundColor: "#FFFFFF"
  },
  scoreText: {
    color: palette.green,
    fontSize: 16,
    fontWeight: "900"
  },
  deepStatus: {
    color: palette.red,
    fontSize: 10,
    fontWeight: "900",
    textTransform: "uppercase"
  },
  deepSub: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900",
    marginTop: 4
  },
  deepScore: {
    color: palette.green,
    fontSize: 34,
    fontWeight: "900"
  },
  block: {
    borderTopWidth: 1,
    borderTopColor: "#EEF2EF",
    paddingTop: 12,
    marginTop: 12
  },
  blockTitle: {
    color: palette.green,
    fontSize: 11,
    fontWeight: "900",
    marginBottom: 7
  },
  blockText: {
    color: palette.dark,
    fontSize: 11,
    lineHeight: 17,
    fontWeight: "800",
    marginBottom: 4
  },
  nextQuestion: {
    borderRadius: 16,
    backgroundColor: "#F7FFF9",
    borderWidth: 1,
    borderColor: "#CFEFD8",
    padding: 12,
    marginTop: 14
  },
  riskText: {
    color: palette.red
  },
  warnText: {
    color: palette.amber
  }
});
