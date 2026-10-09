import { useEffect, useRef } from 'react';
import { getAdvertisingUnit, requestAdvertisingUnit, useAdvertisingPolicy } from '../advertising';

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
  const { eligible, scriptReady } = useAdvertisingPolicy();
  const unit = getAdvertisingUnit(slot);
  const insRef = useRef<HTMLModElement>(null);
  const requestedSlot = useRef<string | null>(null);
  useEffect(() => {
    if (eligible && scriptReady && insRef.current && requestedSlot.current !== unit?.slot) {
      if (requestAdvertisingUnit(insRef.current, slot)) requestedSlot.current = unit?.slot || null;
    }
  }, [eligible, scriptReady, slot, unit?.slot]);
  if (!eligible || !unit) return null;

  return (
    <div data-countrydle-ad="unit" className={`my-6 text-center ${className}`}>
      {label && (
        <div className="mb-1 text-[10px] uppercase tracking-widest text-zinc-600 font-mono">
          Advertisement
        </div>
      )}
      <div className="overflow-hidden rounded-md bg-white/[0.01] border border-white/5 p-1">
        <ins
          key={unit.slot}
          ref={insRef}
          className="adsbygoogle"
          style={style}
          data-ad-client={unit.client}
          data-ad-slot={unit.slot}
          data-ad-format={format}
          data-full-width-responsive={responsive ? 'true' : 'false'}
        />
      </div>
    </div>
  );
};

export default AdSenseUnit;
