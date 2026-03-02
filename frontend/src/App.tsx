import { Routes, Route } from "react-router-dom";
import UploadPage from "@/pages/UploadPage";
import ComparisonPage from "@/pages/ComparisonPage";

export default function App() {
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
      </header>

      <main>
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/compare/:sessionId" element={<ComparisonPage />} />
        </Routes>
      </main>
    </div>
  );
}
