import { useRef, useEffect, useMemo } from "react";
import type { AnnotatedChange } from "@/types/api";
import RiskBadge from "@/components/RiskBadge";

interface DiffViewerProps {
  changes: AnnotatedChange[];
  selectedIdx: number | null;
  onSelectChange: (idx: number) => void;
  viewMode: "side-by-side" | "inline";
}

export default function DiffViewer({
  changes,
  selectedIdx,
  onSelectChange,
  viewMode,
}: DiffViewerProps) {
  const selectedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [selectedIdx]);

  if (changes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-text-secondary">
        No changes detected between these document versions.
      </div>
    );
  }

  if (viewMode === "side-by-side") {
    return <SideBySideView changes={changes} selectedIdx={selectedIdx} onSelectChange={onSelectChange} selectedRef={selectedRef} />;
  }

  return <InlineView changes={changes} selectedIdx={selectedIdx} onSelectChange={onSelectChange} selectedRef={selectedRef} />;
}

/* ---------- Side-by-Side View ---------- */

function SideBySideView({
  changes,
  selectedIdx,
  onSelectChange,
  selectedRef,
}: {
  changes: AnnotatedChange[];
  selectedIdx: number | null;
  onSelectChange: (idx: number) => void;
  selectedRef: React.RefObject<HTMLDivElement | null>;
}) {
  return (
    <div className="divide-y divide-border">
      {changes.map((ac, idx) => {
        const c = ac.change;
        const isSelected = idx === selectedIdx;

        return (
          <div
            key={c.id}
            ref={isSelected ? selectedRef : undefined}
            onClick={() => onSelectChange(idx)}
            className={`
              grid grid-cols-2 gap-0 cursor-pointer transition-colors
              ${isSelected ? "ring-2 ring-addition ring-inset" : "hover:bg-surface-secondary"}
            `}
          >
            {/* Original side */}
            <div className={`px-4 py-3 border-r border-border ${
              c.change_type === "deletion" || c.change_type === "modification"
                ? "bg-deletion/5"
                : ""
            }`}>
              {c.section_context && (
                <div className="text-xs text-text-secondary mb-1 font-mono">
                  {c.section_context}
                </div>
              )}
              {c.original_text ? (
                <p className="text-sm leading-relaxed">
                  {c.change_type === "deletion" && (
                    <span className="text-deletion line-through">{c.original_text}</span>
                  )}
                  {c.change_type === "modification" && (
                    <InlineDiffSpans original={c.original_text} modified={c.modified_text || ""} />
                  )}
                  {c.change_type !== "deletion" && c.change_type !== "modification" && c.original_text}
                </p>
              ) : (
                <p className="text-xs text-text-secondary italic">—</p>
              )}
            </div>

            {/* Modified side */}
            <div className={`px-4 py-3 ${
              c.change_type === "addition" || c.change_type === "modification"
                ? "bg-addition/5"
                : ""
            }`}>
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  {c.modified_text ? (
                    <p className="text-sm leading-relaxed">
                      {c.change_type === "addition" && (
                        <span className="text-addition underline">{c.modified_text}</span>
                      )}
                      {c.change_type === "modification" && (
                        <InlineDiffSpans original={c.original_text || ""} modified={c.modified_text} />
                      )}
                      {c.change_type === "move" && (
                        <span className="text-move">{c.modified_text}</span>
                      )}
                      {c.change_type !== "addition" && c.change_type !== "modification" && c.change_type !== "move" && c.modified_text}
                    </p>
                  ) : (
                    <p className="text-xs text-text-secondary italic">—</p>
                  )}
                </div>
                {ac.risk_assessment && (
                  <RiskBadge severity={ac.risk_assessment.severity} />
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ---------- Inline View ---------- */

function InlineView({
  changes,
  selectedIdx,
  onSelectChange,
  selectedRef,
}: {
  changes: AnnotatedChange[];
  selectedIdx: number | null;
  onSelectChange: (idx: number) => void;
  selectedRef: React.RefObject<HTMLDivElement | null>;
}) {
  return (
    <div className="max-w-4xl mx-auto px-6 py-4 space-y-1">
      {changes.map((ac, idx) => {
        const c = ac.change;
        const isSelected = idx === selectedIdx;

        return (
          <div
            key={c.id}
            ref={isSelected ? selectedRef : undefined}
            onClick={() => onSelectChange(idx)}
            className={`
              px-4 py-2 rounded-lg cursor-pointer transition-colors
              ${isSelected ? "ring-2 ring-addition" : "hover:bg-surface-secondary"}
            `}
          >
            {c.section_context && (
              <span className="text-xs text-text-secondary font-mono mr-2">
                [{c.section_context}]
              </span>
            )}
            {c.change_type === "deletion" && (
              <span className="text-deletion line-through">{c.original_text}</span>
            )}
            {c.change_type === "addition" && (
              <span className="text-addition underline">{c.modified_text}</span>
            )}
            {c.change_type === "modification" && (
              <InlineDiffSpans original={c.original_text || ""} modified={c.modified_text || ""} />
            )}
            {c.change_type === "move" && (
              <span className="text-move italic">[Moved] {c.original_text}</span>
            )}
            {ac.risk_assessment && (
              <RiskBadge severity={ac.risk_assessment.severity} className="ml-2 inline-flex" />
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ---------- Helpers ---------- */

type DiffOp = { type: "equal" | "delete" | "insert"; text: string };

/**
 * Compute character-level diffs between two strings using a simple LCS approach.
 * Returns an array of tagged spans for rendering.
 */
function computeInlineDiffs(original: string, modified: string): DiffOp[] {
  if (!original) return [{ type: "insert", text: modified }];
  if (!modified) return [{ type: "delete", text: original }];

  // Split into words for word-level diffing (much more readable than char-level)
  const origWords = original.split(/(\s+)/);
  const modWords = modified.split(/(\s+)/);

  // Simple O(n*m) LCS on words
  const n = origWords.length;
  const m = modWords.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0));
  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      if (origWords[i - 1] === modWords[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack to get ops
  const ops: DiffOp[] = [];
  let i = n, j = m;
  const rawOps: DiffOp[] = [];
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && origWords[i - 1] === modWords[j - 1]) {
      rawOps.push({ type: "equal", text: origWords[i - 1] });
      i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      rawOps.push({ type: "insert", text: modWords[j - 1] });
      j--;
    } else {
      rawOps.push({ type: "delete", text: origWords[i - 1] });
      i--;
    }
  }
  rawOps.reverse();

  // Merge consecutive same-type ops
  for (const op of rawOps) {
    if (ops.length > 0 && ops[ops.length - 1].type === op.type) {
      ops[ops.length - 1].text += op.text;
    } else {
      ops.push({ ...op });
    }
  }

  return ops;
}

function InlineDiffSpans({ original, modified }: { original: string; modified: string }) {
  const ops = useMemo(() => computeInlineDiffs(original, modified), [original, modified]);

  return (
    <span>
      {ops.map((op, i) => {
        if (op.type === "equal") {
          return <span key={i}>{op.text}</span>;
        }
        if (op.type === "delete") {
          return <span key={i} className="bg-deletion/15 text-deletion line-through">{op.text}</span>;
        }
        return <span key={i} className="bg-addition/15 text-addition underline">{op.text}</span>;
      })}
    </span>
  );
}
