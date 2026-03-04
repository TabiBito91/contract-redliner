import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import { getSession, getResult, exportRedline } from "@/services/api";
import type {
  ComparisonSession,
  ComparisonResult,
  VersionComparison,
  AnnotatedChange,
} from "@/types/api";
import DiffViewer from "@/components/DiffViewer";
import ChangeDetailPanel from "@/components/ChangeDetailPanel";
import { Check, ChevronLeft, ChevronRight, Download } from "lucide-react";

export default function ComparisonPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [session, setSession] = useState<ComparisonSession | null>(null);
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // UI state
  const [activeVersionIdx, setActiveVersionIdx] = useState(0);
  const [selectedChangeIdx, setSelectedChangeIdx] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<"side-by-side" | "inline">("side-by-side");
  const [showSubstantiveOnly, setShowSubstantiveOnly] = useState(true);
  const [exporting, setExporting] = useState(false);

  // Poll for completion
  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const s = await getSession(sessionId!);
        if (cancelled) return;
        setSession(s);

        if (s.status === "complete") {
          const r = await getResult(sessionId!);
          if (!cancelled) setResult(r);
        } else if (s.status === "error") {
          setError("Comparison failed. Please try again.");
        } else {
          timer = setTimeout(poll, 1000);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load");
      }
    }
    poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [sessionId]);

  const activeComparison: VersionComparison | null =
    result?.version_comparisons[activeVersionIdx] ?? null;

  const filteredChanges: AnnotatedChange[] = activeComparison
    ? activeComparison.changes.filter(
        (ac) => !showSubstantiveOnly || ac.change.is_substantive
      )
    : [];

  const selectedChange =
    selectedChangeIdx !== null ? filteredChanges[selectedChangeIdx] ?? null : null;

  const handleExport = useCallback(async () => {
    if (!sessionId || !activeComparison) return;
    setExporting(true);
    try {
      await exportRedline(sessionId, {
        version_comparison_id: activeComparison.modified_document_id,
        show_formatting_changes: !showSubstantiveOnly,
      });
    } catch (e) {
      console.error("Export failed:", e);
    } finally {
      setExporting(false);
    }
  }, [sessionId, activeComparison, showSubstantiveOnly]);

  const navigateChange = useCallback(
    (direction: 1 | -1) => {
      setSelectedChangeIdx((prev) => {
        if (prev === null) return 0;
        const next = prev + direction;
        if (next < 0 || next >= filteredChanges.length) return prev;
        return next;
      });
    },
    [filteredChanges.length],
  );

  // Keyboard navigation
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "ArrowDown" || e.key === "j") {
        e.preventDefault();
        navigateChange(1);
      } else if (e.key === "ArrowUp" || e.key === "k") {
        e.preventDefault();
        navigateChange(-1);
      } else if (e.key === "Escape") {
        setSelectedChangeIdx(null);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [navigateChange]);

  // Loading state
  if (!session || (session.status !== "complete" && session.status !== "error")) {
    const progress = session?.progress ?? 0;

    const stages = [
      { label: "Parsing & Diffing", min: 0,  max: 80  },
      { label: "AI Analysis",       min: 80, max: 95  },
      { label: "Finalizing",        min: 95, max: 100 },
    ].map((s) => ({
      ...s,
      isDone:    progress >= s.max,
      isActive:  progress >= s.min && progress < s.max,
      isPending: progress < s.min,
    }));

    const activeStage = stages.find((s) => s.isActive);

    return (
      <div className="flex flex-col items-center justify-center h-[70vh] gap-10">
        <div className="flex flex-col items-center gap-3">
          {/* Circles + connectors */}
          <div className="flex items-center">
            {stages.map((s, i) => (
              <div key={i} className="flex items-center">
                <div className={`
                  w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold
                  transition-all duration-500
                  ${s.isDone    ? "bg-addition text-white" : ""}
                  ${s.isActive  ? "border-2 border-addition text-addition ring-4 ring-addition/20" : ""}
                  ${s.isPending ? "border-2 border-border text-text-secondary" : ""}
                `}>
                  {s.isDone ? <Check className="w-4 h-4" strokeWidth={3} /> : i + 1}
                </div>
                {i < stages.length - 1 && (
                  <div className="w-12 h-px bg-border relative">
                    <div className={`absolute inset-0 bg-addition transition-all duration-700 ${s.isDone ? "w-full" : "w-0"}`} />
                  </div>
                )}
              </div>
            ))}
          </div>
          {/* Labels */}
          <div className="flex items-start">
            {stages.map((s, i) => (
              <div key={i} className="flex items-start">
                <div className={`
                  w-28 text-center text-xs leading-tight transition-colors duration-500
                  ${s.isActive  ? "text-text-primary font-medium" : ""}
                  ${s.isDone    ? "text-text-primary" : ""}
                  ${s.isPending ? "text-text-secondary" : ""}
                `}>
                  {s.label}
                </div>
                {i < stages.length - 1 && <div className="w-12 shrink-0" />}
              </div>
            ))}
          </div>
        </div>

        {/* Overall progress bar */}
        <div className="w-72 flex flex-col gap-1.5">
          <div className="bg-border rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-addition h-full rounded-full transition-all duration-700"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-text-secondary">
            <span>{activeStage?.label ?? "Starting…"}</span>
            <span>{Math.round(progress)}%</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-[70vh]">
        <div className="bg-deletion/10 text-deletion border border-deletion/20 rounded-lg px-6 py-4">
          {error}
        </div>
      </div>
    );
  }

  if (!result || result.version_comparisons.length === 0) {
    return (
      <div className="flex items-center justify-center h-[70vh] text-text-secondary">
        No comparison results found.
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-57px)] flex flex-col">
      {/* Toolbar */}
      <div className="border-b border-border px-4 py-2 flex items-center gap-4 bg-surface-secondary shrink-0">
        {/* Version tabs */}
        {result.version_comparisons.length > 1 && (
          <div className="flex gap-1">
            {result.version_comparisons.map((vc, i) => (
              <button
                key={i}
                onClick={() => { setActiveVersionIdx(i); setSelectedChangeIdx(null); }}
                className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                  i === activeVersionIdx
                    ? "bg-addition text-white"
                    : "text-text-secondary hover:bg-border"
                }`}
              >
                {vc.version_label}
              </button>
            ))}
          </div>
        )}

        <div className="h-5 w-px bg-border" />

        {/* View mode toggle */}
        <div className="flex gap-1 bg-border rounded-lg p-0.5">
          <button
            onClick={() => setViewMode("side-by-side")}
            className={`px-3 py-1 text-xs rounded-md transition-colors ${
              viewMode === "side-by-side" ? "bg-surface shadow-sm" : "text-text-secondary"
            }`}
          >
            Side by Side
          </button>
          <button
            onClick={() => setViewMode("inline")}
            className={`px-3 py-1 text-xs rounded-md transition-colors ${
              viewMode === "inline" ? "bg-surface shadow-sm" : "text-text-secondary"
            }`}
          >
            Inline
          </button>
        </div>

        <label className="flex items-center gap-1.5 text-xs text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={showSubstantiveOnly}
            onChange={(e) => setShowSubstantiveOnly(e.target.checked)}
            className="accent-addition"
          />
          Substantive only
        </label>

        <div className="flex-1" />

        {/* Export */}
        <button
          onClick={handleExport}
          disabled={exporting}
          className="flex items-center gap-1.5 px-3 py-1 text-xs rounded-lg bg-addition text-white hover:bg-addition/90 disabled:opacity-50 transition-colors"
        >
          <Download className="w-3.5 h-3.5" />
          {exporting ? "Exporting..." : "Export DOCX"}
        </button>

        <div className="h-5 w-px bg-border" />

        {/* Change navigation */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-secondary">
            {selectedChangeIdx !== null ? selectedChangeIdx + 1 : "—"} / {filteredChanges.length} changes
          </span>
          <button
            onClick={() => navigateChange(-1)}
            disabled={selectedChangeIdx === null || selectedChangeIdx <= 0}
            className="p-1 rounded hover:bg-border text-text-secondary disabled:opacity-30"
            title="Previous change"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => navigateChange(1)}
            disabled={
              selectedChangeIdx === null ||
              selectedChangeIdx >= filteredChanges.length - 1
            }
            className="p-1 rounded hover:bg-border text-text-secondary disabled:opacity-30"
            title="Next change"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Diff viewer */}
        <div className="flex-1 overflow-auto">
          <DiffViewer
            changes={filteredChanges}
            selectedIdx={selectedChangeIdx}
            onSelectChange={setSelectedChangeIdx}
            viewMode={viewMode}
          />
        </div>

        {/* Detail panel */}
        {selectedChange && (
          <div className="w-96 border-l border-border overflow-auto shrink-0 bg-surface-secondary">
            <ChangeDetailPanel
              annotatedChange={selectedChange}
              onClose={() => setSelectedChangeIdx(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
