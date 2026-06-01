import React from "react";
import { StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Defs, LinearGradient, Path, Polygon, Stop } from "react-native-svg";
import { palette } from "../theme/theme";

export function MiniLineChart({ data = [], height = 86, stroke = palette.green, fill = "rgba(22,163,74,0.12)" }) {
  const values = data.length ? data : [42, 46, 44, 51, 49, 58, 61, 57, 66, 70];
  const width = 280;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const points = values.map((value, index) => {
    const x = (index / Math.max(1, values.length - 1)) * width;
    const y = height - 12 - ((value - min) / span) * (height - 24);
    return [x, y];
  });
  const line = points.map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const area = `${line} L ${width} ${height} L 0 ${height} Z`;

  return (
    <View style={[styles.chartWrap, { height }]}>
      <Svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} preserveAspectRatio="none">
        <Defs>
          <LinearGradient id="riskwiseChartFill" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor={fill} stopOpacity="1" />
            <Stop offset="1" stopColor={fill} stopOpacity="0" />
          </LinearGradient>
        </Defs>
        <Path d={area} fill="url(#riskwiseChartFill)" />
        <Path d={line} fill="none" stroke={stroke} strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
      </Svg>
    </View>
  );
}

export function ConfidenceRing({ value = 72, label = "AI", sublabel = "confidence", size = 92 }) {
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.max(0, Math.min(100, value)) / 100);
  return (
    <View style={[styles.ringWrap, { width: size, height: size }]}>
      <Svg width={size} height={size} viewBox="0 0 92 92">
        <Circle cx="46" cy="46" r={radius} stroke="#EAF1EA" strokeWidth="9" fill="#FFFFFF" />
        <Circle
          cx="46"
          cy="46"
          r={radius}
          stroke={value >= 70 ? palette.green : palette.teal}
          strokeWidth="9"
          strokeLinecap="round"
          fill="none"
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={offset}
          transform="rotate(-90 46 46)"
        />
      </Svg>
      <View style={styles.ringText}>
        <Text style={styles.ringValue}>{value}</Text>
        <Text style={styles.ringLabel}>{label}</Text>
      </View>
      <Text style={styles.ringSub}>{sublabel}</Text>
    </View>
  );
}

export function IntelligenceStrip({ agreement = 72, agents = 5, pattern = "Risk-balanced setup", missing = 2 }) {
  return (
    <View style={styles.strip}>
      <View style={styles.pulseMark}>
        <View style={styles.pulseCore} />
      </View>
      <View style={styles.stripCopy}>
        <Text style={styles.stripTitle}>RiskWise is weighing this setup</Text>
        <Text style={styles.stripSub}>{agents}/5 agents active - {agreement}% consensus - {pattern}</Text>
      </View>
      <View style={styles.missingBadge}>
        <Text style={styles.missingValue}>{missing}</Text>
        <Text style={styles.missingLabel}>gaps</Text>
      </View>
    </View>
  );
}

