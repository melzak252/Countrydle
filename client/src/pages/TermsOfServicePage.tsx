import LegalDocument from '../components/LegalDocument';

export default function TermsOfServicePage() {
  const lastUpdated = "October 6, 2026";

  return (
    <LegalDocument title="Terms of Service" lastUpdated={lastUpdated}>
      <section>
        <h2>1. Acceptance of Terms</h2>
        <p>
          Countrydle is operated by Jakub Melzacki. By accessing or using the website, you agree to these Terms of Service. The <a href="/privacy-policy">Privacy Policy</a> explains how personal data is processed; accepting these terms or playing a game does not by itself give consent to optional advertising or tracking.
        </p>
      </section>

      <section>
        <h2>2. Accounts and Guest Play</h2>
        <p className="mb-4">
          You may play Countrydle as a guest. Creating an account is optional and allows you to sign in using an email address or Google Login. If you create an account, you agree to:
        </p>
        <ul>
          <li>Provide accurate, current, and complete information.</li>
          <li>Maintain the security of your login credentials.</li>
          <li>Notify us immediately of any unauthorized use of your account.</li>
          <li>We reserve the right to terminate accounts that violate these terms.</li>
        </ul>
      </section>

      <section>
        <h2>3. The Game and Fair Play</h2>
        <p className="mb-4">
          Countrydle is a game of skill and knowledge. To maintain a fun and fair environment for everyone, you agree:
        </p>
        <ul>
          <li>Not to use bots, scripts, or any automated tools to play the game.</li>
          <li>Not to exploit bugs or vulnerabilities in the game engine.</li>
          <li>Daily play is available in nine independent game modes, each with its own daily limit and reset at midnight UTC. Friend duels are separate player-versus-player games.</li>
          <li>Cheating or manipulation may result in immediate suspension or banning.</li>
        </ul>
        <h3 className="mt-6">AI interpretation, factual limitations and reports</h3>
        <p className="mb-4">
          Countrydle uses AI to interpret natural-language questions. Supported questions are evaluated against local facts;
          others may use an AI fallback with retrieved text or general knowledge. Interpretations, source facts and answers
          can be incorrect, incomplete or outdated. The game is for entertainment and learning, not an authoritative source
          for decisions requiring accurate geographic or legal information.
        </p>
        <p>
          Use the answer-report control where available, or the <a href="/contact">General Suggestion Box</a>, to report a
          questionable answer or data error. A report requests review; it does not automatically change a result or award
          points. In friend duels, players give the human answers. Private AI recommendations do not replace those answers
          or decide the duel.
        </p>
      </section>

      <section>
        <h2>4. Google Login and Third-Party Services</h2>
        <p>
          You may log in using your Google account. By doing so, you also agree to Google's terms and privacy policies. We do not store your Google password; authentication is handled securely by Google.
        </p>
      </section>

      <section>
        <h2>5. Advertisements</h2>
        <p>
          The website uses Google AdSense for advertising. Ad availability and personalization depend on applicable consent
          choices, region and provider settings. Advertising choices are separate from accepting these terms and from
          storage needed for login or requested gameplay. See the <a href="/cookie-policy">Cookie Policy</a> for browser
          storage and Privacy settings. Do not click advertisements to support the website or artificially increase ad
          views or clicks.
        </p>
      </section>

      <section>
        <h2>6. User Conduct</h2>
        <p>
          You agree to use the Website responsibly. Prohibited activities include harassment, attempting to access other
          users' accounts, transmitting malicious code, or engaging in illegal activities through our platform. Do not put
          passwords, sensitive information or other people's personal information in questions, display names or reports.
          Educational or classroom use does not remove the privacy and age considerations described in the
          {' '}<a href="/privacy-policy">Privacy Policy</a>.
        </p>
      </section>

      <section>
        <h2>7. Disclaimer of Warranties</h2>
        <p>
          The Website and Game are provided "as is" and "as available" without any warranties. We do not guarantee that the service will be uninterrupted or error-free.
        </p>
      </section>

      <section>
        <h2>8. Limitation of Liability</h2>
        <p>
          To the fullest extent permitted by law, Countrydle shall not be liable for any indirect, incidental, or consequential damages resulting from your use of the website or game.
        </p>
      </section>

      <section>
        <h2>9. Governing Law</h2>
        <p>
          These Terms shall be governed by and construed in accordance with the laws of Poland. Any disputes will be subject to the exclusive jurisdiction of the courts in Poland.
        </p>
      </section>

      <section>
        <h2>10. Contact Information</h2>
        <p>
          If you have any questions about these Terms, please contact us at:<br />
          Email: <strong>melzacki.jakub@gmail.com</strong>
        </p>
      </section>
    </LegalDocument>
  );
}
