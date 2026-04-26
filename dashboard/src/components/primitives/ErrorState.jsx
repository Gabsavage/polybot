import { AlertTriangle, RefreshCw } from "lucide-react";

export default function ErrorState({ error, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <AlertTriangle size={32} className="text-pnl-negative mb-3" />
      <div className="text-text-primary font-medium mb-1">Erreur de chargement</div>
      {error?.message && (
        <details className="text-xs text-text-secondary mt-2 max-w-md">
          <summary className="cursor-pointer">Détails</summary>
          <pre className="mt-2 text-left bg-bg-card p-3 rounded text-text-tertiary overflow-auto">
            {error.message}{error.info ? `\n\n${error.info}` : ""}
          </pre>
        </details>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-accent-orange/10 text-accent-orange hover:bg-accent-orange/20 rounded-lg text-sm font-medium transition-colors"
        >
          <RefreshCw size={14} />
          Réessayer
        </button>
      )}
    </div>
  );
}
