import { useState } from 'react';
import type { FriendMode } from '../../types/friendMatch';
import type { MapMarkerColor } from '../../stores/gameStore';
import { mapClickColor, toggleMapMarking, type MapInteractionState } from '../../lib/mapMarkings';
import { ControlledMapBox } from '../MapBox';
import { ControlledUSStatesMap } from '../USStatesMap';
import { ControlledWojewodztwaMap } from '../WojewodztwaMap';
import { ControlledPowiatyMap } from '../PowiatyMap';

interface FriendDuelMapProps {
  mode: FriendMode;
  matchKey: string;
  finished: boolean;
  revealedEntityName?: string;
  className?: string;
  onEntitySelect?: (name: string) => void;
  isLobby?: boolean;
  selectedSecretName?: string;
}

function MatchMap({
  mode,
  finished,
  revealedEntityName,
  className,
  onEntitySelect,
  isLobby = false,
  selectedSecretName,
}: FriendDuelMapProps) {
  const [entityMarkings, setEntityMarkings] = useState<Record<string, MapMarkerColor>>({});
  const [activeMarkerColor, setActiveMarkerColor] = useState<MapMarkerColor>('green');

  // In the lobby, disable general palette coloring; highlight ONLY the selected secret country
  const effectiveMarkings = isLobby
    ? (selectedSecretName ? { [selectedSecretName.toUpperCase()]: 'green' as MapMarkerColor } : {})
    : entityMarkings;

  const interaction: MapInteractionState = {
    entityMarkings: effectiveMarkings,
    activeMarkerColor,
    setActiveMarkerColor,
    handleEntityMapClick: (name, isSecondary = false) => {
      if (isLobby) {
        // In lobby, map clicks select the secret; coloring is handled via selectedSecretName
        onEntitySelect?.(name);
        return;
      }
      const color = mapClickColor(activeMarkerColor, isSecondary);
      setEntityMarkings(markings => toggleMapMarking(markings, name, color));
    },
    clearMapMarkings: () => setEntityMarkings({}),
    isGameOver: finished,
  };
  const revealedName = finished ? revealedEntityName : undefined;

  switch (mode) {
    case 'countrydle':
      return <ControlledMapBox interaction={interaction} correctCountryName={revealedName} className={className} onCountryClick={onEntitySelect} />;
    case 'europe':
      return (
        <ControlledMapBox
          interaction={interaction}
          correctCountryName={revealedName}
          className={className}
          center={[52, 16]}
          zoom={3.8}
          minZoom={2.5}
          maxZoom={8}
          geoJsonUrl="/europe.geojson"
          onCountryClick={onEntitySelect}
        />
      );
    case 'asia':
      return (
        <ControlledMapBox
          interaction={interaction}
          correctCountryName={revealedName}
          className={className}
          center={[34, 95]}
          zoom={3}
          minZoom={2}
          maxZoom={8}
          geoJsonUrl="/asia.geojson"
          onCountryClick={onEntitySelect}
        />
      );
    case 'africa':
      return (
        <ControlledMapBox
          interaction={interaction}
          correctCountryName={revealedName}
          className={className}
          center={[2, 20]}
          zoom={3}
          minZoom={2}
          maxZoom={8}
          geoJsonUrl="/africa.geojson"
          onCountryClick={onEntitySelect}
        />
      );
    case 'americas':
      return (
        <ControlledMapBox
          interaction={interaction}
          correctCountryName={revealedName}
          className={className}
          center={[15, -85]}
          zoom={2.5}
          minZoom={1.8}
          maxZoom={8}
          geoJsonUrl="/americas.geojson"
          onCountryClick={onEntitySelect}
        />
      );
    case 'us_statedle':
      return <ControlledUSStatesMap interaction={interaction} correctStateName={revealedName} className={className} onStateClick={onEntitySelect} />;
    case 'wojewodztwodle':
      return <ControlledWojewodztwaMap interaction={interaction} correctWojewodztwoName={revealedName} className={className} onWojewodztwoClick={onEntitySelect} />;
    case 'powiatdle':
      return <ControlledPowiatyMap interaction={interaction} correctPowiatName={revealedName} className={className} onPowiatClick={onEntitySelect} />;
  }
}

export default function FriendDuelMap(props: FriendDuelMapProps) {
  // Rematches start with a fresh map, viewport, color, and private markings.
  return <MatchMap key={`${props.matchKey}:${props.mode}`} {...props} />;
}
