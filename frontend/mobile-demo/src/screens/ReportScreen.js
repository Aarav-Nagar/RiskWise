import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Card } from "../components/Card";
import { ConfidenceRing, IntelligenceStrip, MiniLineChart } from "../components/InsightVisuals";
import { Pill } from "../components/Pill";
import { Header, PrimaryButton, SecondaryButton, ScreenScroll, sharedText } from "../components/Shared";
import { getOptionsContext } from "../services/apiClient";
import { palette } from "../theme/theme";

export function ReportScreen({ report, onAskAi, onSave, saveStatus }) {
  const [labelOpen, setLabelOpen] = useState(false);
  const [activePanel, setActivePanel] = useState("Overview");
  const [marketContext, setMarketContext] = useState(null);

  useEffect(() => {
    let mounted = true;
    async function loadMarketContext() {
      if (!report?.ticker) {
        return;
      }
      try {
        const context = await getOptionsContext(report.ticker);
        if (mounted) {
          setMarketContext(context);
        }
      } catch (err) {
        if (mounted) {
          setMarketContext(null);
        }
      }
    }
    loadMarketContext();
    return () => {
      mounted = false;
    };
  }, [report?.ticker]);

  if (!report) {
    return (
      <ScreenScroll>
        <Header title="No report yet" subtitle="Run a check first to generate a trade report." />
      </ScreenScroll>
    );
  }

  return (
    <ScreenScroll>
      <Header title={`${report.ticker} Risk Brief`} subtitle={report.subtitle} right={<Pill label={report.riskPosture} tone="good" />} />
      <View style={styles.methodology}>
        <Text style={styles.methodologyText}>{report.methodologyLabel || "Educational risk review"} - not financial advice</Text>
      </View>
      <IntelligenceStrip
        agreement={report.agentAgreement}
        agents={Array.isArray(report.agentDocket) ? Math.min(5, report.agentDocket.length || 5) : 5}
        pattern={report.weakestLink ? `${report.weakestLink} is the pressure point` : "Risk-balanced setup"}
        missing={report.dataQuality?.missing?.length ?? marketContext?.fields_pending?.length ?? 2}
      />

      <Card style={styles.heroCard}>
        <View style={styles.heroTop}>
          <View style={styles.heroCopy}>
            <Text style={styles.overall}>{report.overallRead}</Text>
            <Text style={sharedText.bodyText}>{report.insight}</Text>
          </View>
          <ConfidenceRing value={report.setupScore} label="setup" sublabel="quality" />
        </View>
        <View style={styles.heroChart}>
          <MiniLineChart data={buildConfidenceCurve(report)} height={78} />
        </View>
        <View style={styles.heroFooter}>
          <View style={styles.weakPill}>
            <Text style={styles.weakLabel}>Weakest Link</Text>
            <Text style={styles.weakText}>{report.weakestLink}</Text>
          </View>
          <View style={styles.weakPillAlt}>
            <Text style={styles.weakLabel}>Risk Posture</Text>
            <Text style={styles.weakText}>{report.riskPosture}</Text>
          </View>
        </View>
      </Card>

      <MarketDataStatus context={marketContext} />

      <PanelTabs activePanel={activePanel} setActivePanel={setActivePanel} />

      {activePanel === "Overview" ? (
        <OverviewPanel report={report} labelOpen={labelOpen} setLabelOpen={setLabelOpen} />
      ) : null}
      {activePanel === "Risk Math" ? <RiskMathPanel report={report} /> : null}
      {activePanel === "Debate" ? <DebatePanel report={report} /> : null}
      {activePanel === "Agents" ? <AgentsPanel report={report} /> : null}

      <View style={styles.actionRow}>
        <SecondaryButton label="Save Check" onPress={onSave} />
        <PrimaryButton label="Ask Coach" onPress={onAskAi} style={styles.actionGrow} />
      </View>
      {saveStatus ? <Text style={styles.saveStatus}>{saveStatus}</Text> : null}
    </ScreenScroll>
  );
}

function PanelTabs({ activePanel, setActivePanel }) {
  const panels = ["Overview", "Risk Math", "Debate", "Agents"];
  return (
    <View style={styles.panelTabs}>
      {panels.map((panel) => (
        <Pressable key={panel} style={[styles.panelTab, activePanel === panel && styles.panelTabActive]} onPress={() => setActivePanel(panel)}>
          <Text style={[styles.panelTabText, activePanel === panel && styles.panelTabTextActive]}>{panel}</Text>
        </Pressable>
      ))}
    </View>
  );
}

