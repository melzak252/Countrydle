import { Globe2, RotateCcw } from 'lucide-react';


export default function MapLoading({ className, error, onRetry }: {
  className: string;
  error: boolean;
  onRetry: () => void;
}) {
  
  
  return (
    <div className={`relative w-full overflow-hidden bg-[#232227] ${className}`} aria-busy={!error}>
      <div className="absolute inset-0 opacity-10 bg-[linear-gradient(#a1a1aa_1px,transparent_1px),linear-gradient(90deg,#a1a1aa_1px,transparent_1px)] bg-[size:64px_64px]" aria-hidden="true" />
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center" role={error ? 'alert' : 'status'}>
        <Globe2 className={`h-10 w-10 text-emerald-400 ${error ? '' : 'motion-safe:animate-pulse'}`} aria-hidden="true" />
        <p className="text-sm font-medium text-zinc-200">
          {error ? ('Could not load the map') : ('Loading map…')}
        </p>
        <p className="text-xs text-zinc-400">
          {error ? ('Check your connection and try again.') : ('Preparing borders and markings.')}
        </p>
        {error && (
          <button type="button" onClick={onRetry} className="flex min-h-11 items-center gap-2 rounded border border-zinc-600 bg-zinc-800 px-4 text-sm text-white hover:bg-zinc-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400">
            <RotateCcw size={16} aria-hidden="true" />
            {'Retry map'}
          </button>
        )}
      </div>
    </div>
  );
}
