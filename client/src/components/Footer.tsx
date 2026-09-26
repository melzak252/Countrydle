import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import CountrydleLogo from './CountrydleLogo';
import { PrivacySettingsButton } from './PrivacySettingsButton';

export default function Footer() {
  const { t } = useTranslation();

  return (
    <footer className="border-t border-white/[0.06] bg-obsidian-950 py-10 text-zinc-500 text-xs mt-20">
      <div className="max-w-6xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <CountrydleLogo size={20} />
          </div>
          <div className="space-y-0.5 text-center md:text-left">
            <div className="text-zinc-300 font-bold tracking-tight text-sm">Countrydle</div>
            <div className="text-xs text-zinc-400">A new puzzle every day · 00:00 UTC</div>
          </div>
        </div>

        <div className="flex flex-wrap justify-center items-center gap-x-5 gap-y-2 text-zinc-400 font-medium">
          <Link to="/about" className="hover:text-white transition-colors">{t('footer.about', 'About')}</Link>
          <Link to="/faq" className="hover:text-white transition-colors">{t('footer.faq', 'FAQ')}</Link>
          <Link to="/blog" className="hover:text-white transition-colors">{t('footer.blog', 'Blog')}</Link>
          <Link to="/contact" className="hover:text-white transition-colors">{t('footer.contact', 'Contact')}</Link>
          <span className="text-zinc-800 hidden sm:inline">•</span>
          <Link to="/privacy-policy" className="hover:text-zinc-300 transition-colors text-zinc-500 text-[11px]">{t('footer.privacyPolicy')}</Link>
          <Link to="/terms" className="hover:text-zinc-300 transition-colors text-zinc-500 text-[11px]">{t('footer.termsOfService')}</Link>
          <Link to="/cookie-policy" className="hover:text-zinc-300 transition-colors text-zinc-500 text-[11px]">{t('footer.cookiePolicy')}</Link>
          <PrivacySettingsButton className="hover:text-zinc-300 transition-colors text-zinc-500 text-[11px]" />
        </div>

        <div className="text-zinc-600 font-mono text-[11px]">
          &copy; {new Date().getFullYear()} Countrydle.
        </div>
      </div>
    </footer>
  );
}
