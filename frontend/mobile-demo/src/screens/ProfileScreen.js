import React from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Card } from "../components/Card";
import { ScreenScroll } from "../components/Shared";
import { palette } from "../theme/theme";

const defaultProfile = {
  decisionQuality: {
    overall: 84,
    signalDiscipline: 81,
    positionSizing: 90,
    volatilityAwareness: 74,
    patience: 86
  },
  learnedInsights: {
    commonMistakes: [
      "Entering before confirmation",
      "Position sizing too large",
      "Chasing momentum",
      "Trading very short expirations",
      "No clear exit plan"
    ],
    strongHabits: [
      "Uses defined risk consistently",
      "Reviews before entering trades",
      "Considers volatility context",
      "Plans exits in advance"
    ]
  },
  analysisSources: {
    savedChecks: { enabled: true, count: 46 },
    chatHistory: { enabled: true, count: 128 },
    uploadedScreenshots: { enabled: true, count: 12 },
    watchlist: { enabled: true, count: 24 }
  }
};

export function ProfileScreen({ user, onSignOut, onUpdateUser, onDeleteAccount }) {
  const [notice, setNotice] = React.useState("");
  const [confirmAction, setConfirmAction] = React.useState(null);
  const [saving, setSaving] = React.useState("");
  const [appPreferences, setAppPreferences] = React.useState(() => ({
    defaultMode: user?.appPreferences?.defaultMode || "Review",
    openAppTo: user?.appPreferences?.defaultTab || user?.appPreferences?.openAppTo || "Coach",
    compactReports: user?.appPreferences?.compactReports !== false,
    weeklyDigest: user?.appPreferences?.weeklyDigest !== false,
    quietHours: user?.appPreferences?.quietHours || "After 9 PM"
  }));
  const [riskRules] = React.useState(() => ({
    maxRiskPerTradePercent: numberFromPercent(user?.riskRules?.maxRiskPerTrade || user?.riskRules?.maxRiskPerTradePercent || user?.maxRiskPerTrade || 2),
    maxTradesPerWeek: user?.riskRules?.maxTradesPerWeek || user?.maxTradesPerWeek || 5,
    avoidEarningsTrades: user?.riskRules?.avoidEarnings ?? user?.avoidEarningsTrades ?? true,
    warnShortExpiration: user?.riskRules?.warnShortExpiry ?? true,
    shortExpirationDays: 7,
    premiumRiskWarningLevelPercent: numberFromPercent(user?.riskRules?.premiumRiskLimit || 5),
    lastUpdated: "May 24, 2026"
  }));
  const [memory] = React.useState(() => ({
    experience: user?.aiMemory?.experienceLevel || user?.experienceLevel || "Some experience",
    riskStyle: user?.aiMemory?.riskStyle || user?.riskStyle || "Balanced",
    preferredExplanation: user?.aiMemory?.explanationStyle || "Step-by-step",
    sectorsToFocus: normalizeList(user?.aiMemory?.sectors || user?.sectors, ["Technology", "Healthcare", "Finance", "Energy"]),
    commonMistakes: normalizeList(user?.aiMemory?.mistakes || user?.struggles, ["Oversizing", "Chasing", "Ignoring IV", "Short expiry", "No exit plan"])
  }));
  const [coachPreferences] = React.useState(() => ({
    defaultAIMode: appPreferences.defaultMode,
    explanationStyle: memory.preferredExplanation,
    coachingApproach: user?.coachStyle?.debateBothSides === false ? "Direct answer first" : "Debate both sides",
    questionStyle: user?.coachStyle?.askQuestionsFirst ? "Ask me questions first" : "Ask me questions first",
    riskStrictness: user?.coachStyle?.strictRisk === false ? "Balanced risk tone" : "Strict about risk"
  }));
  const [analysisSources, setAnalysisSources] = React.useState(defaultProfile.analysisSources);

  const initials = getInitials(user?.name);
  const firstName = firstNameOf(user?.name);
  const email = user?.email || "aarav.nagar22@gmail.com";
  const identity = `${memory.riskStyle} Trader`;
  const synced = saving || "Synced";

  async function persistAppPreferences(next) {
    setAppPreferences(next);
    setSaving("Saving");
    try {
      await onUpdateUser?.({ appPreferences: { ...next, defaultTab: next.openAppTo } });
      setSaving("Saved");
    } catch {
      setSaving("Offline");
    }
  }

  async function clearAllContext() {
    const next = {
      savedChecks: { enabled: false, count: 0 },
      chatHistory: { enabled: false, count: 0 },
      uploadedScreenshots: { enabled: false, count: 0 },
      watchlist: { enabled: false, count: 0 }
    };
    setAnalysisSources(next);
    setConfirmAction(null);
    setNotice("Context cleared for this session.");
    try {
      await onUpdateUser?.({
        savedContext: {
          savedChecks: false,
          chatHistory: false,
          uploadedScreenshots: false,
          watchlist: false
        }
      });
    } catch {
      setNotice("Context cleared locally. Cloud sync is unavailable right now.");
    }
  }

  async function confirmSignOut() {
    setConfirmAction(null);
    await onSignOut?.();
  }

  async function confirmDelete() {
    setConfirmAction(null);
    setNotice("Deleting account data...");
    try {
      await onDeleteAccount?.();
    } catch (error) {
      setNotice(error.message || "Could not delete account data right now.");
    }
  }

  return (
    <ScreenScroll>
      <ProfileTopBar />
      <ProfileHeaderCard
        initials={initials}
        name={firstName}
        identity={identity}
        experience={memory.experience}
        synced={synced}
        riskRule={`${riskRules.maxRiskPerTradePercent}% max`}
        tradesPerWeek={`${riskRules.maxTradesPerWeek} max`}
        aiMode={appPreferences.defaultMode}
      />
      <SectionCard title="Trader DNA" action="Edit" onAction={() => setNotice("Editing coming soon.")}>
        <SettingsRow icon="person-outline" label="Experience Level" value={memory.experience} />
        <SettingsRow icon="shield-checkmark-outline" label="Risk Style" value={memory.riskStyle} />
        <SettingsRow icon="list-outline" label="Preferred Explanations" value={memory.preferredExplanation} />
        <SettingsRow icon="analytics-outline" label="Favorite Markets" value="Technology, Indexes" />
        <SettingsRow icon="warning-outline" label="Common Mistakes to Watch" value={memory.commonMistakes.slice(0, 3).join(", ")} last />
      </SectionCard>
      <SectionCard title="What RiskWise Has Learned" action="View all" onAction={() => setNotice("Detailed learning history coming soon.")}>
        <LearnedInsightCard
          tone="risk"
          title="Common Mistakes"
          items={defaultProfile.learnedInsights.commonMistakes}
        />
        <LearnedInsightCard
          tone="good"
          title="Strong Habits"
          items={defaultProfile.learnedInsights.strongHabits}
        />
      </SectionCard>
      <SectionCard title="Decision Quality Breakdown" action="View history" onAction={() => setNotice("Decision quality history coming soon.")}>
        <ScoreBar label="Signal Discipline" value={defaultProfile.decisionQuality.signalDiscipline} />
        <ScoreBar label="Position Sizing" value={defaultProfile.decisionQuality.positionSizing} />
        <ScoreBar label="Volatility Awareness" value={defaultProfile.decisionQuality.volatilityAwareness} />
        <ScoreBar label="Patience" value={defaultProfile.decisionQuality.patience} />
        <ScoreBar label="Overall" value={defaultProfile.decisionQuality.overall} />
      </SectionCard>
      <SectionCard title="Risk Rules" action="Edit" onAction={() => setNotice("Risk rule editing coming soon.")}>
        <SettingsRow icon="water-outline" label="Max risk per trade" value={`${riskRules.maxRiskPerTradePercent}% of account`} />
        <SettingsRow icon="repeat-outline" label="Max trades per week" value={`${riskRules.maxTradesPerWeek} trades`} />
        <SettingsRow icon="close-circle-outline" label="Avoid earnings trades" value={riskRules.avoidEarningsTrades ? "Enabled" : "Disabled"} />
        <SettingsRow icon="time-outline" label="Warn if expiration < 7 days" value={riskRules.warnShortExpiration ? "Enabled" : "Disabled"} />
        <SettingsRow icon="alert-circle-outline" label="Premium risk warning level" value={`${riskRules.premiumRiskWarningLevelPercent}%`} last />
        <InfoBox title="These rules are used in every analysis" text={`Last updated: ${riskRules.lastUpdated}`} />
      </SectionCard>
      <SectionCard title="Analysis Sources" action="Manage" onAction={() => setNotice("Source management coming soon.")}>
        <SourceRow label="Saved Checks" value={`${analysisSources.savedChecks.count} saved analyses`} enabled={analysisSources.savedChecks.enabled} />
        <SourceRow label="Chat History" value={`${analysisSources.chatHistory.count} conversations`} enabled={analysisSources.chatHistory.enabled} />
        <SourceRow label="Uploaded Screenshots" value={`${analysisSources.uploadedScreenshots.count} images`} enabled={analysisSources.uploadedScreenshots.enabled} />
        <SourceRow label="Watchlist" value={`${analysisSources.watchlist.count} symbols tracked`} enabled={analysisSources.watchlist.enabled} last />
        <Pressable style={styles.clearButton} onPress={() => setConfirmAction("clear")}>
          <Text style={styles.clearButtonText}>Clear all context</Text>
        </Pressable>
      </SectionCard>
      <SectionCard title="Coach Style & Preferences" action="Edit" onAction={() => setNotice("Coach style editing coming soon.")}>
        <SettingsRow icon="chatbubble-ellipses-outline" label="Default AI Mode" value={coachPreferences.defaultAIMode} />
        <SettingsRow icon="reader-outline" label="Explanation Style" value={coachPreferences.explanationStyle} />
        <SettingsRow icon="git-compare-outline" label="Coaching Approach" value={coachPreferences.coachingApproach} />
        <SettingsRow icon="help-buoy-outline" label="Question Style" value={coachPreferences.questionStyle} />
        <SettingsRow icon="shield-outline" label="Risk Strictness" value={coachPreferences.riskStrictness} last />
      </SectionCard>
      <SectionCard title="App Preferences" action="Edit" onAction={() => setNotice("App preference editing coming soon.")}>
        <SettingsRow icon="sparkles-outline" label="Default AI Mode" value={appPreferences.defaultMode} />
        <SettingsRow icon="open-outline" label="Open App To" value={appPreferences.openAppTo} />
        <ToggleRow
          icon="albums-outline"
          label="Use compact report cards"
          value={appPreferences.compactReports}
          onChange={(value) => persistAppPreferences({ ...appPreferences, compactReports: value })}
        />
        <ToggleRow
          icon="notifications-outline"
          label="Weekly learning digest"
          value={appPreferences.weeklyDigest}
          onChange={(value) => persistAppPreferences({ ...appPreferences, weeklyDigest: value })}
        />
        <SettingsRow icon="moon-outline" label="Quiet hours" value={appPreferences.quietHours} last />
      </SectionCard>
      <SectionCard title="AI Memory" action="Edit" onAction={() => setNotice("AI memory editing coming soon.")}>
        <InfoBox title="RiskWise uses your memory to personalize analysis and coaching." />
        <SettingsRow icon="person-outline" label="Experience" value={memory.experience} />
        <SettingsRow icon="shield-checkmark-outline" label="Risk Style" value={memory.riskStyle} />
        <SettingsRow icon="bulb-outline" label="Preferred Explanation" value={memory.preferredExplanation} />
        <SettingsRow icon="pie-chart-outline" label="Sectors to Focus" value={memory.sectorsToFocus.join(", ")} />
        <SettingsRow icon="warning-outline" label="Common Mistakes" value={memory.commonMistakes.join(", ")} last />
      </SectionCard>
      <SectionCard title="Account & Security" action="Edit" onAction={() => setNotice("Account editing coming soon.")}>
        <SettingsRow icon="mail-outline" label="Email" value={email} />
        <SettingsRow icon="key-outline" label="Password" value="********" />
        <SettingsRow icon="refresh-outline" label="Password Reset" value="Use forgot password on sign-in" />
        <ActionRow icon="log-out-outline" label="Sign Out" onPress={() => setConfirmAction("signOut")} />
        <ActionRow icon="trash-outline" label="Delete Account Data" danger onPress={() => setConfirmAction("delete")} last />
      </SectionCard>
      <Card style={styles.footerNote}>
        <Text style={styles.footerText}>RiskWise is here to help you make better decisions.</Text>
      </Card>
      {notice ? <NoticeModal message={notice} onClose={() => setNotice("")} /> : null}
      {confirmAction ? (
        <ConfirmModal
          action={confirmAction}
          onCancel={() => setConfirmAction(null)}
          onConfirm={confirmAction === "clear" ? clearAllContext : confirmAction === "delete" ? confirmDelete : confirmSignOut}
        />
      ) : null}
    </ScreenScroll>
  );
}

