import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { MapInteractionState } from '../lib/mapMarkings';

interface EntityMarkControlsProps {
  entities: readonly { name: string }[];
  interaction: MapInteractionState;
  lockedEntityName?: string;
  disabled?: boolean;
}

export default function EntityMarkControls({ entities, interaction, lockedEntityName, disabled = false }: EntityMarkControlsProps) {
  const { i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');
  const selectId = useId();
  const [selection, setSelection] = useState('');
  // Only the selection is local; all markings remain owned by the game or duel.
  const selectedName = entities.some(entity => entity.name === selection) ? selection : '';
  const marker = selectedName ? interaction.entityMarkings[selectedName.toUpperCase()] : undefined;
  const locked = !!selectedName && selectedName.toUpperCase() === lockedEntityName?.toUpperCase();
  const unavailable = disabled || !selectedName || locked;
  const stateLabel = locked
    ? (isPl ? 'Ujawniony cel — oznaczenie zablokowane' : 'Revealed target — marking locked')
    : marker === 'green' ? (isPl ? 'Kandydat' : 'Candidate')
    : marker === 'red' ? (isPl ? 'Wykluczony' : 'Excluded')
    : marker === 'blue' ? (isPl ? 'Niebieskie oznaczenie' : 'Blue marking')
    : marker === 'orange' ? (isPl ? 'Pomarańczowe oznaczenie' : 'Orange marking')
    : (isPl ? 'Bez oznaczenia' : 'Unmarked');
  const buttonClass = 'min-h-11 rounded border border-zinc-500 px-3 py-2 text-sm disabled:opacity-50';

  return (
    <section aria-label={isPl ? 'Oznaczenia regionów' : 'Entity markings'}
      className="absolute bottom-[calc(4.5rem+env(safe-area-inset-bottom))] left-3 right-3 md:bottom-3 md:left-auto md:w-80 z-[1050] rounded border border-zinc-600 bg-zinc-900 p-3 text-white shadow-lg"
      onPointerDown={event => event.stopPropagation()} onClick={event => event.stopPropagation()}>
      <label htmlFor={selectId} className="block text-sm mb-1">{isPl ? 'Region' : 'Entity'}</label>
      <select id={selectId} value={selectedName} disabled={disabled || entities.length === 0}
        onChange={event => setSelection(event.target.value)}
        className="min-h-11 w-full rounded border border-zinc-500 bg-zinc-900 px-2 text-sm">
        <option value="">{isPl ? 'Wybierz region' : 'Select an entity'}</option>
        {entities.map(entity => <option key={entity.name} value={entity.name}>{entity.name}</option>)}
      </select>
      <div className="mt-2 flex flex-wrap gap-2">
        <button type="button" className={buttonClass} disabled={unavailable} aria-pressed={marker === 'green'}
          onClick={() => interaction.toggleEntityMarker(selectedName, 'green')}>{isPl ? 'Oznacz kandydata' : 'Mark candidate'}</button>
        <button type="button" className={buttonClass} disabled={unavailable} aria-pressed={marker === 'red'}
          onClick={() => interaction.toggleEntityMarker(selectedName, 'red')}>{isPl ? 'Oznacz wykluczony' : 'Mark excluded'}</button>
        <button type="button" className={buttonClass} disabled={unavailable || !marker}
          onClick={() => { if (marker) interaction.toggleEntityMarker(selectedName, marker); }}>{isPl ? 'Usuń oznaczenie' : 'Remove marking'}</button>
      </div>
      <p role="status" aria-label={isPl ? 'Stan oznaczenia' : 'Marking status'} aria-live="polite" aria-atomic="true" className="mt-2 text-sm">
        {selectedName ? `${selectedName}: ${stateLabel}` : (isPl ? 'Wybierz region, aby go oznaczyć.' : 'Select an entity to mark it.')}
      </p>
    </section>
  );
}
