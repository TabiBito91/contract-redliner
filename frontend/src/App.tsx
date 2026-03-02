import { useState } from "react";
import { Routes, Route } from "react-router-dom";
import { KeyRound } from "lucide-react";
import UploadPage from "@/pages/UploadPage";
import ComparisonPage from "@/pages/ComparisonPage";
import ApiKeyModal from "@/components/ApiKeyModal";
import { useApiKey } from "@/hooks/useApiKey";

export default function App() {
  const { apiKey, saveApiKey } = useApiKey();
  const [showKeyModal, setShowKeyModal] = useState(false);

  return (
    <div className="min-h-screen bg-surface">
      <header className="border-b border-border px-6 py-3 flex items-center gap-3">
        <a href="/" className="flex items-center gap-2 no-underline">
          <div className="w-8 h-8 rounded-lg bg-addition flex items-center justify-center">
            <span className="text-white font-bold text-sm">R</span>
          </div>
          <span className="font-semibold text-lg text-text-primary">RedlineAI</span>
        </a>
        <span className="text-xs text-text-secondary ml-2">Intelligent Document Comparison</span>

        <div className="ml-auto">
          <button
            onClick={() => setShowKeyModal(true)}
            title={apiKey ? "API key configured — click to update" : "Add Anthropic API key to enable AI features"}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              apiKey
                ? "border-addition/40 text-addition hover:bg-addition/5"
                : "border-border text-text-secondary hover:bg-surface-secondary"
            }`}
          >
            <KeyRound className="w-3.5 h-3.5" />
            {apiKey ? "AI key set" : "Add API key"}
          </button>
        </div>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<UploadPage apiKey={apiKey} />} />
          <Route path="/compare/:sessionId" element={<ComparisonPage />} />
        </Routes>
      </main>

      {showKeyModal && (
        <ApiKeyModal
          currentKey={apiKey}
          onSave={saveApiKey}
          onClose={() => setShowKeyModal(false)}
        />
      )}
    </div>
  );
}