function ProfileTopBar() {
  return (
    <View style={styles.topBar}>
      <Text style={styles.pageTitle}>Profile</Text>
      <View style={styles.topActions}>
        <Ionicons name="notifications-outline" size={19} color={palette.dark} />
        <Ionicons name="settings-outline" size={20} color={palette.dark} />
      </View>
    </View>
  );
}

function ProfileHeaderCard({ initials, name, identity, experience, synced, riskRule, tradesPerWeek, aiMode }) {
  return (
    <Card style={styles.heroCard}>
      <View style={styles.heroTop}>
        <View style={styles.avatarWrap}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initials}</Text>
          </View>
        </View>
        <View style={styles.heroText}>
          <Text style={styles.userName}>{name}</Text>
          <Text style={styles.identityText}>{identity}</Text>
          <Text style={styles.experienceText}>{experience}</Text>
        </View>
        <View style={styles.syncPill}>
          <View style={styles.syncDot} />
          <Text style={styles.syncText}>{synced}</Text>
        </View>
      </View>
      <View style={styles.heroDivider} />
      <View style={styles.miniStats}>
        <ProfileMiniStat icon="pulse-outline" label="Decision Quality" value="84" suffix="/100" visual="spark" />
        <ProfileMiniStat icon="shield-checkmark-outline" label="Risk Rule" value={riskRule} />
        <ProfileMiniStat icon="calendar-outline" label="Trades / Week" value={tradesPerWeek} />
        <ProfileMiniStat icon="sparkles-outline" label="AI Mode" value={aiMode} />
      </View>
    </Card>
  );
}

