import React from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { ScreenScroll } from "../components/Shared";
import { palette } from "../theme/theme";

const sectionDefaults = {
  memory: false,
  rules: false,
  style: false,
  context: false,
  preferences: false,
  security: false
};

const sectorOptions = ["Tech", "Healthcare", "Finance", "Energy", "Consumer", "Indexes"];
const mistakeOptions = ["Oversizing", "Chasing", "Ignoring IV", "Short expiry", "No exit plan"];

export function ProfileScreen({ user, onSignOut, onUpdateUser, onDeleteAccount }) {
  const [openSections, setOpenSections] = React.useState(sectionDefaults);
  const [saveState, setSaveState] = React.useState("Synced");
  const userMemory = user?.aiMemory || {};
  const userRules = user?.riskRules || {};
  const userCoachStyle = user?.coachStyle || {};
  const userSavedContext = user?.savedContext || {};
  const userAppPreferences = user?.appPreferences || {};
  const [memory, setMemory] = React.useState({
    experienceLevel: userMemory.experienceLevel || user?.experienceLevel || "Learning",
    riskStyle: userMemory.riskStyle || user?.riskStyle || "Balanced",
    explanationStyle: userMemory.explanationStyle || "Plain English",
    sectors: Array.isArray(userMemory.sectors) ? userMemory.sectors : Array.isArray(user?.sectors) ? user.sectors : ["Tech", "Finance"],
    mistakes: Array.isArray(userMemory.mistakes) ? userMemory.mistakes : Array.isArray(user?.struggles) ? user.struggles : ["Oversizing", "Chasing"]
  });
  const [rules, setRules] = React.useState({
    maxRiskPerTrade: userRules.maxRiskPerTrade || user?.maxRiskPerTrade || "2%",
    maxTradesPerWeek: userRules.maxTradesPerWeek || user?.maxTradesPerWeek || "5",
    avoidEarnings: Boolean(userRules.avoidEarnings || user?.avoidEarningsTrades),
    warnShortExpiry: userRules.warnShortExpiry !== false,
    warnPremiumRisk: userRules.warnPremiumRisk !== false,
    premiumRiskLimit: userRules.premiumRiskLimit || "5%"
  });
  const [coachStyle, setCoachStyle] = React.useState({
    simple: userCoachStyle.simple !== false,
    quantHeavy: Boolean(userCoachStyle.quantHeavy),
    debateBothSides: userCoachStyle.debateBothSides !== false,
    askQuestionsFirst: Boolean(userCoachStyle.askQuestionsFirst),
    strictRisk: userCoachStyle.strictRisk !== false
  });
  const [savedContext, setSavedContext] = React.useState({
    savedChecks: userSavedContext.savedChecks !== false,
    chatHistory: userSavedContext.chatHistory !== false,
    uploadedScreenshots: userSavedContext.uploadedScreenshots !== false,
    watchlist: userSavedContext.watchlist !== false
  });
  const [appPreferences, setAppPreferences] = React.useState({
    defaultMode: userAppPreferences.defaultMode || "Review",
    defaultTab: userAppPreferences.defaultTab || "Coach",
    compactReports: userAppPreferences.compactReports !== false,
    weeklyDigest: Boolean(userAppPreferences.weeklyDigest),
    quietHours: userAppPreferences.quietHours || "After 9 PM"
  });
  const [deleteArmed, setDeleteArmed] = React.useState(false);
  const [deleteText, setDeleteText] = React.useState("");
  const [securityStatus, setSecurityStatus] = React.useState("");

  const initials = getInitials(user?.name);
  const firstName = (user?.name || "RiskWise User").split(" ")[0];

  function toggle(section) {
    setOpenSections((current) => ({ ...current, [section]: !current[section] }));
  }

  async function persist(updates) {
    if (!onUpdateUser) {
      return;
    }
    setSaveState("Saving");
    try {
      await onUpdateUser(updates);
      setSaveState("Saved");
    } catch (error) {
      setSaveState("Offline");
    }
  }

  function commitMemory(next) {
    setMemory(next);
    persist({
      experienceLevel: next.experienceLevel,
      riskStyle: next.riskStyle,
      sectors: next.sectors,
      struggles: next.mistakes,
      aiMemory: next
    });
  }

  function commitRules(next) {
    setRules(next);
    persist({ riskRules: next });
  }

  function commitCoachStyle(next) {
    setCoachStyle(next);
    persist({ coachStyle: next });
  }

  function commitSavedContext(next) {
    setSavedContext(next);
    persist({ savedContext: next });
  }

  function commitAppPreferences(next) {
    setAppPreferences(next);
    persist({ appPreferences: next });
  }

  function setMemoryValue(key, value) {
    commitMemory({ ...memory, [key]: value });
  }

  function setRuleValue(key, value) {
    commitRules({ ...rules, [key]: value });
  }

  function setCoachValue(key, value) {
    commitCoachStyle({ ...coachStyle, [key]: value });
  }

  function setContextValue(key, value) {
    commitSavedContext({ ...savedContext, [key]: value });
  }

  function setPreferenceValue(key, value) {
    commitAppPreferences({ ...appPreferences, [key]: value });
  }

  function toggleTag(key, value) {
    const currentValues = Array.isArray(memory[key]) ? memory[key] : [];
    const exists = currentValues.includes(value);
    commitMemory({
      ...memory,
      [key]: exists ? currentValues.filter((item) => item !== value) : [...currentValues, value]
    });
  }

  function clearContext() {
    commitSavedContext({
      savedChecks: false,
      chatHistory: false,
      uploadedScreenshots: false,
      watchlist: false
    });
  }

  async function confirmDeleteAccount() {
    if (!deleteArmed) {
      setDeleteArmed(true);
      setSecurityStatus("Type DELETE to remove RiskWise app data and sign out.");
      return;
    }
    if (deleteText.trim().toUpperCase() !== "DELETE") {
      setSecurityStatus("Type DELETE exactly to confirm.");
      return;
    }
    try {
      setSecurityStatus("Deleting account data...");
      await onDeleteAccount?.();
    } catch (error) {
      setSecurityStatus(error.message || "Could not delete account data right now.");
    }
  }

  return (
    <ScreenScroll>
      <View style={styles.profileTop}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>{initials}</Text>
        </View>
        <View style={styles.profileText}>
          <Text style={styles.profileTitle}>Settings</Text>
          <Text style={styles.profileSub} numberOfLines={1}>
            {user?.email || "RiskWise account"} - {firstName}
          </Text>
        </View>
        <View style={styles.statusPill}>
          <View style={styles.statusDot} />
          <Text style={styles.statusText}>{saveState}</Text>
        </View>
      </View>

      <View style={styles.summaryGrid}>
        <SummaryTile label="Risk cap" value={rules.maxRiskPerTrade} icon="shield-checkmark-outline" />
        <SummaryTile label="Coach" value={appPreferences.defaultMode} icon="chatbubble-ellipses-outline" />
        <SummaryTile label="Context" value={`${Object.values(savedContext).filter(Boolean).length}/4`} icon="folder-open-outline" />
      </View>

      <SettingsSection
        icon="sparkles-outline"
        title="AI Memory"
        subtitle={`${memory.experienceLevel} - ${memory.riskStyle} - ${summarize(memory.sectors, "No sectors")}`}
        open={openSections.memory}
        onPress={() => toggle("memory")}
      >
        <ChoiceGroup
          label="Experience level"
          value={memory.experienceLevel}
          options={["Learning", "Some experience", "Advanced"]}
          onChange={(value) => setMemoryValue("experienceLevel", value)}
        />
        <ChoiceGroup
          label="Risk style"
          value={memory.riskStyle}
          options={["Conservative", "Balanced", "Aggressive"]}
          onChange={(value) => setMemoryValue("riskStyle", value)}
        />
        <ChoiceGroup
          label="Preferred explanation"
          value={memory.explanationStyle}
          options={["Plain English", "Step-by-step", "Quant"]}
          onChange={(value) => setMemoryValue("explanationStyle", value)}
        />
        <MultiSelect label="Sectors RiskWise should care about" values={memory.sectors} options={sectorOptions} onToggle={(value) => toggleTag("sectors", value)} />
        <MultiSelect label="Common mistakes to watch for" values={memory.mistakes} options={mistakeOptions} onToggle={(value) => toggleTag("mistakes", value)} />
      </SettingsSection>

      <SettingsSection
        icon="shield-checkmark-outline"
        title="Risk Rules"
        subtitle={`${rules.maxRiskPerTrade} max risk - ${rules.maxTradesPerWeek} trades/week`}
        open={openSections.rules}
        onPress={() => toggle("rules")}
      >
        <ChoiceGroup label="Max risk per trade" value={rules.maxRiskPerTrade} options={["1%", "2%", "3%", "5%"]} onChange={(value) => setRuleValue("maxRiskPerTrade", value)} />
        <ChoiceGroup label="Max trades per week" value={rules.maxTradesPerWeek} options={["2", "5", "10", "No limit"]} onChange={(value) => setRuleValue("maxTradesPerWeek", value)} />
        <ToggleRow label="Avoid earnings trades" value={rules.avoidEarnings} onChange={(value) => setRuleValue("avoidEarnings", value)} />
        <ToggleRow label="Warn if expiration is under 7 days" value={rules.warnShortExpiry} onChange={(value) => setRuleValue("warnShortExpiry", value)} />
        <ToggleRow label="Warn if premium risk is above X%" value={rules.warnPremiumRisk} onChange={(value) => setRuleValue("warnPremiumRisk", value)} />
        <ChoiceGroup label="Premium risk warning level" value={rules.premiumRiskLimit} options={["2%", "5%", "10%"]} onChange={(value) => setRuleValue("premiumRiskLimit", value)} />
      </SettingsSection>

      <SettingsSection
        icon="chatbubbles-outline"
        title="Coach Style"
        subtitle={summarizeCoachStyle(coachStyle)}
        open={openSections.style}
        onPress={() => toggle("style")}
      >
        <ToggleRow label="Simple explanations" value={coachStyle.simple} onChange={(value) => setCoachValue("simple", value)} />
        <ToggleRow label="Quant-heavy" value={coachStyle.quantHeavy} onChange={(value) => setCoachValue("quantHeavy", value)} />
        <ToggleRow label="Debate both sides" value={coachStyle.debateBothSides} onChange={(value) => setCoachValue("debateBothSides", value)} />
        <ToggleRow label="Ask me questions first" value={coachStyle.askQuestionsFirst} onChange={(value) => setCoachValue("askQuestionsFirst", value)} />
        <ToggleRow label="Be strict about risk" value={coachStyle.strictRisk} onChange={(value) => setCoachValue("strictRisk", value)} />
      </SettingsSection>

      <SettingsSection
        icon="folder-open-outline"
        title="Saved Context"
        subtitle={summarizeEnabled(savedContext)}
        open={openSections.context}
        onPress={() => toggle("context")}
      >
        <ToggleRow label="Saved checks" value={savedContext.savedChecks} onChange={(value) => setContextValue("savedChecks", value)} />
        <ToggleRow label="Chat history" value={savedContext.chatHistory} onChange={(value) => setContextValue("chatHistory", value)} />
        <ToggleRow label="Uploaded screenshots" value={savedContext.uploadedScreenshots} onChange={(value) => setContextValue("uploadedScreenshots", value)} />
        <ToggleRow label="Watchlist" value={savedContext.watchlist} onChange={(value) => setContextValue("watchlist", value)} />
        <Pressable style={styles.outlineDanger} onPress={clearContext}>
          <Text style={styles.outlineDangerText}>Clear all context</Text>
        </Pressable>
      </SettingsSection>

      <SettingsSection
        icon="options-outline"
        title="App Preferences"
        subtitle={`${appPreferences.defaultMode} mode - ${appPreferences.defaultTab} first`}
        open={openSections.preferences}
        onPress={() => toggle("preferences")}
      >
        <ChoiceGroup label="Default AI mode" value={appPreferences.defaultMode} options={["Explain", "Review", "Compare"]} onChange={(value) => setPreferenceValue("defaultMode", value)} />
        <ChoiceGroup label="Open app to" value={appPreferences.defaultTab} options={["Home", "Check", "Coach", "Profile"]} onChange={(value) => setPreferenceValue("defaultTab", value)} />
        <ToggleRow label="Use compact report cards" value={appPreferences.compactReports} onChange={(value) => setPreferenceValue("compactReports", value)} />
        <ToggleRow label="Weekly learning digest" value={appPreferences.weeklyDigest} onChange={(value) => setPreferenceValue("weeklyDigest", value)} />
        <ChoiceGroup label="Quiet hours" value={appPreferences.quietHours} options={["After 8 PM", "After 9 PM", "After 10 PM", "Never"]} onChange={(value) => setPreferenceValue("quietHours", value)} />
      </SettingsSection>

      <SettingsSection
        icon="lock-closed-outline"
        title="Security"
        subtitle="Email, password reset, sign out, delete account"
        open={openSections.security}
        onPress={() => toggle("security")}
      >
        <InfoRow label="Email" value={user?.email || "Not connected"} />
        <InfoRow label="Password reset" value="Use Forgot password on sign-in" />
        <Pressable style={styles.signOutButton} onPress={onSignOut}>
          <Ionicons name="log-out-outline" size={17} color={palette.red} />
          <Text style={styles.signOutText}>Sign out</Text>
        </Pressable>
        {deleteArmed ? (
          <View style={styles.deleteConfirmBox}>
            <Text style={styles.deleteConfirmTitle}>Delete RiskWise account data?</Text>
            <Text style={styles.securityNote}>
              This removes your saved checks, chat history, profile preferences, and app data from the RiskWise database.
              Clerk sign-in deletion is attempted if your account policy allows it.
            </Text>
            <TextInput
              value={deleteText}
              onChangeText={setDeleteText}
              placeholder="Type DELETE"
              placeholderTextColor="#A8AFA9"
              autoCapitalize="characters"
              style={styles.deleteInput}
            />
          </View>
        ) : null}
        <Pressable style={styles.dangerButton} onPress={confirmDeleteAccount}>
          <Ionicons name="trash-outline" size={17} color={palette.red} />
          <Text style={styles.dangerButtonText}>{deleteArmed ? "Confirm delete" : "Delete account data"}</Text>
        </Pressable>
        {securityStatus ? <Text style={styles.securityNote}>{securityStatus}</Text> : null}
      </SettingsSection>
    </ScreenScroll>
  );
}

