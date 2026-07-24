"use client";

import { useEffect, useState } from "react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/auth-context";
import { api, type Decision, type Position, type Signal } from "@/lib/api";

interface HistoryRow {
  signal?: Signal;
  decision: Decision;
  position?: Position;
}

function statusLabel(position?: Position): string {
  if (!position) return "—";
  switch (position.status) {
    case "open":
      return "Open";
    case "closed_target":
      return "Closed (target hit)";
    case "closed_stop":
      return "Closed (stop hit)";
    case "closed_manual":
      return "Closed (manual)";
  }
}

function HistoryContent() {
  const { token } = useAuth();
  const [rows, setRows] = useState<HistoryRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    Promise.all([api.getDecisions(token), api.getPositions(token), api.getSignals(token, 200)])
      .then(([decisions, positions, signals]) => {
        const signalById = new Map(signals.map((s) => [s.id, s]));
        const positionBySignalId = new Map(positions.map((p) => [p.signal_id, p]));

        setRows(
          decisions.map((decision) => ({
            decision,
            signal: signalById.get(decision.signal_id),
            position: positionBySignalId.get(decision.signal_id),
          }))
        );
      })
      .catch(() => setError("Failed to load history."))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8">
      <h1 className="text-xl font-semibold">History</h1>
      {error && <p className="text-sm text-red-500">{error}</p>}

      {loading ? (
        <p className="text-sm text-neutral-500">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-neutral-500">No decisions yet. Signals you OPEN or IGNORE will show up here.</p>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-left text-neutral-500">
            <tr>
              <th className="py-1 pr-4">Date</th>
              <th className="py-1 pr-4">Symbol</th>
              <th className="py-1 pr-4">Strategy</th>
              <th className="py-1 pr-4">Decision</th>
              <th className="py-1 pr-4">Result</th>
              <th className="py-1 pr-4">Close price</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.decision.id} className="border-t border-black/5 dark:border-white/5">
                <td className="py-1 pr-4">{new Date(row.decision.created_at).toLocaleDateString()}</td>
                <td className="py-1 pr-4">{row.signal?.symbol ?? `#${row.decision.signal_id}`}</td>
                <td className="py-1 pr-4">{row.signal?.strategy_name ?? "—"}</td>
                <td className="py-1 pr-4 uppercase">{row.decision.decision}</td>
                <td className="py-1 pr-4">{statusLabel(row.position)}</td>
                <td className="py-1 pr-4">{row.position?.close_price ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function HistoryPage() {
  return (
    <ProtectedRoute>
      <HistoryContent />
    </ProtectedRoute>
  );
}