function OverviewPanel({ report, labelOpen, setLabelOpen }) {
  return (
    <Card>
      <Pressable style={styles.contractToggle} onPress={() => setLabelOpen((open) => !open)}>
        <View>
          <Text style={sharedText.sectionTitle}>Contract Label</Text>
          <Text style={sharedText.bodyText}>Open only if you want the option-style nutrition label.</Text>
        </View>
        <View style={styles.openPill}>
          <Text style={styles.openText}>{labelOpen ? "Hide" : "Open"}</Text>
          <Ionicons name={labelOpen ? "chevron-up" : "chevron-down"} size={15} color={palette.green} />
        </View>
      </Pressable>
      {labelOpen ? <ContractLabel label={report.contractLabel || {}} /> : null}

      <View style={styles.panelDivider} />
      <Text style={sharedText.sectionTitle}>Decision Snapshot</Text>
      <View style={styles.snapshotGrid}>
        <ScoreTile label="Setup" value={report.decisionSnapshot.setup_quality ?? report.setupScore} suffix="/100" />
        <ScoreTile label="Options" value={report.decisionSnapshot.options_structure ?? 58} suffix="/100" />
        <ScoreTile label="Risk Used" value={report.decisionSnapshot.risk_budget_used ?? 0} suffix="%" risk={(report.decisionSnapshot.risk_budget_used ?? 0) > 2} />
        <ScoreTile label="Review Gap" value={report.decisionSnapshot.agent_disagreement || "Med"} />
      </View>

      <View style={styles.panelDivider} />
      <Text style={sharedText.sectionTitle}>Questions Before Acting</Text>
      {report.questions.map((question, index) => (
        <View key={question} style={styles.questionRow}>
          <Text style={styles.questionNumber}>{index + 1}</Text>
          <Text style={styles.questionText}>{question}</Text>
        </View>
      ))}
    </Card>
  );
}

function RiskMathPanel({ report }) {
  return (
    <Card>
      <Text style={sharedText.sectionTitle}>Risk Math</Text>
      <RiskCurve report={report} />
      <View style={styles.mathGrid}>
        <MathItem label="Max loss" value={money(report.riskMath.max_loss)} />
        <MathItem label="50% drawdown" value={money(report.riskMath.half_premium_drawdown)} risk />
        <MathItem label="Above profile" value={money(report.riskMath.amount_above_profile)} risk={Number(report.riskMath.amount_above_profile || 0) > 0} />
        <MathItem label="Breakeven move" value={`${report.riskMath.required_move_to_breakeven_pct ?? "?"}%`} />
        <MathItem label="Trading days" value={`${report.riskMath.trading_days_left ?? "?"}`} />
        <MathItem label="Calendar days" value={`${report.riskMath.calendar_days_left ?? "?"}`} />
        <MathItem label="Planned hold" value={`${report.riskMath.planned_hold_days ?? "?"}d`} />
        <MathItem label="Capital at risk" value={money(report.riskMath.capital_at_risk)} />
      </View>

      <View style={styles.panelDivider} />
      <Text style={sharedText.sectionTitle}>Agreement Map</Text>
      <Text style={styles.conflict}>{report.agreementMap.main_conflict}</Text>
      <MapList title="What lines up" items={report.agreementMap.agree || []} good />
      <MapList title="Needs caution" items={report.agreementMap.disagree || []} />
    </Card>
  );
}

function DebatePanel({ report }) {
  const debate = report.setupDebate || {};
  return (
    <Card>
      <Text style={sharedText.sectionTitle}>Setup Debate</Text>
      <Text style={styles.debateIntro}>
        RiskWise treats the idea like a committee conversation: one voice argues why the setup is interesting,
        one tries to break it, and the risk judge decides what evidence is still missing.
      </Text>
      <ConversationBubble
        speaker="Bull Analyst"
        tone="good"
        text={`${debate.bull_case || "The setup may be worth studying if trend, timing, and volatility line up."} The constructive read is not that the trade is automatically good; it is that the idea has a clean thesis that can be tested. If price confirms, the contract has enough time, and the risk stays inside the user's rule set, the setup becomes easier to explain and review.`}
      />
      <ConversationBubble
        speaker="Skeptic"
        tone="warn"
        text={`${debate.bear_case || "The option can still lose from time decay, weak follow-through, or volatility compression."} The uncomfortable part is that direction is only one input. A long option also needs timing and volatility to cooperate. If the move is slow, if implied volatility falls, or if the spread is wide, the stock can be directionally correct while the contract still disappoints.`}
      />
      <ConversationBubble
        speaker="Risk Judge"
        tone="neutral"
        text={`${debate.risk_judge || "Sizing and contract timing decide whether the idea is manageable."} I would want the user to answer three things before giving this setup any confidence: what invalidates the thesis, how much premium can disappear before the plan is wrong, and whether this same idea still makes sense if the option loses half its value quickly.`}
      />
      <ConversationBubble
        speaker="Coach Takeaway"
        tone="coach"
        text={`The useful conclusion is not a buy or sell call. It is a checklist: define the catalyst, compare required move versus realistic move, keep premium risk inside the rule set, and avoid treating a high-upside payoff diagram as proof that the setup is high quality.`}
      />
    </Card>
  );
}

