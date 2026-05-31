import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { palette } from "../theme/theme";

export const tabs = [
  ["Home", "home"],
  ["Check", "location-outline"],
  ["Coach", "chatbubble-ellipses-outline"],
  ["Profile", "person-outline"]
];

export function BottomTabs({ activeTab, setActiveTab, disabledTabs = [] }) {
  return (
    <View style={styles.tabBar}>
      {tabs.map(([name, icon]) => {
        const homeSubPages = [];
        const isActive = activeTab === name || (name === "Check" && activeTab === "Report") || (name === "Home" && homeSubPages.includes(activeTab));
        return (
        <Pressable
          key={name}
          style={[styles.tabItem, disabledTabs.includes(name) && styles.disabled]}
          onPress={() => !disabledTabs.includes(name) && setActiveTab(name)}
        >
          <View style={[styles.iconWrap, isActive && styles.iconActive]}>
            <Ionicons
              name={icon}
              size={22}
              color={isActive ? palette.green : "#A3AEA6"}
            />
          </View>
          <Text style={[styles.tabLabel, isActive && styles.active]}>{name}</Text>
        </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    height: 74,
    marginHorizontal: 12,
    marginBottom: 12,
    paddingHorizontal: 12,
    paddingTop: 8,
    paddingBottom: 8,
    flexDirection: "row",
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#EAF0EA",
    borderRadius: 34,
    shadowColor: "#16351D",
    shadowOpacity: 0.12,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 10 }
  },
  tabItem: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    minWidth: 0
  },
  iconWrap: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: "center",
    justifyContent: "center"
  },
  iconActive: {
    backgroundColor: "#F0FAF2"
  },
  tabLabel: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 3
  },
  active: {
    color: palette.green
  },
  disabled: {
    opacity: 0.35
  }
});
