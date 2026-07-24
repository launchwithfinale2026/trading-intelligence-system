"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ApiError, type AlertPreference, type RiskPreference, type TradingStyle } from "@/lib/api";

export default function RegisterPage() {
  const { register, user, loading } = useAuth();
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [accountSize, setAccountSize] = useState("1000.00");
  const [riskPreference, setRiskPreference] = useState<RiskPreference>("moderate");
  const [tradingStyle, setTradingStyle] = useState<TradingStyle>("momentum");
  const [alertPreference, setAlertPreference] = useState<AlertPreference>("all_signals");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      router.replace("/");
    }
  }, [loading, user, router]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register({
        username,
        email,
        password,
        profile: {
          account_size: accountSize,
          risk_preference: riskPreference,
          trading_style: tradingStyle,
          alert_preference: alertPreference,
        },
      });
      // Redirect happens via the effect above once `user` updates — a
      // single source of truth instead of a second call site here.
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading || user) {
    return <div className="p-8 text-center text-sm text-neutral-500">Loading…</div>;
  }

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-6 px-4 py-16">
      <h1 className="text-xl font-semibold">Create an account</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          Username
          <input
            className="rounded border border-black/15 bg-transparent px-3 py-2 dark:border-white/15"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Email
          <input
            type="email"
            className="rounded border border-black/15 bg-transparent px-3 py-2 dark:border-white/15"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Password
          <input
            type="password"
            className="rounded border border-black/15 bg-transparent px-3 py-2 dark:border-white/15"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
        </label>
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
        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-foreground px-3 py-2 text-sm font-medium text-background disabled:opacity-50"
        >
          {submitting ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p className="text-sm text-neutral-500">
        Already have an account? <Link href="/login" className="underline">Log in</Link>
      </p>
    </div>
  );
}
