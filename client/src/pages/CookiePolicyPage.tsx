import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';

export default function CookiePolicyPage() {
  const { i18n } = useTranslation();
  const isPolish = (i18n.resolvedLanguage ?? i18n.language) === 'pl';

  const content = isPolish
    ? {
        title: 'Polityka Cookies',
        lastUpdatedLabel: 'Ostatnia aktualizacja',
        lastUpdated: '15 lutego 2026',
        sections: [
          {
            heading: '1. Czym sa cookies?',
            body: 'Cookies to male pliki zapisywane na urzadzeniu. Pomagaja w dzialaniu serwisu, analizie ruchu i personalizacji doswiadczenia.',
          },
          {
            heading: '2. Jak wykorzystujemy cookies',
            body: 'Uzywamy cookies do kluczowych funkcji serwisu oraz analityki i reklam.',
            list: [
              'Niezbedne cookies: utrzymanie sesji logowania i bezpieczenstwa.',
              'Analityczne cookies: lepsze zrozumienie zachowan uzytkownikow i poprawa jakosci.',
              'Reklamowe cookies (Google AdSense): dopasowanie reklam na podstawie aktywnosci.',
            ],
          },
          {
            heading: '3. Cookies podmiotow trzecich',
            body: 'Poza naszymi cookies korzystamy z cookies Google (logowanie i AdSense). Podmioty trzecie maja wlasne polityki prywatnosci i cookies.',
          },
          {
            heading: '4. Zarzadzanie cookies',
            body: 'Wiekszosc przegladarek pozwala zarzadzac cookies. Ograniczenie cookies moze wplynac na logowanie i dostepnosc funkcji.',
            list: [
              'Ustawienia reklam Google: https://www.google.com/settings/ads',
              'Zarzadzanie cookies partnerow: https://www.aboutads.info',
            ],
          },
          {
            heading: '5. Kontakt',
            body: 'W razie pytan o cookies skontaktuj sie z nami:',
            footer: 'Email: support@jmelzacki.com',
          },
        ],
      }
    : {
        title: 'Cookie Policy',
        lastUpdatedLabel: 'Last updated',
        lastUpdated: 'February 15, 2026',
        sections: [
          {
            heading: '1. What Are Cookies?',
            body: 'Cookies are small files stored on your device. They help the website function, analyze traffic, and provide personalized experiences.',
          },
          {
            heading: '2. How We Use Cookies',
            body: 'We use cookies for core site functionality, analytics, and advertising.',
            list: [
              'Strictly necessary cookies: maintain login sessions and security.',
              'Analytics cookies: help us understand usage and improve quality.',
              'Advertising cookies (Google AdSense): help personalize ad delivery.',
            ],
          },
          {
            heading: '3. Third-Party Cookies',
            body: 'In addition to our own cookies, we use cookies from Google (Login and AdSense). Third parties operate under their own privacy and cookie policies.',
          },
          {
            heading: '4. Managing Cookies',
            body: 'Most browsers let you manage cookies. Restricting cookies may impact login and some features.',
            list: [
              'Google ad controls: https://www.google.com/settings/ads',
              'Third-party cookie controls: https://www.aboutads.info',
            ],
          },
          {
            heading: '5. Contact Us',
            body: 'If you have questions about cookies, contact us at:',
            footer: 'Email: support@jmelzacki.com',
          },
        ],
      };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="space-y-6"
      >
        <h1 className="text-4xl font-bold mb-8 text-center bg-clip-text text-transparent bg-gradient-to-r from-green-400 to-blue-500">
          {content.title}
        </h1>

        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-8 shadow-xl">
          <p className="mb-6 text-zinc-400 italic text-sm text-right">
            {content.lastUpdatedLabel}: {content.lastUpdated}
          </p>

          {content.sections.map((section, index) => (
            <section
              key={section.heading}
              className={index === content.sections.length - 1 ? 'mb-8 border-t border-zinc-800 pt-8' : 'mb-8'}
            >
              <h2 className="text-2xl font-semibold mb-4 text-white">{section.heading}</h2>
              <p className="text-zinc-300 leading-relaxed">{section.body}</p>
              {section.list && (
                <ul className="list-disc list-inside text-zinc-300 space-y-2 ml-4 mt-4">
                  {section.list.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
              {section.footer && (
                <p className="text-zinc-300 leading-relaxed mt-2">
                  <strong>{section.footer}</strong>
                </p>
              )}
            </section>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