export function ScenarioFanChart({ scenarios = [], height = 118 }) {
  const normalized = normalizeScenarios(scenarios);
  const values = normalized.map((item) => item.value);
  const min = Math.min(...values, -30);
  const max = Math.max(...values, 40);
  const span = Math.max(1, max - min);
  const zero = height - 24 - ((0 - min) / span) * (height - 42);
  const points = normalized.map((item, index) => {
    const x = 20 + (index / Math.max(1, normalized.length - 1)) * 238;
    const y = height - 24 - ((item.value - min) / span) * (height - 42);
    return { ...item, x, y };
  });
  const line = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ");

  return (
    <View style={styles.fanWrap}>
      <View style={styles.fanHeader}>
        <Text style={styles.fanTitle}>Outcome range</Text>
        <Text style={styles.fanSub}>Bear/base/bull path from the report</Text>
      </View>
      <Svg viewBox={`0 0 280 ${height}`} width="100%" height={height} preserveAspectRatio="none">
        <Defs>
          <LinearGradient id="fanGradient" x1="0" y1="0" x2="1" y2="0">
            <Stop offset="0" stopColor={palette.red} stopOpacity="0.18" />
            <Stop offset="0.5" stopColor={palette.teal} stopOpacity="0.12" />
            <Stop offset="1" stopColor={palette.green} stopOpacity="0.18" />
          </LinearGradient>
        </Defs>
        <Path d={`M 20 ${zero.toFixed(1)} H 258`} stroke="#DCEBDD" strokeWidth="1.4" strokeDasharray="5 5" />
        <Path d={`${line} L 258 ${height - 12} L 20 ${height - 12} Z`} fill="url(#fanGradient)" />
        <Path d={line} fill="none" stroke={palette.dark} strokeOpacity="0.72" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
        {points.map((point) => (
          <Circle key={point.label} cx={point.x} cy={point.y} r="4.6" fill={scenarioColor(point.value)} />
        ))}
      </Svg>
      <View style={styles.fanLabels}>
        {points.map((point) => (
          <View key={point.label} style={styles.fanLabelItem}>
            <Text style={styles.fanLabel}>{point.label}</Text>
            <Text style={[styles.fanValue, { color: scenarioColor(point.value) }]}>{point.display}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

export function RiskBreakdownBars({ items = [] }) {
  const normalized = items.length ? items : [
    { label: "Sizing", value: 58, tone: "warn" },
    { label: "Time", value: 66, tone: "warn" },
    { label: "Liquidity", value: 42, tone: "good" },
    { label: "Volatility", value: 72, tone: "risk" }
  ];
  return (
    <View style={styles.breakdownWrap}>
      {normalized.map((item) => (
        <View key={item.label} style={styles.breakdownRow}>
          <View style={styles.breakdownTop}>
            <Text style={styles.breakdownLabel}>{item.label}</Text>
            <Text style={[styles.breakdownValue, { color: toneToColor(item.tone, item.value) }]}>{Math.round(item.value)}/100</Text>
          </View>
          <View style={styles.breakdownTrack}>
            <View style={[styles.breakdownFill, { width: `${Math.max(4, Math.min(100, item.value))}%`, backgroundColor: toneToColor(item.tone, item.value) }]} />
          </View>
        </View>
      ))}
    </View>
  );
}

export function AgentRadar({ agents = [] }) {
  const normalized = (agents.length ? agents : [
    { name: "Risk", score: 72 },
    { name: "Signal", score: 58 },
    { name: "Vol", score: 64 },
    { name: "Size", score: 82 },
    { name: "Coach", score: 68 }
  ]).slice(0, 5);
  const center = 76;
  const maxRadius = 54;
  const points = normalized.map((agent, index) => {
    const angle = -Math.PI / 2 + (index / normalized.length) * Math.PI * 2;
    const radius = maxRadius * (Math.max(0, Math.min(100, Number(agent.score || 0))) / 100);
    return {
      ...agent,
      x: center + Math.cos(angle) * radius,
      y: center + Math.sin(angle) * radius,
      labelX: center + Math.cos(angle) * (maxRadius + 18),
      labelY: center + Math.sin(angle) * (maxRadius + 18)
    };
  });
  const polygon = points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");

  return (
    <View style={styles.radarWrap}>
      <View style={styles.radarGraphic}>
        <Svg viewBox="0 0 152 152" width="152" height="152">
          {[18, 36, 54].map((radius) => (
            <Circle key={radius} cx={center} cy={center} r={radius} fill="none" stroke="#DCEBDD" strokeWidth="1" />
          ))}
          <Polygon points={polygon} fill="rgba(22,163,74,0.18)" stroke={palette.green} strokeWidth="2.4" />
          {points.map((point) => (
            <Circle key={point.name} cx={point.x} cy={point.y} r="3.8" fill={point.score >= 70 ? palette.green : palette.teal} />
          ))}
        </Svg>
      </View>
      <View style={styles.radarLegend}>
        {normalized.map((agent) => (
          <View key={agent.name} style={styles.radarLegendRow}>
            <Text style={styles.radarName} numberOfLines={1}>{agent.name}</Text>
            <Text style={styles.radarScore}>{Math.round(agent.score || 0)}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

export function AmbientGlow() {
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <View style={[styles.glow, styles.glowOne]} />
      <View style={[styles.glow, styles.glowTwo]} />
      <View style={[styles.glow, styles.glowThree]} />
    </View>
  );
}

function normalizeScenarios(scenarios) {
  if (Array.isArray(scenarios) && scenarios.length) {
    return scenarios.slice(0, 3).map((item, index) => {
      const raw = item.pnl ?? item.return ?? item.value ?? item.amount ?? 0;
      const value = Number(String(raw).replace(/[^0-9.-]/g, "")) || 0;
      return {
        label: item.label || item.name || ["Bear", "Base", "Bull"][index] || "Path",
        value,
        display: typeof raw === "string" ? raw : `${value > 0 ? "+" : ""}${value}%`
      };
    });
  }
  return [
    { label: "Bear", value: -42, display: "-42%" },
    { label: "Base", value: 12, display: "+12%" },
    { label: "Bull", value: 61, display: "+61%" }
  ];
}

function scenarioColor(value) {
  if (value < 0) return palette.red;
  if (value < 25) return palette.teal;
  return palette.green;
}

function toneToColor(tone, value) {
  if (tone === "risk" || value >= 72) return palette.red;
  if (tone === "warn" || value >= 55) return palette.teal;
  return palette.green;
}

const styles = StyleSheet.create({
  chartWrap: {
    width: "100%",
    borderRadius: 18,
    overflow: "hidden"
  },
  ringWrap: {
    alignItems: "center",
    justifyContent: "center",
    position: "relative"
  },
  ringText: {
    position: "absolute",
    alignItems: "center",
    justifyContent: "center"
  },
  ringValue: {
    color: palette.dark,
    fontSize: 21,
    fontWeight: "900",
    lineHeight: 24
  },
  ringLabel: {
    color: palette.green,
    fontSize: 9,
    fontWeight: "900"
  },
  ringSub: {
    position: "absolute",
    bottom: -4,
    color: palette.muted,
    fontSize: 8,
    fontWeight: "900"
  },
  strip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 11,
    borderRadius: 20,
    padding: 13,
    marginBottom: 12,
    backgroundColor: "rgba(255,255,255,0.88)",
    borderWidth: 1,
    borderColor: "rgba(207,239,216,0.95)",
    shadowColor: palette.green,
    shadowOpacity: 0.12,
    shadowRadius: 22,
    shadowOffset: { width: 0, height: 10 }
  },
  fanWrap: {
    borderRadius: 18,
    backgroundColor: "rgba(255,255,255,0.74)",
    borderWidth: 1,
    borderColor: "rgba(207,239,216,0.9)",
    padding: 12,
    marginTop: 12,
    shadowColor: palette.green,
    shadowOpacity: 0.08,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 }
  },
  fanHeader: {
    marginBottom: 4
  },
  fanTitle: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900"
  },
  fanSub: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 2
  },
  fanLabels: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: -4
  },
  fanLabelItem: {
    alignItems: "center"
  },
  fanLabel: {
    color: palette.muted,
    fontSize: 9,
    fontWeight: "900"
  },
  fanValue: {
    fontSize: 12,
    fontWeight: "900",
    marginTop: 2
  },
  breakdownWrap: {
    gap: 10,
    marginTop: 10
  },
  breakdownRow: {
    gap: 5
  },
  breakdownTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  breakdownLabel: {
    color: palette.dark,
    fontSize: 11,
    fontWeight: "900"
  },
  breakdownValue: {
    fontSize: 11,
    fontWeight: "900"
  },
  breakdownTrack: {
    height: 8,
    borderRadius: 999,
    overflow: "hidden",
    backgroundColor: "#EAF1EA"
  },
  breakdownFill: {
    height: "100%",
    borderRadius: 999
  },
  radarWrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    borderRadius: 18,
    backgroundColor: "#FBFFFC",
    borderWidth: 1,
    borderColor: "#DCEBDD",
    padding: 12,
    marginTop: 12
  },
  radarGraphic: {
    width: 152,
    height: 152,
    alignItems: "center",
    justifyContent: "center"
  },
  radarLegend: {
    flex: 1,
    gap: 7
  },
  radarLegendRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderBottomWidth: 1,
    borderBottomColor: "#EAF2EA",
    paddingBottom: 6
  },
  radarName: {
    flex: 1,
    color: palette.dark,
    fontSize: 10,
    fontWeight: "900"
  },
  radarScore: {
    color: palette.green,
    fontSize: 11,
    fontWeight: "900"
  },
  pulseMark: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "rgba(22,163,74,0.10)",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "rgba(22,163,74,0.20)"
  },
  pulseCore: {
    width: 17,
    height: 17,
    borderRadius: 9,
    backgroundColor: palette.green,
    shadowColor: palette.green,
    shadowOpacity: 0.8,
    shadowRadius: 16
  },
  stripCopy: {
    flex: 1
  },
  stripTitle: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  stripSub: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 3
  },
  missingBadge: {
    minWidth: 42,
    borderRadius: 15,
    backgroundColor: palette.greenSoft,
    alignItems: "center",
    paddingVertical: 7
  },
  missingValue: {
    color: palette.green,
    fontSize: 15,
    fontWeight: "900"
  },
  missingLabel: {
    color: palette.green,
    fontSize: 8,
    fontWeight: "900"
  },
  glow: {
    position: "absolute",
    borderRadius: 999,
    opacity: 0.55
  },
  glowOne: {
    width: 230,
    height: 230,
    top: 38,
    right: -110,
    backgroundColor: "rgba(22,163,74,0.12)"
  },
  glowTwo: {
    width: 180,
    height: 180,
    bottom: 90,
    left: -80,
    backgroundColor: "rgba(14,165,233,0.08)"
  },
  glowThree: {
    width: 160,
    height: 160,
    top: 310,
    left: 130,
    backgroundColor: "rgba(22,163,74,0.07)"
  }
});
