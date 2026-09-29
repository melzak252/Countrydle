import { useEffect, useRef } from 'react';

declare global {
  interface Window {
    adsbygoogle: any[];
  }
}

interface AdSenseUnitProps {
  slot: string;
  format?: 'auto' | 'fluid' | 'rectangle';
  responsive?: boolean;
  style?: React.CSSProperties;
  className?: string;
  label?: boolean;
}

const AdSenseUnit = ({ 
  slot, 
  format = 'auto', 
  responsive = true,
  style = { display: 'block' },
  className = '',
  label = true,
}: AdSenseUnitProps) => {
  const client = import.meta.env.VITE_GOOGLE_ADSENSE_ID || 'ca-pub-3937273134876300';
  const insRef = useRef<HTMLModElement>(null);

  useEffect(() => {
    try {
      if (insRef.current && !insRef.current.getAttribute('data-adsbygoogle-status')) {
        (window.adsbygoogle = window.adsbygoogle || []).push({});
      }
    } catch (err) {
      // AdSense initialization error (e.g. adblock or double push in dev)
      console.debug('AdSense notice:', err);
    }
  }, []);

  if (!client) return null;

  return (
    <div className={`my-6 text-center ${className}`}>
      {label && (
        <div className="mb-1 text-[10px] uppercase tracking-widest text-zinc-600 font-mono">
          Advertisement
        </div>
      )}
      <div className="overflow-hidden rounded-md bg-white/[0.01] border border-white/5 p-1">
        <ins
          ref={insRef}
          className="adsbygoogle"
          style={style}
          data-ad-client={client}
          data-ad-slot={slot}
          data-ad-format={format}
          data-full-width-responsive={responsive ? "true" : "false"}
        />
      </div>
    </div>
  );
};

export default AdSenseUnit;
