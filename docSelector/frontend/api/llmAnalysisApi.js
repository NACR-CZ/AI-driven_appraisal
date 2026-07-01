const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

function buildQuery(params) {
  const searchParams = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "" && value !== "all") searchParams.append(key, value);
  });
  const qs = searchParams.toString();
  return qs ? `?${qs}` : "";
}

export async function fetchLlmAnalyses(filters = {}) {
  const response = await fetch(`${API_BASE}/api/llm-analysis${buildQuery(filters)}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function fetchBatchFallback(batchId) {
  const response = await fetch(`${API_BASE}/batches/${batchId}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function saveLlmAnalysisBatch(payload) {
  const response = await fetch(`${API_BASE}/api/llm-analysis`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}
