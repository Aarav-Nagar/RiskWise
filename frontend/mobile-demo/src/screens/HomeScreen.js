import React from "react";
import { Image, Linking, Pressable, StyleSheet, Text, TextInput, useWindowDimensions, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Card } from "../components/Card";
import { Header, money, ScreenScroll, sharedText } from "../components/Shared";
import { getMarketBundle, getMarketProviderStatus, searchMarketSymbols } from "../services/apiClient";
import { palette } from "../theme/theme";

const stockUniverse = [
  { symbol: "SPY", name: "SPDR S&P 500 ETF Trust", sector: "Index" },
  { symbol: "AAPL", name: "Apple Inc.", sector: "Technology" },
  { symbol: "MSFT", name: "Microsoft Corporation", sector: "Technology" },
  { symbol: "NVDA", name: "NVIDIA Corporation", sector: "Technology" },
  { symbol: "TSLA", name: "Tesla Inc.", sector: "Consumer" },
  { symbol: "AMD", name: "Advanced Micro Devices", sector: "Technology" },
  { symbol: "AMZN", name: "Amazon.com Inc.", sector: "Consumer" },
  { symbol: "META", name: "Meta Platforms Inc.", sector: "Technology" },
  { symbol: "JPM", name: "JPMorgan Chase & Co.", sector: "Finance" },
  { symbol: "XOM", name: "Exxon Mobil Corporation", sector: "Energy" },
  { symbol: "UNH", name: "UnitedHealth Group", sector: "Healthcare" },
  { symbol: "LLY", name: "Eli Lilly and Company", sector: "Healthcare" },
  { symbol: "BAC", name: "Bank of America", sector: "Finance" },
  { symbol: "CVX", name: "Chevron Corporation", sector: "Energy" }
];

const newsImages = {
  Technology: "https://images.unsplash.com/photo-1518186285589-2f7649de83e0?auto=format&fit=crop&w=900&q=80",
  Finance: "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=900&q=80",
  Energy: "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?auto=format&fit=crop&w=900&q=80",
  Healthcare: "https://images.unsplash.com/photo-1576091160550-2173dba999ef?auto=format&fit=crop&w=900&q=80",
  Consumer: "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?auto=format&fit=crop&w=900&q=80",
  Index: "https://images.unsplash.com/photo-1520607162513-77705c0f0d4a?auto=format&fit=crop&w=900&q=80"
};

const generalLinks = [
  {
    title: "Market calendar and earnings dates",
    source: "Nasdaq",
    url: "https://www.nasdaq.com/market-activity/earnings"
  },
  {
    title: "Broad market movers and sector heat",
    source: "Yahoo Finance",
    url: "https://finance.yahoo.com/markets/"
  },
  {
    title: "Options education and contract basics",
    source: "Options Industry Council",
    url: "https://www.optionseducation.org/"
  }
];

const savedFilters = ["All", "High risk", "Moderate", "Controlled"];

