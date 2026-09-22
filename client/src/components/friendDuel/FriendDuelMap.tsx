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
}

function MatchMap({ mode, finished, revealedEntityName, className }: FriendDuelMapProps) {
  const [entityMarkings, setEntityMarkings] = useState<Record<string, MapMarkerColor>>({});
  const [activeMarkerColor, setActiveMarkerColor] = useState<MapMarkerColor>('green');
  const interaction: MapInteractionState = {
    entityMarkings,
    activeMarkerColor,
    setActiveMarkerColor,
    handleEntityMapClick: (name, isSecondary = false) => {
      const color = mapClickColor(activeMarkerColor, isSecondary);
      setEntityMarkings(markings => toggleMapMarking(markings, name, color));
    },
    clearMapMarkings: () => setEntityMarkings({}),
    isGameOver: finished,
  };
  const revealedName = finished ? revealedEntityName : undefined;

  switch (mode) {
    case 'countrydle':
      return <ControlledMapBox interaction={interaction} correctCountryName={revealedName} className={className} />;
    case 'us_statedle':
      return <ControlledUSStatesMap interaction={interaction} correctStateName={revealedName} className={className} />;
    case 'wojewodztwodle':
      return <ControlledWojewodztwaMap interaction={interaction} correctWojewodztwoName={revealedName} className={className} />;
    case 'powiatdle':
      return <ControlledPowiatyMap interaction={interaction} correctPowiatName={revealedName} className={className} />;
  }
}

export default function FriendDuelMap(props: FriendDuelMapProps) {
  // Rematches start with a fresh map, viewport, color, and private markings.
  return <MatchMap key={`${props.matchKey}:${props.mode}`} {...props} />;
}
