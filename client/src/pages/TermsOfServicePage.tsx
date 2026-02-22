import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';

export default function TermsOfServicePage() {
  const { i18n } = useTranslation();
  const isPolish = (i18n.resolvedLanguage ?? i18n.language) === 'pl';

  const content = isPolish
    ? {
        title: 'Regulamin',
        lastUpdatedLabel: 'Ostatnia aktualizacja',
        lastUpdated: '15 lutego 2026',
        sections: [
          {
            heading: '1. Akceptacja warunkow',
            body: 'Korzystajac z Countrydle, akceptujesz niniejszy Regulamin oraz Polityke Prywatnosci. Jezeli nie akceptujesz warunkow, nie korzystaj z serwisu.',
          },
          {
            heading: '2. Rejestracja konta',
            body: 'Aby brac udzial w grze, nalezy zalozyc konto przez e-mail lub logowanie Google. Rejestrujac sie, zgadzasz sie na:',
            list: [
              'podawanie prawdziwych i aktualnych danych,',
              'ochrone danych logowania,',
              'niezwloczne zgloszenie nieautoryzowanego dostepu,',
              'mozliwosc zablokowania konta przy naruszeniu regulaminu.',
            ],
          },
          {
            heading: '3. Gra i fair play',
            body: 'Countrydle to gra wiedzy i umiejetnosci. Dla uczciwej rozgrywki zobowiazujesz sie:',
            list: [
              'nie uzywac botow, skryptow ani automatyzacji,',
              'nie wykorzystywac bledow i luk aplikacji,',
              'grac zgodnie z zasadami trybu dziennego,',
              'zaakceptowac, ze oszustwa moga skutkowac blokada.',
            ],
          },
          {
            heading: '4. Logowanie Google i uslugi zewnetrzne',
            body: 'Mozesz logowac sie kontem Google. Korzystajac z tej opcji, akceptujesz takze warunki i polityki Google. Nie przechowujemy Twojego hasla Google.',
          },
          {
            heading: '5. Reklamy',
            body: 'W serwisie wyswietlane sa reklamy Google AdSense. Korzystanie z serwisu oznacza zgode na wykorzystanie cookie do personalizacji reklam zgodnie z Polityka Prywatnosci.',
            highlighted: true,
          },
          {
            heading: '6. Zachowanie uzytkownika',
            body: 'Zobowiazujesz sie korzystac z serwisu zgodnie z prawem i dobrymi praktykami. Zabronione sa m.in. proby przejecia kont, malware i naduzycia.',
          },
          {
            heading: '7. Wylaczenie odpowiedzialnosci gwarancyjnej',
            body: 'Serwis i gra sa udostepniane w stanie "tak jak jest" bez gwarancji ciaglosci i bezblednosci dzialania.',
          },
          {
            heading: '8. Ograniczenie odpowiedzialnosci',
            body: 'W granicach prawa JMelzacki nie ponosi odpowiedzialnosci za szkody posrednie, uboczne lub wynikowe zwiazane z korzystaniem z serwisu.',
          },
          {
            heading: '9. Prawo wlasciwe',
            body: 'Regulamin podlega prawu polskiemu, a ewentualne spory beda rozstrzygane przez sady w Polsce.',
          },
          {
            heading: '10. Kontakt',
            body: 'W sprawach dotyczacych Regulaminu skontaktuj sie z nami:',
            footer: 'Email: support@jmelzacki.com',
          },
        ],
      }
    : {
        title: 'Terms of Service',
        lastUpdatedLabel: 'Last updated',
        lastUpdated: 'February 15, 2026',
        sections: [
          {
            heading: '1. Acceptance of Terms',
            body: 'By using Countrydle, you agree to these Terms of Service and our Privacy Policy. If you do not agree, please do not use the service.',
          },
          {
            heading: '2. Account Registration',
            body: 'To play the game, users must create an account via email or Google Login. By registering, you agree to:',
            list: [
              'provide accurate and up-to-date information,',
              'protect your login credentials,',
              'notify us about unauthorized account use,',
              'accept that violating these terms may result in account suspension.',
            ],
          },
          {
            heading: '3. The Game and Fair Play',
            body: 'Countrydle is a game of skill and knowledge. To keep the game fair, you agree to:',
            list: [
              'not use bots, scripts, or automation tools,',
              'not exploit bugs or vulnerabilities,',
              'play according to daily game rules,',
              'accept that cheating can result in immediate suspension.',
            ],
          },
          {
            heading: '4. Google Login and Third-Party Services',
            body: 'You may sign in using Google. By doing so, you also agree to Google terms and policies. We do not store your Google password.',
          },
          {
            heading: '5. Advertisements',
            body: 'The website displays Google AdSense ads. By using the site, you acknowledge that cookies may be used for ad personalization as described in our Privacy Policy.',
            highlighted: true,
          },
          {
            heading: '6. User Conduct',
            body: 'You agree to use the website responsibly. Prohibited behavior includes harassment, account abuse attempts, malware distribution, or illegal activity.',
          },
          {
            heading: '7. Disclaimer of Warranties',
            body: 'The website and game are provided "as is" and "as available" without warranties of uninterrupted or error-free operation.',
          },
          {
            heading: '8. Limitation of Liability',
            body: 'To the fullest extent allowed by law, JMelzacki is not liable for indirect, incidental, or consequential damages related to using the service.',
          },
          {
            heading: '9. Governing Law',
            body: 'These Terms are governed by the laws of Poland, and disputes are subject to Polish courts.',
          },
          {
            heading: '10. Contact Information',
            body: 'If you have questions about these Terms, contact us at:',
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
              className={section.highlighted
                ? 'mb-8 border-l-4 border-yellow-500 pl-6 py-2 bg-yellow-500/5 rounded-r-lg'
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
