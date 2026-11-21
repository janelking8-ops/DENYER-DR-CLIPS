
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/health") {
      return Response.json({
        ok: true,
        service: "denyer-dr-gateway"
      });
    }

    if (url.pathname !== "/v1/transcribe" || request.method !== "POST") {
      return Response.json({ error: "Not found" }, { status: 404 });
    }

    if (!env.APP_ACCESS_TOKEN || request.headers.get("X-App-Token") !== env.APP_ACCESS_TOKEN) {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }

    if (!env.BACKEND_URL || !env.BACKEND_APP_TOKEN) {
      return Response.json({ error: "Gateway is not configured" }, { status: 503 });
    }

    const headers = new Headers(request.headers);
    headers.delete("X-App-Token");
    headers.set("X-App-Token", env.BACKEND_APP_TOKEN);
    headers.delete("host");

    const target = env.BACKEND_URL.replace(/\/$/, "") + "/v1/transcribe";

    try {
      const upstream = await fetch(target, {
        method: "POST",
        headers,
        body: request.body
      });

      const responseHeaders = new Headers(upstream.headers);
      responseHeaders.set("Access-Control-Allow-Origin", "*");
      responseHeaders.set("Access-Control-Allow-Headers", "Content-Type, X-App-Token");
      responseHeaders.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");

      return new Response(upstream.body, {
        status: upstream.status,
        headers: responseHeaders
      });
    } catch {
      return Response.json({ error: "Backend unavailable" }, { status: 502 });
    }
  }
};
