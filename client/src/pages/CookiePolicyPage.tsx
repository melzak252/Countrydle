import LegalDocument from '../components/LegalDocument';
import { PrivacySettingsButton } from '../components/PrivacySettingsButton';

export default function CookiePolicyPage() {
  const lastUpdated = "September 26, 2026";

  return (
    <LegalDocument title="Cookie Policy" lastUpdated={lastUpdated}>
      <section>
        <h2>1. What Are Cookies?</h2>
        <p>
          Cookies are small text files placed on your device to help the website function properly, analyze usage, and provide a personalized experience. They can be "session" cookies (deleted when you close your browser) or "persistent" cookies (remain until they expire or are deleted).
        </p>
      </section>

      <section>
        <h2>2. How We Use Cookies</h2>
        <p className="mb-4">We use cookies for the following purposes:</p>
        <div className="space-y-4">
          <div>
            <h3>a. Strictly Necessary Cookies</h3>
            <p>Essential for the website to function, such as maintaining your login session and security.</p>
          </div>
          <div>
            <h3>b. Analytics Cookies</h3>
            <p>Help us understand how visitors interact with the website, allowing us to improve performance and user experience.</p>
          </div>
          <div>
            <h3>c. Advertising Cookies (Google AdSense)</h3>
            <p>Google AdSense may use cookies or similar technologies for advertising, including personalized advertising, according to your choices and applicable settings. Advertising choices are managed separately from essential cookies needed for the website to function.</p>
          </div>
        </div>
      </section>

      <section>
        <h2>3. Third-Party Cookies</h2>
        <p>
          Google provides a consent message through its certified consent management platform (CMP) where a message applies. Google and other third parties may use cookies or similar technologies according to the choices made there and applicable settings.
        </p>
      </section>

      <section>
        <h2>4. Managing Cookies and Advertising Choices</h2>
        <p className="mb-4">
          You can use Privacy settings to reopen Google’s consent message and review or change your advertising choices when those settings are available:
        </p>
        <div className="mb-4">
          <PrivacySettingsButton className="min-h-11 rounded-sm border border-emerald-400/40 bg-emerald-400/10 px-4 py-2 text-sm font-medium text-emerald-300 hover:bg-emerald-400/15 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400" />
        </div>
        <p className="mb-4">
          If no consent message applies, there may be no message to display. If Google’s consent services are unavailable, the button reports that settings cannot be opened; it does not save or change an advertising choice. You can also block or delete cookies through your browser, though doing so may prevent login or other features from working. Browser cookie controls are separate from the Privacy settings for your advertising choices.
        </p>
      </section>

      <section>
        <h2>5. Contact Us</h2>
        <p>
          Email: <strong className="break-words">melzacki.jakub@gmail.com</strong>
        </p>
      </section>
    </LegalDocument>
  );
}
