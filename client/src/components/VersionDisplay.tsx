import { useEffect, useState } from 'react';
import axios from 'axios';
import { API_URL } from '../services/api';

export default function VersionDisplay() {
  const [serverVersion, setServerVersion] = useState<string | null>(null);
  const clientVersion = __APP_VERSION__;

  useEffect(() => {
    const fetchServerVersion = async () => {
      try {
        const response = await axios.get(`${API_URL}/version`);
        setServerVersion(response.data.version);
      } catch (error) {
        console.error('Failed to fetch server version', error);
      }
    };

    fetchServerVersion();
  }, []);

  return (
    <div className="hidden xl:block fixed bottom-[calc(env(safe-area-inset-bottom)+0.25rem)] right-1 z-[9999] rounded-sm border border-white/15 bg-obsidian-950/90 px-1.5 py-0.5 font-mono text-[10px] text-zinc-300 pointer-events-none select-none md:bottom-1 md:border-0 md:bg-transparent md:p-0 md:text-zinc-600 md:opacity-50">
      v{clientVersion} {serverVersion && `(s: ${serverVersion})`}
    </div>
  );
}