export function HomeScreen({ user, draft, setDraft, report, savedChecks = [], navigate, openSavedCheck }) {
  const name = (user?.name || draft.user || "Alex").split(" ")[0];
  const startingStock = findStock(draft.ticker) || stockUniverse[1];
  const [query, setQuery] = React.useState(startingStock.symbol);
  const [selectedStock, setSelectedStock] = React.useState(startingStock);
  const [marketBundle, setMarketBundle] = React.useState({ quote: null, profile: null, news: null, earnings: null, optionsContext: null });
  const [marketLoading, setMarketLoading] = React.useState(false);
  const [providerStatus, setProviderStatus] = React.useState(null);
  const [remoteMatches, setRemoteMatches] = React.useState([]);
  const [savedQuery, setSavedQuery] = React.useState("");
  const [savedFilter, setSavedFilter] = React.useState("All");
  const watchlist = buildWatchlist(savedChecks, selectedStock);
  const matches = getMatches(query, selectedStock, remoteMatches);
  const selectedNews = buildStockNews(selectedStock, marketBundle.news, marketBundle.profile);
  const quote = marketBundle.quote;
  const earnings = marketBundle.earnings?.items || [];
  const filteredSavedChecks = filterSavedChecks(savedChecks, savedQuery, savedFilter);

  React.useEffect(() => {
    let mounted = true;
    async function loadProviderStatus() {
      try {
        const status = await getMarketProviderStatus();
        if (mounted) {
          setProviderStatus(status);
        }
      } catch (error) {
        if (mounted) {
          setProviderStatus(null);
        }
      }
    }
    loadProviderStatus();
    return () => {
      mounted = false;
    };
  }, []);

  React.useEffect(() => {
    let mounted = true;
    async function loadMarketData() {
      if (!selectedStock?.symbol) {
        return;
      }
      setMarketLoading(true);
      try {
        const bundle = await getMarketBundle(selectedStock.symbol);
        if (mounted) {
          setMarketBundle(bundle);
        }
      } catch (error) {
        if (mounted) {
          setMarketBundle({ quote: null, profile: null, news: null, earnings: null, optionsContext: null });
        }
      } finally {
        if (mounted) {
          setMarketLoading(false);
        }
      }
    }
    loadMarketData();
    return () => {
      mounted = false;
    };
  }, [selectedStock?.symbol]);

  React.useEffect(() => {
    let mounted = true;
    const searchText = query.replace("-", " ").trim();
    if (searchText.length < 2 || selectedStock) {
      setRemoteMatches([]);
      return () => {
        mounted = false;
      };
    }
    const timeout = setTimeout(async () => {
      try {
        const rows = await searchMarketSymbols(searchText);
        if (mounted) {
          setRemoteMatches(rows.map((row) => ({ symbol: row.symbol, name: row.name, sector: row.sector || "Market" })));
        }
      } catch (error) {
        if (mounted) {
          setRemoteMatches([]);
        }
      }
    }, 220);
    return () => {
      mounted = false;
      clearTimeout(timeout);
    };
  }, [query, selectedStock?.symbol]);

  function chooseStock(stock) {
    setSelectedStock(stock);
    setQuery(`${stock.symbol} - ${stock.name}`);
    setDraft?.({ ...draft, ticker: stock.symbol, tickerName: stock.name, tickerExchange: stock.exchange || "" });
  }

  function handleQuery(text) {
    setQuery(text);
    if (selectedStock && text !== `${selectedStock.symbol} - ${selectedStock.name}` && text.toUpperCase() !== selectedStock.symbol) {
      setSelectedStock(null);
    }
  }

  function openCheck() {
    if (!selectedStock) {
      return;
    }
    setDraft?.({ ...draft, ticker: selectedStock.symbol, tickerName: selectedStock.name, tickerExchange: selectedStock.exchange || "" });
    navigate("Check");
  }

  return (
    <ScreenScroll>
      <Header title={`Good morning, ${name}`} subtitle="Pick a stock, review the current context, then run an options risk check." />

      <Card style={styles.selectorCard}>
        <View style={styles.selectorTop}>
          <View>
            <Text style={styles.eyebrow}>Stock lookup</Text>
            <Text style={styles.selectorTitle}>{selectedStock ? selectedStock.symbol : "Select a ticker"}</Text>
          </View>
          <View style={styles.accountPill}>
            <Text style={styles.accountLabel}>Risk budget</Text>
            <Text style={styles.accountText}>{money(draft.riskBudget)}</Text>
          </View>
        </View>

        <View style={styles.searchBox}>
          <Ionicons name="search-outline" size={18} color={palette.muted} />
          <TextInput
            value={query}
            onChangeText={handleQuery}
            placeholder="Type ticker or company..."
            placeholderTextColor="#98A39D"
            autoCapitalize="characters"
            style={styles.searchInput}
          />
        </View>

        <View style={styles.dropdown}>
          {matches.map((stock) => (
            <Pressable key={stock.symbol} style={[styles.matchRow, selectedStock?.symbol === stock.symbol && styles.matchRowActive]} onPress={() => chooseStock(stock)}>
              <View style={styles.symbolBadge}>
                <Text style={styles.symbolBadgeText}>{stock.symbol}</Text>
              </View>
              <View style={styles.matchText}>
                <Text style={styles.matchName} numberOfLines={1}>{stock.name}</Text>
                <Text style={styles.matchSector}>{stock.sector}</Text>
              </View>
              {selectedStock?.symbol === stock.symbol ? <Ionicons name="checkmark-circle" size={18} color={palette.green} /> : null}
            </Pressable>
          ))}
        </View>

        <Pressable style={[styles.checkButton, !selectedStock && styles.buttonDisabled]} onPress={openCheck}>
          <Ionicons name="location-outline" size={18} color="#FFFFFF" />
          <Text style={styles.checkText}>{selectedStock ? `Risk-check ${selectedStock.symbol}` : "Select a ticker first"}</Text>
        </Pressable>
      </Card>

      <MarketSnapshot stock={selectedStock} quote={quote} earnings={earnings} loading={marketLoading} />
      <OptionsReadinessCard stock={selectedStock} context={marketBundle.optionsContext} loading={marketLoading} />
      <DataStatusCard status={providerStatus} />

      <Card>
        <View style={styles.sectionHeader}>
          <Text style={sharedText.sectionTitle}>News Watch</Text>
          <Text style={styles.sectionSub}>{marketBundle.news?.provider || "Live links"}</Text>
        </View>
        <View style={styles.watchlistRow}>
          {watchlist.map((stock) => (
            <Pressable key={stock.symbol} style={[styles.watchChip, selectedStock?.symbol === stock.symbol && styles.watchChipActive]} onPress={() => chooseStock(stock)}>
              <Text style={[styles.watchChipText, selectedStock?.symbol === stock.symbol && styles.watchChipTextActive]}>{stock.symbol}</Text>
            </Pressable>
          ))}
        </View>
        {selectedNews.map((item) => (
          <NewsCard item={item} key={item.title} />
        ))}
      </Card>

      <Card>
        <Text style={sharedText.sectionTitle}>Useful Links</Text>
        {generalLinks.map((item) => (
          <LinkRow key={item.title} item={item} />
        ))}
      </Card>

      {savedChecks.length ? (
        <Card>
          <View style={styles.sectionHeader}>
            <Text style={sharedText.sectionTitle}>Saved Checks</Text>
            <Text style={styles.countText}>{filteredSavedChecks.length}/{savedChecks.length}</Text>
          </View>
          <View style={styles.savedSearchBox}>
            <Ionicons name="search-outline" size={15} color={palette.muted} />
            <TextInput
              value={savedQuery}
              onChangeText={setSavedQuery}
              placeholder="Find saved context..."
              placeholderTextColor="#98A39D"
              style={styles.savedSearchInput}
            />
          </View>
          <View style={styles.filterRow}>
            {savedFilters.map((filter) => (
              <Pressable key={filter} style={[styles.filterChip, savedFilter === filter && styles.filterChipActive]} onPress={() => setSavedFilter(filter)}>
                <Text style={[styles.filterText, savedFilter === filter && styles.filterTextActive]}>{filter}</Text>
              </Pressable>
            ))}
          </View>
          {filteredSavedChecks.slice(0, 5).map((item) => (
            <SavedCheckRow key={item.id} item={item} onPress={() => openSavedCheck?.(item)} />
          ))}
          {!filteredSavedChecks.length ? (
            <View style={styles.emptySaved}>
              <Text style={styles.emptySavedTitle}>No saved checks match this filter.</Text>
              <Text style={styles.emptySavedText}>Try a ticker, strategy name, or switch back to All.</Text>
            </View>
          ) : null}
        </Card>
      ) : null}
    </ScreenScroll>
  );
}