function SummaryTile({ label, value, icon }) {
  return (
    <View style={styles.summaryTile}>
      <Ionicons name={icon} size={15} color={palette.green} />
      <Text style={styles.summaryLabel}>{label}</Text>
      <Text style={styles.summaryValue} numberOfLines={1}>{value}</Text>
    </View>
  );
}

function SettingsSection({ icon, title, subtitle, open, onPress, children }) {
  return (
    <View style={[styles.sectionShell, open && styles.sectionShellOpen]}>
      <Pressable style={styles.sectionHeader} onPress={onPress}>
        <View style={styles.sectionIcon}>
          <Ionicons name={icon} size={17} color={palette.green} />
        </View>
        <View style={styles.sectionCopy}>
          <Text style={styles.sectionTitle}>{title}</Text>
          <Text style={styles.sectionSubtitle} numberOfLines={1}>
            {subtitle}
          </Text>
        </View>
        <Ionicons name={open ? "chevron-up" : "chevron-down"} size={18} color={palette.muted} />
      </Pressable>
      {open ? <View style={styles.sectionBody}>{children}</View> : null}
    </View>
  );
}

function ChoiceGroup({ label, value, options, onChange }) {
  return (
    <View style={styles.controlBlock}>
      <Text style={styles.controlLabel}>{label}</Text>
      <View style={styles.choiceWrap}>
        {options.map((option) => {
          const active = option === value;
          return (
            <Pressable key={option} style={[styles.choiceChip, active && styles.choiceChipActive]} onPress={() => onChange(option)}>
              <Text style={[styles.choiceText, active && styles.choiceTextActive]}>{option}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function MultiSelect({ label, values, options, onToggle }) {
  const selected = Array.isArray(values) ? values : [];
  return (
    <View style={styles.controlBlock}>
      <Text style={styles.controlLabel}>{label}</Text>
      <View style={styles.choiceWrap}>
        {options.map((option) => {
          const active = selected.includes(option);
          return (
            <Pressable key={option} style={[styles.choiceChip, active && styles.choiceChipActive]} onPress={() => onToggle(option)}>
              <Text style={[styles.choiceText, active && styles.choiceTextActive]}>{option}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function ToggleRow({ label, value, onChange }) {
  return (
    <Pressable style={styles.toggleRow} onPress={() => onChange(!value)}>
      <Text style={styles.toggleLabel}>{label}</Text>
      <View style={[styles.switchTrack, value && styles.switchTrackActive]}>
        <View style={[styles.switchThumb, value && styles.switchThumbActive]} />
      </View>
    </Pressable>
  );
}

function InfoRow({ label, value }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue} numberOfLines={2}>
        {value}
      </Text>
    </View>
  );
}

function summarize(values, fallback) {
  if (Array.isArray(values) && values.length > 0) {
    return values[0] + (values.length > 1 ? ` +${values.length - 1}` : "");
  }
  return fallback;
}

function summarizeCoachStyle(style) {
  const labels = [];
  if (style.simple) {
    labels.push("Simple");
  }
  if (style.quantHeavy) {
    labels.push("Quant");
  }
  if (style.debateBothSides) {
    labels.push("Debate");
  }
  if (style.strictRisk) {
    labels.push("Strict risk");
  }
  return labels.slice(0, 3).join(" - ") || "Default";
}

function summarizeEnabled(values) {
  const count = Object.values(values).filter(Boolean).length;
  if (count === 0) {
    return "No saved context enabled";
  }
  return `${count} context sources enabled`;
}

function getInitials(name) {
  if (!name) {
    return "RW";
  }
  return name
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

const styles = StyleSheet.create({
  profileTop: {
    minHeight: 62,
    borderRadius: 20,
    backgroundColor: "#FBFFFC",
    borderWidth: 1,
    borderColor: "#D7F0DF",
    paddingHorizontal: 11,
    marginTop: 10,
    marginBottom: 7,
    flexDirection: "row",
    alignItems: "center",
    gap: 10
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: palette.greenSoft,
    borderWidth: 1,
    borderColor: "#CFEFD8",
    alignItems: "center",
    justifyContent: "center"
  },
  avatarText: {
    color: palette.green,
    fontSize: 13,
    fontWeight: "900"
  },
  profileText: {
    flex: 1
  },
  profileTitle: {
    color: palette.dark,
    fontSize: 17,
    fontWeight: "900"
  },
  profileSub: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "700",
    marginTop: 2
  },
  statusPill: {
    height: 27,
    borderRadius: 999,
    paddingHorizontal: 8,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "#F2FBF5",
    borderWidth: 1,
    borderColor: "#CFEFD8"
  },
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: palette.green
  },
  statusText: {
    color: palette.green,
    fontSize: 9,
    fontWeight: "900"
  },
  summaryGrid: {
    flexDirection: "row",
    gap: 7,
    marginBottom: 8
  },
  summaryTile: {
    flex: 1,
    minHeight: 57,
    borderRadius: 17,
    borderWidth: 1,
    borderColor: "#DDF1E2",
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 9,
    paddingVertical: 8,
    justifyContent: "space-between"
  },
  summaryLabel: {
    color: palette.muted,
    fontSize: 9,
    fontWeight: "900"
  },
  summaryValue: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  sectionShell: {
    borderRadius: 18,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FFFFFF",
    marginBottom: 7,
    overflow: "hidden"
  },
  sectionShellOpen: {
    borderColor: "#D3EEDB"
  },
  sectionHeader: {
    minHeight: 53,
    paddingHorizontal: 11,
    paddingVertical: 7,
    flexDirection: "row",
    alignItems: "center",
    gap: 10
  },
  sectionIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: palette.greenSoft,
    alignItems: "center",
    justifyContent: "center"
  },
  sectionCopy: {
    flex: 1
  },
  sectionTitle: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900"
  },
  sectionSubtitle: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "700",
    marginTop: 2
  },
  sectionBody: {
    borderTopWidth: 1,
    borderTopColor: palette.border,
    paddingHorizontal: 11,
    paddingVertical: 11
  },
  controlBlock: {
    marginBottom: 12
  },
  controlLabel: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "900",
    marginBottom: 8
  },
  choiceWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 7
  },
  choiceChip: {
    minHeight: 31,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 11,
    alignItems: "center",
    justifyContent: "center"
  },
  choiceChipActive: {
    backgroundColor: palette.green,
    borderColor: palette.green
  },
  choiceText: {
    color: palette.dark,
    fontSize: 11,
    fontWeight: "900"
  },
  choiceTextActive: {
    color: "#FFFFFF"
  },
  toggleRow: {
    minHeight: 43,
    borderBottomWidth: 1,
    borderBottomColor: "#F0F3F0",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 14
  },
  toggleLabel: {
    flex: 1,
    color: palette.dark,
    fontSize: 12,
    fontWeight: "800"
  },
  switchTrack: {
    width: 43,
    height: 25,
    borderRadius: 999,
    backgroundColor: "#E8EEE9",
    padding: 3,
    justifyContent: "center"
  },
  switchTrackActive: {
    backgroundColor: palette.green
  },
  switchThumb: {
    width: 19,
    height: 19,
    borderRadius: 11,
    backgroundColor: "#FFFFFF",
    shadowColor: "#000000",
    shadowOpacity: 0.08,
    shadowRadius: 5
  },
  switchThumbActive: {
    transform: [{ translateX: 18 }]
  },
  infoRow: {
    minHeight: 45,
    borderBottomWidth: 1,
    borderBottomColor: "#F0F3F0",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 14
  },
  infoLabel: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "900"
  },
  infoValue: {
    flex: 1,
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900",
    textAlign: "right"
  },
  signOutButton: {
    minHeight: 43,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#F5D1D1",
    backgroundColor: "#FFFBFB",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    marginTop: 12
  },
  signOutText: {
    color: palette.red,
    fontSize: 12,
    fontWeight: "900"
  },
  dangerButton: {
    minHeight: 43,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#F5D1D1",
    backgroundColor: "#FFFFFF",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    marginTop: 8
  },
  dangerButtonText: {
    color: palette.red,
    fontSize: 12,
    fontWeight: "900"
  },
  outlineDanger: {
    minHeight: 42,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#F5D1D1",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 12,
    backgroundColor: "#FFFFFF"
  },
  outlineDangerText: {
    color: palette.red,
    fontSize: 12,
    fontWeight: "900"
  },
  deleteConfirmBox: {
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#F5D1D1",
    backgroundColor: "#FFFBFB",
    padding: 12,
    marginTop: 12
  },
  deleteConfirmTitle: {
    color: palette.red,
    fontSize: 13,
    fontWeight: "900",
    marginBottom: 4
  },
  deleteInput: {
    minHeight: 38,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#F5D1D1",
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 10,
    marginTop: 10,
    marginBottom: 2,
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900",
    outlineStyle: "none"
  },
  securityNote: {
    color: palette.muted,
    fontSize: 11,
    lineHeight: 16,
    fontWeight: "700",
    marginTop: 8
  }
});
