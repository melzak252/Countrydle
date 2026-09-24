// Server lists are authoritative; retain these exclusions for stale responses and map state.
export function isCountryAvailable(name: string, mode?: string): boolean {
  const normalized = name.trim().toUpperCase();
  return normalized !== 'ISRAEL' && !(mode === 'europe' && normalized === 'AZERBAIJAN');
}