function AgentsPanel({ report }) {
  return (
    <Card>
      <Text style={sharedText.sectionTitle}>Review Panel</Text>
      <Text style={styles.agentPanelSub}>Each agent scores a different failure mode. The useful part is disagreement, not fake certainty.</Text>
      {report.agentDocket.map((agent) => (
        <AgentRow key={agent.name} agent={agent} />
      ))}
    </Card>
  );
}

function RiskCurve({ report }) {
  const risk = Number(report.riskMath?.risk_percent_of_account || 2);
  const days = Number(report.riskMath?.trading_days_left || 15);
  const curve = [22, 24 + risk * 5, 29 + risk * 7, 38 + Math.max(0, 12 - days), 44 + risk * 6, 52 + Math.max(0, 8 - days) * 2];
  return (
    <View style={styles.riskCurve}>
      <View style={styles.curveHeader}>
        <View>
          <Text style={styles.curveTitle}>Risk pressure curve</Text>
          <Text style={styles.curveSub}>Sizing, time decay, and breakeven pressure</Text>
        </View>
        <Text style={styles.curveBadge}>{risk.toFixed(1)}%</Text>
      </View>
      <MiniLineChart data={curve} height={74} stroke={risk > 2 ? palette.teal : palette.green} fill={risk > 2 ? "rgba(14,165,233,0.14)" : "rgba(22,163,74,0.14)"} />
    </View>
  );
}

function MarketDataStatus({ context }) {
  const pending = context?.fields_pending || ["option_chain", "implied_volatility", "expiration_dates", "earnings_dates", "live_premium"];
  return (
    <Card style={styles.dataCard}>
      <View style={styles.dataHeader}>
        <View>
          <Text style={sharedText.sectionTitle}>Market Data Status</Text>
          <Text style={styles.dataSub}>Current report uses user-entered contract details.</Text>
        </View>
        <View style={styles.dataBadge}>
          <Text style={styles.dataBadgeText}>{context?.status === "configured_not_enabled" ? "Ready" : "Planned"}</Text>
        </View>
      </View>
      <View style={styles.dataChips}>
        {pending.slice(0, 5).map((field) => (
          <Text key={field} style={styles.dataChip}>{field.replaceAll("_", " ")}</Text>
        ))}
      </View>
    </Card>
  );
}

function ContractLabel({ label }) {
  return (
    <View style={styles.contractLabel}>
      <LabelRow label="Max Loss" value={money(label.max_loss)} />
      <LabelRow label="Account Risk" value={`${label.account_risk_pct ?? "?"}%`} />
      <LabelRow label="Break-even" value={label.breakeven ? `$${Number(label.breakeven).toLocaleString()}` : "Unknown"} />
      <LabelRow label="Days Left" value={label.days_left ?? "?"} />
      <LabelRow label="Required Move" value={`${label.required_move_pct ?? "?"}%`} />
      <LabelRow label="Theta Risk" value={label.theta_risk || "Unknown"} />
      <LabelRow label="IV/Event Risk" value={label.iv_event_risk || "Unknown"} />
      <LabelRow label="Difficulty" value={label.difficulty || "Review"} strong />
    </View>
  );
}

function LabelRow({ label, value, strong }) {
  return (
    <View style={styles.labelRow}>
      <Text style={styles.labelKey}>{label}</Text>
      <Text style={[styles.labelValue, strong && styles.labelStrong]}>{value}</Text>
    </View>
  );
}