function ProfileMiniStat({ icon, label, value, suffix, visual }) {
  return (
    <View style={styles.miniStat}>
      <Ionicons name={icon} size={16} color={palette.dark} />
      <Text style={styles.miniLabel}>{label}</Text>
      <Text style={styles.miniValue}>
        {value}
        {suffix ? <Text style={styles.miniSuffix}>{suffix}</Text> : null}
      </Text>
      {visual ? <View style={styles.sparkLine}><View style={styles.sparkLineFill} /></View> : null}
    </View>
  );
}

function SectionCard({ title, action, onAction, children }) {
  return (
    <Card style={styles.sectionCard}>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>{title}</Text>
        {action ? (
          <Pressable onPress={onAction}>
            <Text style={styles.sectionAction}>{action}</Text>
          </Pressable>
        ) : null}
      </View>
      {children}
    </Card>
  );
}

function SettingsRow({ icon, label, value, last }) {
  return (
    <View style={[styles.settingsRow, last && styles.noBorder]}>
      <View style={styles.rowIcon}>
        <Ionicons name={icon} size={17} color={palette.dark} />
      </View>
      <View style={styles.rowCopy}>
        <Text style={styles.rowLabel}>{label}</Text>
        <Text style={styles.rowValue} numberOfLines={2}>{value}</Text>
      </View>
    </View>
  );
}

