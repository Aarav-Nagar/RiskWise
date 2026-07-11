import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useAuth, useClerk, useSignIn, useSignUp, useUser } from "@clerk/clerk-expo";
import { AppShell } from "./components/AppShell";
import { Card } from "./components/Card";
import { deepMerge, PrimaryButton, sharedText } from "./components/Shared";
import { tradeDraft } from "./data/mockData";
import { AuthScreen } from "./screens/AuthScreen";
import { CheckScreen } from "./screens/CheckScreen";
import { HomeScreen } from "./screens/HomeScreen";
import { ProfileScreen } from "./screens/ProfileScreen";
import { ReportScreen } from "./screens/ReportScreen";
import { ChatScreen } from "./screens/ChatScreen";
import { clearRiskWiseContext, configureAuthService, deleteRiskWiseAccount, lookupProfileByEmail, requestPasswordReset, syncClerkProfile, updateProfileSettings } from "./services/authService";
import { configureApiAuth, generateTradeCheck, listSavedChecks, saveCheck } from "./services/apiClient";

export default function App() {
  if (!hasClerkRuntime()) {
    return <PreviewApp />;
  }

  return <ClerkApp />;
}

function ClerkApp() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const { user: clerkUser } = useUser();
  const { signOut: clerkSignOut } = useClerk();
  const signUpState = useSignUp();
  const signInState = useSignIn();
  const [currentUser, setCurrentUser] = useState(null);
  const [activeTab, setActiveTab] = useState("Home");
  const [draft, setDraft] = useState(tradeDraft);
  const [currentReport, setCurrentReport] = useState(null);
  const [savedChecks, setSavedChecks] = useState([]);
  const [saveStatus, setSaveStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(true);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState("");
  const [pendingVerification, setPendingVerification] = useState(null);
  const [pendingSignInVerification, setPendingSignInVerification] = useState(null);
  const [pendingPasswordReset, setPendingPasswordReset] = useState(null);

  useEffect(() => {
    configureApiAuth({ getToken });
    configureAuthService({ getToken });
  }, [getToken]);

  useEffect(() => {
    let mounted = true;
    async function restoreClerkProfile() {
      if (isLocalPreviewSession()) {
        enterApp({
          id: "preview-user",
          clerkId: "preview-local",
          name: "Aarav Preview",
          email: "preview@riskwise.local",
          accountSize: 25000,
          riskBudgetPercent: 2,
          experienceLevel: "Learning options"
        });
        setShowOnboarding(false);
        setReady(true);
        return;
      }
      if (!isLoaded) {
        return;
      }
      if (!isSignedIn || !clerkUser) {
        setCurrentUser(null);
        setReady(true);
        return;
      }
      try {
        const session = await restoreRiskWiseUserFromClerk(clerkUser);
        if (!mounted) {
          return;
        }
        setAuthError("");
        enterApp(session);
      } catch (err) {
        if (mounted) {
          setAuthError(err.message || "Could not restore your profile.");
        }
      } finally {
        if (mounted) {
          setReady(true);
        }
      }
    }
    restoreClerkProfile();
    return () => {
      mounted = false;
    };
  }, [isLoaded, isSignedIn, clerkUser?.id]);

  useEffect(() => {
    let mounted = true;
    async function restoreSavedChecks() {
      if (!currentUser?.id) {
        setSavedChecks([]);
        return;
      }
      try {
        const rows = await listSavedChecks(currentUser);
        if (mounted) {
          setSavedChecks(rows);
        }
      } catch (err) {
        if (mounted) {
          setSaveStatus("Saved checks are unavailable right now.");
        }
      }
    }
    restoreSavedChecks();
    return () => {
      mounted = false;
    };
  }, [currentUser?.id]);

  async function handleTradeCheck(options = {}) {
    setLoading(true);
    setError("");
    try {
      const nextReport = await generateTradeCheck(draft, currentUser);
      setCurrentReport(nextReport);
      setSaveStatus("");
      if (!options.stayOnCheck) {
        setActiveTab("Report");
      }
      return nextReport;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveCheck() {
    if (!currentReport || !currentUser) {
      return;
    }
    setSaveStatus("Saving...");
    try {
      const item = await saveCheck(currentUser, currentReport);
      setSavedChecks((items) => [item, ...items.filter((existing) => existing.tradeCheckId !== item.tradeCheckId)].slice(0, 10));
      setSaveStatus("Saved to your RiskWise account.");
    } catch (err) {
      setSaveStatus("Could not save this check. Try again.");
    }
  }

  async function dismissOnboarding() {
    setShowOnboarding(false);
  }

  async function handleCreateAccount(form) {
    setAuthLoading(true);
    setAuthError("");
    try {
      if (!signUpState.isLoaded) {
        throw new Error("Account service is still loading.");
      }
      await signUpState.signUp.create({
        emailAddress: form.email.trim(),
        password: form.password
      });
      await signUpState.signUp.prepareEmailAddressVerification({ strategy: "email_code" });
      setPendingVerification({ form, email: form.email.trim() });
    } catch (err) {
      setAuthError(formatClerkError(err));
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleSignIn(form) {
    setAuthLoading(true);
    setAuthError("");
    try {
      if (!signInState.isLoaded) {
        throw new Error("Account service is still loading.");
      }
      const result = await signInState.signIn.create({
        identifier: form.email.trim(),
        password: form.password
      });
      if (result.status !== "complete") {
        const canContinue = await prepareSignInVerification(result, form);
        if (canContinue) {
          return;
        }
        throw new Error(describeSignInStatus(result.status));
      }
      await activateSignInResult(result, form.email.trim(), form);
    } catch (err) {
      if (isAlreadySignedInError(err)) {
        try {
          const existingSessionId = err?.errors?.[0]?.meta?.sessionId;
          if (existingSessionId && signInState.setActive) {
            await signInState.setActive({ session: existingSessionId });
          }
          const appUser = clerkUser
            ? await restoreRiskWiseUserFromClerk(clerkUser, form)
            : await restoreRiskWiseUserFromEmail(form.email.trim(), form);
          setAuthError("");
          enterApp(appUser);
          return;
        } catch (restoreErr) {
          setAuthError(formatClerkError(restoreErr));
          return;
        }
      }
      setAuthError(formatClerkError(err));
    } finally {
      setAuthLoading(false);
    }
  }

  async function prepareSignInVerification(result, form) {
    const email = form.email.trim();
    const firstFactor = findEmailCodeFactor(result.supportedFirstFactors);
    const secondFactor = findEmailCodeFactor(result.supportedSecondFactors);

    if (result.status === "needs_first_factor" && firstFactor) {
      await signInState.signIn.prepareFirstFactor({
        strategy: "email_code",
        emailAddressId: firstFactor.emailAddressId
      });
      setPendingSignInVerification({ email, form, stage: "first" });
      return true;
    }

    if ((result.status === "needs_second_factor" || result.status === "needs_client_trust") && secondFactor) {
      await signInState.signIn.prepareSecondFactor({
        strategy: "email_code",
        emailAddressId: secondFactor.emailAddressId
      });
      setPendingSignInVerification({ email, form, stage: "second" });
      return true;
    }

    return false;
  }

  async function handleVerifySignInEmail(code) {
    if (!pendingSignInVerification) {
      return;
    }
    setAuthLoading(true);
    setAuthError("");
    try {
      if (!signInState.isLoaded) {
        throw new Error("Account service is still loading.");
      }
      const result =
        pendingSignInVerification.stage === "second"
          ? await signInState.signIn.attemptSecondFactor({ strategy: "email_code", code })
          : await signInState.signIn.attemptFirstFactor({ strategy: "email_code", code });
      if (result.status !== "complete") {
        throw new Error(describeSignInStatus(result.status));
      }
      const { email, form } = pendingSignInVerification;
      setPendingSignInVerification(null);
      await activateSignInResult(result, email, form);
    } catch (err) {
      setAuthError(formatClerkError(err));
    } finally {
      setAuthLoading(false);
    }
  }

  async function activateSignInResult(result, email, form = {}) {
    if (signInState.setActive && result.createdSessionId) {
      await signInState.setActive({ session: result.createdSessionId });
    }
    const user = await restoreRiskWiseUserFromEmail(email, form, result.createdUserId || email);
    enterApp(user);
  }

  async function handleVerifyEmail(code) {
    if (!pendingVerification) {
      return;
    }
    setAuthLoading(true);
    setAuthError("");
    try {
      if (!signUpState.isLoaded) {
        throw new Error("Account service is still loading.");
      }
      const result = await signUpState.signUp.attemptEmailAddressVerification({ code });
      if (result.status !== "complete") {
        throw new Error("Verification is not complete yet.");
      }
      if (signUpState.setActive && result.createdSessionId) {
        await signUpState.setActive({ session: result.createdSessionId });
      }
      const appUser = await syncClerkProfile({
        clerkId: result.createdUserId || pendingVerification.email,
        email: pendingVerification.email,
        name: pendingVerification.form.name,
        profile: pendingVerification.form
      }).catch(() => createLocalRiskWiseUser({
        email: pendingVerification.email,
        profile: pendingVerification.form,
        clerkId: result.createdUserId || pendingVerification.email,
        fallbackName: pendingVerification.form.name
      }));
      setPendingVerification(null);
      enterApp(appUser);
    } catch (err) {
      setAuthError(formatClerkError(err));
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleSignOut() {
    await clerkSignOut();
    setCurrentUser(null);
    setCurrentReport(null);
    setSavedChecks([]);
    setSaveStatus("");
    setActiveTab("Home");
  }

  async function handleDeleteAccount() {
    if (!currentUser?.id) {
      throw new Error("No signed-in user.");
    }
    if (isPreviewUser(currentUser)) {
      await handleSignOut();
      return;
    }
    await deleteRiskWiseAccount(currentUser.id);
    try {
      if (clerkUser?.delete) {
        await clerkUser.delete();
      }
    } catch (err) {
      // Clerk account deletion can be disabled by dashboard policy. App data is still removed.
    }
    await handleSignOut();
  }

  async function handleUpdateProfile(updates) {
    if (!currentUser?.id) {
      throw new Error("No signed-in user.");
    }
    if (isPreviewUser(currentUser)) {
      const nextUser = deepMerge(currentUser, updates);
      setCurrentUser(nextUser);
      return nextUser;
    }
    const nextUser = await updateProfileSettings(currentUser.id, updates);
    setCurrentUser(nextUser);
    return nextUser;
  }

  async function handleClearProfileContext() {
    if (!currentUser?.id) {
      throw new Error("No signed-in user.");
    }
    if (isPreviewUser(currentUser)) {
      const nextUser = {
        ...currentUser,
        savedContext: {
          savedChecks: false,
          chatHistory: false,
          uploadedScreenshots: false,
          watchlist: false
        }
      };
      setCurrentUser(nextUser);
      setSavedChecks([]);
      setCurrentReport(null);
      return nextUser;
    }
    await clearRiskWiseContext(currentUser.id);
    const nextUser = await updateProfileSettings(currentUser.id, {
      savedContext: {
        savedChecks: false,
        chatHistory: false,
        uploadedScreenshots: false,
        watchlist: false
      }
    });
    setCurrentUser(nextUser);
    setSavedChecks([]);
    setCurrentReport(null);
    return nextUser;
  }

  async function handleProfilePasswordReset() {
    if (!currentUser?.email) {
      throw new Error("No profile email is available.");
    }
    if (isPreviewUser(currentUser)) {
      return { email: maskEmail(currentUser.email), message: "Preview mode: password reset is wired for real Clerk accounts." };
    }
    try {
      if (!signInState.isLoaded) {
        throw new Error("Account service is still loading.");
      }
      await signInState.signIn.create({
        strategy: "reset_password_email_code",
        identifier: currentUser.email
      });
      setPendingPasswordReset({ email: currentUser.email });
      return { email: maskEmail(currentUser.email), message: "Password reset email sent. Use the code from your inbox to choose a new password." };
    } catch (err) {
      return requestPasswordReset({ email: currentUser.email });
    }
  }

  async function handlePasswordReset(form) {
    setAuthLoading(true);
    setAuthError("");
    try {
      if (!signInState.isLoaded) {
        throw new Error("Account service is still loading.");
      }
      await signInState.signIn.create({
        strategy: "reset_password_email_code",
        identifier: form.email.trim()
      });
      setPendingPasswordReset({ email: form.email.trim() });
        return { email: maskEmail(form.email.trim()), message: "Check your email for a reset code." };
    } catch (err) {
      try {
        const response = await requestPasswordReset(form);
        setPendingPasswordReset({ email: form.email.trim(), fallback: true });
        return response;
      } catch (fallbackErr) {
        setAuthError(formatClerkError(err));
        throw err;
      }
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleCompletePasswordReset({ code, password }) {
    setAuthLoading(true);
    setAuthError("");
    try {
      if (!signInState.isLoaded) {
        throw new Error("Account service is still loading.");
      }
      const verified = await signInState.signIn.attemptFirstFactor({
        strategy: "reset_password_email_code",
        code
      });
      const reset = verified.status === "needs_new_password"
        ? await signInState.signIn.resetPassword({ password })
        : verified;
      if (reset.status !== "complete") {
        throw new Error("Password reset is not complete yet.");
      }
      if (signInState.setActive && reset.createdSessionId) {
        await signInState.setActive({ session: reset.createdSessionId });
      }
      setPendingPasswordReset(null);
      const email = pendingPasswordReset?.email;
      if (email) {
        const appUser = await lookupProfileByEmail(email).catch(() =>
          syncClerkProfile({ clerkId: reset.createdUserId || email, email, name: "RiskWise User", profile: {} })
        );
        enterApp(appUser);
      }
    } catch (err) {
      setAuthError(formatClerkError(err));
    } finally {
      setAuthLoading(false);
    }
  }

function enterApp(user) {
  setCurrentUser(user);
  setDraft((current) => ({
    ...current,
    user: firstName(user.name),
    accountSize: user.accountSize || 25000,
    riskBudget: Math.round((Number(user.accountSize || 25000) * Number(user.riskBudgetPercent || 2)) / 100)
  }));
  if (!currentUser) {
    setActiveTab("Home");
  }
}

async function restoreRiskWiseUserFromClerk(clerkUser, profile = {}) {
  const email = clerkUser.primaryEmailAddress?.emailAddress || clerkUser.emailAddresses?.[0]?.emailAddress;
  if (!email) {
    throw new Error("Signed in account does not have an email address.");
  }
  return restoreRiskWiseUserFromEmail(
    email,
    profile,
    clerkUser.id,
    clerkUser.fullName || clerkUser.firstName || profile.name || "RiskWise User"
  );
}

async function restoreRiskWiseUserFromEmail(email, profile = {}, clerkId = email, fallbackName = "RiskWise User") {
  try {
    return await lookupProfileByEmail(email);
  } catch (err) {
    try {
      return await syncClerkProfile({
        clerkId,
        email,
        name: profile.name || fallbackName,
        profile
      });
    } catch (syncErr) {
      return createLocalRiskWiseUser({ email, profile, clerkId, fallbackName });
    }
  }
}

function createLocalRiskWiseUser({ email, profile = {}, clerkId, fallbackName = "RiskWise User" }) {
  return {
    id: `local-${clerkId || email}`,
    clerkId: clerkId || email,
    name: profile.name || fallbackName,
    email,
    accountSize: Number(profile.accountSize || 25000),
    riskBudgetPercent: Number(profile.riskBudgetPercent || 2),
    purpose: profile.purpose || [],
    tradeFocus: profile.tradeFocus || [],
    experienceLevel: profile.experienceLevel || "Some experience",
    riskStyle: profile.riskStyle || "Balanced",
    struggles: profile.struggles || [],
    reminders: profile.reminders || [],
    sectors: profile.sectors || [],
    marketCaps: profile.marketCaps || [],
    events: profile.events || [],
    safetyAccepted: Boolean(profile.safetyAccepted),
    aiMemory: profile.aiMemory || {},
    riskRules: profile.riskRules || {},
    coachStyle: profile.coachStyle || {},
    savedContext: profile.savedContext || {},
    appPreferences: profile.appPreferences || {},
    syncMode: "local"
  };
}

  if (!ready) {
    return (
      <AppShell showTabs={false}>
        <View style={styles.loadingScreen}>
          <Text style={sharedText.sectionTitle}>Loading RiskWise...</Text>
        </View>
      </AppShell>
    );
  }

  if (!currentUser) {
    return (
      <AppShell showTabs={false}>
        <AuthScreen
          onCreateAccount={handleCreateAccount}
          onSignIn={handleSignIn}
          onVerifyEmail={handleVerifyEmail}
          onCancelVerification={() => setPendingVerification(null)}
          onVerifySignInEmail={handleVerifySignInEmail}
          onCancelSignInVerification={() => setPendingSignInVerification(null)}
          onRequestPasswordReset={handlePasswordReset}
          onCompletePasswordReset={handleCompletePasswordReset}
          onCancelPasswordReset={() => setPendingPasswordReset(null)}
          pendingVerification={pendingVerification}
          pendingSignInVerification={pendingSignInVerification}
          pendingPasswordReset={pendingPasswordReset}
          loading={authLoading}
          error={authError}
        />
      </AppShell>
    );
  }

  return (
    <AppShell activeTab={activeTab} setActiveTab={setActiveTab}>
      {showOnboarding ? <OnboardingNotice onDismiss={dismissOnboarding} /> : null}
      {activeTab === "Home" && (
        <HomeScreen
          user={currentUser}
          draft={draft}
          setDraft={setDraft}
          report={currentReport}
          savedChecks={savedChecks}
          navigate={setActiveTab}
          openSavedCheck={(item) => {
            setCurrentReport(item.report);
            setActiveTab("Report");
          }}
        />
      )}
      {activeTab === "Check" && (
        <CheckScreen user={currentUser} draft={draft} setDraft={setDraft} onCheck={handleTradeCheck} loading={loading} error={error} />
      )}
      {activeTab === "Coach" && <ChatScreen user={currentUser} currentReport={currentReport} savedChecks={savedChecks} navigate={setActiveTab} />}
      {activeTab === "Report" && (
        <ReportScreen report={currentReport} onAskAi={() => setActiveTab("Coach")} onSave={handleSaveCheck} saveStatus={saveStatus} />
      )}
      {activeTab === "Profile" && (
        <ProfileScreen
          user={currentUser}
          onSignOut={handleSignOut}
          onUpdateUser={handleUpdateProfile}
          onClearContext={handleClearProfileContext}
          onDeleteAccount={handleDeleteAccount}
          onPasswordReset={handleProfilePasswordReset}
        />
      )}
    </AppShell>
  );
}

function PreviewApp() {
  const [currentUser, setCurrentUser] = useState(createPreviewRiskWiseUser());
  const [activeTab, setActiveTab] = useState("Home");
  const [draft, setDraft] = useState(() => ({
    ...tradeDraft,
    user: "Aarav",
    accountSize: 25000,
    riskBudget: 500
  }));
  const [currentReport, setCurrentReport] = useState(null);
  const [savedChecks, setSavedChecks] = useState([]);
  const [saveStatus, setSaveStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    listSavedChecks(currentUser)
      .then((rows) => {
        if (mounted) {
          setSavedChecks(rows);
        }
      })
      .catch(() => {
        if (mounted) {
          setSaveStatus("Saved checks are unavailable right now.");
        }
      });
    return () => {
      mounted = false;
    };
  }, [currentUser?.id]);

  async function handleTradeCheck(options = {}) {
    setLoading(true);
    setError("");
    try {
      const nextReport = await generateTradeCheck(draft, currentUser);
      setCurrentReport(nextReport);
      setSaveStatus("");
      if (!options.stayOnCheck) {
        setActiveTab("Report");
      }
      return nextReport;
    } catch (err) {
      const message = err?.message || "Could not generate this check. Try again.";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveCheck() {
    if (!currentReport) {
      return;
    }
    setSaveStatus("Saving...");
    try {
      const item = await saveCheck(currentUser, currentReport);
      setSavedChecks((items) => [item, ...items.filter((existing) => existing.tradeCheckId !== item.tradeCheckId)].slice(0, 10));
      setSaveStatus("Saved to your RiskWise account.");
    } catch (err) {
      const item = {
        id: `preview-${Date.now()}`,
        tradeCheckId: currentReport.id || `preview-check-${Date.now()}`,
        ticker: currentReport.ticker,
        strategy: currentReport.strategy || currentReport.tradeType,
        savedAt: new Date().toISOString(),
        report: currentReport
      };
      setSavedChecks((items) => [item, ...items].slice(0, 10));
      setSaveStatus("Saved in preview mode.");
    }
  }

  async function handleUpdateProfile(updates) {
    const nextUser = deepMerge(currentUser, updates);
    setCurrentUser(nextUser);
    return nextUser;
  }

  async function handleClearProfileContext() {
    const nextUser = {
      ...currentUser,
      savedContext: {
        savedChecks: false,
        chatHistory: false,
        uploadedScreenshots: false,
        watchlist: false
      }
    };
    setCurrentUser(nextUser);
    setSavedChecks([]);
    setCurrentReport(null);
    return nextUser;
  }

  async function handlePreviewPasswordReset() {
    return {
      email: maskEmail(currentUser.email),
      message: "Preview mode: password reset is wired for real Clerk accounts."
    };
  }

  async function handlePreviewDeleteAccount() {
    setCurrentUser(createPreviewRiskWiseUser());
    setCurrentReport(null);
    setSavedChecks([]);
    setSaveStatus("Preview account reset.");
    setActiveTab("Home");
  }

  return (
    <AppShell activeTab={activeTab} setActiveTab={setActiveTab}>
      {activeTab === "Home" && (
        <HomeScreen
          user={currentUser}
          draft={draft}
          setDraft={setDraft}
          report={currentReport}
          savedChecks={savedChecks}
          navigate={setActiveTab}
          openSavedCheck={(item) => {
            setCurrentReport(item.report || item);
            setActiveTab("Report");
          }}
        />
      )}
      {activeTab === "Check" && (
        <CheckScreen user={currentUser} draft={draft} setDraft={setDraft} onCheck={handleTradeCheck} loading={loading} error={error} />
      )}
      {activeTab === "Coach" && <ChatScreen user={currentUser} currentReport={currentReport} savedChecks={savedChecks} navigate={setActiveTab} />}
      {activeTab === "Report" && (
        <ReportScreen report={currentReport} onAskAi={() => setActiveTab("Coach")} onSave={handleSaveCheck} saveStatus={saveStatus} />
      )}
      {activeTab === "Profile" && (
        <ProfileScreen
          user={currentUser}
          onSignOut={handlePreviewDeleteAccount}
          onUpdateUser={handleUpdateProfile}
          onClearContext={handleClearProfileContext}
          onDeleteAccount={handlePreviewDeleteAccount}
          onPasswordReset={handlePreviewPasswordReset}
        />
      )}
    </AppShell>
  );
}

function createPreviewRiskWiseUser() {
  return {
    id: "preview-user",
    clerkId: "preview-local",
    name: "Aarav Preview",
    email: "preview@riskwise.local",
    accountSize: 25000,
    riskBudgetPercent: 2,
    experienceLevel: "Some experience",
    riskStyle: "Balanced",
    sectors: ["Technology", "Healthcare", "Finance"],
    marketCaps: ["Large cap", "Mega cap"],
    aiMemory: {
      experienceLevel: "Some experience",
      riskStyle: "Balanced",
      preferredExplanation: "Step-by-step",
      commonMistakes: ["Oversizing", "Chasing", "Ignoring IV"]
    },
    riskRules: {
      maxRiskPerTrade: 2,
      maxTradesPerWeek: 5,
      avoidEarningsTrades: true,
      warnExpirationUnderDays: 7,
      premiumRiskWarning: 5
    },
    coachStyle: {
      defaultMode: "Review",
      explanationStyle: "Step-by-step",
      coachingApproach: "Debate both sides",
      questionStyle: "Ask me questions first",
      riskStrictness: "Strict about risk"
    },
    savedContext: {
      savedChecks: true,
      chatHistory: true,
      uploadedScreenshots: true,
      watchlist: true
    },
    appPreferences: {
      defaultAiMode: "Review",
      openAppTo: "Coach",
      compactReportCards: true,
      weeklyDigest: true,
      quietHours: "After 9 PM"
    },
    syncMode: "preview"
  };
}

function firstName(name) {
  return (name || "Alex").split(" ")[0];
}

function formatClerkError(err) {
  const clerkMessage = err?.errors?.[0]?.longMessage || err?.errors?.[0]?.message;
  const message = `${clerkMessage || err?.message || ""}`.toLowerCase();
  if (message.includes("failed to fetch") || message.includes("network request failed")) {
    return "RiskWise account sync is offline. Start the backend, or use preview mode while designing locally.";
  }
  return clerkMessage || err?.message || "Account service is unavailable.";
}

function isAlreadySignedInError(err) {
  const code = err?.errors?.[0]?.code;
  const message = `${err?.errors?.[0]?.message || ""} ${err?.message || ""}`.toLowerCase();
  return code === "identifier_already_signed_in" || message.includes("already signed in");
}

function findEmailCodeFactor(factors = []) {
  return factors.find((factor) => factor?.strategy === "email_code" && factor.emailAddressId);
}

function describeSignInStatus(status) {
  if (status === "needs_new_password") {
    return "This account needs a password reset before signing in.";
  }
  if (status === "needs_second_factor" || status === "needs_client_trust") {
    return "This account needs another verification method. Try the email code if offered, or use password reset.";
  }
  if (status === "needs_first_factor") {
    return "This account needs a supported first sign-in method. If you used Google before, sign in the same way or reset your password.";
  }
  return "This sign-in could not be completed yet. Check your email or try password reset.";
}

function maskEmail(email) {
  const [name, domain] = email.split("@");
  if (!domain) {
    return email;
  }
  return `${name.slice(0, 2)}${"*".repeat(Math.max(2, name.length - 2))}@${domain}`;
}

function isLocalPreviewSession() {
  if (typeof window === "undefined") {
    return false;
  }
  const host = window.location.hostname;
  const local = host === "127.0.0.1" || host === "localhost";
  return local && new URLSearchParams(window.location.search).get("riskwise_preview") === "1";
}

function isPreviewUser(user) {
  return user?.id === "preview-user" || user?.clerkId === "preview-local";
}

function hasClerkRuntime() {
  return Boolean(process.env.EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY);
}

function OnboardingNotice({ onDismiss }) {
  return (
    <View style={styles.onboardingOverlay}>
      <Card style={styles.onboardingCard}>
        <Text style={sharedText.sectionTitle}>Educational risk checks only</Text>
        <Text style={sharedText.bodyText}>
          This app helps structure options risk and explain trade checks. It does not execute trades,
          give financial advice, or tell you what to buy or sell.
        </Text>
        <PrimaryButton label="I Understand" onPress={onDismiss} />
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  onboardingOverlay: {
    position: "absolute",
    zIndex: 10,
    left: 0,
    right: 0,
    top: 0,
    bottom: 74,
    backgroundColor: "rgba(247,249,247,0.92)",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 18
  },
  onboardingCard: {
    borderColor: "#BCEAC9",
    backgroundColor: "#FBFFFC"
  },
  loadingScreen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 18
  }
});
