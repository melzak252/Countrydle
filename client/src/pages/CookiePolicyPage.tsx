import LegalDocument from '../components/LegalDocument';
import { PrivacySettingsButton } from '../components/PrivacySettingsButton';

export default function CookiePolicyPage() {
  const lastUpdated = "October 9, 2026";

  return (
    <LegalDocument title="Cookie Policy" lastUpdated={lastUpdated}>
      <section>
        <h2>1. Cookies and Browser Storage</h2>
        <p>
          Cookies are small values your browser sends with requests to a website. Countrydle also uses localStorage,
          which keeps data in your browser between visits but does not automatically send it with every request.
          This policy covers both. Clearing cookies alone may not clear localStorage; use your browser's site-data
          controls to remove both.
        </p>
      </section>

      <section>
        <h2>2. Storage Used by Countrydle</h2>
        <p className="mb-4">
          These first-party values support login, requested gameplay and interface preferences. Cookie lifetimes
          describe browser access, not how long related server records are retained. Browser settings can remove
          values earlier; the <a href="/privacy-policy">Privacy Policy</a> explains server-side processing.
        </p>
        <ul>
          <li>
            <strong>Login — <code>access_token</code> cookie:</strong> keeps you signed in. The default lifetime is
            60 minutes, or 90 days if you select Remember me. These durations are configurable, and authenticated
            requests can renew the selected lifetime. Logging out clears the login cookie on that browser.
          </li>
          <li>
            <strong>Guest gameplay — <code>guest_identity</code> and game-state cookies:</strong> a pseudonymous
            identifier associates accepted guest activity with server records; mode-specific cookies such as
            <code> guest_countrydle</code> and <code>guest_flagdle</code> preserve guest game state. These cookies
            have a two-day lifetime and may be set again during play.
          </li>
          <li>
            <strong>Friend duels — <code>friend_duel_seat</code> cookie:</strong> preserves access to your guest
            seats for up to 365 days. Removing it can prevent you from returning to those seats.
          </li>
          <li>
            <strong>Daily guest progress — <code>guess_game_*</code> in localStorage:</strong> saves progress,
            questions and guesses by game mode and date. Supported guest progress is sent to your account when
            you sign in, and successfully synced snapshots are removed. Failed syncs retain the local snapshot.
          </li>
          <li>
            <strong>Guest result history — <code>countrydle_guest_result_v1_*</code> in localStorage:</strong> saves
            completed-game summaries used for your local history and statistics. These summaries have no automatic
            expiry; a limited history display does not mean older records have been deleted.
          </li>
          <li>
            <strong>Account display and interface state in localStorage:</strong> <code>user</code> caches account
            display information, not the login token, and is removed on logout or an expired-session response.
            <code> session_expired</code> supports the login notice and is removed when that notice is read.
            <code> countrydle_guide_seen</code> and <code>flagdle_guide_seen</code> remember dismissed instructions.
          </li>
        </ul>
        <p className="mt-4">
          Local guest progress and instruction preferences have no general time-based expiry. They remain until
          removed by the applicable sync or account flow, by you, or by your browser. Clearing browser data does
          not delete records already stored on the server.
        </p>
      </section>

      <section>
        <h2>3. Analytics, Advertising and External Services</h2>
        <p className="mb-4">
          Countrydle can load optional Rybbit analytics to measure visits and navigation when its deployment
          settings are enabled independently of advertising inventory. It is a separate analytics service,
          not an AdSense unit.
          The external script and its configuration determine collection and storage behavior; this policy
          does not assume that analytics necessarily uses cookies. Optional analytics and advertising are not
          loaded during static page capture. Analytics is distinct from storage needed for your game or login.
        </p>
        <p className="mb-4">
          Google AdSense advertising is optional and disabled by default. The deployment must explicitly set
          <code> VITE_ADSENSE_ENABLED=true</code> with a matching publisher and valid ad-unit inventory before advertising can run. Even then,
          ads require an eligible content page and a determinate permission state from the configured Google
          Funding Choices / Privacy &amp; Messaging consent service. Missing configuration, unknown or rejected
          consent, or consent-service failure does not authorize ad requests. Ads do not run on gameplay or result
          screens, account or administrative screens, contact or legal pages, or loading, error or unknown screens;
          blog ads require actual editorial review.
          Regional non-applicability must be explicitly reported by the consent service, not inferred from the
          absence of a message.
        </p>
        <p className="mb-4">
          When these conditions are met, Google and its advertising partners may use cookies or similar
          technologies to deliver and measure ads, including personalized ads according to applicable choices
          and settings. We do not set a single first-party lifetime for Google's or its partners' storage.
        </p>
        <p>
          Google's messages, where available, provide information about advertising purposes and partners.
          See <a href="https://policies.google.com/technologies/cookies" target="_blank" rel="noopener noreferrer">Google's cookie information</a>
          {' '}and <a href="https://policies.google.com/technologies/partner-sites" target="_blank" rel="noopener noreferrer">how Google uses information from partner sites</a>.
        </p>
      </section>

      <section>
        <h2>4. Managing Cookies and Advertising Choices</h2>
        <p className="mb-4">
          Privacy settings reopen the existing Google Funding Choices / Privacy &amp; Messaging consent service
          so you can review, reject or withdraw your optional advertising choices when those settings are available:
        </p>
        <div className="mb-4">
          <PrivacySettingsButton className="min-h-11 rounded-sm border border-emerald-400/40 bg-emerald-400/10 px-4 py-2 text-sm font-medium text-emerald-300 hover:bg-emerald-400/15 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400" />
        </div>
        <p className="mb-4">
          Rejecting or withdrawing optional advertising consent stops advertising requests; active advertising is
          cleared by reloading the page when permission is withdrawn. This does not delete necessary game or login
          cookies, your saved progress, or server records. Playing, creating an account or accepting the Terms of
          Service is not consent to optional advertising storage or tracking.
        </p>
        <p className="mb-4">
          Opening settings while ads are active first takes you to an ad-free Cookie Policy document.
          If no consent message applies, there may be no message to display. If Google's consent services are
          unavailable, the button reports that settings cannot be opened and the settings document remains ad-free.
          It does not save or change an advertising choice. A failed request to open settings is not consent.
          Contact us if you cannot access your choices. Browser controls can block or remove cookies and localStorage, but may also remove
          progress or prevent login and other features from working. Those controls are separate from Google's
          advertising choices; deleting browser data is not a request to erase server records.
        </p>
      </section>

      <section>
        <h2>5. Contact Us</h2>
        <p>
          Countrydle is operated by Jakub Melzacki. For storage or privacy questions, email
          {' '}<a href="mailto:melzacki.jakub@gmail.com">melzacki.jakub@gmail.com</a>.
        </p>
      </section>
    </LegalDocument>
  );
}