function SourceRow({ label, value, enabled, last }) {
  return (
    <View style={[styles.settingsRow, last && styles.noBorder]}>
      <View style={[styles.sourceIcon, !enabled && styles.sourceIconOff]}>
        <Ionicons name={enabled ? "checkmark" : "close"} size={14} color={enabled ? palette.green : palette.muted} />
      </View>
      <View style={styles.rowCopy}>
        <Text style={styles.rowLabel}>{label}</Text>
        <Text style={styles.rowValue}>{value}</Text>
      </View>
    </View>
  );
}

function ToggleRow({ icon, label, value, onChange }) {
  return (
    <Pressable style={styles.settingsRow} onPress={() => onChange(!value)}>
      <View style={styles.rowIcon}>
        <Ionicons name={icon} size={17} color={palette.dark} />
      </View>
      <Text style={[styles.rowLabel, styles.toggleLabel]}>{label}</Text>
      <View style={[styles.toggleTrack, value && styles.toggleTrackOn]}>
        <View style={[styles.toggleThumb, value && styles.toggleThumbOn]} />
      </View>
    </Pressable>
  );
}

function ActionRow({ icon, label, onPress, danger, last }) {
  return (
    <Pressable style={[styles.settingsRow, last && styles.noBorder]} onPress={onPress}>
      <View style={styles.rowIcon}>
        <Ionicons name={icon} size={17} color={danger ? palette.red : palette.dark} />
      </View>
      <Text style={[styles.rowLabel, danger && styles.dangerText]}>{label}</Text>
    </Pressable>
  );
}