function DebateCard({ title, text, tone }) {
  return (
    <View style={[styles.debateCard, tone === "good" && styles.debateGood, tone === "warn" && styles.debateWarn]}>
      <Text style={styles.debateTitle}>{title}</Text>
      <Text style={styles.debateText}>{text || "No read available yet."}</Text>
    </View>
  );
}

function ConversationBubble({ speaker, text, tone }) {
  return (
    <View style={[styles.conversationBubble, tone === "good" && styles.conversationGood, tone === "warn" && styles.conversationWarn, tone === "coach" && styles.conversationCoach]}>
      <View style={styles.conversationHeader}>
        <Text style={styles.conversationSpeaker}>{speaker}</Text>
        <View style={styles.conversationDot} />
      </View>
      <Text style={styles.conversationText}>{text}</Text>
    </View>
  );
}

function ScoreTile({ label, value, suffix = "", risk }) {
  return (
    <View style={styles.scoreTile}>
      <Text style={styles.tileLabel}>{label}</Text>
      <Text style={[styles.tileValue, risk && styles.riskText]}>{value}{suffix}</Text>
    </View>
  );
}

function MathItem({ label, value, risk }) {
  return (
    <View style={styles.mathItem}>
      <Text style={styles.tileLabel}>{label}</Text>
      <Text style={[styles.mathValue, risk && styles.riskText]}>{value}</Text>
    </View>
  );
}

function AgentRow({ agent }) {
  const color = agent.score < 60 ? palette.amber : agent.score > 72 ? palette.green : palette.teal;
  return (
    <View style={styles.agentRow}>
      <View style={styles.agentTop}>
        <View>
          <Text style={styles.agentName}>{agent.name}</Text>
          <Text style={styles.agentRead}>{agent.read}</Text>
        </View>
        <Text style={[styles.agentScore, { color }]}>{agent.score}</Text>
      </View>
      <View style={styles.agentTrack}>
        <View style={[styles.agentFill, { width: `${agent.score}%`, backgroundColor: color }]} />
      </View>
      {agent.focus ? <Text style={styles.agentFocus}>{agent.focus}</Text> : null}
      <AgentInsight label="Evidence" value={agent.evidence} />
      <AgentInsight label="Why it matters" value={agent.why_it_matters} />
      <AgentInsight label="Next question" value={agent.next_question} />
    </View>
  );
}

function AgentInsight({ label, value }) {
  if (!value) {
    return null;
  }
  return (
    <View style={styles.agentInsight}>
      <Text style={styles.agentInsightLabel}>{label}</Text>
      <Text style={styles.agentInsightText}>{value}</Text>
    </View>
  );
}

function MapList({ title, items, good }) {
  return (
    <View style={styles.mapBlock}>
      <Text style={styles.mapTitle}>{title}</Text>
      {items.map((item) => (
        <View key={item} style={styles.mapItem}>
          <Ionicons name={good ? "checkmark-circle" : "alert-circle"} size={15} color={good ? palette.green : palette.amber} />
          <Text style={styles.mapText}>{item}</Text>
        </View>
      ))}
    </View>
  );
}

function money(value) {
  const number = Number(value || 0);
  const sign = number < 0 ? "-" : "";
  return `${sign}$${Math.abs(number).toLocaleString()}`;
}

function buildConfidenceCurve(report) {
  const setup = Number(report.setupScore || 65);
  const options = Number(report.decisionSnapshot?.options_structure || setup - 8);
  const agreement = Number(report.agentAgreement || setup);
  const risk = Number(report.riskScore || 5);
  return [
    Math.max(20, setup - 18),
    Math.max(20, options - 8),
    Math.max(20, agreement - 12),
    Math.max(20, 78 - risk * 4),
    Math.max(20, setup - 4),
    agreement
  ];
}

