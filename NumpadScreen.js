// ============================================================
//  screens/NumpadScreen.js  —  OmniTrack AI
//  Rapid-entry attendance screen for teachers.
//  Teachers select a session, type a roll number on the custom
//  numpad, and press OK to call POST /mark-present.
// ============================================================

import { Ionicons } from "@expo/vector-icons";
import { useState } from "react";
import {
  Alert,
  FlatList,
  Modal,
  Platform,
  SafeAreaView,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  Vibration,
  View,
} from "react-native";

// ── Shared config — change API_BASE in config.js ─────────────
import { API_BASE, SESSIONS } from "../config";

// ── Colour palette ────────────────────────────────────────────
const COLORS = {
  primary:       "#0D1B4B",
  accent:        "#3D5AFE",
  accentLight:   "#E8EAFF",
  success:       "#00BFA5",
  danger:        "#FF1744",
  background:    "#F4F6FF",
  surface:       "#FFFFFF",
  textPrimary:   "#0D1B4B",
  textSecondary: "#6B7A99",
  border:        "#D0D6F0",
  numpadKey:     "#EEF0FF",
};

// ── Numpad layout ─────────────────────────────────────────────
const NUMPAD_ROWS = [
  ["1", "2", "3"],
  ["4", "5", "6"],
  ["7", "8", "9"],
  ["CLR", "0", "OK"],
];