function LearnedInsightCard({ title, items, tone }) {
  const risk = tone === "risk";
  return (
    <View style={styles.learnedCard}>
      <View style={styles.learnedTitleRow}>
        <View style={[styles.learnedIcon, risk ? styles.learnedIconRisk : styles.learnedIconGood]}>
          <Ionicons name={risk ? "alert-outline" : "accessibility-outline"} size={15} color={risk ? palette.red : palette.green} />
        </View>
        <Text style={styles.learnedTitle}>{title}</Text>
      </View>
      {items.map((item) => (
        <Text key={item} style={styles.bulletText}>{risk ? "-" : "✓"} {item}</Text>
      ))}
    </View>
  );
}

function ScoreBar({ label, value }) {
  const tone = value >= 80 ? "good" : value >= 60 ? "warn" : "risk";
  return (
    <View style={styles.scoreRow}>
      <Text style={styles.scoreLabel}>{label}</Text>
      <View style={styles.scoreTrack}>
        <View style={[styles.scoreFill, { width: `${value}%`, backgroundColor: toneColor(tone) }]} />
      </View>
      <Text style={styles.scoreValue}>{value}/100</Text>
    </View>
  );
}

function InfoBox({ title, text }) {
  return (
    <View style={styles.infoBox}>
      <Text style={styles.infoTitle}>{title}</Text>
      {text ? <Text style={styles.infoText}>{text}</Text> : null}
    </View>
  );
}

