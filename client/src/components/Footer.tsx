import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import CountrydleLogo from './CountrydleLogo';
import { PrivacySettingsButton } from './PrivacySettingsButton';

export default function Footer() {
  const { i18n } = useTranslation();
  const isPl = i18n?.language?.startsWith('pl');
  const links = [
    { path: '/privacy-policy', label: isPl ? 'Prywatność' : 'Privacy' },
    { path: '/cookie-policy', label: isPl ? 'Pliki cookie' : 'Cookies' },
    { path: '/terms', label: isPl ? 'Regulamin' : 'Terms of use' },
    { path: '/contact', label: isPl ? 'Kontakt' : 'Contact' },
  ];
  const linkClass = 'flex min-h-11 min-w-0 items-center rounded-lg px-3 py-2 text-sm leading-relaxed text-zinc-400 transition-colors hover:bg-white/5 hover:text-white [overflow-wrap:anywhere]';

  return (
    <footer className="mt-8 border-t border-white/[0.06] bg-obsidian-950 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-4 text-zinc-400">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 md:flex-row md:items-center md:justify-between md:gap-6">
        <div className="flex items-center gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-emerald-500/20 bg-emerald-500/10 text-emerald-400">
            <CountrydleLogo size={20} />
          </div>
          <span className="text-sm font-bold tracking-tight text-zinc-300">Countrydle</span>
        </div>

        <nav aria-label={isPl ? 'Nawigacja w stopce' : 'Footer navigation'} className="grid w-full min-w-0 grid-cols-2 gap-x-2 md:flex md:w-auto md:flex-wrap md:gap-x-1">
          {links.map((link) => (
            <Link key={link.path} to={link.path} className={linkClass}>{link.label}</Link>
          ))}
          <PrivacySettingsButton className={linkClass} />
        </nav>

        <div className="shrink-0 text-xs text-zinc-500">
          &copy; {new Date().getFullYear()} Countrydle.
        </div>
      </div>
    </footer>
  );
}
