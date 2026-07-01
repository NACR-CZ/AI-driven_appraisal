import { useEffect, useMemo, useState } from "react";
import { fetchLlmAnalyses, fetchBatchFallback } from "../api/llmAnalysisApi";
import "./LlmAnalysisTab.css";

const DECISIONS = ["A", "S", "V", "k_revizi"];

function normalizeDecision(value) {
  const v = String(value || "").trim().toUpperCase();
  if (["A", "S", "V"].includes(v)) return v;
  return "k_revizi";
}
function formatDecisionLabel(value) { return value === "k_revizi" ? "K revizi" : value; }
function fmtDuration(ms) {
  if (ms === undefined || ms === null || ms === "") return "—";
  const n = Number(ms);
  if (!Number.isFinite(n)) return "—";
  if (n < 1000) return `${n} ms`;
  const sec = n / 1000;
  if (sec < 60) return `${sec.toFixed(1)} s`;
  return `${Math.floor(sec / 60)} min ${Math.round(sec % 60)} s`;
}

function buildFallbackFromBatch(batch, filters) {
  const model = batch?.last_llm_analysis?.model || "neznamy_model";
  const runId = batch?.last_llm_analysis?.model_run_id || "bez_run_id";
  let items = (batch?.records || []).filter((r) => r.llm_analysis).map((r) => {
    const llm = r.llm_analysis || {};
    return {
      batch_id: batch.id,
      document_id: r.id,
      filename: r.path || r.relative_path || r.filename,
      title: r.title,
      assessed_by_model: r.llm_model || model,
      model_provider: "openai-compatible",
      model_run_id: r.llm_model_run_id || runId,
      assessment_timestamp: batch?.last_llm_analysis?.finished_at || batch?.last_llm_analysis?.created_at || "",
      recommended_decision: normalizeDecision(r.llm_decision || llm.recommendation),
      weighted_total_score: r.scoring?.final_score || 0,
      confidence: llm.confidence || 0,
      explanation: llm.reasoning || llm.reason || llm.summary || "",
      human_review_required: !!llm.error,
      raw_llm_output: llm,
    };
  });
  if (filters.decision && filters.decision !== "all") items = items.filter((x) => x.recommended_decision === normalizeDecision(filters.decision));
  if (filters.model && filters.model !== "all") items = items.filter((x) => x.assessed_by_model === filters.model);
  if (filters.model_run_id) items = items.filter((x) => x.model_run_id === filters.model_run_id);
  const decision_counts = { A: 0, S: 0, V: 0, k_revizi: 0 };
  const counts_by_model = {};
  items.forEach((x) => {
    const d = normalizeDecision(x.recommended_decision);
    decision_counts[d] = (decision_counts[d] || 0) + 1;
    counts_by_model[x.assessed_by_model] ||= { A: 0, S: 0, V: 0, k_revizi: 0 };
    counts_by_model[x.assessed_by_model][d] += 1;
  });
  return { filters, summary: { total: items.length, decision_counts, counts_by_model }, items, last_run: batch?.last_llm_analysis || null, fallback: true };
}

function SummaryCards({ summary }) {
  const counts = summary?.decision_counts || {};
  return <div className="llm-summary-cards"><div className="llm-summary-card"><div className="llm-summary-label">Zobrazeno</div><div className="llm-summary-value">{summary?.total || 0}</div></div>{DECISIONS.map((decision) => <div className="llm-summary-card" key={decision}><div className="llm-summary-label">{formatDecisionLabel(decision)}</div><div className="llm-summary-value">{counts[decision] || 0}</div></div>)}</div>;
}
function CountsByModelTable({ countsByModel }) {
  const rows = Object.entries(countsByModel || {});
  if (!rows.length) return <p className="llm-muted">Pro aktuální filtr nejsou žádné modelové souhrny.</p>;
  return <table className="llm-table"><thead><tr><th>Model</th><th>A</th><th>S</th><th>V</th><th>K revizi</th></tr></thead><tbody>{rows.map(([model, counts]) => <tr key={model}><td>{model}</td><td>{counts.A || 0}</td><td>{counts.S || 0}</td><td>{counts.V || 0}</td><td>{counts.k_revizi || 0}</td></tr>)}</tbody></table>;
}
function ResultTable({ items }) {
  if (!items?.length) return <p className="llm-muted">Pro aktuální filtr nejsou žádné výsledky.</p>;
  return <table className="llm-table"><thead><tr><th>ID</th><th>Název</th><th>Rozhodnutí</th><th>Skóre</th><th>Confidence</th><th>Model</th><th>Provider</th><th>Run ID</th><th>Čas</th><th>Revize</th></tr></thead><tbody>{items.map((item) => <tr key={`${item.model_run_id}-${item.document_id}`}><td>{item.document_id}</td><td>{item.filename || item.title || "—"}</td><td><span className={`decision-pill decision-${item.recommended_decision}`}>{formatDecisionLabel(item.recommended_decision)}</span></td><td>{Number(item.weighted_total_score || 0).toFixed(2)}</td><td>{Number(item.confidence || 0).toFixed(2)}</td><td>{item.assessed_by_model || "—"}</td><td>{item.model_provider || "—"}</td><td>{item.model_run_id || "—"}</td><td>{item.assessment_timestamp || "—"}</td><td>{item.human_review_required ? "ano" : "ne"}</td></tr>)}</tbody></table>;
}