function DataStatusCard({ status }) {
  const providers = Array.isArray(status?.capabilities) ? status.capabilities : [];
  const active = providers.filter((item) => item.status === "active");
  const fieldList = status?.data_quality_labels || [];
  const coreFields = fieldList.length ? fieldList.slice(0, 4) : ["Quote", "News", "Delayed options", "Manual upload"];
  return (
    <Card style={styles.dataStatusCard}>
      <View style={styles.sectionHeader}>
        <View>
          <Text style={styles.eyebrow}>Data transparency</Text>
          <Text style={styles.dataStatusTitle}>{active.length ? `${active.length} source${active.length === 1 ? "" : "s"} ready` : "Backend status pending"}</Text>
        </View>
        <View style={[styles.dataStatusPill, !active.length && styles.dataStatusPillMuted]}>
          <Text style={[styles.dataStatusPillText, !active.length && styles.dataStatusPillTextMuted]}>
            {active.length ? String(status?.strategy || "active").replace(/_/g, " ") : "offline"}
          </Text>
        </View>
      </View>
      <View style={styles.dataFieldRow}>
        {coreFields.map((field) => (
          <View key={field} style={styles.dataFieldChip}>
            <Ionicons name="checkmark-circle-outline" size={13} color={palette.green} />
            <Text style={styles.dataFieldText}>{field}</Text>
          </View>
        ))}
      </View>
      <Text style={styles.dataStatusCopy}>
        {status?.message || "RiskWise labels delayed, estimated, manual, and missing fields instead of pretending every option field is live."}
      </Text>
    </Card>
  );
}

