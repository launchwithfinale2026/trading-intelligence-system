"use client";

import { useEffect, useState } from "react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/auth-context";
import { api, type MarketStatus, type Position, type Signal, type StrategyPerformance } from "@/lib/api";

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-black/10 p-4 dark:border-white/10">
      <h2 className="mb-3 text-sm font-medium text-neutral-500">{title}</h2>
      {children}
    </section>
  );
}

function DashboardContent() {
  const { token } = useAuth();
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [performance, setPerformance] = useState<StrategyPerformance[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      api.getMarketStatus(token),
      api.getPositions(token),
      api.getSignals(token, 10),
      api.getPerformance(token),
    ])
      .then(([status, allPositions, recentSignals, perf]) => {
        setMarketStatus(status);
        setPositions(allPositions.filter((p) => p.status === "open"));
        setSignals(recentSignals);
        setPerformance(perf);
      })
      .catch(() => setError("Failed to load dashboard data."));
  }, [token]);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8">
      <h1 className="text-xl font-semibold">Dashboard</h1>
      {error && <p className="text-sm text-red-500">{error}</p>}

      <Card title="Market status">
        {marketStatus ? (
          <p className="text-sm">
            <span className={marketStatus.is_open ? "text-green-500" : "text-neutral-500"}>
              {marketStatus.is_open ? "● OPEN" : "● CLOSED"}
            </span>{" "}
            <span className="text-neutral-500">
              as of {new Date(marketStatus.as_of).toLocaleString()}
            </span>
          </p>
        ) : (
          <p className="text-sm text-neutral-500">Loading…</p>
        )}
      </Card>

      <Card title={`Active positions (${positions.length})`}>
        {positions.length === 0 ? (
          <p className="text-sm text-neutral-500">No active positions.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-neutral-500">
              <tr>
                <th className="py-1 pr-4">Signal</th>
                <th className="py-1 pr-4">Shares</th>
                <th className="py-1 pr-4">Entry</th>
                <th className="py-1 pr-4">Stop</th>
                <th className="py-1 pr-4">Target</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => (
                <tr key={p.id} className="border-t border-black/5 dark:border-white/5">
                  <td className="py-1 pr-4">#{p.signal_id}</td>
                  <td className="py-1 pr-4">{p.shares}</td>
                  <td className="py-1 pr-4">{p.entry}</td>
                  <td className="py-1 pr-4">{p.stop_loss}</td>
                  <td className="py-1 pr-4">{p.target}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title="Recent signals">
        {signals.length === 0 ? (
          <p className="text-sm text-neutral-500">No signals yet.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {signals.map((s) => (
              <li key={s.id} className="text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium">
                    {s.symbol} · {s.strategy_name} · {s.direction.toUpperCase()}
                  </span>
                  <span className="text-neutral-500">{s.confidence}% confidence</span>
                </div>
                <div className="text-neutral-500">
                  Entry {s.entry} · Stop {s.stop_loss} · Target {s.target}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Performance by strategy">
        {performance.length === 0 ? (
          <p className="text-sm text-neutral-500">No closed trades yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-neutral-500">
              <tr>
                <th className="py-1 pr-4">Strategy</th>
                <th className="py-1 pr-4">Signals</th>
                <th className="py-1 pr-4">Accepted</th>
                <th className="py-1 pr-4">Ignored</th>
                <th className="py-1 pr-4">Closed trades</th>
                <th className="py-1 pr-4">Win rate</th>
                <th className="py-1 pr-4">Avg R</th>
              </tr>
            </thead>
            <tbody>
              {performance.map((p) => (
                <tr key={p.strategy_name} className="border-t border-black/5 dark:border-white/5">
                  <td className="py-1 pr-4">{p.strategy_name}</td>
                  <td className="py-1 pr-4">{p.signals_generated}</td>
                  <td className="py-1 pr-4">{p.accepted}</td>
                  <td className="py-1 pr-4">{p.ignored}</td>
                  <td className="py-1 pr-4">{p.trades_closed}</td>
                  <td className="py-1 pr-4">{p.win_rate ?? "—"}%</td>
                  <td className="py-1 pr-4">{p.average_r_multiple ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
