import { useState } from "react";
import { X, Eye, EyeOff, KeyRound } from "lucide-react";

interface Props {
  currentKey: string;
  onSave: (key: string) => void;
  onClose: () => void;
}

export default function ApiKeyModal({ currentKey, onSave, onClose }: Props) {
  const [value, setValue] = useState(currentKey);
  const [visible, setVisible] = useState(false);

  const handleSave = () => {
    onSave(value);
    onClose();
  };

  const handleClear = () => {
    onSave("");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-surface border border-border rounded-2xl shadow-xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-addition" />
            <h2 className="font-semibold text-text-primary">Anthropic API Key</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-surface-secondary text-text-secondary"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-sm text-text-secondary mb-4">
          Enter your Anthropic API key to enable AI-powered change summaries and
          risk analysis. Your key is stored only in this browser and sent directly
          to the analysis service — it is never saved on any server.
        </p>

        <div className="relative mb-4">
          <input
            type={visible ? "text" : "password"}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="sk-ant-..."
            className="w-full border border-border rounded-lg px-3 py-2 pr-10 text-sm bg-surface font-mono"
            autoFocus
            onKeyDown={(e) => e.key === "Enter" && handleSave()}
          />
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary"
          >
            {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>

        <p className="text-xs text-text-secondary mb-6">
          Don't have a key?{" "}
          <a
            href="https://console.anthropic.com/settings/keys"
            target="_blank"
            rel="noopener noreferrer"
            className="text-addition hover:underline"
          >
            Get one at console.anthropic.com
          </a>
          . AI features are optional — the diff viewer works without a key.
        </p>

        <div className="flex gap-3">
          <button
            onClick={handleSave}
            className="flex-1 py-2 rounded-lg bg-addition text-white text-sm font-medium hover:bg-addition/90"
          >
            Save Key
          </button>
          {currentKey && (
            <button
              onClick={handleClear}
              className="px-4 py-2 rounded-lg border border-deletion/40 text-deletion text-sm font-medium hover:bg-deletion/5"
            >
              Remove
            </button>
          )}
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-border text-text-secondary text-sm hover:bg-surface-secondary"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
