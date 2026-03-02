import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useDropzone } from "react-dropzone";
import { Upload, FileText, X, ChevronUp, ChevronDown, Star } from "lucide-react";
import { uploadDocument, createSession, runComparison } from "@/services/api";
import { formatFileSize } from "@/lib/utils";
import type { DocumentInfo, ReviewingParty, ComparisonMode } from "@/types/api";

export default function UploadPage({ apiKey }: { apiKey?: string }) {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [originalId, setOriginalId] = useState<string | null>(null);
  const [reviewingParty, setReviewingParty] = useState<ReviewingParty>("neutral");
  const [comparisonMode, setComparisonMode] = useState<ComparisonMode>("original_to_each");
  const [uploading, setUploading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    setUploading(true);
    setError(null);
    try {
      for (const file of acceptedFiles) {
        const res = await uploadDocument(file);
        setDocuments((prev) => {
          const next = [...prev, res.document];
          // Auto-select first upload as original
          if (next.length === 1) setOriginalId(res.document.id);
          return next;
        });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    },
    maxFiles: 10,
  });

  const removeDoc = (id: string) => {
    setDocuments((prev) => prev.filter((d) => d.id !== id));
    if (originalId === id) {
      setOriginalId(documents.find((d) => d.id !== id)?.id ?? null);
    }
  };

  const moveDoc = (idx: number, direction: -1 | 1) => {
    setDocuments((prev) => {
      const next = [...prev];
      const target = idx + direction;
      if (target < 0 || target >= next.length) return prev;
      [next[idx], next[target]] = [next[target], next[idx]];
      return next;
    });
  };

  const handleCompare = async () => {
    if (!originalId || documents.length < 2) return;
    setStarting(true);
    setError(null);
    try {
      const docOrder = documents.filter((d) => d.id !== originalId).map((d) => d.id);
      const session = await createSession({
        original_document_id: originalId,
        document_order: docOrder,
        comparison_mode: comparisonMode,
        reviewing_party: reviewingParty,
      });
      await runComparison(session.id, apiKey);
      navigate(`/compare/${session.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start comparison");
      setStarting(false);
    }
  };

  const canCompare = documents.length >= 2 && originalId !== null && !starting;

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-2">
          Compare Documents
        </h1>
        <p className="text-text-secondary">
          Upload two or more DOCX files to generate an intelligent redline comparison
          with AI-powered change summaries and risk analysis.
        </p>
      </div>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-xl p-10 text-center cursor-pointer
          transition-colors mb-6
          ${isDragActive
            ? "border-addition bg-addition/5"
            : "border-border hover:border-addition/50 hover:bg-surface-secondary"
          }
        `}
      >
        <input {...getInputProps()} />
        <Upload className="w-10 h-10 mx-auto mb-3 text-text-secondary" />
        {uploading ? (
          <p className="text-text-secondary">Uploading...</p>
        ) : isDragActive ? (
          <p className="text-addition font-medium">Drop files here</p>
        ) : (
          <>
            <p className="font-medium text-text-primary mb-1">
              Drag & drop DOCX files here, or click to browse
            </p>
            <p className="text-sm text-text-secondary">
              Upload 2-10 files, up to 50MB each
            </p>
          </>
        )}
      </div>

      {/* File list */}
      {documents.length > 0 && (
        <div className="border border-border rounded-xl mb-6 overflow-hidden">
          <div className="bg-surface-secondary px-4 py-2 border-b border-border">
            <span className="text-sm font-medium text-text-secondary">
              {documents.length} document{documents.length !== 1 ? "s" : ""} uploaded
            </span>
          </div>
          <ul>
            {documents.map((doc, idx) => (
              <li
                key={doc.id}
                className={`
                  flex items-center gap-3 px-4 py-3 border-b border-border last:border-b-0
                  ${doc.id === originalId ? "bg-addition/5" : ""}
                `}
              >
                <FileText className="w-5 h-5 text-text-secondary shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm truncate">{doc.filename}</span>
                    {doc.id === originalId && (
                      <span className="text-xs bg-addition text-white px-1.5 py-0.5 rounded font-medium">
                        Original
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-text-secondary">
                    {formatFileSize(doc.file_size)}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={(e) => { e.stopPropagation(); setOriginalId(doc.id); }}
                    title="Set as original"
                    className={`p-1 rounded hover:bg-surface-secondary ${
                      doc.id === originalId ? "text-addition" : "text-text-secondary"
                    }`}
                  >
                    <Star className="w-4 h-4" fill={doc.id === originalId ? "currentColor" : "none"} />
                  </button>
                  <button
                    onClick={() => moveDoc(idx, -1)}
                    disabled={idx === 0}
                    className="p-1 rounded hover:bg-surface-secondary text-text-secondary disabled:opacity-30"
                  >
                    <ChevronUp className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => moveDoc(idx, 1)}
                    disabled={idx === documents.length - 1}
                    className="p-1 rounded hover:bg-surface-secondary text-text-secondary disabled:opacity-30"
                  >
                    <ChevronDown className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => removeDoc(doc.id)}
                    className="p-1 rounded hover:bg-deletion/10 text-text-secondary hover:text-deletion"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Options */}
      {documents.length >= 2 && (
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">
              Reviewing Party
            </label>
            <select
              value={reviewingParty}
              onChange={(e) => setReviewingParty(e.target.value as ReviewingParty)}
              className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-surface"
            >
              <option value="original_drafter">Original Drafter</option>
              <option value="counterparty">Counterparty</option>
              <option value="neutral">Neutral Reviewer</option>
            </select>
          </div>
          {documents.length > 2 && (
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">
                Comparison Mode
              </label>
              <select
                value={comparisonMode}
                onChange={(e) => setComparisonMode(e.target.value as ComparisonMode)}
                className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-surface"
              >
                <option value="original_to_each">Original to Each Version</option>
                <option value="sequential">Sequential (V1 → V2 → V3)</option>
                <option value="cumulative">Cumulative View</option>
              </select>
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-deletion/10 text-deletion border border-deletion/20 rounded-lg px-4 py-3 mb-4 text-sm">
          {error}
        </div>
      )}

      {/* Compare button */}
      <button
        onClick={handleCompare}
        disabled={!canCompare}
        className={`
          w-full py-3 rounded-xl font-semibold text-white transition-colors
          ${canCompare
            ? "bg-addition hover:bg-addition/90 cursor-pointer"
            : "bg-text-secondary/30 cursor-not-allowed"
          }
        `}
      >
        {starting ? "Starting comparison..." : "Compare Documents"}
      </button>

      {documents.length === 1 && (
        <p className="text-center text-sm text-text-secondary mt-3">
          Upload at least one more document to compare
        </p>
      )}
    </div>
  );
}
