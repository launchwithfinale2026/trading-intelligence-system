"use client";

import { useState, type FormEvent } from "react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, type AlertPreference, type RiskPreference, type TradingStyle } from "@/lib/api";

function ProfileContent() {
  const { user, token, refreshUser } = useAuth();
  const profile = user?.profile;

  const [accountSize, setAccountSize] = useState(profile?.account_size ?? "");
  const [riskPreference, setRiskPreference] = useState<RiskPreference>(profile?.risk_preference ?? "moderate");
  const [tradingStyle, setTradingStyle] = useState<TradingStyle>(profile?.trading_style ?? "momentum");
  const [alertPreference, setAlertPreference] = useState<AlertPreference>(profile?.alert_preference ?? "all_signals");
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  if (!user || !profile) return null;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setStatus("saving");
    setError(null);
    try {
      await api.updateProfile(token, {
        account_size: accountSize,
        risk_preference: riskPreference,
        trading_style: tradingStyle,
        alert_preference: alertPreference,
      });
      await refreshUser();
      setStatus("saved");
    } catch (err) {
      setStatus("error");
      setError(err instanceof ApiError ? err.message : "Failed to update profile.");
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col gap-6 px-4 py-8">
      <h1 className="text-xl font-semibold">Profile</h1>
      <div className="text-sm text-neutral-500">
        <p>Username: {user.username}</p>
        <p>Email: {user.email}</p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          Account size (USD)
          <input
            type="number"
            step="0.01"
            min="0.01"
            className="rounded border border-black/15 bg-transparent px-3 py-2 dark:border-white/15"
            value={accountSize}
            onChange={(e) => setAccountSize(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Risk preference
          <select
            className="rounded border border-black/15 bg-transparent px-3 py-2 dark:border-white/15"
            value={riskPreference}
            onChange={(e) => setRiskPreference(e.target.value as RiskPreference)}
          >
            <option value="conservative">Conservative (0.5% risk/trade)</option>
            <option value="moderate">Moderate (1% risk/trade)</option>
            <option value="aggressive">Aggressive (2% risk/trade)</option>
            <option value="experimental">Experimental (scaled by account size)</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Trading style
          <select
            className="rounded border border-black/15 bg-transparent px-3 py-2 dark:border-white/15"
            value={tradingStyle}
            onChange={(e) => setTradingStyle(e.target.value as TradingStyle)}
          >
            <option value="momentum">Momentum</option>
            <option value="swing">Swing</option>
            <option value="breakout">Breakout</option>
            <option value="position">Position</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Alert preference
          <select
            className="rounded border border-black/15 bg-transparent px-3 py-2 dark:border-white/15"
            value={alertPreference}
            onChange={(e) => setAlertPreference(e.target.value as AlertPreference)}
          >
            <option value="all_signals">All signals</option>
            <option value="high_confidence_only">High confidence only</option>
            <option value="none">None</option>
          </select>
        </label>

        {error && <p className="text-sm text-red-500">{error}</p>}
        {status === "saved" && <p className="text-sm text-green-500">Saved.</p>}

        <button
          type="submit"
          disabled={status === "saving"}
          className="rounded bg-foreground px-3 py-2 text-sm font-medium text-background disabled:opacity-50"
        >
          {status === "saving" ? "Saving…" : "Save changes"}
        </button>
      </form>
    </div>
  );
}

export default function ProfilePage() {
  return (
    <ProtectedRoute>
      <ProfileContent />
    </ProtectedRoute>
  );
}