function MarketSnapshot({ stock, quote, earnings, loading }) {
  const { width } = useWindowDimensions();
  const compactGrid = width < 360;
  const nextEarnings = earnings[0];
  const change = Number(quote?.changePercentage || 0);
  const changeText = quote?.price ? `${change >= 0 ? "+" : ""}${change.toFixed(2)}%` : "Pending";
  return (
    <Card style={styles.snapshotCard}>
      <View style={styles.snapshotHeader}>
        <View>
          <Text style={styles.eyebrow}>Market snapshot</Text>
          <Text style={styles.snapshotTitle}>{stock?.symbol || "Market"} {quote?.price ? `$${Number(quote.price).toFixed(2)}` : loading ? "loading..." : "quote unavailable"}</Text>
        </View>
        <View style={[styles.changePill, change < 0 && styles.changePillDown]}>
          <Text style={[styles.changeText, change < 0 && styles.changeTextDown]}>{changeText}</Text>
        </View>
      </View>
      <View style={styles.snapshotGrid}>
        <MiniDatum compact={compactGrid} label="Day range" value={quote?.dayLow && quote?.dayHigh ? `$${Number(quote.dayLow).toFixed(2)} - $${Number(quote.dayHigh).toFixed(2)}` : "Not available"} />
        <MiniDatum compact={compactGrid} label="Volume" value={quote?.volume ? shortNumber(quote.volume) : "Not available"} />
        <MiniDatum compact={compactGrid} label="Market cap" value={quote?.marketCap ? shortMoney(quote.marketCap) : "Not available"} />
        <MiniDatum compact={compactGrid} label="Earnings" value={nextEarnings?.date || "No date found"} />
      </View>
    </Card>
  );
}

