import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';

export default function PrivacyPolicyPage() {
  const { i18n } = useTranslation();
  const isPolish = (i18n.resolvedLanguage ?? i18n.language) === 'pl';

  const content = isPolish
    ? {
        title: 'Polityka Prywatnosci',
        lastUpdatedLabel: 'Ostatnia aktualizacja',
        lastUpdated: '15 lutego 2026',
        sections: [
          {
            heading: '1. Wprowadzenie',
            body: 'W Countrydle traktujemy prywatnosc powaznie. Ten dokument wyjasnia, jakie dane zbieramy, jak je wykorzystujemy i komu je udostepniamy.',
          },
          {
            heading: '2. Jakie dane zbieramy',
            body: 'Podczas rejestracji i korzystania z serwisu mozemy zbierac dane osobowe i techniczne.',
            list: [
              'adres e-mail i podstawowe dane konta (w tym dane Google Login),',
              'adres IP, typ przegladarki i system operacyjny,',
              'aktywnosc w grze (wyniki, liczba rozegranych gier, historia).',
            ],
          },
          {
            heading: '3. Cookies i podobne technologie',
            body: 'Uzywamy cookies do utrzymania sesji logowania, poprawy dzialania serwisu oraz analizy ruchu.',
          },
          {
            heading: '4. Google AdSense i reklamy',
            body: 'Korzystamy z Google AdSense. Google i partnerzy moga uzywac cookies do personalizacji reklam.',
            list: [
              'Ustawienia reklam Google: https://www.google.com/settings/ads',
              'Informacje o rezygnacji z reklam behawioralnych: https://www.aboutads.info',
            ],
            highlighted: true,
          },
          {
            heading: '5. Jak wykorzystujemy dane',
            body: 'Dane wykorzystujemy do obslugi konta, dzialania gry, analizy jakosci uslugi oraz rozwijania nowych funkcji.',
          },
          {
            heading: '6. Udostepnianie danych',
            body: 'Nie sprzedajemy danych osobowych. Dane moga byc udostepniane zaufanym dostawcom uslug (hosting, analityka), Google (logowanie/reklamy) oraz organom, gdy wymagaja tego przepisy.',
          },
          {
            heading: '7. Retencja i prawa uzytkownika',
            body: 'Przechowujemy dane tak dlugo, jak konto jest aktywne. Masz prawo dostepu, sprostowania i usuniecia danych. W UE przysluguja Ci prawa wynikajace z RODO.',
          },
          {
            heading: '8. Bezpieczenstwo',
            body: 'Stosujemy standardowe srodki bezpieczenstwa, ale zadna metoda przesylania i przechowywania danych nie daje 100% gwarancji.',
          },
          {
            heading: '9. Prywatnosc dzieci',
            body: 'Serwis nie jest przeznaczony dla dzieci ponizej 13 lat. W przypadku wykrycia takich danych usuwamy je niezwlocznie.',
          },
          {
            heading: '10. Kontakt',
            body: 'W pytaniach dotyczacych prywatnosci napisz do nas:',
            footer: 'Email: support@jmelzacki.com lub melzacki.jakub@gmail.com',
          },
        ],
      }
    : {
        title: 'Privacy Policy',
        lastUpdatedLabel: 'Last updated',
        lastUpdated: 'February 15, 2026',
        sections: [
          {
            heading: '1. Introduction',
            body: 'At Countrydle, we take privacy seriously. This policy explains what data we collect, how we use it, and when we share it.',
          },
          {
            heading: '2. Information We Collect',
            body: 'When you register and use the service, we may collect personal and technical data.',
            list: [
              'email address and account details (including Google Login data),',
              'IP address, browser type, and operating system,',
              'game activity (scores, played games, and history).',
            ],
          },
          {
            heading: '3. Cookies and Similar Technologies',
            body: 'We use cookies to keep your session active, improve service performance, and analyze traffic.',
          },
          {
            heading: '4. Google AdSense and Advertising',
            body: 'We use Google AdSense. Google and partners may use cookies for ad personalization.',
            list: [
              'Google Ads settings: https://www.google.com/settings/ads',
              'Ad choice and opt-out info: https://www.aboutads.info',
            ],
            highlighted: true,
          },
          {
            heading: '5. How We Use Your Data',
            body: 'We use data for account management, game functionality, service quality analysis, and feature development.',
          },
          {
            heading: '6. Sharing Information',
            body: 'We do not sell personal data. We may share data with trusted service providers (hosting/analytics), Google (login/ads), or authorities where legally required.',
          },
          {
            heading: '7. Retention and User Rights',
            body: 'We retain data while your account is active. You may request access, correction, or deletion. If you are in the EU, GDPR rights also apply.',
          },
          {
            heading: '8. Security',
            body: 'We apply industry-standard safeguards, but no data transmission or storage method is fully secure.',
          },
          {
            heading: '9. Children\'s Privacy',
            body: 'The service is not intended for children under 13. If such data is discovered, it will be removed promptly.',
          },
          {
            heading: '10. Contact Us',
            body: 'For privacy-related questions, contact us at:',
            footer: 'Email: support@jmelzacki.com or melzacki.jakub@gmail.com',
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
              className={section.highlighted
                ? 'mb-8 border-l-4 border-blue-500 pl-6 py-2 bg-blue-500/5 rounded-r-lg'
                : index === content.sections.length - 1
                  ? 'mb-8 border-t border-zinc-800 pt-8'
                  : 'mb-8'}
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
