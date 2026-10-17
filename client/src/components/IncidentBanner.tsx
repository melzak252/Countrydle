import { Info, X } from 'lucide-react';
import { useState, useEffect } from 'react';

const STORAGE_KEY = 'dismissed_incident_20261016';

export default function IncidentBanner() {
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    try {
      const isDismissed = localStorage.getItem(STORAGE_KEY) === '1';
      setDismissed(isDismissed);
    } catch {
      setDismissed(false);
    }
  }, []);

  if (dismissed) {
    return null;
  }

  const handleDismiss = () => {
    try {
      localStorage.setItem(STORAGE_KEY, '1');
    } catch {
      // Ignore localStorage quota or private-browsing errors
    }
    setDismissed(true);
  };

  return (
    <aside
      aria-label="System announcement"
      className="relative z-[1150] flex items-center justify-between gap-3 border-b border-emerald-500/25 bg-emerald-950/90 px-3.5 py-2 text-xs text-emerald-200 backdrop-blur-md transition-all shadow-sm"
    >
      <div className="flex items-center gap-2 min-w-0">
        <Info size={15} className="shrink-0 text-emerald-400" aria-hidden="true" />
        <p className="leading-snug">
          We apologize for yesterday&apos;s question answering hiccups caused by a temporary Google AI service outage. Everything is now fully operational — thank you for your patience!
        </p>
      </div>
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Dismiss announcement"
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-sm text-emerald-300 hover:bg-emerald-900/60 hover:text-sand-100 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400"
      >
        <X size={15} aria-hidden="true" />
      </button>
    </aside>
  );
}