function NoticeModal({ message, onClose }) {
  return (
    <Modal transparent animationType="fade" visible>
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>RiskWise</Text>
          <Text style={styles.modalText}>{message}</Text>
          <Pressable style={styles.modalButton} onPress={onClose}>
            <Text style={styles.modalButtonText}>OK</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

function ConfirmModal({ action, onCancel, onConfirm }) {
  const copy = {
    clear: ["Clear all context?", "Saved checks, chat history, screenshots, and watchlist context will be disabled for analysis."],
    signOut: ["Sign out?", "Your saved profile and checks stay in your RiskWise account."],
    delete: ["Delete account data?", "This removes RiskWise app data tied to this profile. This cannot be undone."]
  }[action];
  return (
    <Modal transparent animationType="fade" visible>
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>{copy[0]}</Text>
          <Text style={styles.modalText}>{copy[1]}</Text>
          <View style={styles.modalActions}>
            <Pressable style={styles.cancelButton} onPress={onCancel}>
              <Text style={styles.cancelText}>Cancel</Text>
            </Pressable>
            <Pressable style={[styles.confirmButton, action === "delete" && styles.confirmDanger]} onPress={onConfirm}>
              <Text style={styles.confirmText}>Confirm</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

function firstNameOf(name) {
  return (name || "Aarav").split(" ")[0];
}

function getInitials(name) {
  const initials = String(name || "Aarav Nagar")
    .split(" ")
    .filter(Boolean)
    .map((word) => word[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return initials || "AN";
}

function normalizeList(value, fallback) {
  return Array.isArray(value) && value.length ? value : fallback;
}

function numberFromPercent(value) {
  const number = Number(String(value || "").replace(/[^0-9.]/g, ""));
  return Number.isFinite(number) && number > 0 ? number : 2;
}

function toneColor(tone) {
  if (tone === "risk") return palette.red;
  if (tone === "warn") return "#F59E0B";
  return palette.green;
}

const styles = StyleSheet.create({
  topBar: {
    minHeight: 48,
    paddingTop: 8,
    paddingBottom: 10,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  pageTitle: {
    color: palette.dark,
    fontSize: 24,
    fontWeight: "900"
  },
  topActions: {
    flexDirection: "row",
    gap: 18,
    alignItems: "center"
  },
  heroCard: {
    padding: 0,
    overflow: "hidden"
  },
  heroTop: {
    minHeight: 108,
    padding: 17,
    flexDirection: "row",
    alignItems: "center",
    gap: 14
  },
  avatarWrap: {
    width: 74,
    height: 74,
    borderRadius: 37,
    backgroundColor: "#DFF5E7",
    alignItems: "center",
    justifyContent: "center"
  },
  avatar: {
    width: 61,
    height: 61,
    borderRadius: 31,
    backgroundColor: "#7AD093",
    alignItems: "center",
    justifyContent: "center"
  },
  avatarText: {
    color: "#FFFFFF",
    fontSize: 24,
    fontWeight: "900"
  },
  heroText: {
    flex: 1
  },
  userName: {
    color: palette.dark,
    fontSize: 18,
    fontWeight: "900"
  },
  identityText: {
    color: palette.green,
    fontSize: 12,
    fontWeight: "900",
    marginTop: 4
  },
  experienceText: {
    color: palette.muted,
    fontSize: 12,
    fontWeight: "700",
    marginTop: 4
  },
  syncPill: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "#CFEFD8",
    backgroundColor: "#F5FFF8",
    paddingHorizontal: 8,
    paddingVertical: 5,
    flexDirection: "row",
    alignItems: "center",
    gap: 5
  },
  syncDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: palette.green
  },
  syncText: {
    color: palette.green,
    fontSize: 9,
    fontWeight: "900"
  },
  heroDivider: {
    height: 1,
    marginHorizontal: 17,
    backgroundColor: "#EEF2EF"
  },
  miniStats: {
    minHeight: 86,
    flexDirection: "row",
    paddingHorizontal: 8,
    paddingVertical: 12
  },
  miniStat: {
    flex: 1,
    alignItems: "center",
    borderRightWidth: 1,
    borderRightColor: "#EEF2EF",
    paddingHorizontal: 4
  },
  miniLabel: {
    color: palette.muted,
    fontSize: 8,
    fontWeight: "900",
    marginTop: 7,
    textAlign: "center"
  },
  miniValue: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900",
    marginTop: 5,
    textAlign: "center"
  },
  miniSuffix: {
    color: palette.muted,
    fontSize: 8,
    fontWeight: "900"
  },
  sparkLine: {
    width: 34,
    height: 4,
    backgroundColor: "#E9F4EC",
    borderRadius: 999,
    marginTop: 4,
    overflow: "hidden"
  },
  sparkLineFill: {
    width: "84%",
    height: "100%",
    backgroundColor: palette.green,
    borderRadius: 999
  },
  sectionCard: {
    padding: 15
  },
  sectionHeader: {
    minHeight: 24,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8
  },
  sectionTitle: {
    color: palette.dark,
    fontSize: 15,
    fontWeight: "900"
  },
  sectionAction: {
    color: palette.green,
    fontSize: 11,
    fontWeight: "900"
  },
  settingsRow: {
    minHeight: 58,
    borderBottomWidth: 1,
    borderBottomColor: "#EEF2EF",
    flexDirection: "row",
    alignItems: "center",
    gap: 12
  },
  noBorder: {
    borderBottomWidth: 0
  },
  rowIcon: {
    width: 25,
    alignItems: "center"
  },
  sourceIcon: {
    width: 25,
    height: 25,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: "#BFEACB",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F5FFF8"
  },
  sourceIconOff: {
    borderColor: palette.border,
    backgroundColor: "#F6F7F6"
  },
  rowCopy: {
    flex: 1
  },
  rowLabel: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  rowValue: {
    color: palette.muted,
    fontSize: 11,
    lineHeight: 15,
    fontWeight: "700",
    marginTop: 3
  },
  toggleLabel: {
    flex: 1
  },
  toggleTrack: {
    width: 43,
    height: 25,
    borderRadius: 999,
    backgroundColor: "#E8EEE9",
    padding: 3,
    justifyContent: "center"
  },
  toggleTrackOn: {
    backgroundColor: palette.green
  },
  toggleThumb: {
    width: 19,
    height: 19,
    borderRadius: 10,
    backgroundColor: "#FFFFFF",
    shadowColor: "#000000",
    shadowOpacity: 0.08,
    shadowRadius: 5
  },
  toggleThumbOn: {
    transform: [{ translateX: 18 }]
  },
  learnedCard: {
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#E6EAE6",
    backgroundColor: "#FFFFFF",
    padding: 13,
    marginTop: 9
  },
  learnedTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 7
  },
  learnedIcon: {
    width: 25,
    height: 25,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center"
  },
  learnedIconRisk: {
    backgroundColor: "#FFF1F1"
  },
  learnedIconGood: {
    backgroundColor: palette.greenSoft
  },
  learnedTitle: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  bulletText: {
    color: palette.dark,
    fontSize: 11,
    lineHeight: 18,
    fontWeight: "700"
  },
  scoreRow: {
    minHeight: 31,
    flexDirection: "row",
    alignItems: "center",
    gap: 10
  },
  scoreLabel: {
    width: 118,
    color: palette.dark,
    fontSize: 10,
    fontWeight: "800"
  },
  scoreTrack: {
    flex: 1,
    height: 8,
    borderRadius: 999,
    backgroundColor: "#ECF1ED",
    overflow: "hidden"
  },
  scoreFill: {
    height: "100%",
    borderRadius: 999
  },
  scoreValue: {
    width: 45,
    color: palette.dark,
    fontSize: 10,
    fontWeight: "900",
    textAlign: "right"
  },
  infoBox: {
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#CFEFD8",
    backgroundColor: "#F4FFF7",
    padding: 12,
    marginTop: 10
  },
  infoTitle: {
    color: palette.green,
    fontSize: 11,
    fontWeight: "900"
  },
  infoText: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "700",
    marginTop: 6
  },
  clearButton: {
    minHeight: 45,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#F8CACA",
    backgroundColor: "#FFF8F8",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 13
  },
  clearButtonText: {
    color: palette.red,
    fontSize: 12,
    fontWeight: "900"
  },
  dangerText: {
    color: palette.red
  },
  footerNote: {
    backgroundColor: "#F0FBF4",
    borderColor: "#CFEFD8",
    alignItems: "center",
    justifyContent: "center"
  },
  footerText: {
    color: palette.dark,
    fontSize: 12,
    lineHeight: 17,
    fontWeight: "800",
    textAlign: "center"
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(23,33,58,0.24)",
    alignItems: "center",
    justifyContent: "center",
    padding: 26
  },
  modalCard: {
    width: "100%",
    maxWidth: 360,
    borderRadius: 22,
    backgroundColor: "#FFFFFF",
    padding: 18,
    borderWidth: 1,
    borderColor: palette.border,
    shadowColor: "#000",
    shadowOpacity: 0.18,
    shadowRadius: 30,
    shadowOffset: { width: 0, height: 16 }
  },
  modalTitle: {
    color: palette.dark,
    fontSize: 18,
    fontWeight: "900"
  },
  modalText: {
    color: palette.muted,
    fontSize: 12,
    lineHeight: 18,
    fontWeight: "700",
    marginTop: 8
  },
  modalButton: {
    minHeight: 43,
    borderRadius: 14,
    backgroundColor: palette.green,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 16
  },
  modalButtonText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "900"
  },
  modalActions: {
    flexDirection: "row",
    gap: 10,
    marginTop: 16
  },
  cancelButton: {
    flex: 1,
    minHeight: 43,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: palette.border,
    alignItems: "center",
    justifyContent: "center"
  },
  cancelText: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900"
  },
  confirmButton: {
    flex: 1,
    minHeight: 43,
    borderRadius: 14,
    backgroundColor: palette.green,
    alignItems: "center",
    justifyContent: "center"
  },
  confirmDanger: {
    backgroundColor: palette.red
  },
  confirmText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "900"
  }
});
