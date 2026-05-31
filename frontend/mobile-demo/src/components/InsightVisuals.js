import React from "react";
import { StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Defs, LinearGradient, Path, Stop } from "react-native-svg";
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

export function AmbientGlow() {
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <View style={[styles.glow, styles.glowOne]} />
      <View style={[styles.glow, styles.glowTwo]} />
      <View style={[styles.glow, styles.glowThree]} />
    </View>
  );
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
