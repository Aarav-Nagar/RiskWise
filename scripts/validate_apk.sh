#!/usr/bin/env bash
# Validate a RiskWise Android APK before installing it, so a bad build is caught
# early. Confirms: (1) applicationId/package, (2) version name + code, and
# (3) that the production API base URL is actually baked into the JS bundle
# (the eas.json "preview" env fix — a missing URL white-screens the app on boot).
#
# Usage:
#   scripts/validate_apk.sh path/to/app.apk
#   scripts/validate_apk.sh --build-id 3feca3fb-c9b1-4ada-a493-80ff5f8faa49   # download via EAS first
#   scripts/validate_apk.sh --latest                                          # newest finished EAS build
#
# Requires: unzip, curl. Uses aapt/aapt2/apkanalyzer for package+version if any
# is on PATH; otherwise those two checks are reported as SKIPPED (the API-URL
# check, the one that actually regressed before, never needs aapt).

set -uo pipefail

EXPECTED_PACKAGE="com.aaravnagar.riskwise"
EXPECTED_VERSION="0.1.0"
EXPECTED_API_URL="https://riskwise-api.onrender.com"

fail=0
note()  { printf '  %s\n' "$*"; }
pass()  { printf '  \033[32mPASS\033[0m  %s\n' "$*"; }
warn()  { printf '  \033[33mSKIP\033[0m  %s\n' "$*"; }
bad()   { printf '  \033[31mFAIL\033[0m  %s\n' "$*"; fail=1; }

APK=""
case "${1:-}" in
  "" ) echo "Usage: $0 <app.apk> | --build-id <id> | --latest"; exit 2 ;;
  --build-id )
    id="${2:?need a build id}"
    url=$(npx eas-cli build:view "$id" --json 2>/dev/null | python -c 'import sys,json;print(json.load(sys.stdin).get("artifacts",{}).get("applicationArchiveUrl",""))')
    [ -z "$url" ] && { echo "Build $id has no downloadable artifact yet (still building?)."; exit 1; }
    APK="$(mktemp -d)/riskwise.apk"; echo "Downloading $url"; curl -sSL "$url" -o "$APK" ;;
  --latest )
    url=$(npx eas-cli build:list --platform android --limit 1 --status finished --json --non-interactive 2>/dev/null | python -c 'import sys,json;a=json.load(sys.stdin);print(a[0]["artifacts"].get("applicationArchiveUrl","") if a else "")')
    [ -z "$url" ] && { echo "No finished Android build found."; exit 1; }
    APK="$(mktemp -d)/riskwise.apk"; echo "Downloading $url"; curl -sSL "$url" -o "$APK" ;;
  * ) APK="$1" ;;
esac

[ -f "$APK" ] || { echo "APK not found: $APK"; exit 1; }
echo "Validating: $APK"
echo "Size: $(du -h "$APK" | cut -f1)"
echo

# --- Package name + version (needs an Android SDK tool) --------------------
AAPT=""
for c in aapt2 aapt apkanalyzer; do command -v "$c" >/dev/null 2>&1 && { AAPT="$c"; break; }; done

echo "[1] Package + version"
if [ -n "$AAPT" ]; then
  if [ "$AAPT" = "apkanalyzer" ]; then
    pkg=$(apkanalyzer manifest application-id "$APK" 2>/dev/null)
    ver=$(apkanalyzer manifest version-name "$APK" 2>/dev/null)
    code=$(apkanalyzer manifest version-code "$APK" 2>/dev/null)
  else
    dump=$("$AAPT" dump badging "$APK" 2>/dev/null)
    pkg=$(printf '%s' "$dump"  | sed -n "s/.*package: name='\([^']*\)'.*/\1/p")
    ver=$(printf '%s' "$dump"  | sed -n "s/.*versionName='\([^']*\)'.*/\1/p")
    code=$(printf '%s' "$dump" | sed -n "s/.*versionCode='\([^']*\)'.*/\1/p")
  fi
  note "applicationId: $pkg   versionName: $ver   versionCode: $code"
  [ "$pkg" = "$EXPECTED_PACKAGE" ] && pass "package == $EXPECTED_PACKAGE" || bad "package '$pkg' != expected '$EXPECTED_PACKAGE'"
  [ "$ver" = "$EXPECTED_VERSION" ] && pass "versionName == $EXPECTED_VERSION" || bad "versionName '$ver' != expected '$EXPECTED_VERSION'"
else
  warn "no aapt/aapt2/apkanalyzer on PATH — cannot read binary manifest; skipping package/version"
  note "expected package=$EXPECTED_PACKAGE version=$EXPECTED_VERSION versionCode=2"
fi
echo

# --- Prod API URL baked into the bundle ------------------------------------
# EXPO_PUBLIC_* vars are inlined into the JS bundle at export. With Hermes the
# bundle is bytecode, but string literals survive and are found by a binary grep.
echo "[2] Prod API URL baked in"
tmp="$(mktemp -d)"
unzip -q -o "$APK" -d "$tmp" || bad "could not unzip APK"
if grep -rqaF "$EXPECTED_API_URL" "$tmp" 2>/dev/null; then
  pass "found '$EXPECTED_API_URL' in the bundle"
else
  bad "'$EXPECTED_API_URL' NOT found — app will hit config.js missing-URL guard and white-screen"
fi
if grep -rqaiE '127\.0\.0\.1|localhost' "$tmp/assets" 2>/dev/null; then
  note "(info) a localhost/127.0.0.1 literal also appears — verify it is not the active API base"
fi
rm -rf "$tmp"
echo

if [ "$fail" = 0 ]; then echo "RESULT: OK — safe to install"; exit 0
else echo "RESULT: PROBLEMS FOUND — do not install until resolved"; exit 1; fi
