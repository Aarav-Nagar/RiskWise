import React from "react";
import { Modal, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Card } from "../components/Card";
import { ScreenScroll } from "../components/Shared";
import { getRiskWiseContextSummary } from "../services/authService";
import { palette } from "../theme/theme";

const PANELS = ["Overview", "Rules & AI", "Account"];
const OPTION_SETS = {
  experience: ["New to options", "Still learning", "Some experience", "Active trader", "Advanced"],
  riskStyle: ["Conservative", "Balanced", "Aggressive"],
  explanation: ["Simple", "Step-by-step", "Quant-heavy"],
  aiMode: ["Explain", "Review", "Compare"],
  openAppTo: ["Home", "Check", "Coach", "Profile"],
  coaching: ["Debate both sides", "Direct answer first", "Strict risk review"],
  questionStyle: ["Ask me questions first", "Give answer first", "Show checklist first"],
  strictness: ["Balanced risk tone", "Strict about risk", "Educational only"],
  quietHours: ["After 8 PM", "After 9 PM", "After 10 PM", "Off"],
  sectors: ["Technology", "Healthcare", "Finance", "Energy", "Consumer", "Industrials", "Indexes", "Small caps"],
  mistakes: ["Oversizing", "Chasing", "Ignoring IV", "Short expiry", "No exit plan", "Entering before confirmation", "Overtrading"],
  markets: ["Technology", "Indexes", "Healthcare", "Finance", "Energy", "Small caps", "High-volatility names"]
};

const defaultInsights = {
  decisionQuality: {
    overall: 84,
    signalDiscipline: 81,
    positionSizing: 90,
    volatilityAwareness: 74,
    patience: 86
  },
  commonMistakes: ["Entering before confirmation", "Position sizing too large", "Chasing momentum", "Trading very short expirations", "No clear exit plan"],
  strongHabits: ["Uses defined risk consistently", "Reviews before entering trades", "Considers volatility context", "Plans exits in advance"]
};