// ── Helpers ───────────────────────────────────────────────────
function getTodayDate() {
  const d    = new Date();
  const yyyy = d.getFullYear();
  const mm   = String(d.getMonth() + 1).padStart(2, "0");
  const dd   = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function getFriendlyDate() {
  return new Date().toLocaleDateString("en-PK", {
    weekday: "long",
    day:     "numeric",
    month:   "long",
    year:    "numeric",
  });
}

// ═════════════════════════════════════════════════════════════
export default function NumpadScreen() {
  const [rollNumber,       setRollNumber]       = useState("");
  const [selectedSession,  setSelectedSession]  = useState(SESSIONS[0]);
  const [modalVisible,     setModalVisible]     = useState(false);
  const [isLoading,        setIsLoading]        = useState(false);
  const [lastFeedback,     setLastFeedback]     = useState(null); // { type: 'ok'|'err', text }

  // ── Numpad handlers ─────────────────────────────────────────

  const handleDigitPress = (digit) => {
    Vibration.vibrate(25);
    if (rollNumber.length < 4) {
      setRollNumber((prev) => prev + digit);
    }
  };

  const handleClear = () => {
    Vibration.vibrate(40);
    setRollNumber("");
    setLastFeedback(null);
  };

  const handleSubmit = async () => {
    if (rollNumber.length === 0) {
      Alert.alert("No Input", "Please enter a roll number.");
      return;
    }

    Vibration.vibrate(Platform.OS === "android" ? [0, 30, 60, 30] : 60);
    setIsLoading(true);
    setLastFeedback(null);

    const payload = {
      roll_number:  parseInt(rollNumber, 10),
      date:         getTodayDate(),
      session_name: selectedSession,
    };

    try {
      const response = await fetch(`${API_BASE}/mark-present`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();

      if (data.error) {
        setLastFeedback({ type: "err", text: data.error });
      } else {
        // Show inline success, auto-clear after 1.5 s
        setLastFeedback({ type: "ok", text: `Roll ${rollNumber} ✅ Present` });
        setRollNumber("");
        setTimeout(() => setLastFeedback(null), 1500);
      }
    } catch (err) {
      setLastFeedback({
        type: "err",
        text: `Cannot reach server.\nCheck Wi-Fi or ngrok URL in config.js.`,
      });
    } finally {
      setIsLoading(false);
    }
  };

  // ── Numpad button renderer ───────────────────────────────────
  const renderButton = (label) => {
    if (label === "CLR") {
      return (
        <TouchableOpacity
          key="CLR"
          style={[styles.numpadKey, styles.clearKey]}
          onPress={handleClear}
          activeOpacity={0.7}
        >
          <Ionicons name="backspace-outline" size={26} color="#fff" />
        </TouchableOpacity>
      );
    }
    if (label === "OK") {
      return (
        <TouchableOpacity
          key="OK"
          style={[styles.numpadKey, styles.submitKey, isLoading && styles.disabledKey]}
          onPress={handleSubmit}
          activeOpacity={0.7}
          disabled={isLoading}
        >
          <Ionicons
            name={isLoading ? "hourglass-outline" : "checkmark-sharp"}
            size={30}
            color="#fff"
          />
        </TouchableOpacity>
      );
    }
    return (
      <TouchableOpacity
        key={label}
        style={styles.numpadKey}
        onPress={() => handleDigitPress(label)}
        activeOpacity={0.7}
      >
        <Text style={styles.numpadKeyText}>{label}</Text>
      </TouchableOpacity>
    );
  };

  // ── Render ───────────────────────────────────────────────────
  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor={COLORS.primary} />

      {/* Date badge */}
      <View style={styles.dateBadge}>
        <Ionicons name="calendar-outline" size={13} color={COLORS.accent} />
        <Text style={styles.dateBadgeText}>{getFriendlyDate()}</Text>
      </View>

      {/* Session picker */}
      <TouchableOpacity
        style={styles.sessionPicker}
        onPress={() => setModalVisible(true)}
        activeOpacity={0.8}
      >
        <View style={styles.sessionPickerLeft}>
          <Ionicons name="school-outline" size={18} color={COLORS.accent} />
          <View style={{ marginLeft: 10 }}>
            <Text style={styles.sessionPickerLabel}>SESSION</Text>
            <Text style={styles.sessionPickerValue} numberOfLines={1}>
              {selectedSession}
            </Text>
          </View>
        </View>
        <Ionicons name="chevron-down" size={18} color={COLORS.textSecondary} />
      </TouchableOpacity>

      {/* Roll-number display */}
      <View style={styles.display}>
        <View style={styles.digitRow}>
          {[0, 1, 2, 3].map((i) => {
            const char   = rollNumber[i] || "";
            const active = i === rollNumber.length && rollNumber.length < 4;
            return (
              <View
                key={i}
                style={[
                  styles.digitSlot,
                  active          && styles.digitSlotActive,
                  rollNumber[i]   && styles.digitSlotFilled,
                ]}
              >
                <Text style={styles.digitChar}>
                  {char || (active ? "|" : "–")}
                </Text>
              </View>
            );
          })}
        </View>
        <Text style={styles.displayHint}>ROLL NUMBER</Text>
      </View>

      {/* Inline feedback strip */}
      {lastFeedback && (
        <View
          style={[
            styles.feedbackStrip,
            lastFeedback.type === "ok" ? styles.feedbackOk : styles.feedbackErr,
          ]}
        >
          <Text style={styles.feedbackText}>{lastFeedback.text}</Text>
        </View>
      )}

      {/* Numpad */}
      <View style={styles.numpad}>
        {NUMPAD_ROWS.map((row, ri) => (
          <View key={ri} style={styles.numpadRow}>
            {row.map(renderButton)}
          </View>
        ))}
      </View>

      {/* Session picker modal */}
      <Modal
        visible={modalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <View style={styles.modalHandle} />
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Select Session</Text>
              <TouchableOpacity onPress={() => setModalVisible(false)}>
                <Ionicons name="close-circle" size={26} color={COLORS.textSecondary} />
              </TouchableOpacity>
            </View>
            <FlatList
              data={SESSIONS}
              keyExtractor={(item) => item}
              showsVerticalScrollIndicator={false}
              renderItem={({ item }) => {
                const selected = item === selectedSession;
                return (
                  <TouchableOpacity
                    style={[styles.sessionRow, selected && styles.sessionRowSelected]}
                    onPress={() => { setSelectedSession(item); setModalVisible(false); }}
                    activeOpacity={0.7}
                  >
                    <Text style={[styles.sessionRowText, selected && styles.sessionRowTextSelected]}>
                      {item}
                    </Text>
                    {selected && (
                      <Ionicons name="checkmark-circle" size={20} color={COLORS.surface} />
                    )}
                  </TouchableOpacity>
                );
              }}
            />
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

// ════════════════════════════════════════════════════════════
const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
    alignItems: "center",
    paddingTop: 12,
  },
  dateBadge: {
    flexDirection:   "row",
    alignItems:      "center",
    backgroundColor: COLORS.accentLight,
    paddingHorizontal: 14,
    paddingVertical:   6,
    borderRadius:    20,
    marginBottom:    14,
    gap: 5,
  },
  dateBadgeText: { fontSize: 12, fontWeight: "600", color: COLORS.accent },
  sessionPicker: {
    flexDirection:   "row",
    alignItems:      "center",
    justifyContent:  "space-between",
    backgroundColor: COLORS.surface,
    width:           "90%",
    borderRadius:    14,
    paddingHorizontal: 16,
    paddingVertical:   13,
    marginBottom:    18,
    elevation:       3,
    shadowColor:     COLORS.primary,
    shadowOpacity:   0.08,
    shadowRadius:    8,
    shadowOffset:    { width: 0, height: 2 },
    borderWidth:     1,
    borderColor:     COLORS.border,
  },
  sessionPickerLeft:  { flexDirection: "row", alignItems: "center", flex: 1 },
  sessionPickerLabel: { fontSize: 10, fontWeight: "700", color: COLORS.textSecondary, letterSpacing: 1.2 },
  sessionPickerValue: { fontSize: 14, fontWeight: "700", color: COLORS.textPrimary, marginTop: 1 },
  display: {
    width:          "90%",
    backgroundColor: COLORS.primary,
    borderRadius:   20,
    alignItems:     "center",
    paddingVertical: 28,
    paddingHorizontal: 16,
    marginBottom:   10,
    elevation:      8,
    shadowColor:    COLORS.primary,
    shadowOpacity:  0.4,
    shadowRadius:   16,
    shadowOffset:   { width: 0, height: 6 },
  },
  digitRow:    { flexDirection: "row", gap: 12, marginBottom: 10 },
  digitSlot: {
    width: 58, height: 72, borderRadius: 12,
    backgroundColor: "rgba(255,255,255,0.07)",
    borderWidth: 1.5, borderColor: "rgba(255,255,255,0.15)",
    alignItems: "center", justifyContent: "center",
  },
  digitSlotActive: { borderColor: COLORS.accent, backgroundColor: "rgba(61,90,254,0.18)" },
  digitSlotFilled: { borderColor: "rgba(255,255,255,0.35)", backgroundColor: "rgba(255,255,255,0.10)" },
  digitChar: {
    fontSize: 34, fontWeight: "800", color: "#fff",
    fontFamily: Platform.OS === "ios" ? "Courier New" : "monospace",
  },
  displayHint: { fontSize: 10, fontWeight: "700", color: "rgba(255,255,255,0.35)", letterSpacing: 3 },

  // Feedback strip
  feedbackStrip: {
    width: "90%", borderRadius: 10,
    paddingVertical: 9, paddingHorizontal: 16,
    marginBottom: 8, alignItems: "center",
  },
  feedbackOk:   { backgroundColor: "#E6F9F5" },
  feedbackErr:  { backgroundColor: "#FFF0F0" },
  feedbackText: { fontSize: 13, fontWeight: "700" },

  numpad: {
    width: "90%", backgroundColor: COLORS.surface,
    borderRadius: 22, padding: 16, gap: 10,
    elevation: 4,
    shadowColor: "#000", shadowOpacity: 0.07, shadowRadius: 12, shadowOffset: { width: 0, height: 3 },
    borderWidth: 1, borderColor: COLORS.border,
  },
  numpadRow:    { flexDirection: "row", gap: 10 },
  numpadKey: {
    flex: 1, height: 66, borderRadius: 14,
    backgroundColor: COLORS.numpadKey,
    alignItems: "center", justifyContent: "center",
    elevation: 1,
    shadowColor: COLORS.primary, shadowOpacity: 0.06, shadowRadius: 3, shadowOffset: { width: 0, height: 1 },
  },
  numpadKeyText: { fontSize: 28, fontWeight: "700", color: COLORS.textPrimary },
  clearKey:      { backgroundColor: COLORS.danger },
  submitKey:     { backgroundColor: COLORS.success },
  disabledKey:   { opacity: 0.5 },

  modalOverlay:  { flex: 1, backgroundColor: "rgba(13,27,75,0.5)", justifyContent: "flex-end" },
  modalSheet:    { backgroundColor: COLORS.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingHorizontal: 16, paddingBottom: 34, maxHeight: "65%" },
  modalHandle:   { width: 42, height: 5, backgroundColor: COLORS.border, borderRadius: 3, alignSelf: "center", marginTop: 10, marginBottom: 14 },
  modalHeader:   { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12, paddingHorizontal: 4 },
  modalTitle:    { fontSize: 17, fontWeight: "800", color: COLORS.textPrimary },
  sessionRow:    { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 13, paddingHorizontal: 16, borderRadius: 12, marginBottom: 6, backgroundColor: COLORS.background },
  sessionRowSelected:     { backgroundColor: COLORS.accent },
  sessionRowText:         { fontSize: 15, fontWeight: "500", color: COLORS.textPrimary },
  sessionRowTextSelected: { color: "#fff", fontWeight: "700" },
});
