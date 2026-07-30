import React, { useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Alert, Image, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, useWindowDimensions, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as Clipboard from "expo-clipboard";
import * as DocumentPicker from "expo-document-picker";
import * as FileSystem from "expo-file-system";
import * as ImagePicker from "expo-image-picker";
import * as Sharing from "expo-sharing";
import { fetchAlternatives, getSavedCheckExport, gradeChallenge, listChatMessages, listChatThreads, startChallenge, streamChatMessage } from "../services/apiClient";
import { palette } from "../theme/theme";

const askModes = ["Explain", "Challenge", "Alternatives"];

const demoCoachTrades = [
  { id: "demo-aapl", ticker: "AAPL", tradeType: "7D Call @ $200", expiration: "Jun 7, 2025", contracts: 1, maxLoss: "$320", maxLossPct: "3.2%", breakeven: "$203.20", dte: "7 days", iv: "27.3%", liquidity: "Medium" },
  { id: "demo-tsla", ticker: "TSLA", tradeType: "14D Put @ $180", expiration: "Jun 10, 2025", contracts: 1, maxLoss: "$410", maxLossPct: "2.8%", breakeven: "$175.90", dte: "14 days", iv: "31.8%", liquidity: "Medium" },
  { id: "demo-nvda", ticker: "NVDA", tradeType: "21D Call @ $950", expiration: "Jun 9, 2025", contracts: 1, maxLoss: "$680", maxLossPct: "4.1%", breakeven: "$956.80", dte: "21 days", iv: "35.1%", liquidity: "High" },
  { id: "demo-spy", ticker: "SPY", tradeType: "5D Put @ $525", expiration: "Jun 6, 2025", contracts: 2, maxLoss: "$250", maxLossPct: "1.0%", breakeven: "$523.75", dte: "5 days", iv: "18.4%", liquidity: "High" }
];

const challengeTopics = ["Thesis & Timing", "Breakeven", "Risk & Size", "IV & Volatility", "Exit Plan"];

export function ChatScreen({ user, currentReport, savedChecks = [], navigate }) {
  const [threadId, setThreadId] = useState(null);
  const [threads, setThreads] = useState([]);
  const [messages, setMessages] = useState([initialGreeting(user)]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [chatMode, setChatMode] = useState("Explain");
  const [selectedTrade, setSelectedTrade] = useState(currentReport || null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const [attachmentMenuOpen, setAttachmentMenuOpen] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [exportPreview, setExportPreview] = useState(null);
  const [exportStatus, setExportStatus] = useState("");
  const [sheet, setSheet] = useState(null);
  const [challengeStarted, setChallengeStarted] = useState(false);
  const [challengeIndex, setChallengeIndex] = useState(0);
  const [answerDraft, setAnswerDraft] = useState("");
  const [challengeAnswers, setChallengeAnswers] = useState([]);
  const [challengeSession, setChallengeSession] = useState(null);
  const [challengeResult, setChallengeResult] = useState(null);
  const [challengeLoading, setChallengeLoading] = useState(false);
  const [conviction, setConviction] = useState("");
  const [direction, setDirection] = useState("bullish");
  const [alternativeDetail, setAlternativeDetail] = useState(null);
  const scrollRef = useRef(null);
  const tradeOptions = useMemo(() => buildTradeOptions(currentReport, savedChecks), [currentReport, savedChecks]);
  const selectedSavedCheck = useMemo(
    () => findSelectedSavedCheck(selectedTrade, savedChecks),
    [selectedTrade, savedChecks]
  );

  useEffect(() => {
    if (currentReport && !selectedTrade) {
      setSelectedTrade(currentReport);
    }
  }, [currentReport?.id]);

  useEffect(() => {
    requestAnimationFrame(() => scrollRef.current?.scrollToEnd?.({ animated: true }));
  }, [messages.length, loading]);

  async function submit(text = input, options = {}) {
    const clean = text.trim();
    if ((!clean && attachments.length === 0) || loading) {
      return;
    }
    const analysisDepth = options.analysisDepth || "standard";
    const outgoingAttachments = attachments;
    const messageText = clean || "Review these attachments.";
    setInput("");
    setAttachments([]);
    setAttachmentMenuOpen(false);
    setUploadStatus("");
    setMessages((items) => [...items, { role: "user", content: messageText, attachments: outgoingAttachments }]);
    setLoading(true);

    // Progressive reveal: a "Thinking..." bubble (via `loading`) covers the full compute + guard
    // pass; once `meta` lands we swap in a streaming assistant bubble and append `delta` chunks.
    const placeholderId = `assistant-stream-${Date.now()}`;
    let placeholderAdded = false;
    let receivedContent = false;
    const updateStreaming = (patch) =>
      setMessages((items) => items.map((m) => (m.id === placeholderId ? { ...m, ...patch } : m)));
    const ensurePlaceholder = (patch = {}) => {
      setLoading(false);
      if (placeholderAdded) {
        updateStreaming(patch);
      } else {
        placeholderAdded = true;
        setMessages((items) => [...items, { role: "assistant", id: placeholderId, content: "", streaming: true, ...patch }]);
      }
    };

    try {
      await streamChatMessage({
        user,
        threadId,
        message: messageText,
        currentReport: selectedTrade,
        chatMode,
        analysisDepth,
        attachments: outgoingAttachments,
        onMeta: (meta) => {
          if (meta.thread_id) {
            setThreadId(meta.thread_id);
          }
          ensurePlaceholder({
            mode: meta.mode,
            analysisDepth: meta.analysis_depth,
            confidence: meta.confidence,
            missingData: meta.missing_data || [],
            riskFlags: meta.risk_flags || [],
            toolsUsed: meta.tools_used || [],
            whatUsed: meta.what_used || [],
            summaryCards: meta.summary_cards || [],
            visualBlocks: meta.visual_blocks || [],
            agentDocket: meta.agent_docket || [],
            provider: meta.provider,
            usedFallback: meta.used_fallback,
            suggestedPrompts: meta.suggested_prompts || []
          });
        },
        onDelta: (chunk) => {
          if (!chunk) {
            return;
          }
          receivedContent = true;
          if (!placeholderAdded) {
            ensurePlaceholder();
          }
          setMessages((items) => items.map((m) => (m.id === placeholderId ? { ...m, content: (m.content || "") + chunk } : m)));
        },
        onDone: (data) => {
          if (data?.thread_id) {
            setThreadId(data.thread_id);
          }
          ensurePlaceholder({ streaming: false });
          if (historyOpen) {
            refreshThreads();
          }
        }
      });
      if (placeholderAdded && !receivedContent) {
        updateStreaming({ streaming: false, content: "The coach didn't return an answer. Please try again in a moment." });
      }
    } catch (err) {
      if (placeholderAdded) {
        updateStreaming({
          streaming: false,
          content: "The coach is unavailable right now. Your checks are still saved, and you can try again in a moment."
        });
      } else {
        setMessages((items) => [
          ...items,
          {
            role: "assistant",
            content: "The coach is unavailable right now. Your checks are still saved, and you can try again in a moment.",
            mode: "fallback"
          }
        ]);
      }
    } finally {
      setLoading(false);
    }
  }

  async function openThread(thread) {
    setHistoryOpen(false);
    setThreadId(thread.id);
    setChatMode(thread.mode || "Explain");
    setLoading(true);
    try {
      const rows = await listChatMessages(user, thread.id);
      const loaded = rows.map((row) => ({
        role: row.role,
        content: row.content,
        attachments: row.attachments || [],
        mode: row.mode
      }));
      setMessages(loaded.length ? loaded : [initialGreeting(user)]);
    } catch (err) {
      setMessages([initialGreeting(user), { role: "assistant", content: "I could not load that conversation yet. Try another thread." }]);
    } finally {
      setLoading(false);
    }
  }

  function newThread() {
    setThreadId(null);
    setMessages([initialGreeting(user)]);
    setHistoryOpen(false);
    setAttachments([]);
    setAttachmentMenuOpen(false);
    setInput("");
  }

  async function refreshThreads() {
    try {
      const rows = await listChatThreads(user);
      setThreads(rows);
    } catch (err) {
      setThreads([]);
    }
  }

  function toggleHistory() {
    const next = !historyOpen;
    setHistoryOpen(next);
    if (next) {
      refreshThreads();
    }
  }

  function openAttachmentMenu() {
    setSheet("add-context");
  }

  async function selectUploadSource(source) {
    setAttachmentMenuOpen(false);
    if (source === "external_ai_export") {
      await openExternalAiExport();
      return;
    }
    if (source === "deep_analysis") {
      const prompt = selectedTrade
        ? `Run deep analysis on ${tradeTitle(selectedTrade)}.`
        : attachments.length
          ? "Run deep analysis on these attachments."
          : "Run deep analysis.";
      await submit(prompt, { analysisDepth: "deep_analysis" });
      return;
    }
    if (source === "upload" && Platform.OS !== "web") {
      openNativeUploadChooser();
      return;
    }
    if (source === "upload") {
      source = "files";
    }
    if (Platform.OS !== "web" || typeof document === "undefined") {
      await pickNativeAttachment(source);
      return;
    }
    const inputEl = document.createElement("input");
    inputEl.type = "file";
    inputEl.multiple = source !== "camera";
    if (source === "camera") {
      inputEl.accept = "image/*";
      inputEl.capture = "environment";
    } else if (source === "library") {
      inputEl.accept = "image/*";
    } else {
      inputEl.accept = "image/*,.txt,.csv,.pdf";
    }
    inputEl.onchange = async () => {
      const files = Array.from(inputEl.files || []).slice(0, 4);
      setUploadStatus(files.length ? `Reading ${uploadSourceLabel(source).toLowerCase()}...` : "");
      const parsed = await Promise.all(files.map((file) => readAttachment(file, source)));
      setAttachments((items) => [...items, ...parsed].slice(0, 4));
      setUploadStatus(parsed.length ? `${parsed.length} ${parsed.length === 1 ? "item" : "items"} added from ${uploadSourceLabel(source)}. Ask RiskWiseAI to review them.` : "");
    };
    inputEl.click();
  }

  function openNativeUploadChooser() {
    Alert.alert(
      "Add upload",
      "Choose where your screenshot, image, or file comes from.",
      [
        { text: "Take Photo", onPress: () => pickNativeAttachment("camera") },
        { text: "Photo Library", onPress: () => pickNativeAttachment("library") },
        { text: "Files", onPress: () => pickNativeAttachment("files") },
        { text: "Cancel", style: "cancel" }
      ]
    );
  }

  async function pickNativeAttachment(source) {
    try {
      setUploadStatus(`Opening ${uploadSourceLabel(source)}...`);
      if (source === "camera" || source === "library") {
        const permission =
          source === "camera"
            ? await ImagePicker.requestCameraPermissionsAsync()
            : await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (permission.status !== "granted") {
          setUploadStatus(`${uploadSourceLabel(source)} permission was not granted.`);
          return;
        }
        const result =
          source === "camera"
            ? await ImagePicker.launchCameraAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.75, base64: true })
            : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.75, base64: true, allowsMultipleSelection: true, selectionLimit: 4 });
        if (result.canceled) {
          setUploadStatus("");
          return;
        }
        const parsed = (result.assets || []).slice(0, 4).map((asset, index) => nativeImageAttachment(asset, source, index));
        setAttachments((items) => [...items, ...parsed].slice(0, 4));
        setUploadStatus(parsed.length ? `${parsed.length} ${parsed.length === 1 ? "image" : "images"} added from ${uploadSourceLabel(source)}.` : "");
        return;
      }
      const result = await DocumentPicker.getDocumentAsync({
        copyToCacheDirectory: true,
        multiple: true,
        type: ["image/*", "text/*", "application/pdf", "text/csv"]
      });
      if (result.canceled) {
        setUploadStatus("");
        return;
      }
      const parsed = (result.assets || []).slice(0, 4).map((asset) => ({
        name: asset.name || "uploaded-file",
        type: asset.mimeType || "application/octet-stream",
        size: asset.size || 0,
        source: "files",
        uri: asset.uri
      }));
      setAttachments((items) => [...items, ...parsed].slice(0, 4));
      setUploadStatus(parsed.length ? `${parsed.length} ${parsed.length === 1 ? "file" : "files"} added from Files.` : "");
    } catch (err) {
      setUploadStatus("Could not attach that file. Try a smaller image or file.");
    }
  }

  async function openExternalAiExport() {
    if (!selectedSavedCheck) {
      setUploadStatus("Select a saved Check before exporting for AI review.");
      return;
    }
    setExportModalOpen(true);
    setExportLoading(true);
    setExportPreview(null);
    setExportStatus("");
    try {
      const result = await getSavedCheckExport(user, selectedSavedCheck.id);
      setExportPreview(result);
    } catch (err) {
      setExportStatus(err?.message || "Could not build this export. Try again.");
    } finally {
      setExportLoading(false);
    }
  }

  async function copyExternalAiExport() {
    if (!exportPreview?.markdown) {
      return;
    }
    try {
      await Clipboard.setStringAsync(exportPreview.markdown);
      setExportStatus("Copied to clipboard.");
    } catch (err) {
      setExportStatus("Could not copy the export. You can select the preview text manually.");
    }
  }

  async function downloadExternalAiExport() {
    if (!exportPreview?.markdown) {
      return;
    }
    try {
      if (Platform.OS === "web" && typeof document !== "undefined") {
        const blob = new Blob([exportPreview.markdown], { type: "text/markdown;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = exportPreview.filename || "riskwise-check-export.md";
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        setExportStatus("Download started.");
        return;
      }
      if (!FileSystem.cacheDirectory) {
        throw new Error("No writable export directory is available.");
      }
      const filename = safeExportFilename(exportPreview.filename);
      const uri = `${FileSystem.cacheDirectory}${filename}`;
      await FileSystem.writeAsStringAsync(uri, exportPreview.markdown, {
        encoding: FileSystem.EncodingType.UTF8
      });
      if (!(await Sharing.isAvailableAsync())) {
        throw new Error("File sharing is not available on this device.");
      }
      await Sharing.shareAsync(uri, {
        dialogTitle: "Save RiskWise export",
        mimeType: "text/markdown",
        UTI: "net.daringfireball.markdown"
      });
      setExportStatus("Export file is ready.");
    } catch (err) {
      setExportStatus(err?.message || "Could not create the export file.");
    }
  }

  return (
    <View style={styles.screen}>
      <View style={styles.topBar}>
        <Pressable style={styles.iconButton} onPress={toggleHistory}>
          <Ionicons name="time-outline" size={19} color={historyOpen ? palette.green : palette.dark} />
        </Pressable>
        <View style={styles.modeRow}>
          {askModes.map((mode) => (
            <Pressable key={mode} style={[styles.modeButton, chatMode === mode && styles.modeButtonActive]} onPress={() => setChatMode(mode)}>
              <Text style={[styles.modeText, chatMode === mode && styles.modeTextActive]}>{mode}</Text>
            </Pressable>
          ))}
        </View>
        <Pressable style={styles.iconButton} onPress={newThread}>
          <Ionicons name="create-outline" size={18} color={palette.dark} />
        </Pressable>
      </View>

      {historyOpen ? <HistoryPanel threads={threads} activeId={threadId} onOpen={openThread} onNew={newThread} /> : null}

      {chatMode === "Challenge" ? (
        <ChallengeCoach
          selectedTrade={selectedTrade}
          started={challengeStarted}
          session={challengeSession}
          result={challengeResult}
          loading={challengeLoading}
          topicIndex={challengeIndex}
          answerDraft={answerDraft}
          answers={challengeAnswers}
          conviction={conviction}
          direction={direction}
          onConviction={setConviction}
          onDirection={setDirection}
          onAnswer={setAnswerDraft}
          onStart={startChallengeSession}
          onHowItWorks={() => setSheet("how-it-works")}
          onChangeTrade={() => setSheet("trade-context")}
          onSubmit={submitChallengeAnswer}
          onRestart={resetChallenge}
          onAlternatives={() => setChatMode("Alternatives")}
        />
      ) : null}

      {chatMode === "Alternatives" ? (
        <AlternativesCoach user={user} selectedTrade={selectedTrade} onChangeTrade={() => setSheet("trade-context")} onDetail={setAlternativeDetail} />
      ) : null}

      {chatMode === "Explain" ? (
        <>
      <Pressable style={styles.contextRow} onPress={() => setSheet("trade-context")}>
        <Text style={styles.contextValue} numberOfLines={1}>{selectedTrade ? tradeTitle(selectedTrade) : "No trade selected"}</Text>
        <Text style={styles.changeText}>Trade context</Text>
      </Pressable>
      {pickerOpen ? (
        <View style={styles.pickerPanel}>
          <TradeOption label="No trade" sub="General options questions" active={!selectedTrade} onPress={() => chooseTrade(null)} />
          {tradeOptions.map((option) => (
            <TradeOption
              key={option.key}
              label={tradeTitle(option.report)}
              sub={`${option.report.riskPosture || "Mixed"} risk - ${option.report.setupScore || "--"} setup`}
              active={selectedTrade?.id === option.report.id}
              onPress={() => chooseTrade(option.report)}
            />
          ))}
          <Pressable style={styles.newCheckRow} onPress={() => navigate?.("Check")}>
            <Ionicons name="add-circle-outline" size={16} color={palette.green} />
            <Text style={styles.newCheckText}>New check</Text>
          </Pressable>
        </View>
      ) : null}

      <ScrollView ref={scrollRef} style={styles.chatScroll} contentContainerStyle={styles.chatContent} showsVerticalScrollIndicator={false}>
        {messages.map((message, index) => (
          <MessageBubble key={message.id || `${message.role}-${index}-${(message.content || "").slice(0, 8)}`} message={message} />
        ))}
        {loading ? (
          <View style={[styles.bubble, styles.aiBubble]}>
            <View style={styles.thinkingRow}>
              <View style={styles.dot} />
            <Text style={styles.bubbleText}>{chatMode === "Review" ? "Reviewing..." : "Thinking..."}</Text>
            </View>
          </View>
        ) : null}
      </ScrollView>

      <View style={styles.composerWrap}>
        {attachmentMenuOpen ? (
          <AttachmentMenu
            onPick={selectUploadSource}
            onClose={() => setAttachmentMenuOpen(false)}
            canExport={Boolean(selectedSavedCheck)}
          />
        ) : null}
        {attachments.length ? <AttachmentTray attachments={attachments} onRemove={(index) => setAttachments((items) => items.filter((_, i) => i !== index))} /> : null}
        {uploadStatus ? <Text style={styles.uploadStatus}>{uploadStatus}</Text> : null}
        <View style={styles.inputRow}>
          <Pressable accessibilityLabel="Add context" style={[styles.plusButton, attachmentMenuOpen && styles.plusButtonActive]} onPress={openAttachmentMenu}>
            <Ionicons name="add" size={22} color={palette.green} />
          </Pressable>
          <TextInput
            value={input}
            onChangeText={setInput}
            placeholder="Ask RiskWiseAI"
            placeholderTextColor={palette.muted}
            style={styles.input}
            onSubmitEditing={() => submit()}
            returnKeyType="send"
            multiline
          />
          <Pressable accessibilityLabel="Send message" style={[styles.sendButton, (!input.trim() && !attachments.length || loading) && styles.sendDisabled]} onPress={() => submit()}>
            <Ionicons name="arrow-up" size={18} color="#FFFFFF" />
          </Pressable>
        </View>
        <Text style={styles.disclaimerText}>Educational only. Not financial advice.</Text>
      </View>
      <ExportReviewModal
        visible={exportModalOpen}
        loading={exportLoading}
        exportData={exportPreview}
        status={exportStatus}
        onClose={() => setExportModalOpen(false)}
        onCopy={copyExternalAiExport}
        onDownload={downloadExternalAiExport}
      />
        </>
      ) : null}
      <CoachSheet visible={sheet === "add-context"} onClose={() => setSheet(null)}>
        <Text style={styles.coachSheetTitle}>Add context</Text>
        <SheetAction icon="cloud-upload-outline" title="Upload" subtitle="Photo, screenshot, PDF, CSV, or text" onPress={() => selectUploadSource("upload")} />
        <SheetAction icon="albums-outline" title="Select saved Check or trade" subtitle="Choose context for Coach modes" onPress={() => setSheet("trade-context")} />
        <SheetAction icon="document-text-outline" title="Export for AI Review" subtitle={selectedSavedCheck ? "Preview a saved Check as Markdown" : "Select a saved Check first"} disabled={!selectedSavedCheck} onPress={() => selectUploadSource("external_ai_export")} />
        <SheetAction icon="sparkles-outline" title="Deep Analysis" subtitle="Run the 5-agent committee" onPress={() => selectUploadSource("deep_analysis")} />
        <SheetAction icon="book-outline" title="Use Example" subtitle="Load a sample trade/report" onPress={() => { chooseTrade(demoCoachTrades[0]); setSheet(null); }} />
      </CoachSheet>
      <CoachSheet visible={sheet === "trade-context"} onClose={() => setSheet(null)}>
        <Text style={styles.coachSheetTitle}>Trade context</Text>
        <Text style={styles.coachSheetSub}>Select a trade</Text>
        {currentReport ? <TradeContextRow report={currentReport} active={selectedTrade?.id === currentReport.id} onPress={() => chooseTrade(currentReport)} /> : null}
        {tradeOptions.length ? <Text style={styles.coachSheetSection}>Saved trades</Text> : null}
        {tradeOptions.map((option) => <TradeContextRow key={option.key} report={option.report} active={selectedTrade?.id === option.report.id} onPress={() => chooseTrade(option.report)} />)}
        <Text style={styles.coachSheetSection}>Development examples</Text>
        {demoCoachTrades.map((report) => <TradeContextRow key={report.id} report={report} active={selectedTrade?.id === report.id} onPress={() => chooseTrade(report)} />)}
        <Pressable style={styles.coachSheetButton} onPress={() => { setSheet(null); navigate?.("Check"); }}>
          <Ionicons name="add-circle-outline" size={18} color={palette.green} />
          <Text style={styles.coachSheetButtonText}>Start a new Check</Text>
        </Pressable>
      </CoachSheet>
      <CoachSheet visible={sheet === "how-it-works"} onClose={() => setSheet(null)}>
        <Text style={styles.coachSheetTitle}>How this works</Text>
        <InfoSheetRow icon="help-buoy-outline" title="We ask questions" text="One at a time, focused on what matters most for your trade." />
        <InfoSheetRow icon="search-outline" title="You answer honestly" text="Your answers help us understand your thinking, not predict the market." />
        <InfoSheetRow icon="bulb-outline" title="We find the gaps" text="RiskWise highlights anything that could hurt the trade." />
        <InfoSheetRow icon="trending-up-outline" title="You get better decisions" text="Know whether to keep, change, or skip the idea." />
        <Pressable accessibilityLabel="Got it" style={styles.coachSheetButton} onPress={() => setSheet(null)}>
          <Text style={styles.coachSheetButtonText}>Got it</Text>
        </Pressable>
      </CoachSheet>
      <CoachSheet visible={Boolean(alternativeDetail)} onClose={() => setAlternativeDetail(null)}>
        <Text style={styles.coachSheetTitle}>{alternativeDetail?.label}</Text>
        <Text style={styles.coachSheetSub}>
          {alternativeDetail?.fit?.score != null ? `Fit score ${alternativeDetail.fit.score}/100 (profile-weighted)` : "Fit score unavailable"}
        </Text>
        <Text style={styles.altNote}>{alternativeDetail?.thesis_note}</Text>
        {(alternativeDetail?.fit?.sub_scores || []).filter((sub) => sub.included).map((sub) => (
          <Text key={sub.name} style={styles.challengeSub}>
            {`${subScoreLabel(sub.name)}: ${(sub.value * 100).toFixed(0)}/100 x weight ${sub.weight}`}
          </Text>
        ))}
        {alternativeDetail?.probability?.status === "ok" ? (
          <Text style={styles.challengeSub}>
            {`P(profit) ${Math.round(alternativeDetail.probability.p_profit * 100)}% / P(max loss) ${Math.round(alternativeDetail.probability.p_max_loss * 100)}% — delayed-IV Black-Scholes`}
          </Text>
        ) : null}
        {alternativeDetail?.status === "needs_live_premium" ? (
          <Text style={styles.challengeSub}>Unpriced: the needed premium is not attached and RiskWise does not invent prices.</Text>
        ) : null}
      </CoachSheet>
    </View>
  );

  function chooseTrade(report) {
    setSelectedTrade(report);
    setPickerOpen(false);
    setSheet(null);
    resetChallenge();
  }

  function resetChallenge() {
    setChallengeStarted(false);
    setChallengeIndex(0);
    setAnswerDraft("");
    setChallengeAnswers([]);
    setChallengeSession(null);
    setChallengeResult(null);
  }

  async function startChallengeSession() {
    if (!selectedTrade) {
      setSheet("trade-context");
      return;
    }
    const convictionPct = Number(conviction);
    if (!Number.isFinite(convictionPct) || convictionPct < 0 || convictionPct > 100) {
      Alert.alert("Conviction needed", "Enter how convinced you are this trade works, from 0 to 100%, before the questions start.");
      return;
    }
    setChallengeLoading(true);
    try {
      const started = await startChallenge({
        user,
        report: selectedTrade,
        convictionPct,
        direction
      });
      setChallengeSession(started);
      setChallengeAnswers([]);
      setChallengeIndex(0);
      setAnswerDraft("");
      setChallengeResult(null);
      setChallengeStarted(true);
    } catch (err) {
      Alert.alert("Challenge unavailable", err.message);
    } finally {
      setChallengeLoading(false);
    }
  }

  async function submitChallengeAnswer() {
    const questions = challengeSession?.session?.questions || [];
    const question = questions[challengeIndex];
    if (!question || challengeLoading) {
      return;
    }
    const answer = answerDraft.trim() || "Skipped for now.";
    const nextAnswers = [
      ...challengeAnswers.filter((item) => item.dimension !== question.dimension),
      { dimension: question.dimension, answer }
    ];
    setChallengeAnswers(nextAnswers);
    setAnswerDraft("");
    if (challengeIndex < questions.length - 1) {
      setChallengeIndex((value) => value + 1);
      return;
    }
    setChallengeLoading(true);
    try {
      const graded = await gradeChallenge({
        user,
        report: selectedTrade,
        session: challengeSession.session,
        answers: nextAnswers,
        predictionLock: challengeSession.prediction_lock
      });
      setChallengeResult(graded);
      setChallengeStarted("summary");
    } catch (err) {
      Alert.alert("Grading unavailable", err.message);
    } finally {
      setChallengeLoading(false);
    }
  }
}

function AttachmentMenu({ onPick, onClose, canExport }) {
  return (
    <View style={styles.attachmentMenu}>
      <View style={styles.attachmentMenuHeader}>
        <Text style={styles.attachmentMenuTitle}>Add context</Text>
        <Pressable accessibilityLabel="Close sheet" style={styles.attachmentMenuClose} onPress={onClose}>
          <Ionicons name="close" size={15} color={palette.muted} />
        </Pressable>
      </View>
      <View style={styles.attachmentOptions}>
        <AttachmentAction
          icon="cloud-upload-outline"
          title="Upload"
          subtitle="Photo, screenshot, PDF, CSV, or text"
          onPress={() => onPick("upload")}
        />
        <AttachmentAction
          icon="document-text-outline"
          title="Export for AI Review"
          subtitle={canExport ? "Preview a saved Check as Markdown" : "Select a saved Check first"}
          disabled={!canExport}
          onPress={() => onPick("external_ai_export")}
        />
        <AttachmentAction
          icon="sparkles-outline"
          title="Deep Analysis"
          subtitle="Run the 5-agent committee"
          onPress={() => onPick("deep_analysis")}
        />
      </View>
    </View>
  );
}

function ChallengeCoach({ selectedTrade, started, session, result, loading, topicIndex, answerDraft, answers, conviction, direction, onConviction, onDirection, onAnswer, onStart, onHowItWorks, onChangeTrade, onSubmit, onRestart, onAlternatives }) {
  const questions = session?.session?.questions || [];
  const topics = questions.length ? questions.map((item) => item.dimension) : challengeTopics;

  if (started === "summary" && result) {
    const scorePct = Math.round((result.overall_score || 0) * 100);
    const verdict = result.verdict || {};
    const probability = result.probability || {};
    const lock = result.prediction_lock || {};
    const isRubric = result.grading_basis === "llm_rubric";
    return (
      <ScrollView style={styles.coachModeScroll} contentContainerStyle={styles.coachModeContent} showsVerticalScrollIndicator={false}>
        <SelectedCoachTrade report={selectedTrade} onChangeTrade={onChangeTrade} />
        <ChallengeProgress index={topics.length - 1} topics={topics} complete />
        <View style={styles.summaryCard}>
          <View style={styles.scoreRing}>
            <Text style={styles.scoreNumber}>{scorePct}</Text>
            <Text style={styles.scoreSub}>/100</Text>
          </View>
          <View style={styles.flex}>
            <Text style={styles.challengeTitle}>{isRubric ? "Your understanding score" : "Your coverage score"}</Text>
            <Text style={styles.challengeSub}>
              {isRubric
                ? "Graded by the local rubric model plus deterministic risk-math checks."
                : "The local grading model was unavailable, so this reflects concept coverage and the numeric risk-math checks only."}
            </Text>
          </View>
        </View>
        <View style={styles.recommendationCard}>
          <Text style={styles.recommendationLabel}>Overall recommendation</Text>
          <Text style={styles.recommendationValue}>{verdict.verdict || "Revise"}</Text>
          <Text style={styles.challengeSub}>
            {verdict.hard_cap_applied
              ? `Capped at Revise because ${verdict.hard_cap_reason}.`
              : "Deterministic gate over your per-question scores."}
          </Text>
        </View>
        {probability.status === "ok" ? (
          <View style={styles.recommendationCard}>
            <Text style={styles.recommendationLabel}>Model probability — revealed only now</Text>
            <Text style={styles.recommendationValue}>{Math.round((probability.p_profit || 0) * 100)}% chance of profit at expiry</Text>
            <Text style={styles.challengeSub}>
              Basis: delayed-IV Black-Scholes. You locked {Math.round(lock.conviction_pct ?? 0)}% conviction before the questions
              {result.conviction_gap_pct != null
                ? ` — ${Math.abs(result.conviction_gap_pct).toFixed(0)} points ${result.conviction_gap_pct > 0 ? "above" : "below"} the model.`
                : "."}
            </Text>
          </View>
        ) : (
          <View style={styles.recommendationCard}>
            <Text style={styles.recommendationLabel}>Model probability</Text>
            <Text style={styles.challengeSub}>
              Not computable for this trade ({(probability.missing || []).join(", ") || "missing inputs"}). RiskWise never substitutes a default volatility.
            </Text>
          </View>
        )}
        {result.follow_up ? (
          <View style={styles.concernCard}>
            <Ionicons name="help-circle-outline" size={22} color="#F97316" />
            <Text style={styles.concernText}>{result.follow_up.question}</Text>
          </View>
        ) : null}
        <Pressable accessibilityLabel="View better alternatives" style={styles.challengePrimary} onPress={onAlternatives}>
          <Ionicons name="scale-outline" size={20} color="#FFFFFF" />
          <Text style={styles.challengePrimaryText}>View better alternatives</Text>
        </Pressable>
        <Pressable accessibilityLabel="Run the Challenge again" style={styles.linkButton} onPress={onRestart}>
          <Text style={styles.linkButtonText}>Run again</Text>
        </Pressable>
      </ScrollView>
    );
  }

  if (started && questions.length) {
    const question = questions[Math.min(topicIndex, questions.length - 1)];
    const isLast = topicIndex >= questions.length - 1;
    return (
      <ScrollView style={styles.coachModeScroll} contentContainerStyle={styles.coachModeContent} showsVerticalScrollIndicator={false}>
        <SelectedCoachTrade report={selectedTrade} onChangeTrade={onChangeTrade} />
        <ChallengeProgress index={topicIndex} topics={topics} answers={answers} />
        <View style={styles.questionCard}>
          <View style={styles.questionIntro}>
            <View style={styles.iconHalo}>
              <Ionicons name="locate-outline" size={22} color={palette.green} />
            </View>
            <View style={styles.flex}>
              <Text style={styles.challengeTitle}>Question {topicIndex + 1} of {questions.length}</Text>
              <Text style={styles.challengeSub}>We will focus on {String(question.dimension || "").toLowerCase()}.</Text>
            </View>
          </View>
          <Text style={styles.greenHeading}>{question.dimension}</Text>
          <Text style={styles.questionText}>{question.question}</Text>
          <View style={styles.hintRow}>
            <Ionicons name="bulb-outline" size={17} color={palette.green} />
            <Text style={styles.challengeSub}>Why this was asked: {question.evidence}.</Text>
          </View>
          <View style={styles.answerBox}>
            <TextInput
              value={answerDraft}
              onChangeText={onAnswer}
              placeholder="Type your answer..."
              placeholderTextColor={palette.muted}
              style={styles.answerInput}
              multiline
            />
            <Text style={styles.answerCount}>{answerDraft.length} / 1000</Text>
          </View>
          <View style={styles.challengeActions}>
            <Pressable style={styles.mutedChallenge} onPress={onSubmit} disabled={loading}>
              <Text style={styles.mutedChallengeText}>Skip for now</Text>
            </Pressable>
            <Pressable style={styles.primaryChallengeSmall} onPress={onSubmit} disabled={loading}>
              {loading ? <ActivityIndicator size="small" color="#FFFFFF" /> : (
                <Text style={styles.primaryChallengeText}>{isLast ? "Submit & grade" : "Submit answer"}</Text>
              )}
            </Pressable>
          </View>
        </View>
      </ScrollView>
    );
  }

  return (
    <ScrollView style={styles.coachModeScroll} contentContainerStyle={styles.coachModeContent} showsVerticalScrollIndicator={false}>
      <View style={styles.challengeInitial}>
        <View style={styles.challengeInitialHeader}>
          <View style={styles.flex}>
            <Text style={styles.challengeScreenTitle}>Challenge Your Trade</Text>
            <Text style={styles.challengeSub}>Test your understanding. Uncover hidden risks.</Text>
          </View>
          <View style={styles.securePill}>
            <Ionicons name="shield-checkmark-outline" size={13} color={palette.green} />
            <Text style={styles.secureText}>Private & Secure</Text>
          </View>
        </View>
        <SelectedCoachTrade report={selectedTrade} onChangeTrade={onChangeTrade} />
        <View style={styles.questionCard}>
          <Text style={styles.greenHeading}>Lock your conviction first</Text>
          <Text style={styles.challengeSub}>
            State how convinced you are this trade works, from 0 to 100%. It is locked before any question is shown, and the model's
            probability stays hidden until the end so it cannot anchor you.
          </Text>
          <View style={styles.challengeActions}>
            <Pressable
              style={direction === "bullish" ? styles.primaryChallengeSmall : styles.mutedChallenge}
              onPress={() => onDirection("bullish")}
            >
              <Text style={direction === "bullish" ? styles.primaryChallengeText : styles.mutedChallengeText}>Bullish</Text>
            </Pressable>
            <Pressable
              style={direction === "bearish" ? styles.primaryChallengeSmall : styles.mutedChallenge}
              onPress={() => onDirection("bearish")}
            >
              <Text style={direction === "bearish" ? styles.primaryChallengeText : styles.mutedChallengeText}>Bearish</Text>
            </Pressable>
          </View>
          <View style={styles.answerBox}>
            <TextInput
              value={conviction}
              onChangeText={onConviction}
              placeholder="Conviction, e.g. 65"
              placeholderTextColor={palette.muted}
              style={styles.answerInput}
              keyboardType="numeric"
            />
            <Text style={styles.answerCount}>%</Text>
          </View>
        </View>
        <Pressable accessibilityLabel="Start Challenge" style={styles.challengePrimary} onPress={onStart} disabled={loading}>
          {loading ? <ActivityIndicator size="small" color="#FFFFFF" /> : <Ionicons name="locate-outline" size={22} color="#FFFFFF" />}
          <Text style={styles.challengePrimaryText}>{loading ? "Preparing questions..." : "Lock conviction & start"}</Text>
        </Pressable>
        <Pressable accessibilityLabel="How this works" style={styles.linkButton} onPress={onHowItWorks}>
          <Text style={styles.linkButtonText}>How this works</Text>
        </Pressable>
      </View>
      <PrivacyNote />
    </ScrollView>
  );
}

function AlternativesCoach({ user, selectedTrade, onChangeTrade, onDetail }) {
  const [state, setState] = useState({ loading: false, data: null, error: "" });

  useEffect(() => {
    let active = true;
    if (!selectedTrade) {
      setState({ loading: false, data: null, error: "" });
      return undefined;
    }
    setState({ loading: true, data: null, error: "" });
    fetchAlternatives({ user, report: selectedTrade })
      .then((data) => { if (active) setState({ loading: false, data, error: "" }); })
      .catch((err) => { if (active) setState({ loading: false, data: null, error: err.message }); });
    return () => { active = false; };
  }, [selectedTrade?.id]);

  const candidates = state.data?.candidates || [];
  return (
    <ScrollView style={styles.coachModeScroll} contentContainerStyle={styles.coachModeContent} showsVerticalScrollIndicator={false}>
      <View style={styles.altHeaderCard}>
        <View style={styles.flex}>
          <Text style={styles.challengeScreenTitle}>Better-fitting alternatives</Text>
          <Text style={styles.challengeSub}>Same thesis, different structures — scored against your risk profile.</Text>
        </View>
        <Pressable onPress={onChangeTrade}>
          <Text style={styles.changeText}>Change trade</Text>
        </Pressable>
      </View>
      <View style={styles.altInfoCard}>
        <Text style={styles.challengeTitle}>Original trade</Text>
        <Text style={styles.tradeOptionLabel}>{selectedTrade ? tradeTitle(selectedTrade) : "No trade selected"}</Text>
        <Text style={styles.challengeSub}>
          {state.data?.profile_context?.over_profile_limit
            ? `Above your ${state.data.profile_context.max_risk_per_trade_percent}% per-trade risk limit, so risk reduction is weighted up.`
            : "RiskWise compares against the selected Check context."}
        </Text>
      </View>
      {!selectedTrade ? (
        <View style={styles.altInfoCard}>
          <Text style={styles.challengeSub}>Select a saved Check so RiskWise can price alternatives from the real report.</Text>
        </View>
      ) : null}
      {state.loading ? (
        <View style={styles.altInfoCard}>
          <ActivityIndicator size="small" color={palette.green} />
          <Text style={styles.challengeSub}>Pricing alternatives from the same payoff math...</Text>
        </View>
      ) : null}
      {state.error ? (
        <View style={styles.altInfoCard}>
          <Text style={styles.challengeSub}>{state.error}</Text>
        </View>
      ) : null}
      {candidates.map((item, index) => (
        <Pressable key={item.type} accessibilityLabel={`Open ${item.label} alternative`} style={styles.altCard} onPress={() => onDetail(item)}>
          <View style={styles.altCardTop}>
            <View style={styles.altRank}><Text style={styles.altRankText}>{index + 1}</Text></View>
            <View style={styles.flex}>
              <Text style={styles.challengeTitle}>{item.label}</Text>
              <Text style={styles.challengeSub}>
                {item.fit?.score != null ? `Fit score ${item.fit.score}/100` : "Fit score unavailable"}
                {item.status === "needs_live_premium" ? " - needs live premium data" : ""}
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color={palette.muted} />
          </View>
          <Text style={styles.altNote}>{candidateSummary(item)}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

function subScoreLabel(name) {
  return {
    risk_reduction: "Risk reduction",
    thesis_preservation: "Thesis preservation",
    time_relief: "Time relief",
    cost_efficiency: "Cost efficiency"
  }[name] || name;
}

function candidateSummary(candidate) {
  if (candidate.status === "needs_live_premium") {
    return `${candidate.thesis_note} RiskWise will not invent the missing premium, so this candidate stays unpriced until delayed chain data is attached.`;
  }
  const metrics = candidate.metrics || {};
  const parts = [];
  if (metrics.max_loss != null) parts.push(`Max loss ${formatMoney(metrics.max_loss)}`);
  if (metrics.breakeven != null) parts.push(`breakeven ${formatMoney(metrics.breakeven)}`);
  if (metrics.days_to_expiry != null) parts.push(`${Math.round(metrics.days_to_expiry)} days`);
  const probability = candidate.probability || {};
  if (probability.status === "ok" && probability.p_profit != null) {
    parts.push(`${Math.round(probability.p_profit * 100)}% P(profit), delayed-IV basis`);
  }
  const line = parts.join(" - ");
  return line ? `${candidate.thesis_note} ${line}.` : candidate.thesis_note;
}

function SelectedCoachTrade({ report, onChangeTrade }) {
  if (!report) {
    return (
      <View style={styles.selectedCoachTrade}>
        <Text style={styles.challengeTitle}>Selected Trade</Text>
        <Text style={styles.challengeSub}>No trade selected yet.</Text>
        <Pressable onPress={onChangeTrade}><Text style={styles.changeText}>Choose trade</Text></Pressable>
      </View>
    );
  }
  // Real backend reports keep these under riskMath/contractSnapshot; the flat
  // report.maxLoss/... shape only exists on the labelled development examples.
  // Missing values must read as missing, never as demo numbers.
  const riskMath = report.riskMath || report.risk_math || {};
  const snapshot = report.contractSnapshot || report.contract_snapshot || {};
  const maxLoss = riskMath.max_loss != null ? formatMoney(riskMath.max_loss) : report.maxLoss || "Not available";
  const breakeven = riskMath.breakeven != null ? formatMoney(riskMath.breakeven) : report.breakeven || "Not available";
  const dteDays = riskMath.calendar_days_left ?? riskMath.trading_days_left;
  const dte = dteDays != null ? `${dteDays} days` : report.dte || "Not available";
  const ivValue = snapshot.implied_volatility ?? snapshot.impliedVolatility ?? report.implied_volatility;
  const iv = ivValue != null ? formatIvPercent(ivValue) : report.iv || "Not attached";
  return (
    <View style={styles.selectedCoachTrade}>
      <View style={styles.tradeTop}>
        <TickerLogo ticker={report.ticker} />
        <View style={styles.flex}>
          <Text style={styles.tradeOptionLabel}>{tradeTitle(report)}</Text>
          <Text style={styles.challengeSub}>{report.expiration || "Selected Check"} - {report.contracts || snapshot.contracts || 1} Contract</Text>
        </View>
        <Pressable onPress={onChangeTrade}><Text style={styles.changeText}>Change trade</Text></Pressable>
      </View>
      <View style={styles.metricStrip}>
        <MiniMetric label="Max loss" value={maxLoss} danger />
        <MiniMetric label="Breakeven" value={breakeven} />
        <MiniMetric label="DTE" value={dte} />
        <MiniMetric label="IV" value={iv} />
      </View>
    </View>
  );
}

function formatMoney(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "Not available";
  }
  return `$${number.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function formatIvPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "Not attached";
  }
  // Delayed feeds report IV as a decimal (0.27) or a percent (27); match the backend's convention.
  return `${(number > 3 ? number : number * 100).toFixed(1)}%`;
}

function ChallengeProgress({ index, complete, topics = challengeTopics }) {
  return (
    <View style={styles.progressCard}>
      <View style={styles.progressHeader}>
        <Text style={styles.challengeTitle}>Challenge progress</Text>
        <Text style={styles.challengeTitle}>{complete ? `${topics.length} of ${topics.length}` : `${index + 1} of ${topics.length}`}</Text>
      </View>
      <View style={styles.progressSteps}>
        {topics.map((topic, step) => (
          <View key={topic} style={styles.progressStep}>
            <View style={[styles.progressDot, (complete || step <= index) && styles.progressDotActive]}>
              <Text style={[styles.progressDotText, (complete || step <= index) && styles.progressDotTextActive]}>{complete || step < index ? "✓" : step + 1}</Text>
            </View>
            <Text style={[styles.progressLabel, step === index && styles.progressLabelActive]} numberOfLines={1}>{topic}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

function MiniMetric({ label, value, danger }) {
  return (
    <View style={styles.miniMetric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, danger && styles.metricDanger]}>{value}</Text>
    </View>
  );
}

function PrivacyNote() {
  return (
    <View style={styles.privacyRow}>
      <Ionicons name="lock-closed" size={12} color={palette.muted} />
      <Text style={styles.challengeSub}>Your answers are private and used only to improve your experience.</Text>
    </View>
  );
}

function AttachmentAction({ icon, title, subtitle, onPress, disabled = false }) {
  return (
    <Pressable
      accessibilityLabel={title}
      accessibilityState={{ disabled }}
      disabled={disabled}
      style={[styles.attachmentAction, disabled && styles.attachmentActionDisabled]}
      onPress={onPress}
    >
      <View style={styles.attachmentActionIcon}>
        <Ionicons name={icon} size={19} color={palette.green} />
      </View>
      <View style={styles.attachmentActionCopy}>
        <Text style={styles.attachmentActionTitle}>{title}</Text>
        <Text style={styles.attachmentActionSub}>{subtitle}</Text>
      </View>
      <Ionicons name="chevron-forward" size={16} color={palette.muted} />
    </Pressable>
  );
}

function CoachSheet({ visible, onClose, children }) {
  const sheet = (
    <Pressable style={styles.coachSheetBackdrop} onPress={onClose}>
      <Pressable style={styles.coachSheetFrame} onPress={(event) => event.stopPropagation()}>
        <View style={styles.sheetGrabber} />
        <Pressable accessibilityLabel="Close sheet" style={styles.coachSheetClose} onPress={onClose}>
          <Ionicons name="close" size={17} color={palette.dark} />
        </Pressable>
        <ScrollView style={styles.coachSheetScroll} contentContainerStyle={styles.coachSheetContent} showsVerticalScrollIndicator={false}>
          {children}
        </ScrollView>
      </Pressable>
    </Pressable>
  );
  if (Platform.OS === "web") {
    return visible ? sheet : null;
  }
  return (
    <Modal visible={visible} transparent animationType="slide" statusBarTranslucent onRequestClose={onClose}>
      {sheet}
    </Modal>
  );
}

function SheetAction({ icon, title, subtitle, onPress, disabled = false }) {
  return (
    <Pressable accessibilityLabel={title} disabled={disabled} style={[styles.sheetAction, disabled && styles.sheetActionDisabled]} onPress={onPress}>
      <View style={styles.sheetIcon}>
        <Ionicons name={icon} size={19} color={palette.green} />
      </View>
      <View style={styles.flex}>
        <Text style={styles.sheetActionTitle}>{title}</Text>
        <Text style={styles.sheetActionSub}>{subtitle}</Text>
      </View>
      <Ionicons name="chevron-forward" size={17} color={palette.muted} />
    </Pressable>
  );
}

function InfoSheetRow({ icon, title, text }) {
  return (
    <View style={styles.infoSheetRow}>
      <View style={styles.sheetIcon}>
        <Ionicons name={icon} size={19} color={palette.green} />
      </View>
      <View style={styles.flex}>
        <Text style={styles.sheetActionTitle}>{title}</Text>
        <Text style={styles.sheetActionSub}>{text}</Text>
      </View>
    </View>
  );
}

function TradeContextRow({ report, active, onPress }) {
  return (
    <Pressable style={[styles.tradeContextRow, active && styles.tradeContextRowActive]} onPress={onPress}>
      <TickerLogo ticker={report.ticker} small />
      <View style={styles.flex}>
        <Text style={styles.tradeOptionLabel}>{tradeTitle(report)}</Text>
        <Text style={styles.tradeOptionSub}>{report.expiration || "Saved Check"} - {report.contracts || 1} Contract</Text>
      </View>
      <Ionicons name={active ? "checkmark-circle" : "chevron-forward"} size={19} color={active ? palette.green : palette.dark} />
    </Pressable>
  );
}

function TickerLogo({ ticker, small = false }) {
  return (
    <View style={[styles.tickerLogo, small && styles.tickerLogoSmall]}>
      <Text style={[styles.tickerLogoText, small && styles.tickerLogoTextSmall]}>{String(ticker || "RW").slice(0, 4).toUpperCase()}</Text>
    </View>
  );
}

function ExportReviewModal({ visible, loading, exportData, status, onClose, onCopy, onDownload }) {
  const content = (
    <Pressable style={styles.exportBackdrop} onPress={onClose}>
      <Pressable style={styles.exportSheet} onPress={(event) => event.stopPropagation()}>
        <View style={styles.exportHeader}>
          <View style={styles.exportTitleWrap}>
            <Text style={styles.exportEyebrow}>EXTERNAL AI REVIEW</Text>
            <Text style={styles.exportTitle}>Export saved Check</Text>
          </View>
          <Pressable accessibilityLabel="Close export preview" style={styles.exportClose} onPress={onClose}>
            <Ionicons name="close" size={18} color={palette.dark} />
          </Pressable>
        </View>

        {loading ? (
          <View style={styles.exportLoading}>
            <ActivityIndicator color={palette.green} />
            <Text style={styles.exportLoadingText}>Building your export...</Text>
          </View>
        ) : exportData?.markdown ? (
          <>
            <ScrollView style={styles.exportPreview} contentContainerStyle={styles.exportPreviewContent}>
              <Text selectable style={styles.exportMarkdown}>{exportData.markdown}</Text>
            </ScrollView>
            <Text style={styles.exportGuidance}>
              Paste this into Claude, ChatGPT, or any AI assistant. When you have a response, come back and paste it here in Coach as a follow-up message.
            </Text>
            <View style={styles.exportActions}>
              <Pressable accessibilityLabel="Copy export to clipboard" style={styles.exportSecondaryButton} onPress={onCopy}>
                <Ionicons name="copy-outline" size={17} color={palette.green} />
                <Text style={styles.exportSecondaryText}>Copy to clipboard</Text>
              </Pressable>
              <Pressable accessibilityLabel="Download export as a file" style={styles.exportPrimaryButton} onPress={onDownload}>
                <Ionicons name="download-outline" size={17} color="#FFFFFF" />
                <Text style={styles.exportPrimaryText}>Download as file</Text>
              </Pressable>
            </View>
          </>
        ) : (
          <View style={styles.exportLoading}>
            <Ionicons name="alert-circle-outline" size={24} color={palette.red} />
            <Text selectable style={styles.exportError}>{status || "Could not build this export."}</Text>
          </View>
        )}
        {status && exportData?.markdown ? <Text selectable style={styles.exportStatus}>{status}</Text> : null}
      </Pressable>
    </Pressable>
  );
  if (Platform.OS === "web") {
    return visible ? content : null;
  }
  return (
    <Modal visible={visible} transparent animationType="slide" statusBarTranslucent onRequestClose={onClose}>
      {content}
    </Modal>
  );
}

function MessageBubble({ message }) {
  const isUser = message.role === "user";
  const hasMeta = !isUser && (
    message.missingData?.length ||
    message.riskFlags?.length ||
    message.summaryCards?.length ||
    message.toolsUsed?.length ||
    message.whatUsed?.length ||
    message.visualBlocks?.length ||
    message.suggestedPrompts?.length ||
    typeof message.confidence === "number"
  );
  return (
    <View style={[styles.bubble, isUser ? styles.userBubble : styles.aiBubble]}>
      <Text style={[styles.bubbleText, isUser && styles.userBubbleText]}>{message.content}</Text>
      {hasMeta ? <AssistantMetadata message={message} /> : null}
      {message.attachments?.length ? (
        <View style={styles.bubbleAttachments}>
          {message.attachments.map((item) => (
            <View key={`${item.name}-${item.size}`} style={styles.bubbleAttachmentChip}>
              <Ionicons name={item.type?.startsWith("image/") ? "image-outline" : "document-text-outline"} size={13} color={isUser ? "#FFFFFF" : palette.green} />
              <Text style={[styles.attachmentChipText, isUser && styles.userAttachmentText]} numberOfLines={1}>{item.name}</Text>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function AssistantMetadata({ message }) {
  const sourceLabels = message.whatUsed?.length ? message.whatUsed : (message.toolsUsed || []).map((tool) => tool.name?.replace(/_/g, " "));
  const confidence = typeof message.confidence === "number" ? Math.round(message.confidence * 100) : null;
  return (
    <View style={styles.metaWrap}>
      <View style={styles.metaSourceRow}>
        {confidence !== null ? (
          <View style={styles.sourceChip}>
            <Ionicons name="speedometer-outline" size={12} color={palette.green} />
            <Text style={styles.sourceChipText}>{confidence}% confidence</Text>
          </View>
        ) : null}
        {message.provider ? (
          <View style={[styles.sourceChip, message.usedFallback && styles.sourceChipWarn]}>
            <Ionicons name={message.usedFallback ? "shield-checkmark-outline" : "sparkles-outline"} size={12} color={message.usedFallback ? "#B45309" : palette.green} />
            <Text style={[styles.sourceChipText, message.usedFallback && styles.sourceChipTextWarn]}>
              {message.usedFallback ? "Guarded fallback" : message.provider}
            </Text>
          </View>
        ) : null}
      </View>
      {message.summaryCards?.length ? (
        <View style={styles.metaCards}>
          {message.summaryCards.slice(0, 5).map((card, index) => (
            <View key={`${card.label}-${index}`} style={styles.metaCard}>
              <Text style={styles.metaLabel}>{card.label}</Text>
              <Text style={[styles.metaValue, card.tone === "risk" && styles.metaRisk, card.tone === "warn" && styles.metaWarn]} numberOfLines={1}>
                {card.value}
              </Text>
            </View>
          ))}
        </View>
      ) : null}
      {message.missingData?.length ? (
        <View style={styles.metaLine}>
          <Ionicons name="information-circle-outline" size={13} color={palette.muted} />
          <Text style={styles.metaText}>Missing: {message.missingData.slice(0, 3).join(", ")}</Text>
        </View>
      ) : null}
      {message.riskFlags?.length ? (
        <View style={styles.metaLine}>
          <Ionicons name="warning-outline" size={13} color="#B45309" />
          <Text style={styles.metaText}>Watch: {message.riskFlags.slice(0, 2).join("; ")}</Text>
        </View>
      ) : null}
      {sourceLabels?.length ? (
        <View style={styles.metaLine}>
          <Ionicons name="construct-outline" size={13} color={palette.green} />
          <Text style={styles.metaText}>Used: {sourceLabels.slice(0, 4).join(", ")}</Text>
        </View>
      ) : null}
      {message.visualBlocks?.length ? <AssistantVisualBlocks blocks={message.visualBlocks} /> : null}
      {message.suggestedPrompts?.length ? (
        <View style={styles.promptRail}>
          {message.suggestedPrompts.slice(0, 3).map((prompt) => (
            <View key={prompt} style={styles.promptChip}>
              <Text style={styles.promptChipText}>{prompt}</Text>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function AssistantVisualBlocks({ blocks }) {
  return (
    <View style={styles.visualBlocks}>
      {blocks.slice(0, 6).map((block, index) => {
        if (block.type === "score_bar") {
          const value = Math.max(0, Math.min(100, Number(block.value || 0)));
          return (
            <View key={`${block.title}-${index}`} style={styles.visualBlock}>
              <View style={styles.visualHeader}>
                <Text style={styles.visualTitle}>{block.title}</Text>
                <Text style={styles.visualValue}>{value}/100</Text>
              </View>
              <View style={styles.visualTrack}>
                <View style={[styles.visualFill, { width: `${value}%`, backgroundColor: block.tone === "risk" ? palette.red : block.tone === "warn" ? palette.teal : palette.green }]} />
              </View>
            </View>
          );
        }
        if (block.type === "mini_table") {
          return (
            <View key={`${block.title}-${index}`} style={styles.visualBlock}>
              <Text style={styles.visualTitle}>{block.title}</Text>
              {(block.rows || []).slice(0, 5).map((row) => (
                <View key={`${row[0]}-${row[1]}`} style={styles.visualRow}>
                  <Text style={styles.visualKey}>{row[0]}</Text>
                  <Text style={styles.visualCell}>{row[1]}</Text>
                </View>
              ))}
            </View>
          );
        }
        if (block.type === "agent_committee") {
          return (
            <View key={`${block.title}-${index}`} style={styles.visualBlock}>
              <Text style={styles.visualTitle}>{block.title}</Text>
              {(block.agents || []).slice(0, 5).map((agent) => (
                <View key={agent.agent} style={styles.agentRow}>
                  <View style={styles.agentScore}>
                    <Text style={styles.agentScoreText}>{agent.score}</Text>
                  </View>
                  <View style={styles.agentCopy}>
                    <Text style={styles.agentName}>{agent.agent}</Text>
                    <Text style={styles.agentFinding} numberOfLines={2}>{agent.finding}</Text>
                  </View>
                </View>
              ))}
            </View>
          );
        }
        return null;
      })}
    </View>
  );
}

function HistoryPanel({ threads, activeId, onOpen, onNew }) {
  return (
    <View style={styles.historyPanel}>
      <View style={styles.historyHeader}>
        <Text style={styles.historyTitle}>Conversations</Text>
        <Pressable onPress={onNew}>
          <Text style={styles.newChatText}>New</Text>
        </Pressable>
      </View>
      {threads.length ? (
        threads.slice(0, 6).map((thread) => (
          <Pressable key={thread.id} style={[styles.threadRow, activeId === thread.id && styles.threadRowActive]} onPress={() => onOpen(thread)}>
            <Text style={styles.threadTitle} numberOfLines={1}>{thread.title || "Options question"}</Text>
            <Text style={styles.threadMeta}>{thread.mode || "Explain"} - {thread.messageCount || 0} msgs</Text>
          </Pressable>
        ))
      ) : (
        <Text style={styles.historyEmpty}>No saved conversations yet.</Text>
      )}
    </View>
  );
}

function AttachmentTray({ attachments, onRemove }) {
  return (
    <View style={styles.attachmentTray}>
      {attachments.map((item, index) => (
        <View key={`${item.name}-${index}`} style={styles.pendingAttachment}>
          {item.dataUrl ? (
            <Image source={{ uri: item.dataUrl }} style={styles.attachmentThumb} />
          ) : (
            <Ionicons name={item.type?.startsWith("image/") ? "image-outline" : "document-text-outline"} size={14} color={palette.green} />
          )}
          <View style={styles.pendingAttachmentCopy}>
            <Text style={styles.pendingAttachmentText} numberOfLines={1}>{item.name}</Text>
            <Text style={styles.pendingAttachmentMeta}>{formatBytes(item.size)} {item.text ? "- text ready" : item.dataUrl ? "- image ready" : "- metadata only"}</Text>
          </View>
          <Pressable onPress={() => onRemove(index)}>
            <Ionicons name="close" size={14} color={palette.muted} />
          </Pressable>
        </View>
      ))}
    </View>
  );
}

function TradeOption({ label, sub, active, onPress }) {
  return (
    <Pressable style={[styles.tradeOption, active && styles.tradeOptionActive]} onPress={onPress}>
      <View style={styles.tradeOptionText}>
        <Text style={styles.tradeOptionLabel} numberOfLines={1}>{label}</Text>
        <Text style={styles.tradeOptionSub} numberOfLines={1}>{sub}</Text>
      </View>
      {active ? <Ionicons name="checkmark-circle" size={17} color={palette.green} /> : null}
    </Pressable>
  );
}

async function readAttachment(file, source = "files") {
  const base = {
    name: file.name,
    type: file.type || "application/octet-stream",
    size: file.size,
    source
  };
  if (file.type?.startsWith("image/") && file.size < 1_500_000) {
    return { ...base, dataUrl: await readAsDataUrl(file) };
  }
  if ((file.type?.startsWith("text/") || file.name.endsWith(".csv") || file.name.endsWith(".txt")) && file.size < 400_000) {
    return { ...base, text: await file.text() };
  }
  return base;
}

function readAsDataUrl(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => resolve("");
    reader.readAsDataURL(file);
  });
}

function formatBytes(size) {
  const number = Number(size || 0);
  if (number < 1024) return `${number} B`;
  if (number < 1024 * 1024) return `${(number / 1024).toFixed(1)} KB`;
  return `${(number / (1024 * 1024)).toFixed(1)} MB`;
}

function uploadSourceLabel(source) {
  if (source === "camera") return "Camera";
  if (source === "library") return "Photo Library";
  return "Files";
}

function nativeImageAttachment(asset, source, index) {
  const type = asset.mimeType || "image/jpeg";
  const extension = type.includes("png") ? "png" : "jpg";
  const base = {
    name: asset.fileName || `${source}-image-${index + 1}.${extension}`,
    type,
    size: asset.fileSize || 0,
    source,
    uri: asset.uri
  };
  if (asset.base64) {
    return { ...base, dataUrl: `data:${type};base64,${asset.base64}` };
  }
  return base;
}

function initialGreeting(user) {
  return {
    role: "assistant",
    content: `Hi, ${firstName(user?.name)}.`
  };
}

function firstName(name) {
  return (name || "there").split(" ")[0];
}

function buildTradeOptions(currentReport, savedChecks) {
  const options = [];
  if (currentReport) {
    options.push({ key: `current-${currentReport.id}`, report: currentReport });
  }
  savedChecks.forEach((item) => {
    const report = item.report;
    if (report && !options.some((option) => option.report.id === report.id)) {
      options.push({ key: item.id, report });
    }
  });
  return options.slice(0, 5);
}

function findSelectedSavedCheck(selectedTrade, savedChecks) {
  if (!selectedTrade) {
    return null;
  }
  return savedChecks.find((item) => item?.id && (item.report === selectedTrade || item.report?.id === selectedTrade.id)) || null;
}

function safeExportFilename(filename) {
  const clean = String(filename || "riskwise-check-export.md").replace(/[^a-zA-Z0-9._-]/g, "-");
  return clean.endsWith(".md") ? clean : `${clean}.md`;
}

function tradeTitle(report) {
  if (!report) {
    return "No trade selected";
  }
  return `${report.ticker || "Trade"} ${report.tradeType || "check"}`;
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    paddingHorizontal: 16,
    backgroundColor: "#FBFDFB"
  },
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingTop: 8,
    paddingBottom: 8
  },
  iconButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    borderWidth: 1,
    borderColor: "#E1ECE2",
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center"
  },
  modeRow: {
    flex: 1,
    flexDirection: "row",
    gap: 5,
    padding: 4,
    borderRadius: 19,
    borderWidth: 1,
    borderColor: "#E1ECE2",
    backgroundColor: "#FFFFFF"
  },
  modeButton: {
    flex: 1,
    minHeight: 30,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center"
  },
  modeButtonActive: {
    backgroundColor: palette.green
  },
  modeText: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "900"
  },
  modeTextActive: {
    color: "#FFFFFF"
  },
  historyPanel: {
    borderWidth: 1,
    borderColor: "#E1ECE2",
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    padding: 10,
    marginBottom: 8
  },
  historyHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8
  },
  historyTitle: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900"
  },
  newChatText: {
    color: palette.green,
    fontSize: 12,
    fontWeight: "900"
  },
  threadRow: {
    borderRadius: 14,
    paddingVertical: 10,
    paddingHorizontal: 10,
    borderWidth: 1,
    borderColor: "#EEF3EF",
    marginBottom: 6
  },
  threadRowActive: {
    backgroundColor: "#F3FFF6",
    borderColor: "#CFEFD8"
  },
  threadTitle: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  threadMeta: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 2
  },
  historyEmpty: {
    color: palette.muted,
    fontSize: 12,
    fontWeight: "800",
    paddingVertical: 8
  },
  contextRow: {
    minHeight: 42,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#E1ECE2",
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 8
  },
  contextValue: {
    flex: 1,
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  changeText: {
    color: palette.green,
    fontSize: 10,
    fontWeight: "900"
  },
  pickerPanel: {
    borderWidth: 1,
    borderColor: "#E1ECE2",
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    overflow: "hidden",
    marginBottom: 8
  },
  tradeOption: {
    minHeight: 50,
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderBottomWidth: 1,
    borderBottomColor: "#EDF3ED",
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  tradeOptionActive: {
    backgroundColor: "#F3FFF6"
  },
  tradeOptionText: {
    flex: 1
  },
  tradeOptionLabel: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  tradeOptionSub: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 2
  },
  newCheckRow: {
    minHeight: 42,
    paddingHorizontal: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  newCheckText: {
    color: palette.green,
    fontSize: 12,
    fontWeight: "900"
  },
  chatScroll: {
    flex: 1
  },
  chatContent: {
    flexGrow: 1,
    justifyContent: "flex-end",
    paddingTop: 8,
    paddingBottom: 16
  },
  bubble: {
    maxWidth: "94%",
    borderRadius: 20,
    paddingVertical: 12,
    paddingHorizontal: 14,
    marginBottom: 10
  },
  aiBubble: {
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E8F1E8",
    alignSelf: "flex-start"
  },
  userBubble: {
    backgroundColor: palette.green,
    alignSelf: "flex-end"
  },
  bubbleText: {
    color: palette.dark,
    fontSize: 14,
    lineHeight: 21,
    fontWeight: "800",
    flexShrink: 1
  },
  userBubbleText: {
    color: "#FFFFFF"
  },
  bubbleAttachments: {
    gap: 6,
    marginTop: 9
  },
  bubbleAttachmentChip: {
    maxWidth: 220,
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "rgba(22,163,74,0.18)",
    paddingHorizontal: 8,
    paddingVertical: 5
  },
  attachmentChipText: {
    flex: 1,
    color: palette.dark,
    fontSize: 10,
    fontWeight: "800"
  },
  userAttachmentText: {
    color: "#FFFFFF"
  },
  metaWrap: {
    gap: 7,
    marginTop: 10,
    paddingTop: 9,
    borderTopWidth: 1,
    borderTopColor: "#EEF4EF"
  },
  metaSourceRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6
  },
  sourceChip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "#D7EEDF",
    backgroundColor: "#F4FFF7",
    paddingHorizontal: 8,
    paddingVertical: 5,
    flexDirection: "row",
    alignItems: "center",
    gap: 4
  },
  sourceChipWarn: {
    borderColor: "#F3DCA8",
    backgroundColor: "#FFFBEB"
  },
  sourceChipText: {
    color: palette.green,
    fontSize: 9,
    fontWeight: "900"
  },
  sourceChipTextWarn: {
    color: "#B45309"
  },
  visualBlocks: {
    gap: 8,
    marginTop: 3
  },
  visualBlock: {
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#DDEBDF",
    backgroundColor: "#FBFFFC",
    padding: 10
  },
  visualHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 7
  },
  visualTitle: {
    color: palette.dark,
    fontSize: 11,
    fontWeight: "900"
  },
  visualValue: {
    color: palette.green,
    fontSize: 11,
    fontWeight: "900"
  },
  visualTrack: {
    height: 7,
    borderRadius: 999,
    backgroundColor: "#EAF1EA",
    overflow: "hidden"
  },
  visualFill: {
    height: "100%",
    borderRadius: 999
  },
  visualRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 10,
    borderTopWidth: 1,
    borderTopColor: "#EAF2EA",
    paddingTop: 7,
    marginTop: 7
  },
  visualKey: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "900"
  },
  visualCell: {
    flex: 1,
    color: palette.dark,
    fontSize: 10,
    fontWeight: "800",
    textAlign: "right"
  },
  agentRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    borderTopWidth: 1,
    borderTopColor: "#EAF2EA",
    paddingTop: 8,
    marginTop: 8
  },
  agentScore: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: "#EAF8EE",
    alignItems: "center",
    justifyContent: "center"
  },
  agentScoreText: {
    color: palette.green,
    fontSize: 10,
    fontWeight: "900"
  },
  agentCopy: {
    flex: 1
  },
  agentName: {
    color: palette.dark,
    fontSize: 10,
    fontWeight: "900"
  },
  agentFinding: {
    color: palette.muted,
    fontSize: 10,
    lineHeight: 14,
    fontWeight: "800",
    marginTop: 2
  },
  metaCards: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 7
  },
  metaCard: {
    minWidth: 92,
    flexGrow: 1,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#E3EEE4",
    backgroundColor: "#FBFEFB",
    paddingHorizontal: 9,
    paddingVertical: 8
  },
  metaLabel: {
    color: palette.muted,
    fontSize: 9,
    fontWeight: "900"
  },
  metaValue: {
    color: palette.dark,
    fontSize: 11,
    fontWeight: "900",
    marginTop: 2
  },
  metaRisk: {
    color: "#DC2626"
  },
  metaWarn: {
    color: "#B45309"
  },
  metaLine: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5
  },
  metaText: {
    flex: 1,
    color: palette.muted,
    fontSize: 10,
    lineHeight: 14,
    fontWeight: "800"
  },
  promptRail: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 2
  },
  promptChip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "#E4EEE5",
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 8,
    paddingVertical: 5
  },
  promptChipText: {
    color: palette.dark,
    fontSize: 9,
    fontWeight: "900"
  },
  thinkingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: palette.green
  },
  composerWrap: {
    paddingTop: 8,
    paddingBottom: 8,
    borderTopWidth: 1,
    borderTopColor: "#ECF1EC",
    backgroundColor: "#FBFDFB"
  },
  attachmentMenu: {
    borderRadius: 22,
    borderWidth: 1,
    borderColor: "#DCEBDD",
    backgroundColor: "#FFFFFF",
    padding: 12,
    marginBottom: 9,
    shadowColor: palette.green,
    shadowOpacity: 0.13,
    shadowRadius: 22,
    shadowOffset: { width: 0, height: 12 }
  },
  attachmentMenuHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 9
  },
  attachmentMenuTitle: {
    color: palette.dark,
    fontSize: 13,
    fontWeight: "900"
  },
  attachmentMenuClose: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "#F5F8F5",
    alignItems: "center",
    justifyContent: "center"
  },
  attachmentOptions: {
    gap: 7
  },
  attachmentAction: {
    minHeight: 58,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#E5F0E6",
    backgroundColor: "#FBFFFC",
    paddingHorizontal: 10,
    paddingVertical: 9,
    flexDirection: "row",
    alignItems: "center",
    gap: 10
  },
  attachmentActionDisabled: {
    opacity: 0.48
  },
  attachmentActionIcon: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: palette.greenSoft,
    alignItems: "center",
    justifyContent: "center"
  },
  attachmentActionCopy: {
    flex: 1
  },
  attachmentActionTitle: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900"
  },
  attachmentActionSub: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 2
  },
  attachmentTray: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 7,
    marginBottom: 8
  },
  pendingAttachment: {
    maxWidth: "100%",
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "#CFEFD8",
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 9,
    paddingVertical: 6
  },
  attachmentThumb: {
    width: 28,
    height: 28,
    borderRadius: 8,
    backgroundColor: "#EAF1EA"
  },
  pendingAttachmentCopy: {
    maxWidth: 235
  },
  pendingAttachmentText: {
    maxWidth: 210,
    color: palette.dark,
    fontSize: 11,
    fontWeight: "800"
  },
  pendingAttachmentMeta: {
    color: palette.muted,
    fontSize: 8,
    fontWeight: "800",
    marginTop: 1
  },
  uploadStatus: {
    color: palette.green,
    fontSize: 10,
    fontWeight: "900",
    marginBottom: 6,
    paddingLeft: 7
  },
  exportBackdrop: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(17, 24, 39, 0.48)"
  },
  exportSheet: {
    maxHeight: "90%",
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    borderWidth: 1,
    borderColor: "#DCEBDD",
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 18,
    paddingTop: 18,
    paddingBottom: 24,
    gap: 13
  },
  exportHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12
  },
  exportTitleWrap: {
    flex: 1,
    gap: 3
  },
  exportEyebrow: {
    color: palette.green,
    fontSize: 9,
    fontWeight: "900",
    letterSpacing: 1.1
  },
  exportTitle: {
    color: palette.dark,
    fontSize: 20,
    fontWeight: "900"
  },
  exportClose: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "#F2F6F2",
    alignItems: "center",
    justifyContent: "center"
  },
  exportLoading: {
    minHeight: 260,
    alignItems: "center",
    justifyContent: "center",
    gap: 10
  },
  exportLoadingText: {
    color: palette.muted,
    fontSize: 12,
    fontWeight: "800"
  },
  exportPreview: {
    minHeight: 240,
    maxHeight: 430,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#DCEBDD",
    backgroundColor: "#F7FAF7"
  },
  exportPreviewContent: {
    padding: 14
  },
  exportMarkdown: {
    color: "#26322A",
    fontSize: 11,
    lineHeight: 17,
    fontFamily: Platform.select({ ios: "Menlo", android: "monospace", web: "monospace" })
  },
  exportGuidance: {
    color: palette.muted,
    fontSize: 11,
    lineHeight: 16,
    fontWeight: "700"
  },
  exportActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 9
  },
  exportSecondaryButton: {
    minHeight: 44,
    flexGrow: 1,
    flexBasis: 150,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: "#BFE5C8",
    backgroundColor: "#F6FFF8",
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  exportSecondaryText: {
    color: palette.green,
    fontSize: 12,
    fontWeight: "900"
  },
  exportPrimaryButton: {
    minHeight: 44,
    flexGrow: 1,
    flexBasis: 150,
    borderRadius: 15,
    backgroundColor: palette.green,
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  exportPrimaryText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "900"
  },
  exportError: {
    maxWidth: 280,
    color: palette.red,
    fontSize: 12,
    lineHeight: 17,
    fontWeight: "800",
    textAlign: "center"
  },
  exportStatus: {
    color: palette.green,
    fontSize: 10,
    fontWeight: "900",
    textAlign: "center"
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8
  },
  plusButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: "#CFEFD8",
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center"
  },
  plusButtonActive: {
    backgroundColor: palette.greenSoft,
    borderColor: palette.green
  },
  input: {
    flex: 1,
    minHeight: 44,
    maxHeight: 98,
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 22,
    paddingHorizontal: 15,
    paddingTop: 12,
    paddingBottom: 10,
    color: palette.dark,
    backgroundColor: "#FFFFFF",
    fontWeight: "800",
    outlineStyle: "none"
  },
  sendButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: palette.green,
    alignItems: "center",
    justifyContent: "center"
  },
  sendDisabled: {
    opacity: 0.55
  },
  disclaimerText: {
    color: palette.muted,
    fontSize: 9,
    fontWeight: "800",
    textAlign: "center",
    marginTop: 7
  },
  flex: {
    flex: 1
  },
  coachModeScroll: {
    flex: 1
  },
  coachModeContent: {
    gap: 12,
    paddingBottom: 96
  },
  challengeInitial: {
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 20,
    backgroundColor: "#FFFFFF",
    padding: 16,
    gap: 14,
    boxShadow: "0 8px 28px rgba(15, 23, 42, 0.07)"
  },
  challengeInitialHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
    flexWrap: "wrap"
  },
  challengeScreenTitle: {
    color: palette.dark,
    fontSize: 22,
    lineHeight: 27,
    fontWeight: "900"
  },
  challengeTitle: {
    color: palette.dark,
    fontSize: 14,
    fontWeight: "900"
  },
  challengeSub: {
    color: palette.muted,
    fontSize: 12,
    lineHeight: 17,
    fontWeight: "700",
    marginTop: 3
  },
  securePill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    borderRadius: 999,
    backgroundColor: palette.greenSoft,
    paddingHorizontal: 9,
    paddingVertical: 7
  },
  secureText: {
    color: palette.green,
    fontSize: 10,
    fontWeight: "900"
  },
  selectedCoachTrade: {
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    padding: 14,
    gap: 12
  },
  tradeTop: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12
  },
  tickerLogo: {
    width: 52,
    height: 52,
    borderRadius: 13,
    backgroundColor: "#050712",
    alignItems: "center",
    justifyContent: "center"
  },
  tickerLogoSmall: {
    width: 38,
    height: 38,
    borderRadius: 10
  },
  tickerLogoText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "900"
  },
  tickerLogoTextSmall: {
    fontSize: 9
  },
  metricStrip: {
    flexDirection: "row",
    gap: 8
  },
  miniMetric: {
    flex: 1,
    borderRadius: 12,
    backgroundColor: "#F7FAF7",
    padding: 8,
    alignItems: "center"
  },
  metricLabel: {
    color: palette.muted,
    fontSize: 9,
    fontWeight: "800"
  },
  metricValue: {
    color: palette.dark,
    fontSize: 11,
    fontWeight: "900",
    marginTop: 4
  },
  metricDanger: {
    color: palette.red
  },
  concernCard: {
    borderWidth: 1,
    borderColor: "#FED7AA",
    borderRadius: 16,
    backgroundColor: "#FFF7ED",
    padding: 14,
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10
  },
  concernText: {
    flex: 1,
    color: palette.dark,
    fontSize: 13,
    lineHeight: 19,
    fontWeight: "800"
  },
  challengePrimary: {
    minHeight: 54,
    borderRadius: 14,
    backgroundColor: palette.green,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  challengePrimaryText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "900"
  },
  linkButton: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 8
  },
  linkButtonText: {
    color: palette.green,
    fontWeight: "900",
    textDecorationLine: "underline"
  },
  progressCard: {
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    padding: 12,
    gap: 12
  },
  progressHeader: {
    flexDirection: "row",
    justifyContent: "space-between"
  },
  progressSteps: {
    flexDirection: "row",
    gap: 6
  },
  progressStep: {
    flex: 1,
    alignItems: "center",
    gap: 5
  },
  progressDot: {
    width: 30,
    height: 30,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center"
  },
  progressDotActive: {
    backgroundColor: palette.green,
    borderColor: palette.green
  },
  progressDotText: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "900"
  },
  progressDotTextActive: {
    color: "#FFFFFF"
  },
  progressLabel: {
    color: palette.muted,
    fontSize: 9,
    fontWeight: "800",
    textAlign: "center"
  },
  progressLabelActive: {
    color: palette.green
  },
  questionCard: {
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    padding: 14,
    gap: 12
  },
  questionIntro: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderWidth: 1,
    borderColor: "#CFEFD8",
    borderRadius: 15,
    backgroundColor: "#F4FBF7",
    padding: 12
  },
  iconHalo: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: palette.greenSoft,
    alignItems: "center",
    justifyContent: "center"
  },
  greenHeading: {
    color: palette.green,
    fontSize: 16,
    fontWeight: "900"
  },
  questionText: {
    color: palette.dark,
    fontSize: 16,
    lineHeight: 25,
    fontWeight: "900"
  },
  hintRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  answerBox: {
    minHeight: 108,
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 14,
    backgroundColor: "#FDFEFD",
    padding: 12
  },
  answerInput: {
    flex: 1,
    color: palette.dark,
    fontSize: 14,
    textAlignVertical: "top",
    outlineStyle: "none"
  },
  answerCount: {
    color: palette.muted,
    textAlign: "right",
    fontSize: 11,
    fontWeight: "700"
  },
  challengeActions: {
    flexDirection: "row",
    gap: 8
  },
  secondaryChallenge: {
    flex: 1,
    minHeight: 48,
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 5,
    paddingHorizontal: 6
  },
  secondaryChallengeText: {
    color: palette.green,
    fontSize: 11,
    fontWeight: "900",
    textAlign: "center"
  },
  mutedChallenge: {
    flex: 0.78,
    minHeight: 48,
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 13,
    backgroundColor: "#F8FAF8",
    alignItems: "center",
    justifyContent: "center"
  },
  mutedChallengeText: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "900",
    textAlign: "center"
  },
  primaryChallengeSmall: {
    flex: 1,
    minHeight: 48,
    borderRadius: 13,
    backgroundColor: palette.green,
    alignItems: "center",
    justifyContent: "center"
  },
  primaryChallengeText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "900",
    textAlign: "center"
  },
  summaryCard: {
    borderWidth: 1,
    borderColor: "#CFEFD8",
    borderRadius: 18,
    backgroundColor: "#F4FBF7",
    padding: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: 14
  },
  scoreRing: {
    width: 78,
    height: 78,
    borderRadius: 39,
    borderWidth: 8,
    borderColor: palette.green,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FFFFFF"
  },
  scoreNumber: {
    color: palette.dark,
    fontSize: 24,
    fontWeight: "900"
  },
  scoreSub: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "800"
  },
  recommendationCard: {
    borderWidth: 1,
    borderColor: "#FED7AA",
    borderRadius: 16,
    backgroundColor: "#FFF7ED",
    padding: 14
  },
  recommendationLabel: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "900"
  },
  recommendationValue: {
    color: "#F97316",
    fontSize: 18,
    fontWeight: "900",
    marginVertical: 4
  },
  altHeaderCard: {
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    padding: 16,
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10
  },
  altInfoCard: {
    borderWidth: 1,
    borderColor: "#CFEFD8",
    borderRadius: 16,
    backgroundColor: "#F4FBF7",
    padding: 14
  },
  altCard: {
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    padding: 14,
    gap: 12,
    boxShadow: "0 8px 28px rgba(15, 23, 42, 0.06)"
  },
  altCardTop: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12
  },
  altRank: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: palette.green,
    alignItems: "center",
    justifyContent: "center"
  },
  altRankText: {
    color: "#FFFFFF",
    fontWeight: "900"
  },
  altNote: {
    color: palette.muted,
    fontSize: 12,
    lineHeight: 18,
    fontWeight: "700"
  },
  privacyRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    paddingVertical: 8
  },
  coachSheetBackdrop: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.24)",
    justifyContent: "flex-end",
    alignItems: "center",
    ...(Platform.OS === "web"
      ? { position: "absolute", top: 0, right: 0, bottom: 0, left: 0, zIndex: 50 }
      : null)
  },
  coachSheetFrame: {
    width: "100%",
    maxWidth: 420,
    maxHeight: Platform.OS === "web" ? "92vh" : "92%",
    borderRadius: 24,
    borderWidth: 1,
    borderColor: palette.border,
    backgroundColor: "#FFFFFF",
    paddingTop: 22,
    marginHorizontal: 12,
    marginBottom: 10,
    overflow: "hidden",
    boxShadow: "0 -12px 34px rgba(15, 23, 42, 0.14)"
  },
  coachSheetScroll: {
    maxHeight: Platform.OS === "web" ? "calc(92vh - 48px)" : 640
  },
  coachSheetContent: {
    gap: 12,
    padding: 16,
    paddingTop: 8,
    paddingBottom: 16
  },
  sheetGrabber: {
    position: "absolute",
    top: 8,
    alignSelf: "center",
    width: 44,
    height: 5,
    borderRadius: 999,
    backgroundColor: "#D1D5DB"
  },
  coachSheetClose: {
    position: "absolute",
    top: 14,
    right: 14,
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: "#F3F4F6",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2
  },
  coachSheetTitle: {
    color: palette.dark,
    fontSize: 21,
    fontWeight: "900",
    paddingRight: 42
  },
  coachSheetSub: {
    color: palette.muted,
    fontSize: 12,
    fontWeight: "700"
  },
  coachSheetSection: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "900",
    marginTop: 4
  },
  sheetAction: {
    minHeight: 72,
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    padding: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 12
  },
  sheetActionDisabled: {
    opacity: 0.5
  },
  sheetIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: palette.greenSoft,
    alignItems: "center",
    justifyContent: "center"
  },
  sheetActionTitle: {
    color: palette.dark,
    fontSize: 14,
    fontWeight: "900"
  },
  sheetActionSub: {
    color: palette.muted,
    fontSize: 12,
    lineHeight: 17,
    marginTop: 3,
    fontWeight: "700"
  },
  infoSheetRow: {
    minHeight: 76,
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 16,
    padding: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 12
  },
  tradeContextRow: {
    minHeight: 64,
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 14,
    backgroundColor: "#FFFFFF",
    padding: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 10
  },
  tradeContextRowActive: {
    borderColor: palette.green,
    backgroundColor: "#FBFFFC"
  },
  coachSheetButton: {
    minHeight: 48,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: palette.green,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 8,
    marginTop: 4
  },
  coachSheetButtonText: {
    color: palette.green,
    fontWeight: "900"
  }
});
