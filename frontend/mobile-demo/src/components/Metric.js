import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { palette } from "../theme/theme";

export function Metric({ label, value }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.value}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  metric: {
    flex: 1
  },
  label: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "800",
    marginBottom: 4
  },
  value: {
    color: palette.dark,
    fontSize: 18,
    fontWeight: "900"
  }
});

