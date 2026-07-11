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
        <View style={styles.screen}>
          <AppErrorBoundary>{children}</AppErrorBoundary>
        </View>
        {showTabs ? <BottomTabs activeTab={activeTab} setActiveTab={setActiveTab} disabledTabs={disabledTabs} /> : null}
      </View>
    </SafeAreaView>
  );
}

class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("AppShell caught a render error", error, info?.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <View style={styles.errorFallback}>
          <Text style={styles.errorTitle}>Something went wrong</Text>
          <Text style={styles.errorMessage}>
            {this.state.error?.message || "This screen failed to render."}
          </Text>
        </View>
      );
    }
    return this.props.children;
  }
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
    borderColor: palette.blackA08,
    shadowColor: palette.black,
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
  },
  errorFallback: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    gap: 8
  },
  errorTitle: {
    color: palette.dark,
    fontSize: 17,
    fontWeight: "900"
  },
  errorMessage: {
    color: palette.muted,
    fontSize: 13,
    fontWeight: "600",
    textAlign: "center"
  }
});
