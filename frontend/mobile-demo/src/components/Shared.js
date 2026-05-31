import React from "react";
import { Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { Card } from "./Card";
import { palette } from "../theme/theme";

export function ScreenScroll({ children }) {
  return (
    <ScrollView style={styles.scroll} showsVerticalScrollIndicator={false}>
      {children}
      <View style={styles.bottomSpace} />
    </ScrollView>
  );
}

export function Header({ kicker, title, subtitle, right }) {
  return (
    <View style={styles.header}>
      <View style={styles.headerText}>
        {kicker ? <Text style={styles.kicker}>{kicker}</Text> : null}
        <Text style={styles.title}>{title}</Text>
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      </View>
      {right ? <View>{right}</View> : null}
    </View>
  );
}

export function Field({
  label,
  value,
  onChangeText,
  suffix,
  placeholder,
  secureTextEntry,
  keyboardType,
  autoCapitalize = "sentences",
  error,
  helper
}) {
  return (
    <View style={styles.fieldWrap}>
      <Text style={styles.inputLabel}>{label}</Text>
      <View style={[styles.field, error && styles.fieldError]}>
        <TextInput
          value={String(value)}
          onChangeText={onChangeText}
          style={styles.input}
          placeholder={placeholder}
          placeholderTextColor="#9AA5A0"
          secureTextEntry={secureTextEntry}
          keyboardType={keyboardType}
          autoCapitalize={autoCapitalize}
        />
        {suffix ? <Text style={styles.fieldSuffix}>{suffix}</Text> : null}
      </View>
      {error ? <Text style={styles.fieldErrorText}>{error}</Text> : helper ? <Text style={styles.fieldHelperText}>{helper}</Text> : null}
    </View>
  );
}

export function SelectLike({ label, value, options = [], onSelect }) {
  const [open, setOpen] = React.useState(false);
  const choose = (option) => {
    onSelect?.(option);
    setOpen(false);
  };

  if (Platform.OS === "web") {
    return (
      <View style={styles.fieldWrap}>
        <Text style={styles.inputLabel}>{label}</Text>
        <select
          aria-label={label}
          value={value}
          onChange={(event) => choose(event.target.value)}
          style={webSelectStyle}
        >
          {options.map((option) => (
            <option value={option} key={option}>
              {option}
            </option>
          ))}
        </select>
      </View>
    );
  }

  return (
    <View style={styles.fieldWrap}>
      <Text style={styles.inputLabel}>{label}</Text>
      <Pressable style={styles.field} onPress={() => setOpen((current) => !current)}>
        <Text style={styles.selectText}>{value}</Text>
        <Text style={styles.fieldSuffix}>{open ? "^" : "v"}</Text>
      </Pressable>
      {open ? (
        <View style={styles.optionPanel}>
          {options.map((option) => (
            <Pressable
              key={option}
              accessibilityRole="button"
              accessibilityLabel={`Select ${option}`}
              style={[styles.option, option === value && styles.optionActive]}
              onPress={() => choose(option)}
              onClick={() => choose(option)}
              onStartShouldSetResponder={() => true}
              onResponderRelease={() => choose(option)}
            >
              <Text
                style={[styles.optionText, option === value && styles.optionTextActive]}
                onPress={() => choose(option)}
                onClick={() => choose(option)}
              >
                {option}
              </Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

const webSelectStyle = {
  width: "100%",
  minHeight: 43,
  border: `1px solid ${palette.border}`,
  borderRadius: 12,
  padding: "0 12px",
  backgroundColor: "#FBFCFB",
  color: palette.dark,
  fontWeight: "800",
  fontSize: 13,
  outline: "none"
};

export function PrimaryButton({ label, onPress, style, disabled }) {
  return (
    <Pressable style={[styles.primaryButton, disabled && styles.disabled, style]} onPress={disabled ? undefined : onPress}>
      <Text style={styles.primaryButtonText}>{label}</Text>
      <Text style={styles.primaryButtonArrow}>-&gt;</Text>
    </Pressable>
  );
}

export function SecondaryButton({ label, onPress }) {
  return (
    <Pressable style={styles.secondaryButton} onPress={onPress}>
      <Text style={styles.secondaryButtonText}>{label}</Text>
    </Pressable>
  );
}

export function AiCard({ text, compact }) {
  return (
    <Card style={[styles.aiCard, compact && styles.aiCardCompact]}>
      <View style={styles.aiBadge}>
        <Text style={styles.aiBadgeText}>RW</Text>
      </View>
      <View style={styles.flex}>
        <Text style={styles.mediumTitle}>Risk Review</Text>
        <Text style={styles.bodyText}>{text}</Text>
      </View>
      <View style={styles.botBubble}>
        <Text style={styles.botText}>?</Text>
      </View>
    </Card>
  );
}

export function ChipRow({ items, active }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chips}>
      {items.map((item) => (
        <View key={item} style={[styles.chip, item === active && styles.chipActive]}>
          <Text style={[styles.chipText, item === active && styles.chipTextActive]}>{item}</Text>
        </View>
      ))}
    </ScrollView>
  );
}

export function StatCard({ label, value, sub, good, risk }) {
  return (
    <Card style={styles.statCard}>
      <Text style={styles.cardLabel}>{label}</Text>
      <Text style={[styles.statValue, good && styles.goodText, risk && styles.riskText]}>{value}</Text>
      {sub ? <Text style={styles.microcopy}>{sub}</Text> : null}
    </Card>
  );
}

export function ErrorCard({ message }) {
  return (
    <Card style={styles.errorCard}>
      <Text style={styles.mediumTitle}>Something went wrong</Text>
      <Text style={styles.bodyText}>{message}</Text>
    </Card>
  );
}

export function money(value) {
  return `$${Number(value || 0).toLocaleString()}`;
}

export const sharedText = StyleSheet.create({
  sectionTitle: {
    color: palette.dark,
    fontSize: 15,
    fontWeight: "900",
    marginBottom: 10
  },
  mediumTitle: {
    color: palette.dark,
    fontSize: 14,
    fontWeight: "900"
  },
  bodyText: {
    color: palette.muted,
    fontSize: 12,
    lineHeight: 17
  },
  cardLabel: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "800",
    marginBottom: 4
  },
  microcopy: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "700",
    marginTop: 6
  }
});

const styles = StyleSheet.create({
  scroll: {
    flex: 1,
    paddingHorizontal: 18
  },
  bottomSpace: {
    height: 12
  },
  header: {
    paddingTop: 10,
    paddingBottom: 14,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center"
  },
  headerText: {
    flex: 1
  },
  kicker: {
    textAlign: "center",
    color: palette.green,
    fontWeight: "900",
    letterSpacing: 0.4,
    marginBottom: 8
  },
  title: {
    color: palette.dark,
    fontSize: 23,
    fontWeight: "900"
  },
  subtitle: {
    color: palette.muted,
    marginTop: 4,
    fontSize: 13,
    lineHeight: 18
  },
  fieldWrap: {
    flex: 1,
    marginBottom: 10
  },
  inputLabel: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: "800",
    marginBottom: 5
  },
  field: {
    minHeight: 43,
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 12,
    paddingHorizontal: 12,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FBFCFB"
  },
  fieldError: {
    borderColor: palette.red,
    backgroundColor: "#FFFBFB"
  },
  input: {
    flex: 1,
    color: palette.dark,
    fontWeight: "800",
    outlineStyle: "none"
  },
  fieldErrorText: {
    color: palette.red,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 5
  },
  fieldHelperText: {
    color: palette.muted,
    fontSize: 10,
    fontWeight: "700",
    marginTop: 5
  },
  selectText: {
    flex: 1,
    color: palette.dark,
    fontWeight: "800",
    fontSize: 13
  },
  fieldSuffix: {
    color: palette.green,
    fontSize: 12,
    fontWeight: "900"
  },
  optionPanel: {
    marginTop: 6,
    borderWidth: 1,
    borderColor: palette.border,
    borderRadius: 12,
    backgroundColor: "#FFFFFF",
    overflow: "hidden"
  },
  option: {
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#F0F3F0"
  },
  optionActive: {
    backgroundColor: palette.greenSoft
  },
  optionText: {
    color: palette.dark,
    fontSize: 12,
    fontWeight: "800"
  },
  optionTextActive: {
    color: palette.green
  },
  primaryButton: {
    minHeight: 49,
    borderRadius: 15,
    backgroundColor: palette.green,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 8,
    marginTop: 4
  },
  disabled: {
    opacity: 0.65
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "900"
  },
  primaryButtonArrow: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "900"
  },
  secondaryButton: {
    minHeight: 49,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: palette.green,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 14,
    backgroundColor: "#FFFFFF"
  },
  secondaryButtonText: {
    color: palette.green,
    fontWeight: "900"
  },
  aiCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: "#FEFFFE"
  },
  aiCardCompact: {
    marginTop: 0
  },
  aiBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: palette.greenSoft,
    alignItems: "center",
    justifyContent: "center"
  },
  aiBadgeText: {
    color: palette.green,
    fontSize: 11,
    fontWeight: "900"
  },
  botBubble: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#DFF8EA",
    shadowColor: palette.green,
    shadowOpacity: 0.2,
    shadowRadius: 16
  },
  botText: {
    color: palette.green,
    fontSize: 13,
    fontWeight: "900"
  },
  flex: {
    flex: 1
  },
  chips: {
    marginBottom: 12,
    flexGrow: 0
  },
  chip: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 999,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: palette.border,
    marginRight: 8
  },
  chipActive: {
    backgroundColor: palette.green,
    borderColor: palette.green
  },
  chipText: {
    color: palette.muted,
    fontWeight: "900",
    fontSize: 12
  },
  chipTextActive: {
    color: "#FFFFFF"
  },
  statCard: {
    width: "31%",
    minHeight: 88,
    alignItems: "center",
    justifyContent: "center"
  },
  statValue: {
    color: palette.dark,
    fontSize: 20,
    fontWeight: "900",
    textAlign: "center"
  },
  goodText: {
    color: palette.green
  },
  riskText: {
    color: palette.red
  },
  cardLabel: sharedText.cardLabel,
  mediumTitle: sharedText.mediumTitle,
  bodyText: sharedText.bodyText,
  microcopy: sharedText.microcopy,
  errorCard: {
    backgroundColor: "#FFFBFB",
    borderColor: "#FAD1D1"
  }
});