export function ProfileScreen({ user, onSignOut, onUpdateUser, onClearContext, onDeleteAccount, onPasswordReset }) {
  const [panel, setPanel] = React.useState("Overview");
  const [notice, setNotice] = React.useState("");
  const [confirmAction, setConfirmAction] = React.useState(null);
  const [saving, setSaving] = React.useState("");
  const [editor, setEditor] = React.useState(null);
  const [profile, setProfile] = React.useState(() => profileFromUser(user));

  React.useEffect(() => {
    setProfile(profileFromUser(user));
  }, [user?.id]);

  React.useEffect(() => {
    let active = true;
    async function loadContextSummary() {
      if (!user?.id || String(user.id).startsWith("preview")) {
        return;
      }
      try {
        const summary = await getRiskWiseContextSummary(user.id);
        if (!active) {
          return;
        }
        setProfile((current) => ({
          ...current,
          analysisSources: {
            savedChecks: { ...current.analysisSources.savedChecks, count: summary.savedChecks || 0 },
            chatHistory: { ...current.analysisSources.chatHistory, count: summary.chatThreads || 0 },
            uploadedScreenshots: { ...current.analysisSources.uploadedScreenshots, count: summary.uploadedScreenshots || 0 },
            watchlist: { ...current.analysisSources.watchlist, count: summary.watchlist || 0 }
          }
        }));
      } catch (error) {
        // Counts are helpful but should never block profile editing.
      }
    }
    loadContextSummary();
    return () => {
      active = false;
    };
  }, [user?.id]);

  const firstName = firstNameOf(profile.name);
  const initials = getInitials(profile.name);

  async function saveProfile(patch, localPatch = {}) {
    const nextProfile = deepMerge(profile, localPatch);
    setProfile(nextProfile);
    setSaving("Saving");
    try {
      const saved = await onUpdateUser?.(patch);
      setProfile(profileFromUser(saved || { ...user, ...patch }));
      setSaving("Saved");
      setNotice("Profile saved.");
      return saved;
    } catch (error) {
      setSaving("Retry");
      setNotice(error.message || "Could not save this profile setting.");
      throw error;
    }
  }

  function editText(title, value, onSave, options = {}) {
    setEditor({ title, value: String(value ?? ""), type: options.type || "text", keyboardType: options.keyboardType, suffix: options.suffix, helper: options.helper, onSave });
  }

  function editChoice(title, value, choices, onSave, helper) {
    setEditor({ title, value, type: "choice", choices, helper, onSave });
  }

  function editMulti(title, value, choices, onSave, helper) {
    setEditor({ title, value: normalizeList(value, []), type: "multi", choices, helper, onSave });
  }

  async function sendPasswordReset() {
    setSaving("Sending");
    try {
      const response = await onPasswordReset?.();
      setSaving("Sent");
      setNotice(response?.message || "Password reset email requested. Check your inbox.");
    } catch (error) {
      setSaving("Retry");
      setNotice(error.message || "Could not request a password reset.");
    }
  }

  async function clearContext() {
    setConfirmAction(null);
    setSaving("Clearing");
    try {
      await onClearContext?.();
      setProfile((current) => ({
        ...current,
        savedContext: {
          savedChecks: false,
          chatHistory: false,
          uploadedScreenshots: false,
          watchlist: false
        },
        analysisSources: {
          savedChecks: { enabled: false, count: 0 },
          chatHistory: { enabled: false, count: 0 },
          uploadedScreenshots: { enabled: false, count: 0 },
          watchlist: { enabled: false, count: 0 }
        }
      }));
      setSaving("Cleared");
      setNotice("Saved checks, chat history, screenshot context, and watchlist context were cleared.");
    } catch (error) {
      setSaving("Retry");
      setNotice(error.message || "Could not clear context.");
    }
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
      <ProfileTopBar status={saving || "Synced"} />
      <PanelTabs active={panel} onChange={setPanel} />

      {panel === "Overview" ? (
        <>
          <ProfileHeaderCard
            initials={initials}
            name={firstName}
            identity={`${profile.aiMemory.riskStyle} Trader`}
            experience={profile.aiMemory.experienceLevel}
            synced={saving || "Synced"}
            riskRule={`${profile.riskRules.maxRiskPerTradePercent}% max`}
            tradesPerWeek={`${profile.riskRules.maxTradesPerWeek} max`}
            aiMode={profile.appPreferences.defaultMode}
            onEditName={() => editText("Display name", profile.name, (value) => saveProfile({ name: cleanText(value, "RiskWise User") }, { name: cleanText(value, "RiskWise User") }), { helper: "This is how RiskWise greets you." })}
          />
          <SectionCard title="Trader DNA" action="Edit memory" onAction={() => setPanel("Rules & AI")}>
            <SettingsRow icon="person-outline" label="Experience Level" value={profile.aiMemory.experienceLevel} onPress={() => editChoice("Experience level", profile.aiMemory.experienceLevel, OPTION_SETS.experience, (value) => saveMemory({ experienceLevel: value }))} />
            <SettingsRow icon="shield-checkmark-outline" label="Risk Style" value={profile.aiMemory.riskStyle} onPress={() => editChoice("Risk style", profile.aiMemory.riskStyle, OPTION_SETS.riskStyle, (value) => saveMemory({ riskStyle: value }))} />
            <SettingsRow icon="list-outline" label="Preferred Explanations" value={profile.aiMemory.explanationStyle} onPress={() => editChoice("Preferred explanations", profile.aiMemory.explanationStyle, OPTION_SETS.explanation, (value) => saveMemory({ explanationStyle: value }))} />
            <SettingsRow icon="analytics-outline" label="Favorite Markets" value={profile.favoriteMarkets.join(", ")} onPress={() => editMulti("Favorite markets", profile.favoriteMarkets, OPTION_SETS.markets, (value) => saveProfile({ sectors: value }, { favoriteMarkets: value, aiMemory: { sectors: value } }))} />
            <SettingsRow icon="warning-outline" label="Common Mistakes to Watch" value={profile.aiMemory.mistakes.join(", ")} onPress={() => editMulti("Common mistakes to watch", profile.aiMemory.mistakes, OPTION_SETS.mistakes, (value) => saveMemory({ mistakes: value }))} last />
          </SectionCard>
          <SectionCard title="What RiskWise Has Learned" action="View all" onAction={() => setNotice("This summary updates as saved checks and Coach conversations grow.")}>
            <LearnedInsightCard tone="risk" title="Common Mistakes" items={profile.aiMemory.mistakes.length ? profile.aiMemory.mistakes : defaultInsights.commonMistakes} />
            <LearnedInsightCard tone="good" title="Strong Habits" items={defaultInsights.strongHabits} />
          </SectionCard>
          <SectionCard title="Decision Quality Breakdown" action="View history" onAction={() => setNotice("Decision history will use saved checks once enough reviews exist.")}>
            <ScoreBar label="Signal Discipline" value={defaultInsights.decisionQuality.signalDiscipline} />
            <ScoreBar label="Position Sizing" value={defaultInsights.decisionQuality.positionSizing} />
            <ScoreBar label="Volatility Awareness" value={defaultInsights.decisionQuality.volatilityAwareness} />
            <ScoreBar label="Patience" value={defaultInsights.decisionQuality.patience} />
            <ScoreBar label="Overall" value={defaultInsights.decisionQuality.overall} />
          </SectionCard>
        </>
      ) : null}

      {panel === "Rules & AI" ? (
        <>
          <SectionCard title="Risk Rules" action="Edit all" onAction={() => setNotice("Tap any row to edit that rule.")}>
            <SettingsRow icon="water-outline" label="Max risk per trade" value={`${profile.riskRules.maxRiskPerTradePercent}% of account`} onPress={() => editText("Max risk per trade", profile.riskRules.maxRiskPerTradePercent, (value) => saveRiskRule({ maxRiskPerTradePercent: clampNumber(value, 0.1, 25, 2) }), { type: "number", keyboardType: "decimal-pad", suffix: "%", helper: "Used in every risk check." })} />
            <SettingsRow icon="repeat-outline" label="Max trades per week" value={`${profile.riskRules.maxTradesPerWeek} trades`} onPress={() => editText("Max trades per week", profile.riskRules.maxTradesPerWeek, (value) => saveRiskRule({ maxTradesPerWeek: clampNumber(value, 1, 100, 5) }), { type: "number", keyboardType: "number-pad" })} />
            <ToggleRow icon="close-circle-outline" label="Avoid earnings trades" value={profile.riskRules.avoidEarningsTrades} onChange={(value) => saveRiskRule({ avoidEarningsTrades: value })} />
            <ToggleRow icon="time-outline" label={`Warn if expiration < ${profile.riskRules.shortExpirationDays} days`} value={profile.riskRules.warnShortExpiration} onChange={(value) => saveRiskRule({ warnShortExpiration: value })} />
            <SettingsRow icon="calendar-outline" label="Short expiration window" value={`${profile.riskRules.shortExpirationDays} days`} onPress={() => editText("Short expiration warning", profile.riskRules.shortExpirationDays, (value) => saveRiskRule({ shortExpirationDays: clampNumber(value, 1, 60, 7) }), { type: "number", keyboardType: "number-pad", suffix: "days" })} />
            <SettingsRow icon="alert-circle-outline" label="Premium risk warning level" value={`${profile.riskRules.premiumRiskWarningLevelPercent}%`} onPress={() => editText("Premium risk warning level", profile.riskRules.premiumRiskWarningLevelPercent, (value) => saveRiskRule({ premiumRiskWarningLevelPercent: clampNumber(value, 0.1, 50, 5) }), { type: "number", keyboardType: "decimal-pad", suffix: "%" })} last />
            <InfoBox title="These rules are used in every analysis" text={`Last updated: ${profile.riskRules.lastUpdated}`} />
          </SectionCard>

          <SectionCard title="Coach Style & Preferences" action="Edit all" onAction={() => setNotice("Tap any row to tune the Coach.")}>
            <SettingsRow icon="chatbubble-ellipses-outline" label="Default AI Mode" value={profile.coachStyle.defaultAIMode} onPress={() => editChoice("Default AI mode", profile.coachStyle.defaultAIMode, OPTION_SETS.aiMode, (value) => saveCoach({ defaultAIMode: value }, { appPreferences: { defaultMode: value } }))} />
            <SettingsRow icon="reader-outline" label="Explanation Style" value={profile.coachStyle.explanationStyle} onPress={() => editChoice("Explanation style", profile.coachStyle.explanationStyle, OPTION_SETS.explanation, (value) => saveCoach({ explanationStyle: value }, { aiMemory: { explanationStyle: value } }))} />
            <SettingsRow icon="git-compare-outline" label="Coaching Approach" value={profile.coachStyle.coachingApproach} onPress={() => editChoice("Coaching approach", profile.coachStyle.coachingApproach, OPTION_SETS.coaching, (value) => saveCoach({ coachingApproach: value }))} />
            <SettingsRow icon="help-buoy-outline" label="Question Style" value={profile.coachStyle.questionStyle} onPress={() => editChoice("Question style", profile.coachStyle.questionStyle, OPTION_SETS.questionStyle, (value) => saveCoach({ questionStyle: value }))} />
            <SettingsRow icon="shield-outline" label="Risk Strictness" value={profile.coachStyle.riskStrictness} onPress={() => editChoice("Risk strictness", profile.coachStyle.riskStrictness, OPTION_SETS.strictness, (value) => saveCoach({ riskStrictness: value }))} last />
          </SectionCard>

          <SectionCard title="App Preferences" action="Edit all" onAction={() => setNotice("Tap a row or toggle to edit app behavior.")}>
            <SettingsRow icon="sparkles-outline" label="Default AI Mode" value={profile.appPreferences.defaultMode} onPress={() => editChoice("Default AI mode", profile.appPreferences.defaultMode, OPTION_SETS.aiMode, (value) => saveAppPreference({ defaultMode: value }, { coachStyle: { defaultAIMode: value } }))} />
            <SettingsRow icon="open-outline" label="Open App To" value={profile.appPreferences.openAppTo} onPress={() => editChoice("Open app to", profile.appPreferences.openAppTo, OPTION_SETS.openAppTo, (value) => saveAppPreference({ openAppTo: value, defaultTab: value }))} />
            <ToggleRow icon="albums-outline" label="Use compact report cards" value={profile.appPreferences.compactReports} onChange={(value) => saveAppPreference({ compactReports: value })} />
            <ToggleRow icon="notifications-outline" label="Weekly learning digest" value={profile.appPreferences.weeklyDigest} onChange={(value) => saveAppPreference({ weeklyDigest: value })} />
            <SettingsRow icon="moon-outline" label="Quiet hours" value={profile.appPreferences.quietHours} onPress={() => editChoice("Quiet hours", profile.appPreferences.quietHours, OPTION_SETS.quietHours, (value) => saveAppPreference({ quietHours: value }))} last />
          </SectionCard>

          <SectionCard title="AI Memory" action="Edit all" onAction={() => setNotice("Tap any memory row to edit what RiskWise remembers.")}>
            <InfoBox title="RiskWise uses your memory to personalize analysis and coaching." />
            <SettingsRow icon="person-outline" label="Experience" value={profile.aiMemory.experienceLevel} onPress={() => editChoice("Experience", profile.aiMemory.experienceLevel, OPTION_SETS.experience, (value) => saveMemory({ experienceLevel: value }))} />
            <SettingsRow icon="shield-checkmark-outline" label="Risk Style" value={profile.aiMemory.riskStyle} onPress={() => editChoice("Risk style", profile.aiMemory.riskStyle, OPTION_SETS.riskStyle, (value) => saveMemory({ riskStyle: value }))} />
            <SettingsRow icon="bulb-outline" label="Preferred Explanation" value={profile.aiMemory.explanationStyle} onPress={() => editChoice("Preferred explanation", profile.aiMemory.explanationStyle, OPTION_SETS.explanation, (value) => saveMemory({ explanationStyle: value }))} />
            <SettingsRow icon="pie-chart-outline" label="Sectors to Focus" value={profile.aiMemory.sectors.join(", ")} onPress={() => editMulti("Sectors to focus", profile.aiMemory.sectors, OPTION_SETS.sectors, (value) => saveMemory({ sectors: value }, { sectors: value }))} />
            <SettingsRow icon="warning-outline" label="Common Mistakes" value={profile.aiMemory.mistakes.join(", ")} onPress={() => editMulti("Common mistakes", profile.aiMemory.mistakes, OPTION_SETS.mistakes, (value) => saveMemory({ mistakes: value }))} last />
          </SectionCard>
        </>
      ) : null}

      {panel === "Account" ? (
        <>
          <SectionCard title="Account & Security" action="Edit" onAction={() => setNotice("Tap a row to edit account settings.")}>
            <SettingsRow icon="person-circle-outline" label="Display Name" value={profile.name} onPress={() => editText("Display name", profile.name, (value) => saveProfile({ name: cleanText(value, "RiskWise User") }, { name: cleanText(value, "RiskWise User") }))} />
            <SettingsRow icon="mail-outline" label="Email" value={profile.email} onPress={() => setNotice("Email is managed by your sign-in provider so account recovery stays secure.")} />
            <SettingsRow icon="wallet-outline" label="Account Size" value={money(profile.accountSize)} onPress={() => editText("Account size", profile.accountSize, (value) => saveProfile({ accountSize: clampNumber(value, 100, 100000000, 25000) }, { accountSize: clampNumber(value, 100, 100000000, 25000) }), { type: "number", keyboardType: "decimal-pad", helper: "Used to calculate account risk." })} />
            <SettingsRow icon="speedometer-outline" label="Risk Budget" value={`${profile.riskBudgetPercent}% default`} onPress={() => editText("Risk budget", profile.riskBudgetPercent, (value) => saveProfile({ riskBudgetPercent: clampNumber(value, 0.1, 25, 2) }, { riskBudgetPercent: clampNumber(value, 0.1, 25, 2) }), { type: "number", keyboardType: "decimal-pad", suffix: "%" })} />
            <ActionRow icon="refresh-outline" label="Send Password Reset Email" value="Uses your profile email" onPress={sendPasswordReset} />
            <ActionRow icon="log-out-outline" label="Sign Out" onPress={() => setConfirmAction("signOut")} />
            <ActionRow icon="trash-outline" label="Delete Account Data" danger onPress={() => setConfirmAction("delete")} last />
          </SectionCard>

          <SectionCard title="Analysis Sources" action="Manage" onAction={() => setNotice("Toggle source memory or clear all context below.")}>
            <SourceToggle label="Saved Checks" value={`${profile.analysisSources.savedChecks.count} saved analyses`} enabled={profile.analysisSources.savedChecks.enabled} onChange={(value) => saveSavedContext("savedChecks", value)} />
            <SourceToggle label="Chat History" value={`${profile.analysisSources.chatHistory.count} conversations`} enabled={profile.analysisSources.chatHistory.enabled} onChange={(value) => saveSavedContext("chatHistory", value)} />
            <SourceToggle label="Uploaded Screenshots" value={`${profile.analysisSources.uploadedScreenshots.count} images`} enabled={profile.analysisSources.uploadedScreenshots.enabled} onChange={(value) => saveSavedContext("uploadedScreenshots", value)} />
            <SourceToggle label="Watchlist" value={`${profile.analysisSources.watchlist.count} symbols tracked`} enabled={profile.analysisSources.watchlist.enabled} onChange={(value) => saveSavedContext("watchlist", value)} last />
            <Pressable style={styles.clearButton} onPress={() => setConfirmAction("clear")}>
              <Text style={styles.clearButtonText}>Clear all context</Text>
            </Pressable>
          </SectionCard>

          <Card style={styles.footerNote}>
            <Text style={styles.footerText}>RiskWise is educational decision support. It stores only the context needed to personalize checks and coaching.</Text>
          </Card>
        </>
      ) : null}

      {notice ? <NoticeModal message={notice} onClose={() => setNotice("")} /> : null}
      {confirmAction ? (
        <ConfirmModal
          action={confirmAction}
          onCancel={() => setConfirmAction(null)}
          onConfirm={confirmAction === "clear" ? clearContext : confirmAction === "delete" ? confirmDelete : async () => { setConfirmAction(null); await onSignOut?.(); }}
        />
      ) : null}
      {editor ? <FieldEditorModal editor={editor} onClose={() => setEditor(null)} /> : null}
    </ScreenScroll>
  );

  function saveMemory(next, extra = {}) {
    const aiMemory = { ...profile.aiMemory, ...next };
    return saveProfile(
      {
        aiMemory,
        experienceLevel: aiMemory.experienceLevel,
        riskStyle: aiMemory.riskStyle,
        sectors: extra.sectors || aiMemory.sectors,
        struggles: aiMemory.mistakes
      },
      { aiMemory, ...extra }
    );
  }

  function saveRiskRule(next) {
    const riskRules = { ...profile.riskRules, ...next, lastUpdated: todayLabel() };
    return saveProfile({ riskRules }, { riskRules });
  }

  function saveCoach(next, extra = {}) {
    const coachStyle = { ...profile.coachStyle, ...next };
    return saveProfile({ coachStyle, ...extra }, { coachStyle, ...extra });
  }

  function saveAppPreference(next, extra = {}) {
    const appPreferences = { ...profile.appPreferences, ...next };
    return saveProfile({ appPreferences, ...extra }, { appPreferences, ...extra });
  }

  function saveSavedContext(key, enabled) {
    const savedContext = { ...profile.savedContext, [key]: enabled };
    const analysisSources = {
      ...profile.analysisSources,
      [key]: { ...profile.analysisSources[key], enabled }
    };
    return saveProfile({ savedContext }, { savedContext, analysisSources });
  }
}

