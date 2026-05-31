import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { palette } from "../theme/theme";

export function ScoreRing({ score, label }) {
  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{label}</Text>
      <View style={styles.circle}>
        <View style={styles.inner}>
          <Text style={styles.number}>{score}</Text>
          <Text style={styles.denom}>/100</Text>
        </View>
      </View>
    </View>
  );
}

export function RiskGauge({ value }) {
  return (
    <View style={styles.gaugeWrap}>
      <View style={styles.gaugeTrack}>
        <View style={[styles.gaugeFill, { width: `${value * 10}%` }]} />
      </View>
      <Text style={styles.gaugeValue}>{value}</Text>
      <Text style={styles.denom}>/10</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    width: 128,
    alignItems: "center"
  },
  label: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "800",
    marginBottom: 4
  },
  circle: {
    width: 92,
    height: 92,
    borderRadius: 46,
    borderWidth: 9,
    borderColor: "#BEEBCB",
    borderLeftColor: palette.green,
    borderBottomColor: palette.green,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 8
  },
  inner: {
    width: 62,
    height: 62,
    borderRadius: 31,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FFFFFF"
  },
  number: {
    color: palette.dark,
    fontSize: 25,
    fontWeight: "900"
  },
  denom: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800"
  },
  gaugeWrap: {
    width: 120,
    alignItems: "center"
  },
  gaugeTrack: {
    width: 108,
    height: 16,
    borderRadius: 999,
    backgroundColor: "#E5E7EB",
    overflow: "hidden",
    marginBottom: 10
  },
  gaugeFill: {
    height: "100%",
    backgroundColor: palette.amber
  },
  gaugeValue: {
    color: palette.dark,
    fontSize: 26,
    fontWeight: "900"
  }
});

