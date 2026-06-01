import React, { useEffect, useMemo, useRef, useState } from "react";
import { Image, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { listChatMessages, listChatThreads, sendChatMessage } from "../services/apiClient";
import { palette } from "../theme/theme";

const askModes = ["Explain", "Review", "Compare"];

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
  const [uploadStatus, setUploadStatus] = useState("");
  const scrollRef = useRef(null);
  const tradeOptions = useMemo(() => buildTradeOptions(currentReport, savedChecks), [currentReport, savedChecks]);

  useEffect(() => {
    if (currentReport && !selectedTrade) {
      setSelectedTrade(currentReport);
    }
  }, [currentReport?.id]);

  useEffect(() => {
    requestAnimationFrame(() => scrollRef.current?.scrollToEnd?.({ animated: true }));
  }, [messages.length, loading]);

  async function submit(text = input) {
    const clean = text.trim();
    if ((!clean && attachments.length === 0) || loading) {
      return;
    }
    const outgoingAttachments = attachments;
    const messageText = clean || "Review these attachments.";
    setInput("");
    setAttachments([]);
    setUploadStatus("");
    setMessages((items) => [...items, { role: "user", content: messageText, attachments: outgoingAttachments }]);
    setLoading(true);
    try {
      const response = await sendChatMessage({
        user,
        threadId,
        message: messageText,
        currentReport: selectedTrade,
        chatMode,
        attachments: outgoingAttachments
      });
      setThreadId(response.thread_id);
      if (historyOpen) {
        refreshThreads();
      }
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: response.answer,
          mode: response.mode,
          confidence: response.confidence,
          missingData: response.missing_data || [],
          riskFlags: response.risk_flags || [],
          toolsUsed: response.tools_used || [],
          summaryCards: response.summary_cards || [],
          visualBlocks: response.visual_blocks || []
        }
      ]);
    } catch (err) {
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: "The coach is unavailable right now. Your checks are still saved, and you can try again in a moment.",
          mode: "fallback"
        }
      ]);
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

  function attachFile() {
    if (Platform.OS !== "web" || typeof document === "undefined") {
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: "File upload is active in the browser preview. Native document upload comes when we package the iOS build."
        }
      ]);
      return;
    }
    const inputEl = document.createElement("input");
    inputEl.type = "file";
    inputEl.multiple = true;
    inputEl.accept = "image/*,.txt,.csv,.pdf";
    inputEl.onchange = async () => {
      const files = Array.from(inputEl.files || []).slice(0, 4);
      setUploadStatus(files.length ? "Reading upload..." : "");
      const parsed = await Promise.all(files.map(readAttachment));
      setAttachments((items) => [...items, ...parsed].slice(0, 4));
      setUploadStatus(parsed.length ? `${parsed.length} file${parsed.length === 1 ? "" : "s"} attached. Ask RiskWiseAI to review them.` : "");
    };
    inputEl.click();
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

      <Pressable style={styles.contextRow} onPress={() => setPickerOpen((open) => !open)}>
        <Text style={styles.contextValue} numberOfLines={1}>{selectedTrade ? tradeTitle(selectedTrade) : "No trade selected"}</Text>
        <Text style={styles.changeText}>{pickerOpen ? "Close" : "Trade context"}</Text>
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
          <MessageBubble key={`${message.role}-${index}-${message.content.slice(0, 8)}`} message={message} />
        ))}
        {loading ? (
          <View style={[styles.bubble, styles.aiBubble]}>
            <View style={styles.thinkingRow}>
              <View style={styles.dot} />
              <Text style={styles.bubbleText}>Thinking...</Text>
            </View>
          </View>
        ) : null}
      </ScrollView>

      <View style={styles.composerWrap}>
        {attachments.length ? <AttachmentTray attachments={attachments} onRemove={(index) => setAttachments((items) => items.filter((_, i) => i !== index))} /> : null}
        {uploadStatus ? <Text style={styles.uploadStatus}>{uploadStatus}</Text> : null}
        <View style={styles.inputRow}>
          <Pressable accessibilityLabel="Add attachment" style={styles.plusButton} onPress={attachFile}>
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
    </View>
  );

  function chooseTrade(report) {
    setSelectedTrade(report);
    setPickerOpen(false);
  }
}

function MessageBubble({ message }) {
  const isUser = message.role === "user";
  const hasMeta = !isUser && (message.missingData?.length || message.riskFlags?.length || message.summaryCards?.length || message.toolsUsed?.length || message.visualBlocks?.length);
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
  return (
    <View style={styles.metaWrap}>
      {message.summaryCards?.length ? (
        <View style={styles.metaCards}>
          {message.summaryCards.slice(0, 4).map((card, index) => (
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
      {message.toolsUsed?.length ? (
        <View style={styles.metaLine}>
          <Ionicons name="construct-outline" size={13} color={palette.green} />
          <Text style={styles.metaText}>Checked: {message.toolsUsed.map((tool) => tool.name.replace("get_", "")).slice(0, 3).join(", ")}</Text>
        </View>
      ) : null}
      {message.visualBlocks?.length ? <AssistantVisualBlocks blocks={message.visualBlocks} /> : null}
    </View>
  );
}

function AssistantVisualBlocks({ blocks }) {
  return (
    <View style={styles.visualBlocks}>
      {blocks.slice(0, 3).map((block, index) => {
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
              {(block.rows || []).slice(0, 4).map((row) => (
                <View key={`${row[0]}-${row[1]}`} style={styles.visualRow}>
                  <Text style={styles.visualKey}>{row[0]}</Text>
                  <Text style={styles.visualCell}>{row[1]}</Text>
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

async function readAttachment(file) {
  const base = {
    name: file.name,
    type: file.type || "application/octet-stream",
    size: file.size
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
  }
});