function ProfileTopBar({ status }) {
  return (
    <View style={styles.topBar}>
      <Text style={styles.pageTitle}>Profile</Text>
      <View style={styles.topActions}>
        <Text style={styles.statusText}>{status}</Text>
        <Ionicons name="notifications-outline" size={19} color={palette.dark} />
        <Ionicons name="settings-outline" size={20} color={palette.dark} />
      </View>
    </View>
  );
}

function PanelTabs({ active, onChange }) {
  return (
    <View style={styles.panelTabs}>
      {PANELS.map((item) => (
        <Pressable
          key={item}
          accessibilityRole="button"
          accessibilityLabel={`Profile section ${item}`}
          style={[styles.panelTab, active === item && styles.panelTabActive]}
          onPress={() => onChange(item)}
        >
          <Text style={[styles.panelTabText, active === item && styles.panelTabTextActive]}>{item}</Text>
        </Pressable>
      ))}
    </View>
  );
}

function ProfileHeaderCard({ initials, name, identity, experience, synced, riskRule, tradesPerWeek, aiMode, onEditName }) {
  return (
    <Card style={styles.heroCard}>
      <View style={styles.heroTop}>
        <View style={styles.avatarWrap}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initials}</Text>
          </View>
        </View>
        <Pressable style={styles.heroText} onPress={onEditName}>
          <Text style={styles.userName}>{name}</Text>
          <Text style={styles.identityText}>{identity}</Text>
          <Text style={styles.experienceText}>{experience}</Text>
        </Pressable>
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

function SettingsRow({ icon, label, value, onPress, last }) {
  const Wrapper = onPress ? Pressable : View;
  return (
    <Wrapper style={[styles.settingsRow, last && styles.noBorder]} onPress={onPress}>
      <View style={styles.rowIcon}>
        <Ionicons name={icon} size={17} color={palette.dark} />
      </View>
      <View style={styles.rowCopy}>
        <Text style={styles.rowLabel}>{label}</Text>
        <Text style={styles.rowValue} numberOfLines={2}>{value}</Text>
      </View>
      {onPress ? <Ionicons name="chevron-forward" size={15} color={palette.muted} /> : null}
    </Wrapper>
  );
}

function ToggleRow({ icon, label, value, onChange, last }) {
  return (
    <Pressable style={[styles.settingsRow, last && styles.noBorder]} onPress={() => onChange(!value)}>
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

function SourceToggle({ label, value, enabled, onChange, last }) {
  return (
    <Pressable style={[styles.settingsRow, last && styles.noBorder]} onPress={() => onChange(!enabled)}>
      <View style={[styles.sourceIcon, !enabled && styles.sourceIconOff]}>
        <Ionicons name={enabled ? "checkmark" : "close"} size={14} color={enabled ? palette.green : palette.muted} />
      </View>
      <View style={styles.rowCopy}>
        <Text style={styles.rowLabel}>{label}</Text>
        <Text style={styles.rowValue}>{value}</Text>
      </View>
      <View style={[styles.toggleTrack, enabled && styles.toggleTrackOn]}>
        <View style={[styles.toggleThumb, enabled && styles.toggleThumbOn]} />
      </View>
    </Pressable>
  );
}

function ActionRow({ icon, label, value, onPress, danger, last }) {
  return (
    <Pressable style={[styles.settingsRow, last && styles.noBorder]} onPress={onPress}>
      <View style={styles.rowIcon}>
        <Ionicons name={icon} size={17} color={danger ? palette.red : palette.dark} />
      </View>
      <View style={styles.rowCopy}>
        <Text style={[styles.rowLabel, danger && styles.dangerText]}>{label}</Text>
        {value ? <Text style={styles.rowValue}>{value}</Text> : null}
      </View>
      <Ionicons name="chevron-forward" size={15} color={danger ? palette.red : palette.muted} />
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
        <Text key={item} style={styles.bulletText}>- {item}</Text>
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

function FieldEditorModal({ editor, onClose }) {
  const [value, setValue] = React.useState(editor.value);
  const [saving, setSaving] = React.useState(false);

  async function save() {
    setSaving(true);
    try {
      await editor.onSave(value);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal transparent animationType="fade" visible>
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>{editor.title}</Text>
          {editor.helper ? <Text style={styles.modalText}>{editor.helper}</Text> : null}
          {editor.type === "choice" ? (
            <View style={styles.choiceList}>
              {editor.choices.map((choice) => (
                <Pressable key={choice} style={[styles.choiceButton, value === choice && styles.choiceButtonActive]} onPress={() => setValue(choice)}>
                  <Text style={[styles.choiceText, value === choice && styles.choiceTextActive]}>{choice}</Text>
                </Pressable>
              ))}
            </View>
          ) : null}
          {editor.type === "multi" ? (
            <View style={styles.multiGrid}>
              {editor.choices.map((choice) => {
                const selected = value.includes(choice);
                return (
                  <Pressable
                    key={choice}
                    style={[styles.multiChip, selected && styles.multiChipActive]}
                    onPress={() => setValue(selected ? value.filter((item) => item !== choice) : [...value, choice])}
                  >
                    <Text style={[styles.multiChipText, selected && styles.multiChipTextActive]}>{choice}</Text>
                  </Pressable>
                );
              })}
            </View>
          ) : null}
          {editor.type === "text" || editor.type === "number" ? (
            <View style={styles.inputWrap}>
              <TextInput
                style={styles.editorInput}
                value={String(value)}
                onChangeText={setValue}
                keyboardType={editor.keyboardType || "default"}
                autoCapitalize="words"
              />
              {editor.suffix ? <Text style={styles.inputSuffix}>{editor.suffix}</Text> : null}
            </View>
          ) : null}
          <View style={styles.modalActions}>
            <Pressable style={styles.cancelButton} onPress={onClose}>
              <Text style={styles.cancelText}>Cancel</Text>
            </Pressable>
            <Pressable style={styles.confirmButton} onPress={save} disabled={saving}>
              <Text style={styles.confirmText}>{saving ? "Saving..." : "Save"}</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
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
    clear: ["Clear all context?", "This removes saved checks, chat history, screenshot context, and watchlist context from RiskWise analysis."],
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

function profileFromUser(user) {
  const aiMemory = {
    experienceLevel: user?.aiMemory?.experienceLevel || user?.experienceLevel || "Some experience",
    riskStyle: user?.aiMemory?.riskStyle || user?.riskStyle || "Balanced",
    explanationStyle: user?.aiMemory?.explanationStyle || "Step-by-step",
    sectors: normalizeList(user?.aiMemory?.sectors || user?.sectors, ["Technology", "Healthcare", "Finance", "Energy"]),
    mistakes: normalizeList(user?.aiMemory?.mistakes || user?.struggles, ["Oversizing", "Chasing", "Ignoring IV", "Short expiry", "No exit plan"])
  };
  const riskRules = {
    maxRiskPerTradePercent: numberFromPercent(user?.riskRules?.maxRiskPerTradePercent || user?.riskRules?.maxRiskPerTrade || user?.maxRiskPerTrade || user?.riskBudgetPercent || 2),
    maxTradesPerWeek: numberFromPercent(user?.riskRules?.maxTradesPerWeek || user?.maxTradesPerWeek || 5),
    avoidEarningsTrades: user?.riskRules?.avoidEarningsTrades ?? user?.riskRules?.avoidEarnings ?? true,
    warnShortExpiration: user?.riskRules?.warnShortExpiration ?? user?.riskRules?.warnShortExpiry ?? true,
    shortExpirationDays: numberFromPercent(user?.riskRules?.shortExpirationDays || 7),
    premiumRiskWarningLevelPercent: numberFromPercent(user?.riskRules?.premiumRiskWarningLevelPercent || user?.riskRules?.premiumRiskLimit || 5),
    lastUpdated: user?.riskRules?.lastUpdated || "May 31, 2026"
  };
  const appPreferences = {
    defaultMode: user?.appPreferences?.defaultMode || "Review",
    openAppTo: user?.appPreferences?.defaultTab || user?.appPreferences?.openAppTo || "Coach",
    defaultTab: user?.appPreferences?.defaultTab || user?.appPreferences?.openAppTo || "Coach",
    compactReports: user?.appPreferences?.compactReports !== false,
    weeklyDigest: user?.appPreferences?.weeklyDigest !== false,
    quietHours: user?.appPreferences?.quietHours || "After 9 PM"
  };
  const coachStyle = {
    defaultAIMode: user?.coachStyle?.defaultAIMode || appPreferences.defaultMode,
    explanationStyle: user?.coachStyle?.explanationStyle || aiMemory.explanationStyle,
    coachingApproach: user?.coachStyle?.coachingApproach || (user?.coachStyle?.debateBothSides === false ? "Direct answer first" : "Debate both sides"),
    questionStyle: user?.coachStyle?.questionStyle || (user?.coachStyle?.askQuestionsFirst === false ? "Give answer first" : "Ask me questions first"),
    riskStrictness: user?.coachStyle?.riskStrictness || (user?.coachStyle?.strictRisk === false ? "Balanced risk tone" : "Strict about risk")
  };
  const savedContext = {
    savedChecks: user?.savedContext?.savedChecks !== false,
    chatHistory: user?.savedContext?.chatHistory !== false,
    uploadedScreenshots: user?.savedContext?.uploadedScreenshots !== false,
    watchlist: user?.savedContext?.watchlist !== false
  };
  return {
    name: user?.name || "Aarav Nagar",
    email: user?.email || "aarav.nagar22@gmail.com",
    accountSize: Number(user?.accountSize || 25000),
    riskBudgetPercent: Number(user?.riskBudgetPercent || riskRules.maxRiskPerTradePercent || 2),
    favoriteMarkets: normalizeList(user?.sectors || aiMemory.sectors, ["Technology", "Indexes"]),
    aiMemory,
    riskRules,
    appPreferences,
    coachStyle,
    savedContext,
    analysisSources: {
      savedChecks: { enabled: savedContext.savedChecks, count: Number(user?.contextSummary?.savedChecks || 0) },
      chatHistory: { enabled: savedContext.chatHistory, count: Number(user?.contextSummary?.chatThreads || 0) },
      uploadedScreenshots: { enabled: savedContext.uploadedScreenshots, count: Number(user?.contextSummary?.uploadedScreenshots || 0) },
      watchlist: { enabled: savedContext.watchlist, count: Number(user?.contextSummary?.watchlist || 0) }
    }
  };
}

function firstNameOf(name) {
  return (name || "Aarav").split(" ")[0];
}

function getInitials(name) {
  return String(name || "Aarav Nagar").split(" ").filter(Boolean).map((word) => word[0]).join("").slice(0, 2).toUpperCase() || "AN";
}

function normalizeList(value, fallback) {
  return Array.isArray(value) && value.length ? value : fallback;
}

function numberFromPercent(value) {
  const number = Number(String(value ?? "").replace(/[^0-9.]/g, ""));
  return Number.isFinite(number) && number > 0 ? number : 2;
}

function clampNumber(value, min, max, fallback) {
  const number = Number(String(value ?? "").replace(/[^0-9.]/g, ""));
  if (!Number.isFinite(number)) return fallback;
  return Math.min(max, Math.max(min, number));
}

function cleanText(value, fallback) {
  const clean = String(value || "").trim();
  return clean || fallback;
}

function todayLabel() {
  return new Date().toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function money(value) {
  return `$${Number(value || 0).toLocaleString()}`;
}

function deepMerge(base, patch) {
  const result = { ...base };
  Object.entries(patch || {}).forEach(([key, value]) => {
    if (value && typeof value === "object" && !Array.isArray(value) && base[key] && typeof base[key] === "object" && !Array.isArray(base[key])) {
      result[key] = { ...base[key], ...value };
    } else {
      result[key] = value;
    }
  });
  return result;
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
  pageTitle: { color: palette.dark, fontSize: 24, fontWeight: "900" },
  topActions: { flexDirection: "row", gap: 14, alignItems: "center" },
  statusText: { color: palette.green, fontSize: 10, fontWeight: "900" },
  panelTabs: {
    flexDirection: "row",
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 18,
    padding: 5,
    marginBottom: 10
  },
  panelTab: { flex: 1, minHeight: 36, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  panelTabActive: { backgroundColor: palette.green },
  panelTabText: { color: palette.muted, fontSize: 12, fontWeight: "900" },
  panelTabTextActive: { color: "#FFFFFF" },
  heroCard: { padding: 0, overflow: "hidden" },
  heroTop: { minHeight: 108, padding: 17, flexDirection: "row", alignItems: "center", gap: 14 },
  avatarWrap: { width: 74, height: 74, borderRadius: 37, backgroundColor: "#DFF5E7", alignItems: "center", justifyContent: "center" },
  avatar: { width: 61, height: 61, borderRadius: 31, backgroundColor: "#7AD093", alignItems: "center", justifyContent: "center" },
  avatarText: { color: "#FFFFFF", fontSize: 24, fontWeight: "900" },
  heroText: { flex: 1 },
  userName: { color: palette.dark, fontSize: 18, fontWeight: "900" },
  identityText: { color: palette.green, fontSize: 12, fontWeight: "900", marginTop: 4 },
  experienceText: { color: palette.muted, fontSize: 12, fontWeight: "700", marginTop: 4 },
  syncPill: { borderRadius: 999, borderWidth: 1, borderColor: "#CFEFD8", backgroundColor: "#F5FFF8", paddingHorizontal: 8, paddingVertical: 5, flexDirection: "row", alignItems: "center", gap: 5 },
  syncDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: palette.green },
  syncText: { color: palette.green, fontSize: 9, fontWeight: "900" },
  heroDivider: { height: 1, marginHorizontal: 17, backgroundColor: "#EEF2EF" },
  miniStats: { minHeight: 86, flexDirection: "row", paddingHorizontal: 8, paddingVertical: 12 },
  miniStat: { flex: 1, alignItems: "center", borderRightWidth: 1, borderRightColor: "#EEF2EF", paddingHorizontal: 4 },
  miniLabel: { color: palette.muted, fontSize: 8, fontWeight: "900", marginTop: 7, textAlign: "center" },
  miniValue: { color: palette.dark, fontSize: 13, fontWeight: "900", marginTop: 5, textAlign: "center" },
  miniSuffix: { color: palette.muted, fontSize: 8, fontWeight: "900" },
  sparkLine: { width: 34, height: 4, backgroundColor: "#E9F4EC", borderRadius: 999, marginTop: 4, overflow: "hidden" },
  sparkLineFill: { width: "84%", height: "100%", backgroundColor: palette.green, borderRadius: 999 },
  sectionCard: { padding: 15 },
  sectionHeader: { minHeight: 24, flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 8 },
  sectionTitle: { color: palette.dark, fontSize: 15, fontWeight: "900" },
  sectionAction: { color: palette.green, fontSize: 11, fontWeight: "900" },
  settingsRow: { minHeight: 58, borderBottomWidth: 1, borderBottomColor: "#EEF2EF", flexDirection: "row", alignItems: "center", gap: 12 },
  noBorder: { borderBottomWidth: 0 },
  rowIcon: { width: 25, alignItems: "center" },
  sourceIcon: { width: 25, height: 25, borderRadius: 13, borderWidth: 1, borderColor: "#BFEACB", alignItems: "center", justifyContent: "center", backgroundColor: "#F5FFF8" },
  sourceIconOff: { borderColor: palette.border, backgroundColor: "#F6F7F6" },
  rowCopy: { flex: 1 },
  rowLabel: { color: palette.dark, fontSize: 12, fontWeight: "900" },
  rowValue: { color: palette.muted, fontSize: 11, lineHeight: 15, fontWeight: "700", marginTop: 3 },
  toggleLabel: { flex: 1 },
  toggleTrack: { width: 43, height: 25, borderRadius: 999, backgroundColor: "#E8EEE9", padding: 3, justifyContent: "center" },
  toggleTrackOn: { backgroundColor: palette.green },
  toggleThumb: { width: 19, height: 19, borderRadius: 10, backgroundColor: "#FFFFFF", shadowColor: "#000000", shadowOpacity: 0.08, shadowRadius: 5 },
  toggleThumbOn: { transform: [{ translateX: 18 }] },
  learnedCard: { borderRadius: 16, borderWidth: 1, borderColor: "#E6EAE6", backgroundColor: "#FFFFFF", padding: 13, marginTop: 9 },
  learnedTitleRow: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 7 },
  learnedIcon: { width: 25, height: 25, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  learnedIconRisk: { backgroundColor: "#FFF1F1" },
  learnedIconGood: { backgroundColor: palette.greenSoft },
  learnedTitle: { color: palette.dark, fontSize: 12, fontWeight: "900" },
  bulletText: { color: palette.dark, fontSize: 11, lineHeight: 18, fontWeight: "700" },
  scoreRow: { minHeight: 31, flexDirection: "row", alignItems: "center", gap: 10 },
  scoreLabel: { width: 118, color: palette.dark, fontSize: 10, fontWeight: "800" },
  scoreTrack: { flex: 1, height: 8, borderRadius: 999, backgroundColor: "#ECF1ED", overflow: "hidden" },
  scoreFill: { height: "100%", borderRadius: 999 },
  scoreValue: { width: 45, color: palette.dark, fontSize: 10, fontWeight: "900", textAlign: "right" },
  infoBox: { borderRadius: 14, borderWidth: 1, borderColor: "#CFEFD8", backgroundColor: "#F4FFF7", padding: 12, marginTop: 10 },
  infoTitle: { color: palette.green, fontSize: 11, fontWeight: "900" },
  infoText: { color: palette.muted, fontSize: 10, fontWeight: "700", marginTop: 6 },
  clearButton: { minHeight: 45, borderRadius: 14, borderWidth: 1, borderColor: "#F8CACA", backgroundColor: "#FFF8F8", alignItems: "center", justifyContent: "center", marginTop: 13 },
  clearButtonText: { color: palette.red, fontSize: 12, fontWeight: "900" },
  dangerText: { color: palette.red },
  footerNote: { backgroundColor: "#F0FBF4", borderColor: "#CFEFD8", alignItems: "center", justifyContent: "center" },
  footerText: { color: palette.dark, fontSize: 12, lineHeight: 17, fontWeight: "800", textAlign: "center" },
  modalOverlay: { flex: 1, backgroundColor: "rgba(23,33,58,0.24)", alignItems: "center", justifyContent: "center", padding: 26 },
  modalCard: { width: "100%", maxWidth: 360, borderRadius: 22, backgroundColor: "#FFFFFF", padding: 18, borderWidth: 1, borderColor: palette.border, shadowColor: "#000", shadowOpacity: 0.18, shadowRadius: 30, shadowOffset: { width: 0, height: 16 } },
  modalTitle: { color: palette.dark, fontSize: 18, fontWeight: "900" },
  modalText: { color: palette.muted, fontSize: 12, lineHeight: 18, fontWeight: "700", marginTop: 8 },
  modalButton: { minHeight: 43, borderRadius: 14, backgroundColor: palette.green, alignItems: "center", justifyContent: "center", marginTop: 16 },
  modalButtonText: { color: "#FFFFFF", fontSize: 13, fontWeight: "900" },
  modalActions: { flexDirection: "row", gap: 10, marginTop: 16 },
  cancelButton: { flex: 1, minHeight: 43, borderRadius: 14, borderWidth: 1, borderColor: palette.border, alignItems: "center", justifyContent: "center" },
  cancelText: { color: palette.dark, fontSize: 13, fontWeight: "900" },
  confirmButton: { flex: 1, minHeight: 43, borderRadius: 14, backgroundColor: palette.green, alignItems: "center", justifyContent: "center" },
  confirmDanger: { backgroundColor: palette.red },
  confirmText: { color: "#FFFFFF", fontSize: 13, fontWeight: "900" },
  choiceList: { gap: 9, marginTop: 14 },
  choiceButton: { minHeight: 42, borderRadius: 14, borderWidth: 1, borderColor: palette.border, justifyContent: "center", paddingHorizontal: 13 },
  choiceButtonActive: { backgroundColor: palette.greenSoft, borderColor: palette.green },
  choiceText: { color: palette.dark, fontSize: 13, fontWeight: "800" },
  choiceTextActive: { color: palette.green, fontWeight: "900" },
  multiGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 14 },
  multiChip: { borderRadius: 999, borderWidth: 1, borderColor: palette.border, paddingHorizontal: 12, paddingVertical: 9 },
  multiChipActive: { backgroundColor: palette.greenSoft, borderColor: palette.green },
  multiChipText: { color: palette.dark, fontSize: 12, fontWeight: "800" },
  multiChipTextActive: { color: palette.green, fontWeight: "900" },
  inputWrap: { marginTop: 14, borderWidth: 1, borderColor: palette.border, borderRadius: 14, minHeight: 48, flexDirection: "row", alignItems: "center", paddingHorizontal: 12 },
  editorInput: { flex: 1, color: palette.dark, fontSize: 16, fontWeight: "800", outlineStyle: "none" },
  inputSuffix: { color: palette.muted, fontSize: 12, fontWeight: "900" }
});