const styles = StyleSheet.create({
  methodology: {
    backgroundColor: "#F3FBFF",
    borderColor: "#CFEFFF",
    borderWidth: 1,
    borderRadius: 14,
    paddingVertical: 9,
    paddingHorizontal: 12,
    marginBottom: 12
  },
  methodologyText: {
    color: palette.teal,
    fontSize: 11,
    fontWeight: "800"
  },
  heroCard: {
    backgroundColor: "#FBFFFC",
    borderColor: "#CFEFD8"
  },
  heroTop: {
    flexDirection: "row",
    gap: 14,
    alignItems: "flex-start"
  },
  heroCopy: {
    flex: 1
  },
  overall: {
    color: palette.dark,
    fontSize: 19,
    fontWeight: "900",
    lineHeight: 24,
    marginBottom: 7
  },
  scoreOrb: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 7,
    borderColor: "#CFEFD8",
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center"
  },
  scoreNumber: {
    color: palette.green,
    fontSize: 21,
    fontWeight: "900",
    lineHeight: 24
  },
  scoreLabel: {
    color: palette.muted,
    fontSize: 9,
    fontWeight: "900"
  },
  heroChart: {
    marginTop: 12,
    borderRadius: 18,
    backgroundColor: "rgba(234,248,238,0.55)",
    borderWidth: 1,
    borderColor: "rgba(207,239,216,0.8)",
    padding: 8
  },
  heroFooter: {
    flexDirection: "row",
    gap: 10,
    marginTop: 13
  },
  weakPill: {
    flex: 1,
    borderRadius: 16,
    backgroundColor: palette.greenSoft,
    borderWidth: 1,
    borderColor: "#CFEFD8",
    padding: 10
  },
  weakPillAlt: {
    flex: 1,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: palette.border,
    padding: 10
  },
  weakLabel: {
    color: palette.green,
    fontSize: 9,
    fontWeight: "900",
    marginBottom: 4
  },
  weakText: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  dataCard: {
    paddingVertical: 13
  },
  dataHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    alignItems: "flex-start"
  },
  dataSub: {
    color: palette.muted,
    fontSize: 11,
    lineHeight: 16,
    fontWeight: "800",
    marginTop: 3
  },
  dataBadge: {
    borderRadius: 999,
    backgroundColor: palette.greenSoft,
    paddingHorizontal: 10,
    paddingVertical: 6
  },
  dataBadgeText: {
    color: palette.green,
    fontSize: 10,
    fontWeight: "900"
  },
  dataChips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 7,
    marginTop: 10
  },
  dataChip: {
    color: palette.dark,
    fontSize: 10,
    fontWeight: "800",
    borderWidth: 1,
    borderColor: "#E2ECE3",
    backgroundColor: "#FBFDFB",
    borderRadius: 999,
    paddingHorizontal: 9,
    paddingVertical: 5,
    overflow: "hidden"
  },
  panelTabs: {
    flexDirection: "row",
    gap: 7,
    marginBottom: 12
  },
  panelTab: {
    flex: 1,
    minHeight: 39,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 6
  },
  panelTabActive: {
    backgroundColor: palette.green,
    borderColor: palette.green
  },
  panelTabText: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "900"
  },
  panelTabTextActive: {
    color: "#FFFFFF"
  },
  panelDivider: {
    height: 1,
    backgroundColor: palette.border,
    marginVertical: 14
  },
  contractToggle: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12
  },
  openPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    borderRadius: 999,
    backgroundColor: palette.greenSoft,
    paddingHorizontal: 10,
    paddingVertical: 7
  },
  openText: {
    color: palette.green,
    fontSize: 10,
    fontWeight: "900"
  },
  contractLabel: {
    marginTop: 12,
    borderWidth: 1,
    borderColor: "#DCEBDD",
    borderRadius: 16,
    backgroundColor: "#FBFFFC",
    overflow: "hidden"
  },
  labelRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 14,
    borderBottomWidth: 1,
    borderBottomColor: "#EAF2EA",
    paddingVertical: 10,
    paddingHorizontal: 12
  },
  labelKey: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "900"
  },
  labelValue: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  labelStrong: {
    color: palette.green
  },
  snapshotGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10
  },
  scoreTile: {
    width: "48.3%",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FCFDFC",
    padding: 13
  },
  tileLabel: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "900",
    marginBottom: 5
  },
  tileValue: {
    color: palette.dark,
    fontSize: 21,
    fontWeight: "900"
  },
  mathGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 9
  },
  riskCurve: {
    borderRadius: 18,
    backgroundColor: "#FBFEFB",
    borderWidth: 1,
    borderColor: "#E2EEE4",
    padding: 12,
    marginBottom: 12
  },
  curveHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 12,
    marginBottom: 6
  },
  curveTitle: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900"
  },
  curveSub: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 2
  },
  curveBadge: {
    color: palette.green,
    backgroundColor: palette.greenSoft,
    borderRadius: 999,
    overflow: "hidden",
    paddingHorizontal: 9,
    paddingVertical: 5,
    fontSize: 10,
    fontWeight: "900"
  },
  mathItem: {
    width: "31.3%",
    minHeight: 76,
    borderRadius: 14,
    backgroundColor: "#F8FAF8",
    borderWidth: 1,
    borderColor: palette.border,
    padding: 10,
    justifyContent: "center"
  },
  mathValue: {
    color: palette.dark,
    fontSize: 15,
    fontWeight: "900"
  },
  riskText: {
    color: palette.red
  },
  debateGrid: {
    gap: 9
  },
  debateCard: {
    borderRadius: 15,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FFFFFF",
    padding: 12
  },
  debateGood: {
    backgroundColor: "#FBFFFC",
    borderColor: "#D7F0DE"
  },
  debateWarn: {
    backgroundColor: "#F3FBFF",
    borderColor: "#CFEFFF"
  },
  debateTitle: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900",
    marginBottom: 5
  },
  debateText: {
    color: palette.muted,
    fontSize: 11,
    lineHeight: 16,
    fontWeight: "800"
  },
  debateIntro: {
    color: palette.dark,
    fontSize: 12,
    lineHeight: 18,
    fontWeight: "800",
    marginBottom: 10
  },
  conversationBubble: {
    borderRadius: 17,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FFFFFF",
    padding: 13,
    marginTop: 9
  },
  conversationGood: {
    borderColor: "#CFEFD8",
    backgroundColor: "#FBFFFC"
  },
  conversationWarn: {
    borderColor: "#CFEFFF",
    backgroundColor: "#F6FCFF"
  },
  conversationCoach: {
    borderColor: "#D7F0DE",
    backgroundColor: palette.greenSoft
  },
  conversationHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 7
  },
  conversationSpeaker: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  conversationDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: palette.green
  },
  conversationText: {
    color: palette.dark,
    fontSize: 12,
    lineHeight: 18,
    fontWeight: "800"
  },
  agentRow: {
    borderTopWidth: 1,
    borderTopColor: palette.border,
    paddingTop: 12,
    marginTop: 12
  },
  agentPanelSub: {
    color: palette.muted,
    fontSize: 11,
    lineHeight: 16,
    fontWeight: "800",
    marginBottom: 4
  },
  agentTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    alignItems: "center"
  },
  agentName: {
    color: palette.dark,
    fontSize: 14,
    fontWeight: "900"
  },
  agentRead: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "800",
    marginTop: 2
  },
  agentScore: {
    fontSize: 22,
    fontWeight: "900"
  },
  agentTrack: {
    height: 8,
    borderRadius: 999,
    backgroundColor: "#ECF0ED",
    overflow: "hidden",
    marginVertical: 9
  },
  agentFill: {
    height: "100%"
  },
  agentFocus: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900",
    lineHeight: 17,
    marginBottom: 8
  },
  agentInsight: {
    borderTopWidth: 1,
    borderTopColor: "#EEF2EF",
    paddingTop: 8,
    marginTop: 8
  },
  agentInsightLabel: {
    color: palette.green,
    fontSize: 9,
    fontWeight: "900",
    textTransform: "uppercase",
    marginBottom: 4
  },
  agentInsightText: {
    color: palette.dark,
    fontSize: 11,
    lineHeight: 16,
    fontWeight: "800"
  },
  conflict: {
    color: palette.dark,
    fontSize: 14,
    fontWeight: "900",
    marginBottom: 12
  },
  mapBlock: {
    marginTop: 10
  },
  mapTitle: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "900",
    marginBottom: 7
  },
  mapItem: {
    flexDirection: "row",
    gap: 8,
    alignItems: "flex-start",
    marginBottom: 8
  },
  mapText: {
    flex: 1,
    color: palette.dark,
    fontSize: 12,
    fontWeight: "800",
    lineHeight: 17
  },
  questionRow: {
    flexDirection: "row",
    gap: 10,
    alignItems: "flex-start",
    borderTopWidth: 1,
    borderTopColor: palette.border,
    paddingVertical: 10
  },
  questionNumber: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: palette.greenSoft,
    color: palette.green,
    textAlign: "center",
    lineHeight: 24,
    fontSize: 12,
    fontWeight: "900"
  },
  questionText: {
    flex: 1,
    color: palette.dark,
    fontSize: 13,
    fontWeight: "800",
    lineHeight: 18
  },
  actionRow: {
    flexDirection: "row",
    gap: 10,
    marginBottom: 12
  },
  actionGrow: {
    flex: 1
  },
  saveStatus: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "800",
    textAlign: "center",
    marginBottom: 12
  }
});