function OptionsReadinessCard({ stock, context, loading }) {
  const pending = Array.isArray(context?.fields_pending) ? context.fields_pending : [];
  const ready = context?.status && !["needs_provider_key", "requires_options_provider"].includes(context.status);
  const title = loading
    ? "Checking option data..."
    : ready
      ? `${stock?.symbol || "Ticker"} options context attached`
      : `${stock?.symbol || "Ticker"} needs option-chain proof`;
  const provider = context?.provider || (loading ? "loading" : "not attached");
  const pendingLabels = pending.length ? pending.slice(0, 5).map(friendlyField) : ["Bid/ask", "IV", "Greeks", "Volume", "Open interest"];
  return (
    <Card style={styles.optionsReadinessCard}>
      <View style={styles.sectionHeader}>
        <View>
          <Text style={styles.eyebrow}>Options readiness</Text>
          <Text style={styles.optionsReadinessTitle}>{title}</Text>
        </View>
        <View style={[styles.optionsStatusPill, !ready && styles.optionsStatusPillWarn]}>
          <Text style={[styles.optionsStatusText, !ready && styles.optionsStatusTextWarn]}>{provider.replace(/_/g, " ")}</Text>
        </View>
      </View>
      <View style={styles.dataFieldRow}>
        {pendingLabels.map((field) => (
          <View key={field} style={[styles.dataFieldChip, styles.optionsMissingChip]}>
            <Ionicons name={ready && !pending.length ? "checkmark-circle-outline" : "ellipse-outline"} size={13} color={ready && !pending.length ? palette.green : "#B45309"} />
            <Text style={styles.dataFieldText}>{field}</Text>
          </View>
        ))}
      </View>
      <Text style={styles.dataStatusCopy}>
        {context?.message || "RiskWise can review structure with manual contract inputs, but it will not invent live premium, IV, Greeks, bid/ask, volume, or open interest."}
      </Text>
    </Card>
  );
}

function MiniDatum({ label, value, compact }) {
  return (
    <View style={[styles.miniDatum, compact && styles.miniDatumCompact]}>
      <Text style={styles.miniDatumLabel}>{label}</Text>
      <Text style={styles.miniDatumValue} numberOfLines={1}>{value}</Text>
    </View>
  );
}

function NewsCard({ item }) {
  return (
    <Pressable style={styles.newsCard} onPress={() => Linking.openURL(item.url)}>
      <Image source={{ uri: item.image }} style={styles.newsImage} />
      <View style={styles.newsOverlay}>
        <View style={styles.newsSource}>
          <Text style={styles.newsSourceText}>{item.source}</Text>
        </View>
        <Text style={styles.newsTitle} numberOfLines={2}>{item.title}</Text>
      </View>
    </Pressable>
  );
}

function LinkRow({ item }) {
  return (
    <Pressable style={styles.linkRow} onPress={() => Linking.openURL(item.url)}>
      <View>
        <Text style={styles.linkTitle}>{item.title}</Text>
        <Text style={styles.linkSource}>{item.source}</Text>
      </View>
      <Ionicons name="open-outline" size={18} color={palette.green} />
    </Pressable>
  );
}

function SavedCheckRow({ item, onPress }) {
  const report = item.report || {};
  return (
    <Pressable style={styles.savedRow} onPress={onPress}>
      <View style={styles.savedIcon}>
        <Ionicons name="bookmark-outline" size={16} color={palette.green} />
      </View>
      <View style={styles.savedBody}>
        <Text style={styles.savedTitle}>{report.ticker || "Saved"} {report.tradeType || "Check"}</Text>
        <Text style={styles.savedSub}>{report.weakestLink || "Risk review"} - {report.riskPosture || "Mixed"}</Text>
        {item.note ? <Text style={styles.savedNote} numberOfLines={1}>{item.note}</Text> : null}
      </View>
      <View style={styles.savedScore}>
        <Text style={styles.savedScoreText}>{report.setupScore || "--"}</Text>
      </View>
    </Pressable>
  );
}

function filterSavedChecks(items, query, filter) {
  const clean = String(query || "").trim().toLowerCase();
  return items.filter((item) => {
    const report = item.report || {};
    const haystack = [
      report.ticker,
      report.tradeType,
      report.weakestLink,
      report.riskPosture,
      report.overallRead,
      item.note
    ].join(" ").toLowerCase();
    const matchesQuery = !clean || haystack.includes(clean);
    const posture = String(report.riskPosture || "").toLowerCase();
    const riskScore = Number(report.riskScore || 0);
    const matchesFilter =
      filter === "All" ||
      (filter === "High risk" && (posture.includes("high") || posture.includes("elevated") || riskScore >= 6.5)) ||
      (filter === "Moderate" && (posture.includes("moderate") || posture.includes("mixed") || (riskScore >= 3.5 && riskScore < 6.5))) ||
      (filter === "Controlled" && (posture.includes("controlled") || posture.includes("low") || riskScore < 3.5));
    return matchesQuery && matchesFilter;
  });
}

