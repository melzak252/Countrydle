import { useLayoutEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { usePageMetadataOverride, type PageMetadataInput } from '../lib/pageMetadata';

const ORIGIN = 'https://countrydle.online';
const IMAGE = `${ORIGIN}/android-chrome-512x512.png`;


type RouteMetadata = PageMetadataInput & { pageType?: string };
const publicPages: Record<string, RouteMetadata> = {
  '/': {
    title: 'Countrydle — Nine Daily Geography Games',
    description: 'Play nine daily geography puzzles: world countries, flags, four continents, US states and Polish regions. Ask yes-or-no questions and reset at 00:00 UTC.',
  },
  '/about': {
    title: 'About Countrydle — Publisher, Geography Data and Limitations',
    description: 'Meet Countrydle’s independent creator and learn how its daily geography games use data, AI interpretation and deduction, including their limitations.',
    pageType: 'AboutPage',
  },
  '/how-it-works': {
    title: 'How Countrydle Works — Questions, Rules and Geography Data',
    description: 'Learn how natural-language questions become geography checks, how daily puzzles and scoring work, and where data and interpretation can be imperfect.',
  },
  '/faq': {
    title: 'Countrydle FAQ — Daily Puzzles, Scoring and Accounts',
    description: 'Answers to common Countrydle questions about daily resets, nine game modes, question budgets, guesses, scoring, guest progress and accounts.',
  },
  '/explore': {
    title: 'Explore Countrydle — Geography Modes and Deduction Guides',
    description: 'Compare Countrydle’s daily geography modes and explore practical deduction guides for countries, flags, continents, US states and Polish regions.',
    pageType: 'CollectionPage',
  },
  '/blog': {
    title: 'Countrydle Geography Blog — Past Puzzle Recaps and Deduction',
    description: 'Explore past Countrydle answers, country facts and community deduction analysis, with clear source and editorial-review information.',
    pageType: 'CollectionPage',
  },
  '/contact': {
    title: 'Contact Countrydle — Support, Corrections and Feedback',
    description: 'Contact the Countrydle publisher about support, geography corrections, privacy questions and feedback on the daily games.',
    pageType: 'ContactPage',
  },
  '/privacy-policy': {
    title: 'Countrydle Privacy Policy — Data, Accounts and Advertising',
    description: 'Read how Countrydle handles account data, guest progress, analytics, advertising consent and your privacy rights.',
  },
  '/terms': {
    title: 'Countrydle Terms of Service — Rules and Responsibilities',
    description: 'Read the terms for playing Countrydle, using an account and submitting questions, including acceptable use and service limitations.',
  },
  '/cookie-policy': {
    title: 'Countrydle Cookie Policy — Storage and Consent Controls',
    description: 'Learn about Countrydle’s browser storage, essential game progress, advertising cookies and available consent controls.',
  },
  '/patch-notes': {
    title: 'Countrydle Patch Notes — Game Updates and Fixes',
    description: 'Read Countrydle’s published release notes covering game improvements, new features and fixes.',
  },
};

const modeGuides: Record<string, [string, string]> = {
  countrydle: ['World Countries', 'Use regions, coastlines and borders to narrow down the daily world-country puzzle. Learn question limits, data conventions and deduction examples.'],
  flagdle: ['Flags', 'Learn how to combine flag clues and geographic deduction in Countrydle’s daily Flagdle puzzle.'],
  europe: ['European Countries', 'Learn to narrow down Europe’s daily country puzzle using regional geography, borders and careful yes-or-no questions.'],
  asia: ['Asian Countries', 'Explore deduction strategies for Asia’s daily country puzzle using regions, borders and geographic clues.'],
  africa: ['African Countries', 'Explore deduction strategies for Africa’s daily country puzzle using regions, coastlines and neighboring countries.'],
  americas: ['Countries of the Americas', 'Explore deduction strategies for the Americas’ daily country puzzle using regions, coastlines and neighboring countries.'],
  'us-states': ['US States', 'Learn to identify the daily US state using regional geography, coastlines and deduction within its question and guess budgets.'],
  wojewodztwa: ['Polish Voivodeships', 'Learn to distinguish Poland’s voivodeships using borders, regions and geography within the daily puzzle’s question and guess budgets.'],
  powiaty: ['Polish Counties', 'Learn to narrow down Poland’s counties using their voivodeships, roads and registration codes in the daily Powiatdle puzzle.'],
};

const utilityPages: Record<string, [string, string]> = {
  '/login': ['Log In', 'Log in to your Countrydle account.'],
  '/register': ['Create an Account', 'Create a Countrydle account to save your progress.'],
  '/setup-profile': ['Set Up Your Profile', 'Set up your personal Countrydle profile.'],
  '/admin': ['Administration', 'Private Countrydle administration.'],
  '/friends': ['Play a Friend', 'Arrange a live Countrydle duel with a friend.'],
  '/archive': ['Puzzle Archive', 'Browse past Countrydle puzzle answers.'],
  '/leaderboard': ['Leaderboard', 'View Countrydle player rankings.'],
  '/game': ['Play Today’s Country', 'Play today’s world-country deduction puzzle.'],
  '/powiaty': ['Play Today’s Polish County', 'Play today’s Polish-county deduction puzzle.'],
  '/us-states': ['Play Today’s US State', 'Play today’s US-state deduction puzzle.'],
  '/wojewodztwa': ['Play Today’s Voivodeship', 'Play today’s Polish-voivodeship deduction puzzle.'],
  '/europe': ['Play Today’s European Country', 'Play today’s European-country deduction puzzle.'],
  '/asia': ['Play Today’s Asian Country', 'Play today’s Asian-country deduction puzzle.'],
  '/africa': ['Play Today’s African Country', 'Play today’s African-country deduction puzzle.'],
  '/americas': ['Play Today’s Country of the Americas', 'Play today’s country puzzle for the Americas.'],
  '/flagdle': ['Play Today’s Flag', 'Play today’s Flagdle puzzle.'],
  '/border-hop': ['Border Hop', 'Play the Countrydle border-route challenge.'],
};
const modeGuidePaths: Record<string, string> = {
  '/game': '/explore/modes/countrydle',
  '/flagdle': '/explore/modes/flagdle',
  '/europe': '/explore/modes/europe',
  '/asia': '/explore/modes/asia',
  '/africa': '/explore/modes/africa',
  '/americas': '/explore/modes/americas',
  '/us-states': '/explore/modes/us-states',
  '/wojewodztwa': '/explore/modes/wojewodztwa',
  '/powiaty': '/explore/modes/powiaty',
  '/border-hop': '/explore/modes/countrydle',
};

function normalizePath(path: string): string {
  return `/${path.split('/').filter(Boolean).join('/')}`;
}

function routeMetadata(path: string): RouteMetadata {
  if (publicPages[path]) return publicPages[path];
  if (path.startsWith('/explore/modes/')) {
    const modeId = path.slice('/explore/modes/'.length);
    const normalizedId = modeId === 'us_statedle' ? 'us-states' : modeId;
    const mode = modeGuides[normalizedId];
    if (mode) return {
      title: `${mode[0]} Deduction Guide | Countrydle`,
      description: mode[1],
      canonicalPath: `/explore/modes/${normalizedId}`,
    };
  }
  const utility = utilityPages[path];
  if (utility) return {
    title: `${utility[0]} | Countrydle`,
    description: utility[1],
    canonicalPath: modeGuidePaths[path],
    noindex: path === '/login' || path === '/register' || path === '/setup-profile' || path === '/admin' || path === '/friends' || path === '/archive' || path === '/leaderboard',
  };
  if (/^\/profile\/[^/]+$/.test(path)) return {
    title: 'Player Profile | Countrydle', description: 'View a Countrydle player profile.', noindex: true,
  };
  if (/^\/duel\/[^/]+$/.test(path)) return {
    title: 'Live Duel | Countrydle', description: 'Join a live Countrydle duel.', noindex: true,
  };
  if (/^\/blog\/[^/]+$/.test(path)) return {
    title: 'Loading Geography Recap | Countrydle',
    description: 'The requested past-puzzle recap is not yet available.',
    noindex: true,
  };
  return { title: 'Page Not Found | Countrydle', description: 'This Countrydle page does not exist.', noindex: true };
}


function setMeta(attribute: 'name' | 'property', key: string, content: string | null) {
  const elements = document.head.querySelectorAll<HTMLMetaElement>(`meta[${attribute}="${key}"]`);
  const element = elements[0] ?? document.createElement('meta');
  elements.forEach((duplicate) => { if (duplicate !== element) duplicate.remove(); });
  if (content === null) {
    element.remove();
    return;
  }
  element.setAttribute(attribute, key);
  element.content = content;
  if (!element.parentElement) document.head.appendChild(element);
}

function structuredData(metadata: RouteMetadata, path: string, url: string) {
  if (metadata.noindex) return null;
  const page = {
    '@context': 'https://schema.org',
    '@type': metadata.pageType ?? 'WebPage',
    '@id': `${url}#page`,
    url,
    name: metadata.title,
    description: metadata.description,
    isPartOf: { '@type': 'WebSite', name: 'Countrydle', url: `${ORIGIN}/` },
  };
  if (metadata.article) {
    const article = metadata.article;
    return {
      ...page,
      '@type': 'Article',
      headline: metadata.title,
      mainEntityOfPage: url,
      ...(article.publishedAt ? { datePublished: article.publishedAt } : {}),
      dateModified: article.updatedAt ?? article.publishedAt,
      temporalCoverage: article.puzzleDate,
      about: { '@type': 'Place', name: article.countryName },
      publisher: { '@type': 'Organization', name: 'Countrydle', url: `${ORIGIN}/about` },
      author: { '@type': 'Person', name: article.authorName || 'Jakub Melzacki', url: `${ORIGIN}/about` },
      ...(article.reviewedBy ? { reviewedBy: { '@type': 'Person', name: article.reviewedBy } } : {}),
    };
  }
  if (path === '/') return {
    ...page,
    '@type': 'WebApplication',
    name: 'Countrydle',
    applicationCategory: 'GameApplication',
    operatingSystem: 'Web browser',
    isAccessibleForFree: true,
    featureList: ['World countries', 'Flagdle', 'Europe', 'Asia', 'Africa', 'Americas', 'US states', 'Polish voivodeships', 'Polish counties', 'Live 1v1 duels'],
    author: { '@type': 'Person', name: 'Jakub Melzacki', url: `${ORIGIN}/about` },
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
  };
  return page;
}

export default function PageMetadata() {
  const { pathname } = useLocation();
  const loaded = usePageMetadataOverride();
  const path = normalizePath(pathname);
  const defaults = routeMetadata(path);
  let metadata: RouteMetadata = loaded?.pathname === pathname
    ? { ...defaults, ...loaded.metadata, noindex: loaded.metadata.noindex ?? false }
    : defaults;
  // Unknown, invalid or current-day dates must not expose a secret in metadata.
  if (metadata.article) {
    const date = metadata.article.puzzleDate;
    const timestamp = Date.parse(`${date}T00:00:00Z`);
    const validDate = /^\d{4}-\d{2}-\d{2}$/.test(date) && Number.isFinite(timestamp) &&
      new Date(timestamp).toISOString().slice(0, 10) === date;
    if (!validDate || date >= new Date().toISOString().slice(0, 10)) {
      metadata = {
        title: 'Geography Recap Unavailable | Countrydle',
        description: 'Only published past-day Countrydle recaps are available.',
        noindex: true,
      };
    }
  }
  const canonicalPath = normalizePath(metadata.canonicalPath ?? path);
  const url = `${ORIGIN}${canonicalPath}`;
  const schema = JSON.stringify(structuredData(metadata, path, url));

  useLayoutEffect(() => {
    document.title = metadata.title;
    setMeta('name', 'description', metadata.description);
    setMeta('name', 'robots', metadata.noindex ? 'noindex, follow' : 'index, follow');
    setMeta('property', 'og:title', metadata.title);
    setMeta('property', 'og:description', metadata.description);
    setMeta('property', 'og:url', url);
    setMeta('property', 'og:type', metadata.article ? 'article' : 'website');
    setMeta('property', 'og:site_name', 'Countrydle');
    setMeta('property', 'og:image', IMAGE);
    setMeta('property', 'article:published_time', metadata.article?.publishedAt || null);
    setMeta('property', 'article:modified_time', metadata.article?.updatedAt ?? metadata.article?.publishedAt ?? null);
    setMeta('name', 'twitter:card', 'summary');
    setMeta('name', 'twitter:title', metadata.title);
    setMeta('name', 'twitter:description', metadata.description);
    setMeta('name', 'twitter:image', IMAGE);
    // The shell's author described its operator, not every article's author.
    setMeta('name', 'author', metadata.article?.authorName ?? 'Jakub Melzacki');
    const canonicals = document.head.querySelectorAll<HTMLLinkElement>('link[rel="canonical"]');
    const canonical = canonicals[0] ?? document.createElement('link');
    canonical.rel = 'canonical';
    canonical.href = url;
    if (!canonical.parentElement) document.head.appendChild(canonical);
    canonicals.forEach((duplicate) => { if (duplicate !== canonical) duplicate.remove(); });
    const existing = document.getElementById('countrydle-page-schema');
    if (schema === 'null') {
      existing?.remove();
    } else {
      const script = existing ?? document.createElement('script');
      script.id = 'countrydle-page-schema';
      script.setAttribute('type', 'application/ld+json');
      script.textContent = schema.replace(/</g, '\\u003c');
      if (!script.parentElement) document.head.appendChild(script);
    }
  }, [metadata.title, metadata.description, metadata.noindex, metadata.article, path, url, schema]);

  return null;
}
