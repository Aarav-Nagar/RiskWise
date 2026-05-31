import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Card } from "../components/Card";
import { Field, Header, ScreenScroll, sharedText } from "../components/Shared";
import { palette } from "../theme/theme";

const popular = ["SPY", "AAPL", "NVDA", "MSFT", "AMD", "TSLA"];

export function SearchScreen({ user, draft, setDraft, navigate }) {
  const sectors = user?.sectors?.length ? user.sectors : ["Technology", "Healthcare", "Financials", "Energy"];
  const caps = user?.marketCaps?.length ? user.marketCaps : ["Mega cap", "Large cap", "High-volatility"];
  const events = user?.events?.length ? user.events : ["Earnings", "Sector rotation", "Unusual volume"];

  return (
    <ScreenScroll>
      <Header title="Explore" subtitle="Find what you want to risk-check next." />
      <Card style={styles.searchCard}>
        <Field label="Ticker or company" value={draft.ticker} onChangeText={(ticker) => setDraft({ ...draft, ticker: ticker.toUpperCase() })} />
        <Pressable style={styles.checkButton} onPress={() => navigate("Check")}>
          <Ionicons name="location-outline" size={18} color="#FFFFFF" />
          <Text style={styles.checkText}>Open Risk Check</Text>
        </Pressable>
      </Card>

      <Card>
        <Text style={sharedText.sectionTitle}>Popular Checks</Text>
        <View style={styles.symbolGrid}>
          {popular.map((ticker) => (
            <Pressable key={ticker} style={styles.symbol} onPress={() => {
              setDraft({ ...draft, ticker });
              navigate("Check");
            }}>
              <Text style={styles.symbolText}>{ticker}</Text>
            </Pressable>
          ))}
        </View>
      </Card>

      <FocusCard title="Sector Focus" icon="business-outline" items={sectors} />
      <FocusCard title="Market-Cap Focus" icon="pie-chart-outline" items={caps} />
      <FocusCard title="Event Focus" icon="flash-outline" items={events} />
    </ScreenScroll>
  );
}

function FocusCard({ title, icon, items }) {
  return (
    <Card>
      <View style={styles.focusHeader}>
        <View style={styles.focusIcon}>
          <Ionicons name={icon} size={18} color={palette.green} />
        </View>
        <Text style={sharedText.sectionTitle}>{title}</Text>
      </View>
      <View style={styles.chips}>
        {items.map((item) => (
          <View key={item} style={styles.chip}>
            <Text style={styles.chipText}>{item}</Text>
          </View>
        ))}
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  searchCard: {
    backgroundColor: "#FBFFFC"
  },
  checkButton: {
    minHeight: 47,
    borderRadius: 15,
    backgroundColor: palette.green,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 8
  },
  checkText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "900"
  },
  symbolGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 9
  },
  symbol: {
    width: "31.3%",
    borderWidth: 1,
    borderColor: "#DDEFE2",
    backgroundColor: "#F8FFF9",
    borderRadius: 14,
    paddingVertical: 13,
    alignItems: "center"
  },
  symbolText: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900"
  },
  focusHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10
  },
  focusIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: palette.greenSoft,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 10
  },
  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  chip: {
    borderWidth: 1,
    borderColor: "#CFEFD8",
    backgroundColor: "#F3FFF6",
    borderRadius: 999,
    paddingVertical: 8,
    paddingHorizontal: 11
  },
  chipText: {
    color: palette.green,
    fontSize: 11,
    fontWeight: "900"
  }
});