function getMatches(query, selectedStock, remoteMatches = []) {
  const clean = String(query || "").replace("-", " ").toLowerCase().trim();
  if (!clean) {
    return [...remoteMatches, ...stockUniverse].slice(0, 5);
  }
  const pool = dedupeStocks([...remoteMatches, ...stockUniverse]);
  const matches = pool
    .map((stock) => {
      const symbol = stock.symbol.toLowerCase();
      const name = stock.name.toLowerCase();
      let score = 0;
      if (symbol === clean) score += 20;
      if (symbol.startsWith(clean)) score += 12;
      if (name.includes(clean)) score += 9;
      if (`${symbol} ${name}`.includes(clean)) score += 5;
      return { stock, score };
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((item) => item.stock)
    .slice(0, 5);
  if (!matches.length && selectedStock) {
    return [selectedStock];
  }
  return matches.length ? matches : stockUniverse.slice(0, 5);
}

function dedupeStocks(items) {
  const seen = new Set();
  return items.filter((stock) => {
    const symbol = String(stock.symbol || "").toUpperCase();
    if (!symbol || seen.has(symbol)) {
      return false;
    }
    seen.add(symbol);
    return true;
  });
}

function buildWatchlist(savedChecks, selectedStock) {
  const symbols = [selectedStock?.symbol, ...savedChecks.map((item) => item.report?.ticker), "SPY", "AAPL", "NVDA"].filter(Boolean);
  const unique = [...new Set(symbols)].slice(0, 6);
  return unique.map((symbol) => findStock(symbol) || { symbol, name: symbol, sector: "Market" });
}

function buildStockNews(stock, providerNews, profile) {
  const active = stock || stockUniverse[0];
  const profileSector = profile?.sector || active.sector;
  const image = profile?.image || newsImages[profileSector] || newsImages[active.sector] || newsImages.Index;
  const liveItems = Array.isArray(providerNews?.items) ? providerNews.items.filter((item) => item.title && item.url).slice(0, 3) : [];
  if (liveItems.length) {
    return liveItems.map((item) => ({
      title: item.title,
      source: item.source || providerNews.provider || "Market news",
      image: item.image || image,
      url: item.url
    }));
  }
  return [
    {
      title: `${active.symbol} headlines, price context, and market chatter`,
      source: "Yahoo Finance",
      image,
      url: `https://finance.yahoo.com/quote/${active.symbol}/news/`
    },
    {
      title: `${active.name} quote page, chart, and key statistics`,
      source: "MarketWatch",
      image,
      url: `https://www.marketwatch.com/investing/stock/${active.symbol.toLowerCase()}`
    }
  ];
}

function findStock(symbol) {
  const clean = String(symbol || "").toUpperCase();
  return stockUniverse.find((stock) => stock.symbol === clean);
}

function shortNumber(value) {
  const number = Number(value || 0);
  if (number >= 1_000_000_000_000) {
    return `${(number / 1_000_000_000_000).toFixed(2)}T`;
  }
  if (number >= 1_000_000_000) {
    return `${(number / 1_000_000_000).toFixed(2)}B`;
  }
  if (number >= 1_000_000) {
    return `${(number / 1_000_000).toFixed(1)}M`;
  }
  return number.toLocaleString();
}

function shortMoney(value) {
  return `$${shortNumber(value)}`;
}

function friendlyField(value) {
  const clean = String(value || "").replace(/_/g, " ");
  if (clean.toLowerCase() === "bid ask") return "Bid/ask";
  if (clean.toLowerCase() === "implied volatility") return "IV";
  if (clean.toLowerCase() === "provider reported greeks") return "Provider Greeks";
  return clean.replace(/\b\w/g, (char) => char.toUpperCase());
}

const styles = StyleSheet.create({
  selectorCard: {
    backgroundColor: "#FBFFFC"
  },
  selectorTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 12,
    marginBottom: 13
  },
  eyebrow: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "900",
    marginBottom: 4
  },
  selectorTitle: {
    color: palette.dark,
    fontSize: 24,
    fontWeight: "900"
  },
  accountPill: {
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#CFEFD8",
    backgroundColor: "#F3FFF6",
    paddingHorizontal: 11,
    paddingVertical: 8,
    alignItems: "flex-end"
  },
  accountLabel: {
    color: palette.muted,
    fontSize: 9,
    fontWeight: "900"
  },
  accountText: {
    color: palette.green,
    fontSize: 13,
    fontWeight: "900",
    marginTop: 2
  },
  searchBox: {
    minHeight: 48,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FFFFFF",
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    paddingHorizontal: 12
  },
  searchInput: {
    flex: 1,
    color: palette.dark,
    fontSize: 14,
    fontWeight: "800",
    outlineStyle: "none"
  },
  dropdown: {
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    marginTop: 8,
    overflow: "hidden"
  },
  matchRow: {
    minHeight: 54,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#F0F3F0"
  },
  matchRowActive: {
    backgroundColor: "#F4FCF6"
  },
  symbolBadge: {
    width: 48,
    height: 34,
    borderRadius: 12,
    backgroundColor: palette.greenSoft,
    alignItems: "center",
    justifyContent: "center"
  },
  symbolBadgeText: {
    color: palette.green,
    fontSize: 12,
    fontWeight: "900"
  },
  matchText: {
    flex: 1
  },
  matchName: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900"
  },
  matchSector: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 2
  },
  checkButton: {
    minHeight: 49,
    borderRadius: 16,
    backgroundColor: palette.green,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 8,
    marginTop: 12
  },
  buttonDisabled: {
    opacity: 0.5
  },
  checkText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "900"
  },
  snapshotCard: {
    backgroundColor: "#FFFFFF"
  },
  dataStatusCard: {
    backgroundColor: "#FBFFFC",
    borderColor: "#DDF3E3"
  },
  optionsReadinessCard: {
    backgroundColor: "#FFFCF4",
    borderColor: "#F2DFA8"
  },
  optionsReadinessTitle: {
    color: palette.dark,
    fontSize: 16,
    fontWeight: "900",
    maxWidth: 235
  },
  optionsStatusPill: {
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 7,
    backgroundColor: palette.greenSoft,
    borderWidth: 1,
    borderColor: "#CFEFD8",
    maxWidth: 130
  },
  optionsStatusPillWarn: {
    backgroundColor: "#FFF7E6",
    borderColor: "#F1D39A"
  },
  optionsStatusText: {
    color: palette.green,
    fontSize: 9,
    fontWeight: "900",
    textTransform: "capitalize"
  },
  optionsStatusTextWarn: {
    color: "#B45309"
  },
  optionsMissingChip: {
    backgroundColor: "#FFFFFF"
  },
  dataStatusTitle: {
    color: palette.dark,
    fontSize: 16,
    fontWeight: "900"
  },
  dataStatusPill: {
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 7,
    backgroundColor: palette.greenSoft,
    borderWidth: 1,
    borderColor: "#CFEFD8",
    maxWidth: 120
  },
  dataStatusPillMuted: {
    backgroundColor: "#F3F5F3",
    borderColor: palette.border
  },
  dataStatusPillText: {
    color: palette.green,
    fontSize: 9,
    fontWeight: "900",
    textTransform: "capitalize"
  },
  dataStatusPillTextMuted: {
    color: palette.muted
  },
  dataFieldRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 7,
    marginTop: 10
  },
  dataFieldChip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "#DDF3E3",
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 9,
    paddingVertical: 6,
    flexDirection: "row",
    alignItems: "center",
    gap: 5
  },
  dataFieldText: {
    color: palette.dark,
    fontSize: 10,
    fontWeight: "900"
  },
  dataStatusCopy: {
    color: palette.muted,
    fontSize: 11,
    lineHeight: 16,
    fontWeight: "800",
    marginTop: 10
  },
  snapshotHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 12,
    marginBottom: 12
  },
  snapshotTitle: {
    color: palette.dark,
    fontSize: 20,
    fontWeight: "900"
  },
  changePill: {
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 7,
    backgroundColor: palette.greenSoft,
    borderWidth: 1,
    borderColor: "#CFEFD8"
  },
  changePillDown: {
    backgroundColor: "#FFF5F5",
    borderColor: "#F5D1D1"
  },
  changeText: {
    color: palette.green,
    fontSize: 12,
    fontWeight: "900"
  },
  changeTextDown: {
    color: palette.red
  },
  snapshotGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  miniDatum: {
    width: "48.6%",
    borderRadius: 14,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FBFCFB",
    padding: 10
  },
  miniDatumCompact: {
    width: "100%"
  },
  miniDatumLabel: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "900",
    marginBottom: 5
  },
  miniDatumValue: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center"
  },
  sectionSub: {
    color: palette.green,
    fontSize: 11,
    fontWeight: "900",
    marginBottom: 10
  },
  watchlistRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 7,
    marginBottom: 10
  },
  watchChip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FFFFFF",
    paddingVertical: 7,
    paddingHorizontal: 11
  },
  watchChipActive: {
    backgroundColor: palette.green,
    borderColor: palette.green
  },
  watchChipText: {
    color: palette.dark,
    fontSize: 11,
    fontWeight: "900"
  },
  watchChipTextActive: {
    color: "#FFFFFF"
  },
  newsCard: {
    height: 148,
    borderRadius: 18,
    overflow: "hidden",
    backgroundColor: "#E9F1EA",
    marginTop: 9
  },
  newsImage: {
    width: "100%",
    height: "100%"
  },
  newsOverlay: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    padding: 12,
    backgroundColor: "rgba(13, 24, 20, 0.64)"
  },
  newsSource: {
    alignSelf: "flex-start",
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.18)",
    paddingHorizontal: 8,
    paddingVertical: 4,
    marginBottom: 7
  },
  newsSourceText: {
    color: "#FFFFFF",
    fontSize: 9,
    fontWeight: "900"
  },
  newsTitle: {
    color: "#FFFFFF",
    fontSize: 14,
    lineHeight: 18,
    fontWeight: "900"
  },
  linkRow: {
    minHeight: 56,
    borderTopWidth: 1,
    borderTopColor: palette.border,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12
  },
  linkTitle: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900"
  },
  linkSource: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 2
  },
  countText: {
    color: palette.green,
    fontSize: 11,
    fontWeight: "900"
  },
  savedRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderTopWidth: 1,
    borderTopColor: palette.border,
    paddingVertical: 11
  },
  savedIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: palette.greenSoft,
    alignItems: "center",
    justifyContent: "center"
  },
  savedBody: {
    flex: 1
  },
  savedTitle: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900"
  },
  savedSub: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 2
  },
  savedNote: {
    color: palette.dark,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 3
  },
  savedSearchBox: {
    minHeight: 42,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FBFCFB",
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 11,
    marginTop: 10
  },
  savedSearchInput: {
    flex: 1,
    color: palette.dark,
    fontSize: 12,
    fontWeight: "800",
    outlineStyle: "none"
  },
  filterRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 7,
    marginTop: 9,
    marginBottom: 2
  },
  filterChip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FFFFFF",
    paddingVertical: 7,
    paddingHorizontal: 10
  },
  filterChipActive: {
    backgroundColor: palette.greenSoft,
    borderColor: palette.green
  },
  filterText: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "900"
  },
  filterTextActive: {
    color: palette.green
  },
  emptySaved: {
    borderTopWidth: 1,
    borderTopColor: palette.border,
    paddingVertical: 14
  },
  emptySavedTitle: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  emptySavedText: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 3
  },
  savedScore: {
    width: 42,
    height: 34,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: "#CFEFD8",
    backgroundColor: "#FBFFFC",
    alignItems: "center",
    justifyContent: "center"
  },
  savedScoreText: {
    color: palette.green,
    fontSize: 14,
    fontWeight: "900"
  }
});
