import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import CountrydleLogo from './CountrydleLogo';
import { PrivacySettingsButton } from './PrivacySettingsButton';

export default function Footer() {
  const { t } = useTranslation();

  return (
    <footer className="border-t border-white/[0.06] bg-obsidian-950 pt-6 pb-[calc(1.5rem+env(safe-area-inset-bottom))] text-zinc-500 text-xs mt-20">
      <div className="max-w-6xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <CountrydleLogo size={20} />
          </div>
          <div className="text-center md:text-left">
            <div className="text-zinc-300 font-bold tracking-tight text-sm">Countrydle</div>
          </div>
        </div>

        <div className="flex flex-wrap justify-center items-center gap-x-2 gap-y-1 text-zinc-400 font-medium">
          <Link to="/how-it-works" className="flex min-h-11 items-center px-2 hover:text-white transition-colors">{t('footer.howItWorks', 'How Questions Work')}</Link>
          <Link to="/about" className="flex min-h-11 items-center px-2 hover:text-white transition-colors">{t('footer.about', 'About')}</Link>
          <Link to="/faq" className="flex min-h-11 items-center px-2 hover:text-white transition-colors">{t('footer.faq', 'FAQ')}</Link>
          <Link to="/explore" className="flex min-h-11 items-center px-2 hover:text-white transition-colors">{t('footer.explore', 'Geography Guides')}</Link>
          <Link to="/blog" className="flex min-h-11 items-center px-2 hover:text-white transition-colors">{t('footer.blog', 'Blog')}</Link>
          <Link to="/contact" className="flex min-h-11 items-center px-2 hover:text-white transition-colors">{t('footer.suggestions', 'Suggestions')}</Link>
          <span className="text-zinc-800 hidden sm:inline">•</span>
          <Link to="/privacy-policy" className="flex min-h-11 items-center px-2 hover:text-zinc-300 transition-colors text-zinc-500 text-[11px]">{t('footer.privacyPolicy')}</Link>
          <Link to="/terms" className="flex min-h-11 items-center px-2 hover:text-zinc-300 transition-colors text-zinc-500 text-[11px]">{t('footer.termsOfService')}</Link>
          <Link to="/cookie-policy" className="flex min-h-11 items-center px-2 hover:text-zinc-300 transition-colors text-zinc-500 text-[11px]">{t('footer.cookiePolicy')}</Link>
          <PrivacySettingsButton className="min-h-11 px-2 hover:text-zinc-300 transition-colors text-zinc-500 text-[11px]" />
        </div>

        <div className="text-zinc-600 font-mono text-[11px]">
          &copy; {new Date().getFullYear()} Countrydle.
        </div>
      </div>
    </footer>
  );
}
