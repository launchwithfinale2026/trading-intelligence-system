const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export type RiskPreference = "conservative" | "moderate" | "aggressive";
export type TradingStyle = "momentum" | "swing" | "breakout" | "position";
export type AlertPreference = "all_signals" | "high_confidence_only" | "none";
export type SignalDirection = "long" | "short";
export type DecisionType = "open" | "ignore";
export type PositionStatus = "open" | "closed_stop" | "closed_target" | "closed_manual";

export interface Profile {
  id: number;
  user_id: number;
  account_size: string;
  risk_preference: RiskPreference;
  trading_style: TradingStyle;
  alert_preference: AlertPreference;
}

export interface User {
  id: number;
  username: string;
  email: string;
  profile: Profile | null;
}

export interface Signal {
  id: number;
  symbol: string;
  strategy_name: string;
  direction: SignalDirection;
  entry: string;
  stop_loss: string;
  target: string;
  confidence: number;
  reasoning: string[];
  created_at: string;
}

export interface Position {
  id: number;
  signal_id: number;
  entry: string;
  stop_loss: string;
  target: string;
  shares: number;
  status: PositionStatus;
  close_price: string | null;
  closed_at: string | null;
  created_at: string;
}

export interface Decision {
  id: number;
  signal_id: number;
  decision: DecisionType;
  created_at: string;
}

export interface StrategyPerformance {
  strategy_name: string;
  signals_generated: number;
  accepted: number;
  ignored: number;
  trades_closed: number;
  wins: number;
  win_rate: string | null;
  average_r_multiple: string | null;
}

export interface MarketStatus {
  is_open: boolean;
  session: string;
  as_of: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  profile: {
    account_size: string;
    risk_preference: RiskPreference;
    trading_style: TradingStyle;
    alert_preference?: AlertPreference;
  };
}

async function request<T>(
  path: string,
  options: { method?: string; token?: string; json?: unknown; form?: Record<string, string> } = {}
): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;

  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  } else if (options.form !== undefined) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    body = new URLSearchParams(options.form).toString();
  }

  if (options.token) {
    headers["Authorization"] = `Bearer ${options.token}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const errorBody = await response.json();
      detail = errorBody.detail ?? detail;
    } catch {
      // response wasn't JSON — fall back to statusText
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  register: (payload: RegisterPayload) => request<User>("/auth/register", { method: "POST", json: payload }),

  login: (username: string, password: string) =>
    request<Token>("/auth/login", { method: "POST", form: { username, password } }),

  logout: (token: string) => request<{ detail: string }>("/auth/logout", { method: "POST", token }),

  getMe: (token: string) => request<User>("/users/me", { token }),

  updateProfile: (
    token: string,
    payload: Partial<{
      account_size: string;
      risk_preference: RiskPreference;
      trading_style: TradingStyle;
      alert_preference: AlertPreference;
    }>
  ) => request<Profile>("/users/me/profile", { method: "PATCH", token, json: payload }),

  getSignals: (token: string, limit = 50) => request<Signal[]>(`/signals?limit=${limit}`, { token }),

  getPerformance: (token: string) => request<StrategyPerformance[]>("/feedback/performance", { token }),

  getPositions: (token: string) => request<Position[]>("/portfolio/positions", { token }),

  getDecisions: (token: string) => request<Decision[]>("/portfolio/decisions", { token }),

  getMarketStatus: (token: string) => request<MarketStatus>("/market/status", { token }),
};