export default function LlmAnalysisTab({ batchId = "" }) {
  const [decision, setDecision] = useState("all");
  const [model, setModel] = useState("all");
  const [modelRunId, setModelRunId] = useState("");
  const [data, setData] = useState({ filters: {}, summary: { total: 0, decision_counts: { A: 0, S: 0, V: 0, k_revizi: 0 }, counts_by_model: {} }, items: [], last_run: null });
  const [loading, setLoading] = useState(false);
  const [warning, setWarning] = useState("");

  async function loadData() {
    setLoading(true); setWarning("");
    const filters = { batch_id: batchId, decision, model, model_run_id: modelRunId };
    try {
      const response = await fetchLlmAnalyses(filters);
      setData(response);
    } catch (err) {
      if (batchId) {
        try {
          const batch = await fetchBatchFallback(batchId);
          setData(buildFallbackFromBatch(batch, filters));
          setWarning(`Endpoint /api/llm-analysis se nepodařilo načíst, zobrazuji náhradní přehled přímo z dávky. Detail: ${err.message || err}`);
        } catch (fallbackErr) {
          setWarning(`Nepodařilo se načíst ani přehled, ani dávku: ${fallbackErr.message || fallbackErr}`);
        }
      } else {
        setWarning(`Nepodařilo se načíst LLM přehled. Není vybraná dávka. Detail: ${err.message || err}`);
      }
    } finally { setLoading(false); }
  }
  useEffect(() => { loadData(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [batchId, decision, model, modelRunId]);

  const availableModels = useMemo(() => {
    const models = new Set();
    Object.keys(data?.summary?.counts_by_model || {}).forEach((m) => models.add(m));
    (data?.items || []).forEach((item) => item.assessed_by_model && models.add(item.assessed_by_model));
    return Array.from(models).sort();
  }, [data]);
  const lastRun = data?.last_run;

  return <section className="llm-analysis-tab"><div className="llm-header"><div><h2>LLM analýzy</h2><p>Přehled posouzení dokumentů podle rozhodnutí a podle modelu, který posouzení provedl.</p></div><button className="llm-button" onClick={loadData} disabled={loading}>{loading ? "Načítám…" : "Obnovit"}</button></div>
    <div className="llm-filters"><label>Rozhodnutí<select value={decision} onChange={(e) => setDecision(e.target.value)}><option value="all">Všechna</option><option value="A">A</option><option value="S">S</option><option value="V">V</option><option value="k_revizi">K revizi</option></select></label><label>Model<select value={model} onChange={(e) => setModel(e.target.value)}><option value="all">Všechny modely</option>{availableModels.map((modelName) => <option key={modelName} value={modelName}>{modelName}</option>)}</select></label><label>Run ID<input value={modelRunId} onChange={(e) => setModelRunId(e.target.value)} placeholder="např. RUN-20260612-001" /></label></div>
    {warning && <div className="llm-error">{warning}</div>}
    {lastRun && <div className="llm-run-summary"><h3>Poslední běh</h3><span><b>Začátek:</b> {lastRun.started_at || lastRun.created_at || "—"}</span><span><b>Konec:</b> {lastRun.finished_at || "—"}</span><span><b>Trvání:</b> {fmtDuration(lastRun.elapsed_ms)}</span><span><b>Zpracováno:</b> {lastRun.processed ?? 0}</span><span><b>Přeskočeno:</b> {lastRun.skipped ?? 0}</span><span><b>Chyby:</b> {lastRun.errors ?? 0}</span><span><b>Model:</b> {lastRun.model || "—"}</span><span><b>Run ID:</b> {lastRun.model_run_id || "—"}</span></div>}
    <SummaryCards summary={data.summary} />
    <h3>Počty A/S/V podle modelu</h3><CountsByModelTable countsByModel={data.summary?.counts_by_model} />
    <h3>Výsledky posouzení</h3><ResultTable items={data.items} />
  </section>;
}
