import { useEffect } from 'react';
import L from 'leaflet';
import { useMap } from 'react-leaflet';
import './mapSurface.css';

const SVG_NAMESPACE = 'http://www.w3.org/2000/svg';
const PAPER_EDGE_OUTER =
  'M 0 23 L 16 19 L 32 23 L 49 18 L 68 22 L 86 17 L 105 21 L 123 18 L 143 22 L 162 17 L 181 21 L 199 18 L 220 23 L 239 18 L 259 21 L 278 17 L 298 22 L 318 18 L 338 22 L 358 17 L 378 21 L 399 18 L 418 23 L 439 17 L 460 21 L 480 18 L 501 22 L 521 17 L 542 21 L 562 18 L 582 22 L 603 17 L 623 21 L 644 18 L 664 22 L 685 17 L 706 21 L 726 18 L 747 23 L 767 17 L 788 21 L 809 18 L 829 22 L 850 17 L 871 21 L 891 18 L 912 22 L 933 17 L 953 21 L 975 18 L 1000 24 L 997 48 L 1000 72 L 996 96 L 999 121 L 995 145 L 1000 170 L 996 195 L 999 220 L 995 244 L 999 269 L 996 294 L 1000 319 L 995 344 L 999 369 L 996 393 L 1000 418 L 995 443 L 999 468 L 996 493 L 1000 518 L 995 543 L 999 568 L 995 592 L 1000 617 L 978 622 L 957 618 L 936 623 L 915 619 L 894 624 L 873 619 L 852 623 L 831 618 L 810 624 L 789 619 L 768 623 L 747 618 L 726 624 L 705 619 L 684 623 L 663 618 L 642 624 L 621 619 L 600 623 L 579 618 L 558 624 L 537 619 L 516 623 L 495 618 L 474 624 L 453 619 L 432 623 L 411 618 L 390 624 L 369 619 L 348 623 L 327 618 L 306 624 L 285 619 L 264 623 L 243 618 L 222 624 L 201 619 L 180 623 L 159 618 L 138 624 L 117 619 L 96 623 L 75 618 L 54 624 L 33 619 L 11 623 L 5 598 L 9 574 L 4 549 L 8 524 L 3 499 L 7 474 L 3 449 L 8 424 L 4 399 L 9 374 L 3 349 L 8 324 L 4 299 L 9 274 L 3 249 L 8 224 L 4 199 L 9 174 L 3 149 L 8 124 L 4 99 L 9 74 L 3 49 Z';
const PAPER_EDGE_WINDOW =
  'M 44 58 L 99 56 L 154 59 L 209 55 L 264 58 L 319 56 L 374 59 L 429 55 L 484 58 L 539 56 L 594 59 L 649 55 L 704 58 L 759 56 L 814 59 L 869 55 L 924 58 L 958 56 L 957 111 L 960 166 L 956 221 L 959 276 L 956 331 L 960 386 L 956 441 L 959 496 L 956 551 L 959 604 L 906 602 L 852 606 L 797 602 L 742 605 L 687 601 L 632 605 L 577 602 L 522 606 L 467 602 L 412 605 L 357 601 L 302 606 L 247 602 L 192 605 L 137 601 L 82 605 L 42 602 L 44 548 L 41 493 L 45 438 L 41 383 L 45 328 L 41 273 L 45 218 L 41 163 L 45 108 Z';

function createPaperArtwork(): SVGSVGElement {
  const svg = document.createElementNS(SVG_NAMESPACE, 'svg');
  svg.setAttribute('class', 'map-paper-artwork');
  svg.setAttribute('viewBox', '0 0 1000 660');
  svg.setAttribute('preserveAspectRatio', 'none');
  svg.setAttribute('aria-hidden', 'true');

  const margin = document.createElementNS(SVG_NAMESPACE, 'path');
  margin.setAttribute('class', 'map-paper-artwork__margin');
  margin.setAttribute('d', `${PAPER_EDGE_OUTER} ${PAPER_EDGE_WINDOW}`);
  margin.setAttribute('fill-rule', 'evenodd');
  svg.appendChild(margin);

  const edge = document.createElementNS(SVG_NAMESPACE, 'path');
  edge.setAttribute('class', 'map-paper-artwork__edge');
  edge.setAttribute('d', PAPER_EDGE_OUTER);
  svg.appendChild(edge);

  return svg;
}

export default function MapPaperEdge() {
  const map = useMap();

  useEffect(() => {
    const bounds = map.getMaxBounds();
    if (!bounds) return;

    const paneName = 'map-paper-artwork';
    const pane = map.getPane(paneName) ?? map.createPane(paneName);
    pane.style.zIndex = '250';
    pane.style.pointerEvents = 'none';

    const artwork = L.svgOverlay(createPaperArtwork(), bounds, {
      pane: paneName,
      interactive: false,
    });
    artwork.addTo(map);

    return () => {
      artwork.remove();
    };
  }, [map]);

  return null;
}
