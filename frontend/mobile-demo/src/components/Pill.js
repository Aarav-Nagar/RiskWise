import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { palette } from "../theme/theme";

export function Pill({ label, tone }) {
  const risk = tone === "risk";
  return (
    <View style={[styles.pill, risk && styles.pillRisk]}>
      <Text style={[styles.text, risk && styles.textRisk]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    backgroundColor: palette.greenSoft,
    paddingHorizontal: 11,
    paddingVertical: 6,
    borderRadius: 999
  },
  pillRisk: {
    backgroundColor: palette.redSoft
  },
  text: {
    color: palette.green,
    fontSize: 11,
    fontWeight: "900"
  },
  textRisk: {
    color: palette.red
  }
});

