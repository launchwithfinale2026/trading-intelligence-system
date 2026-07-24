import { describe, expect, it, vi, beforeEach } from "vitest";
import { api, ApiError } from "./api";

describe("api client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("sends login credentials as a form-encoded body", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ access_token: "abc", token_type: "bearer" }), { status: 200 })
    );

    const result = await api.login("jake", "hunter2");

    expect(result.access_token).toBe("abc");
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/auth/login");
    expect(options.headers["Content-Type"]).toBe("application/x-www-form-urlencoded");
    expect(options.body).toBe("username=jake&password=hunter2");
  });

  it("sends the bearer token on authenticated requests", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ id: 1, username: "jake", email: "jake@example.com", profile: null }), {
        status: 200,
      })
    );

    await api.getMe("my-token");

    const [, options] = mockFetch.mock.calls[0];
    expect(options.headers["Authorization"]).toBe("Bearer my-token");
  });

  it("throws ApiError with the server's detail message on failure", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "invalid username or password" }), { status: 401 })
    );

    await expect(api.login("jake", "wrong")).rejects.toMatchObject(
      new ApiError(401, "invalid username or password")
    );
  });

  it("falls back to statusText when the error body isn't JSON", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
    mockFetch.mockResolvedValueOnce(new Response("not json", { status: 500, statusText: "Internal Server Error" }));

    await expect(api.getMe("token")).rejects.toMatchObject({ status: 500 });
  });

  it("appends the limit query parameter for signal history", async () => {
    const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;
    mockFetch.mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));

    await api.getSignals("token", 5);

    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("/signals?limit=5");
  });
});
