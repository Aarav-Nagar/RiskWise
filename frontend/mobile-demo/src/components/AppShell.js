import React from "react";
import { SafeAreaView, StatusBar, StyleSheet, Text, View } from "react-native";
import { StatusBar as ExpoStatusBar } from "expo-status-bar";
import { Ionicons } from "@expo/vector-icons";
import { BottomTabs } from "./BottomTabs";
import { AmbientGlow } from "./InsightVisuals";
import { palette } from "../theme/theme";

export function AppShell({ activeTab, setActiveTab, disabledTabs, showTabs = true, children }) {
  return (
    <SafeAreaView style={styles.appCanvas}>
      <StatusBar barStyle="dark-content" />
      <ExpoStatusBar style="dark" />
      <View style={styles.phone}>
        {showTabs ? <AmbientGlow /> : null}
        <PhoneStatusBar />
        <View style={styles.screen}>{children}</View>
        {showTabs ? <BottomTabs activeTab={activeTab} setActiveTab={setActiveTab} disabledTabs={disabledTabs} /> : null}
      </View>
    </SafeAreaView>
  );
}

function PhoneStatusBar() {
  return (
    <View style={styles.statusBar}>
      <Text style={styles.statusText}>9:41</Text>
      <View style={styles.statusDots}>
        <Ionicons name="cellular-outline" size={15} color={palette.dark} />
        <Ionicons name="wifi-outline" size={15} color={palette.dark} />
        <Ionicons name="battery-full-outline" size={18} color={palette.dark} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  appCanvas: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: palette.canvas,
    padding: 0
  },
  phone: {
    width: "100%",
    maxWidth: 430,
    height: "100%",
    maxHeight: 900,
    minHeight: 780,
    backgroundColor: palette.bg,
    borderRadius: 34,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "rgba(0,0,0,0.08)",
    shadowColor: "#000",
    shadowOpacity: 0.18,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 12 }
  },
  statusBar: {
    height: 34,
    paddingHorizontal: 22,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: palette.bg
  },
  statusText: {
    color: palette.dark,
    fontWeight: "800",
    fontSize: 13
  },
  statusDots: {
    flexDirection: "row",
    gap: 8
  },
  screen: {
    flex: 1,
    zIndex: 1
  }
});
