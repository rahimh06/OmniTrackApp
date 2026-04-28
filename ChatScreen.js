// ============================================================
//  screens/ChatScreen.js  —  OmniTrack AI
//  AI Analytics screen.  Teachers type a plain-English question
//  and the backend converts it to SQL via Gemini, runs it,
//  and returns results.
// ============================================================

import { Ionicons } from "@expo/vector-icons";
import { useRef, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

// ── Shared config — change API_BASE in config.js ─────────────
import { API_BASE } from "../config";

// ── Colour palette ────────────────────────────────────────────
const COLORS = {
  primary:       "#0D1B4B",
  accent:        "#3D5AFE",
  accentLight:   "#E8EAFF",
  success:       "#00BFA5",
  danger:        "#FF1744",
  dangerLight:   "#FFF0F0",
  purple:        "#7C4DFF",
  purpleLight:   "#F0EBFF",
  background:    "#F4F6FF",
  surface:       "#FFFFFF",
  textPrimary:   "#0D1B4B",
  textSecondary: "#6B7A99",
  border:        "#D0D6F0",
  codeBg:        "#1A2240",
  codeText:      "#A5F3FC",
};

// ── Suggestion chips ──────────────────────────────────────────
const SUGGESTIONS = [
  { icon: "people-outline",      text: "Show all students present today" },
  { icon: "person-outline",      text: "Show attendance for roll number 674" },
  { icon: "alert-circle-outline",text: "Who was absent in AI Theory?" },
  { icon: "stats-chart-outline", text: "List students absent more than 3 times" },
  { icon: "calendar-outline",    text: "Show AI Lab attendance for this week" },
];

// ════════════════════════════════════════════════════════════
export default function ChatScreen() {
  const [query,         setQuery]         = useState("");
  const [results,       setResults]       = useState(null);
  const [sqlUsed,       setSqlUsed]       = useState("");
  const [clarification, setClarification] = useState("");
  const [loading,       setLoading]       = useState(false);
  const [error,         setError]         = useState("");

  const scrollRef = useRef(null);

  // ── Send query ──────────────────────────────────────────────
  const handleSearch = async (overrideQuery) => {
    const q = (overrideQuery ?? query).trim();
    if (!q) return;

    setResults(null);
    setSqlUsed("");
    setClarification("");
    setError("");
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/ai-sql-search`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ user_query: q }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const data = await response.json();

      if (data.error) {
        setError(data.error);
      } else if (data.clarification) {
        setClarification(data.clarification);
      } else if (Array.isArray(data.data)) {
        setResults(data.data);
        setSqlUsed(data.sql_used || "");
        setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 200);
      } else {
        setError("Unexpected response format from server.");
      }
    } catch (err) {
      setError(
        "Network error: Could not reach the server.\n" +
        "Check your API_BASE setting in config.js."
      );
    } finally {
      setLoading(false);
    }
  };

  // ── Result card ─────────────────────────────────────────────
  const renderResultCard = (item, index) => {
    const entries = Object.entries(item);
    const getValueStyle = (key, value) => {
      if (key === "status") {
        if (String(value).toLowerCase() === "present") return styles.valuePresent;
        if (String(value).toLowerCase() === "absent")  return styles.valueAbsent;
      }
      return styles.cellValue;
    };

    return (
      <View key={index} style={styles.resultCard}>
        <View style={styles.resultCardHeader}>
          <Text style={styles.resultCardIndex}>Record {index + 1}</Text>
        </View>
        {entries.map(([key, value]) => (
          <View key={key} style={styles.cellRow}>
            <Text style={styles.cellKey}>{key.replace(/_/g, " ").toUpperCase()}</Text>
            <Text style={getValueStyle(key, value)}>
              {value !== null && value !== undefined ? String(value) : "—"}
            </Text>
          </View>
        ))}
      </View>
    );
  };

  // ── Render ──────────────────────────────────────────────────
  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor={COLORS.primary} />

      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={{ flex: 1 }}
        keyboardVerticalOffset={90}
      >
        {/* Search bar */}
        <View style={styles.searchContainer}>
          <View style={styles.searchBar}>
            <Ionicons name="sparkles-outline" size={18} color={COLORS.accent} />
            <TextInput
              style={styles.searchInput}
              placeholder="Ask anything about attendance…"
              placeholderTextColor="#9BA3C7"
              value={query}
              onChangeText={setQuery}
              returnKeyType="search"
              onSubmitEditing={() => handleSearch()}
            />
            {query.length > 0 && (
              <TouchableOpacity onPress={() => setQuery("")}>
                <Ionicons name="close-circle" size={18} color={COLORS.textSecondary} />
              </TouchableOpacity>
            )}
          </View>
          <TouchableOpacity
            style={[styles.searchButton, loading && styles.searchButtonDisabled]}
            onPress={() => handleSearch()}
            disabled={loading}
            activeOpacity={0.85}
          >
            {loading ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <Text style={styles.searchButtonText}>Search</Text>
            )}
          </TouchableOpacity>
        </View>

        {/* Scrollable results area */}
        <ScrollView
          ref={scrollRef}
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* A: Suggestions (shown before first search) */}
          {results === null && !loading && !error && !clarification && (
            <View>
              <View style={styles.introBanner}>
                <Ionicons name="sparkles" size={28} color={COLORS.accent} />
                <Text style={styles.introBannerTitle}>AI-Powered Analytics</Text>
                <Text style={styles.introBannerSubtitle}>
                  Ask a question in plain English — AI converts it to SQL instantly.
                </Text>
              </View>
              <Text style={styles.sectionLabel}>💡  Try one of these…</Text>
              {SUGGESTIONS.map((s, i) => (
                <TouchableOpacity
                  key={i}
                  style={styles.suggestionChip}
                  onPress={() => { setQuery(s.text); handleSearch(s.text); }}
                  activeOpacity={0.75}
                >
                  <View style={styles.suggestionIconWrap}>
                    <Ionicons name={s.icon} size={16} color={COLORS.accent} />
                  </View>
                  <Text style={styles.suggestionText}>{s.text}</Text>
                  <Ionicons name="arrow-forward-outline" size={14} color={COLORS.textSecondary} />
                </TouchableOpacity>
              ))}
            </View>
          )}

          {/* B: Loading */}
          {loading && (
            <View style={styles.centreBox}>
              <ActivityIndicator size="large" color={COLORS.accent} />
              <Text style={styles.loadingTitle}>AI is thinking…</Text>
              <Text style={styles.loadingSubtitle}>
                Converting your question to SQL and querying the database.
              </Text>
            </View>
          )}

          {/* C: Error */}
          {!!error && (
            <View style={styles.errorBox}>
              <Ionicons name="alert-circle" size={20} color={COLORS.danger} style={{ marginRight: 10, marginTop: 2 }} />
              <View style={{ flex: 1 }}>
                <Text style={styles.errorTitle}>Something went wrong</Text>
                <Text style={styles.errorBody}>{error}</Text>
              </View>
            </View>
          )}

          {/* D: Clarification */}
          {!!clarification && (
            <View style={styles.clarificationBox}>
              <View style={styles.clarificationHeader}>
                <Ionicons name="help-circle" size={18} color={COLORS.purple} />
                <Text style={styles.clarificationTitle}>AI needs more info</Text>
              </View>
              <Text style={styles.clarificationBody}>{clarification}</Text>
              <Text style={styles.clarificationHint}>Try rephrasing your question above.</Text>
            </View>
          )}

          {/* E: Results */}
          {results !== null && !loading && (
            <View>
              {/* SQL block */}
              {!!sqlUsed && (
                <View style={styles.sqlBlock}>
                  <View style={styles.sqlBlockHeader}>
                    <Ionicons name="code-slash" size={14} color={COLORS.codeText} />
                    <Text style={styles.sqlBlockLabel}>SQL GENERATED</Text>
                  </View>
                  <Text style={styles.sqlBlockCode}>{sqlUsed}</Text>
                </View>
              )}

              {/* Count badge */}
              <View style={styles.resultCountRow}>
                <Ionicons name="checkmark-circle" size={16} color={COLORS.success} />
                <Text style={styles.resultCountText}>
                  {results.length} record{results.length !== 1 ? "s" : ""} found
                </Text>
              </View>

              {results.length === 0 ? (
                <View style={styles.emptyBox}>
                  <Ionicons name="search-outline" size={40} color={COLORS.textSecondary} />
                  <Text style={styles.emptyText}>No results found</Text>
                  <Text style={styles.emptySubtext}>
                    No records matched your query. Try a different question.
                  </Text>
                </View>
              ) : (
                results.map(renderResultCard)
              )}
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// ════════════════════════════════════════════════════════════
const styles = StyleSheet.create({
  container:    { flex: 1, backgroundColor: COLORS.background },
  searchContainer: {
    flexDirection:   "row",
    alignItems:      "center",
    padding:         12,
    gap:             10,
    backgroundColor: COLORS.surface,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  searchBar: {
    flex:            1,
    flexDirection:   "row",
    alignItems:      "center",
    backgroundColor: COLORS.background,
    borderRadius:    12,
    paddingHorizontal: 12,
    paddingVertical:   10,
    gap:             8,
    borderWidth:     1,
    borderColor:     COLORS.border,
  },
  searchInput:    { flex: 1, fontSize: 14, color: COLORS.textPrimary },
  searchButton: {
    backgroundColor: COLORS.accent,
    paddingHorizontal: 20,
    paddingVertical:   12,
    borderRadius:    12,
    minWidth:        82,
    alignItems:      "center",
    elevation:       2,
  },
  searchButtonDisabled: { opacity: 0.55 },
  searchButtonText:     { color: "#fff", fontWeight: "700", fontSize: 14 },
  scrollView:    { flex: 1 },
  scrollContent: { padding: 16, paddingBottom: 50 },
  introBanner: {
    backgroundColor: COLORS.primary,
    borderRadius:    18,
    padding:         22,
    alignItems:      "center",
    marginBottom:    20,
    elevation:       4,
    shadowColor:     COLORS.primary,
    shadowOpacity:   0.25,
    shadowRadius:    10,
    shadowOffset:    { width: 0, height: 4 },
  },
  introBannerTitle:    { fontSize: 18, fontWeight: "800", color: "#fff", marginTop: 10 },
  introBannerSubtitle: { fontSize: 13, color: "rgba(255,255,255,0.6)", marginTop: 6, textAlign: "center", lineHeight: 19 },
  sectionLabel:        { fontSize: 12, fontWeight: "700", color: COLORS.textSecondary, letterSpacing: 0.5, marginBottom: 10 },
  suggestionChip: {
    flexDirection:   "row",
    alignItems:      "center",
    backgroundColor: COLORS.surface,
    borderRadius:    12,
    paddingVertical: 13,
    paddingHorizontal: 14,
    marginBottom:    8,
    borderWidth:     1,
    borderColor:     COLORS.border,
    gap:             10,
    elevation:       1,
  },
  suggestionIconWrap: { width: 30, height: 30, borderRadius: 8, backgroundColor: COLORS.accentLight, alignItems: "center", justifyContent: "center" },
  suggestionText:     { flex: 1, fontSize: 14, color: COLORS.textPrimary, fontWeight: "500" },
  centreBox:          { alignItems: "center", marginTop: 70, gap: 10 },
  loadingTitle:       { fontSize: 16, fontWeight: "700", color: COLORS.textPrimary },
  loadingSubtitle:    { fontSize: 13, color: COLORS.textSecondary, textAlign: "center" },
  errorBox: {
    flexDirection: "row", alignItems: "flex-start",
    backgroundColor: COLORS.dangerLight,
    borderRadius: 14, padding: 16,
    borderLeftWidth: 4, borderLeftColor: COLORS.danger,
  },
  errorTitle:  { fontSize: 14, fontWeight: "700", color: COLORS.danger, marginBottom: 4 },
  errorBody:   { fontSize: 13, color: "#B71C1C", lineHeight: 20 },
  clarificationBox: {
    backgroundColor: COLORS.purpleLight,
    borderRadius: 14, padding: 16,
    borderLeftWidth: 4, borderLeftColor: COLORS.purple,
  },
  clarificationHeader:  { flexDirection: "row", alignItems: "center", gap: 7, marginBottom: 8 },
  clarificationTitle:   { fontSize: 14, fontWeight: "700", color: COLORS.purple },
  clarificationBody:    { fontSize: 14, color: "#37006E", lineHeight: 21, fontStyle: "italic", marginBottom: 8 },
  clarificationHint:    { fontSize: 12, color: "#6B4FA0", fontWeight: "500" },
  sqlBlock: { backgroundColor: COLORS.codeBg, borderRadius: 12, padding: 14, marginBottom: 14 },
  sqlBlockHeader: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 8 },
  sqlBlockLabel:  { fontSize: 10, fontWeight: "700", color: COLORS.codeText, letterSpacing: 1.5 },
  sqlBlockCode:   { fontFamily: Platform.OS === "ios" ? "Courier New" : "monospace", fontSize: 12, color: "#E0F2F1", lineHeight: 20 },
  resultCountRow: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 12 },
  resultCountText:{ fontSize: 13, fontWeight: "600", color: COLORS.textSecondary },
  resultCard: {
    backgroundColor: COLORS.surface,
    borderRadius: 14, marginBottom: 12,
    overflow: "hidden", elevation: 2,
    shadowColor: "#000", shadowOpacity: 0.06, shadowRadius: 8, shadowOffset: { width: 0, height: 2 },
    borderWidth: 1, borderColor: COLORS.border,
  },
  resultCardHeader:{ backgroundColor: COLORS.accent, paddingHorizontal: 14, paddingVertical: 7 },
  resultCardIndex: { fontSize: 11, fontWeight: "700", color: "rgba(255,255,255,0.85)", letterSpacing: 0.5 },
  cellRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 14, paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: "#F0F2FF" },
  cellKey:      { fontSize: 10, fontWeight: "700", color: COLORS.textSecondary, letterSpacing: 0.8, flex: 1 },
  cellValue:    { fontSize: 14, fontWeight: "600", color: COLORS.textPrimary, flex: 1, textAlign: "right" },
  valuePresent: { fontSize: 14, fontWeight: "700", color: COLORS.success, flex: 1, textAlign: "right" },
  valueAbsent:  { fontSize: 14, fontWeight: "700", color: COLORS.danger,  flex: 1, textAlign: "right" },
  emptyBox:     { alignItems: "center", paddingVertical: 50, gap: 10 },
  emptyText:    { fontSize: 16, fontWeight: "700", color: COLORS.textSecondary },
  emptySubtext: { fontSize: 13, color: COLORS.textSecondary, textAlign: "center", lineHeight: 19, paddingHorizontal: 20 },
});
