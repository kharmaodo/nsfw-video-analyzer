const BACKEND_URL = process.env.BACKEND_API_URL ?? "http://localhost:8000";

async function proxy(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const incoming = new URL(request.url);
  const target = new URL(`/${path.join("/")}${incoming.search}`, BACKEND_URL);
  const headers = new Headers(request.headers);
  headers.delete("host");
  const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();
  try {
    const response = await fetch(target, { method: request.method, headers, body, redirect: "manual" });
    return new Response(response.body, { status: response.status, headers: response.headers });
  } catch {
    return Response.json({ detail: "Le backend FastAPI est indisponible." }, { status: 503 });
  }
}
export const GET = proxy; export const POST = proxy; export const PATCH = proxy; export const DELETE = proxy;
