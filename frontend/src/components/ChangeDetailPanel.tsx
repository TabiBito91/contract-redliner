import type { AnnotatedChange } from "@/types/api";
import RiskBadge from "@/components/RiskBadge";
import { X, AlertTriangle, Lightbulb, Info } from "lucide-react";

interface ChangeDetailPanelProps {
  annotatedChange: AnnotatedChange;
  onClose: () => void;
}

const changeTypeLabels: Record<string, string> = {
  addition: "Addition",
  deletion: "Deletion",
  modification: "Modification",
  move: "Moved",
  format_only: "Formatting Only",
};

export default function ChangeDetailPanel({
  annotatedChange: ac,
  onClose,
}: ChangeDetailPanelProps) {
  const { change, ai_summary, risk_assessment } = ac;

  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <span className={`
            text-xs font-bold uppercase px-2 py-0.5 rounded
            ${change.change_type === "deletion" ? "bg-deletion/15 text-deletion" :
              change.change_type === "addition" ? "bg-addition/15 text-addition" :
              change.change_type === "move" ? "bg-move/15 text-move" :
              "bg-addition/15 text-addition"}
          `}>
            {changeTypeLabels[change.change_type] ?? change.change_type}
          </span>
          {change.section_context && (
            <p className="text-xs text-text-secondary mt-1 font-mono">
              Section {change.section_context}
            </p>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-border text-text-secondary"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Original text */}
      {change.original_text && (
        <div>
          <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-1">
            Original
          </h4>
          <div className="bg-deletion/5 border border-deletion/15 rounded-lg p-3">
            <p className="text-sm text-deletion line-through leading-relaxed">
              {change.original_text}
            </p>
          </div>
        </div>
      )}

      {/* Modified text */}
      {change.modified_text && (
        <div>
          <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-1">
            Modified
          </h4>
          <div className="bg-addition/5 border border-addition/15 rounded-lg p-3">
            <p className="text-sm text-addition underline leading-relaxed">
              {change.modified_text}
            </p>
          </div>
        </div>
      )}

      {/* AI Summary */}
      {ai_summary && (
        <div>
          <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-1 flex items-center gap-1">
            <Lightbulb className="w-3 h-3" /> AI Summary
          </h4>
          <div className="bg-surface border border-border rounded-lg p-3">
            <p className="text-sm leading-relaxed">{ai_summary.summary}</p>
            <p className="text-xs text-text-secondary mt-1">
              Category: {ai_summary.change_category}
            </p>
          </div>
        </div>
      )}

      {/* Risk Assessment */}
      {risk_assessment && (
        <div>
          <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-1 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> Risk Assessment
          </h4>
          <div className="bg-surface border border-border rounded-lg p-3 space-y-2">
            <div className="flex items-center gap-2">
              <RiskBadge severity={risk_assessment.severity} />
              <span className="text-xs text-text-secondary">
                Confidence: {risk_assessment.confidence}%
              </span>
            </div>
            <p className="text-sm leading-relaxed">
              {risk_assessment.risk_explanation}
            </p>
            <div className="border-t border-border pt-2 mt-2">
              <p className="text-xs font-semibold text-text-secondary uppercase mb-0.5">
                Recommendation
              </p>
              <p className="text-sm font-medium">{risk_assessment.recommendation}</p>
            </div>
          </div>
        </div>
      )}

      {/* No AI disclaimer */}
      {!ai_summary && !risk_assessment && (
        <div className="flex items-start gap-2 bg-surface-secondary rounded-lg p-3">
          <Info className="w-4 h-4 text-text-secondary shrink-0 mt-0.5" />
          <p className="text-xs text-text-secondary">
            AI analysis not available. Set the ANTHROPIC_API_KEY environment
            variable to enable AI-powered summaries and risk assessments.
          </p>
        </div>
      )}

      {/* Disclaimer */}
      {(ai_summary || risk_assessment) && (
        <p className="text-[10px] text-text-secondary/70 leading-tight">
          AI-generated analysis. Does not constitute legal advice.
        </p>
      )}
    </div>
  );
}
