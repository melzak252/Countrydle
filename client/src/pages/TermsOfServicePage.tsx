import LegalDocument from '../components/LegalDocument';

export default function TermsOfServicePage() {
  const lastUpdated = "September 26, 2026";

  return (
    <LegalDocument title="Terms of Service" lastUpdated={lastUpdated}>
      <section>
        <h2>1. Acceptance of Terms</h2>
        <p>
          By accessing or using the Countrydle website, you agree to comply with and be bound by these Terms of Service and our Privacy Policy. If you do not agree to these terms, please do not use our services.
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
          Our website displays advertisements served by Google AdSense. Advertising choices, including whether personalized advertising is allowed, are handled separately through the Google-certified consent message and its Privacy settings. Essential cookies needed for site functionality are distinct from optional advertising cookies.
        </p>
      </section>

      <section>
        <h2>6. User Conduct</h2>
        <p>
          You agree to use the Website responsibly. Prohibited activities include harassment, attempting to access other users' accounts, transmitting malicious code, or engaging in any illegal activities through our platform.
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
