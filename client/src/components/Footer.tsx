import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

export default function Footer() {
  const { t } = useTranslation();

  return (
    <footer className="bg-zinc-900 border-t border-zinc-800 py-6 text-center text-zinc-500 text-sm">
      <p>&copy; {new Date().getFullYear()} Countrydle. {t('footer.rights')}</p>
      <div className="mt-2 flex flex-wrap justify-center gap-x-6 gap-y-2 text-xs md:text-sm">
        <Link to="/about" className="hover:text-zinc-300 transition-colors">{t('footer.about', 'About')}</Link>
        <Link to="/faq" className="hover:text-zinc-300 transition-colors">{t('footer.faq', 'FAQ')}</Link>
        <Link to="/contact" className="hover:text-zinc-300 transition-colors">{t('footer.contact', 'Contact')}</Link>
        <span className="text-zinc-700 hidden sm:inline">•</span>
        <Link to="/privacy-policy" className="hover:text-zinc-300 transition-colors">{t('footer.privacyPolicy')}</Link>
        <Link to="/terms" className="hover:text-zinc-300 transition-colors">{t('footer.termsOfService')}</Link>
        <Link to="/cookie-policy" className="hover:text-zinc-300 transition-colors">{t('footer.cookiePolicy')}</Link>
      </div>
    </footer>
  );
}
