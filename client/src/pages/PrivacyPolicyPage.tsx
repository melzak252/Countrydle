import LegalDocument from '../components/LegalDocument';

export default function PrivacyPolicyPage() {
  const lastUpdated = "October 6, 2026";

  return (
    <LegalDocument title="Privacy Policy" lastUpdated={lastUpdated}>
          <section>
            <h2 className="mb-4">1. Introduction</h2>
            <p>
              Countrydle is operated by <strong>Jakub Melzacki</strong>, the controller responsible for the personal data
              described here. Contact <a href="mailto:melzacki.jakub@gmail.com">melzacki.jakub@gmail.com</a> about privacy
              or your rights. This policy explains processing when you visit Countrydle, play daily games or friend
              duels, create an account or send feedback. Playing or accepting our terms is not consent to optional
              advertising or tracking.
            </p>
          </section>

          <section>
            <h2 className="mb-4">2. Information We Collect</h2>
            <div className="space-y-4">
              <div>
                <h3>a. Personal Information</h3>
                <p>When you register on our Website or log in using Google, we collect the following personal information:</p>
                <ul className="mt-2">
                  <li><strong>Email Address:</strong> Used to create and manage your account.</li>
                  <li><strong>Account Details:</strong> Your username, a password hash for password-based accounts, verification status, account dates and saved game statistics. We do not receive your Google password.</li>
                  <li><strong>Google Profile Information:</strong> If you log in using Google, we may access your Google account’s basic information, such as your email address and name.</li>
                </ul>
              </div>
              
              <div>
                <h3>b. Technical Data and Gameplay</h3>
                <p>
                  Technical data can include IP addresses, browser and device information, request times and errors.
                  Gameplay records include questions, answers and explanations, guesses, results, points and timestamps.
                  IP addresses, account identifiers and pseudonymous browser identifiers can be personal data; they are
                  not automatically anonymous just because they do not contain your name.
                </p>
                <p className="mt-2">
                  Guest daily progress is saved in your browser, but accepted guest activity is also recorded on our
                  server using a short-lived pseudonymous identifier. Signing in can sync guest progress and link
                  associated participation to your account. Authorized administrators can review gameplay and answer
                  reports to investigate errors and improve the game.
                </p>
              </div>

              <div>
                <h3>c. Cookies and Similar Technologies</h3>
                <p>
                  Login cookies, guest gameplay cookies and localStorage support your account and progress. Browser
                  storage has different lifetimes from server records. See the <a href="/cookie-policy">Cookie Policy</a>
                  {' '}for names, purposes, lifetimes and controls. Clearing browser data does not erase server records.
                </p>
              </div>
              <div>
                <h3>d. Friend Duels</h3>
                <p>
                  Friend duels store display names, chosen locations, questions, guesses, human answers and their revisions,
                  AI recommendations and explanations, timing and available evidence, and submitted reports. We retain
                  agreements as well as disagreements to verify and improve question answering. Avoid including personal
                  or sensitive information in questions, names or reports.
                </p>
                <p className="mt-2">
                  Your opponent sees your human answers, not your private AI advice or reports. Secret locations are revealed
                  when the duel ends. Authorized administrators can review completed-game evidence. A necessary HttpOnly
                  browser cookie preserves your guest seats for up to one year; clearing it can remove your access to them.
                </p>
              </div>
              <div>
                <h3>e. Player Suggestions</h3>
                <p>
                  When you use the General Suggestion Box, we store your selected topic, message, submission time,
                  and any name or email address you choose to provide. If you are signed in, the submission is
                  linked to your account. You can also submit as a guest without providing contact details.
                  Suggestions are available only to authorized administrators, who use them to review feedback,
                  improve Countrydle, and contact you about your suggestion when you provide an email address.
                  Do not include passwords or sensitive personal information.
                </p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="mb-4">3. Google AdSense, Cookies, and Advertising</h2>
            <p className="mb-4">
              Countrydle uses <strong>Google AdSense</strong>. Google and its advertising partners may process device
              information, identifiers and ad interactions to deliver and measure advertisements. Personalization and
              available choices depend on the applicable region, consent choices and provider settings.
            </p>
            <ul className="mb-4">
              <li>
                <strong>Advertising technologies:</strong> Google and its partners may use cookies or similar technologies
                to serve ads based on visits to this or other websites, subject to applicable choices and settings.
              </li>
              <li>
                <strong>Provider information:</strong> See <a href="https://policies.google.com/technologies/partner-sites" target="_blank" rel="noopener noreferrer">how Google uses information from partner sites</a> for its advertising and measurement practices.
              </li>
              <li>
                <strong>Opting out of personalized advertising:</strong> Users may opt out of personalized advertising at any time by visiting <a href="https://www.google.com/settings/ads" target="_blank" rel="noopener noreferrer">Google Ads Settings</a>. Alternatively, users can opt out of a third-party vendor's use of cookies for personalized advertising by visiting <a href="https://www.aboutads.info" target="_blank" rel="noopener noreferrer">www.aboutads.info</a>.
              </li>
              <li>
                <strong>Privacy settings:</strong> We provide a button in the footer and Cookie Policy to reopen Google's
                consent message when available. Messages and choices depend on Google's published configuration and
                regional rules. If the service is unavailable, the button reports a failure without changing choices;
                that failure is not consent. Contact us if you cannot access your choices.
              </li>
            </ul>
            <p>
              Storage needed for login or requested gameplay is distinct from optional advertising technologies. Where
              consent is required for optional storage or personalized advertising, it must be obtained separately
              from agreement to the Terms of Service.
            </p>
          </section>

          <section>
            <h2 className="mb-4">4. Purposes and Legal Bases</h2>
            <p className="mb-4">Where the GDPR applies, we rely on the following grounds, depending on the processing:</p>
            <ul>
              <li><strong>Providing the service:</strong> Processing needed to create and authenticate your account,
                preserve requested gameplay, sync progress and provide results is necessary to perform our agreement
                with you.</li>
              <li><strong>Security and quality:</strong> Preventing abuse, diagnosing failures, reviewing disputed
                answers, handling feedback and understanding aggregate usage serve our legitimate interests in
                operating and improving a reliable, fair game, subject to your rights and interests.</li>
              <li><strong>Optional advertising and storage:</strong> Consent where required by applicable law. You may
                withdraw consent without affecting the lawfulness of processing before withdrawal.</li>
              <li><strong>Legal obligations:</strong> Processing necessary to meet applicable legal duties and respond
                to valid legal requests.</li>
            </ul>
            <p className="mt-3">
              Rybbit analytics may be enabled to measure visits and navigation and understand site usage. It is separate
              from gameplay records; its deployed configuration determines collection and storage behavior. Aggregate
              AI-cost measurements record request counts and token usage rather than player identities or question text.
              Do not include sensitive or unnecessary personal information in questions or feedback.
            </p>
          </section>

          <section>
            <h2 className="mb-4">5. Recipients, AI Processing and International Transfers</h2>
            <p className="mb-4">
              Data is processed by the services needed to run Countrydle: hosting and database infrastructure,
              the configured email service for account messages, Google for sign-in and advertising, and Rybbit
              analytics when enabled. Authorized administrators can access relevant records for support and review.
              Account usernames, scores and public profile statistics can be seen by other visitors; choose a username
              you are comfortable making public. We may disclose information when legally required.
            </p>
            <ul className="mb-4">
              <li><strong>Google Gemini:</strong> Daily-game questions may be sent for interpretation and fallback
                answering, with relevant location facts or retrieved text. Friend-duel questions and relevant
                location facts may also be sent for private AI recommendations. Supported plans can be evaluated
                locally instead of requiring a generated answer.</li>
              <li><strong>OpenAI:</strong> When vector retrieval is used, question text is sent to OpenAI to generate
                a numerical representation (an embedding) for searching relevant facts.</li>
              <li><strong>Question content:</strong> These question-processing requests do not deliberately add your
                account email, username or guest identifier. However, personal information you type into a question
                can still reach a provider. Do not include it unnecessarily.</li>
              <li><strong>Saved interpretations:</strong> We retain question-derived text and generated plans in a
                shared planner cache to reuse interpretations. Other players can benefit from cached answers;
                this is not a promise that submitted text is anonymous or immediately deleted.</li>
            </ul>
            <p className="mb-4">
              Friend-duel AI recommendations remain private to the location owner and authorized reviewers; they do
              not replace the human player's answer or decide the duel. Provider handling of requests is subject
              to the service and account terms in use; we do not promise zero provider retention or that all inputs
              are excluded from provider model improvement.
            </p>
            <p>
              External providers may process information outside your country, including in the United States,
              where data-protection rules can differ. See <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">Google's Privacy Policy</a>
              {' '}and <a href="https://openai.com/policies/privacy-policy/" target="_blank" rel="noopener noreferrer">OpenAI's Privacy Policy</a>
              {' '}for their practices. Contact us for information about recipients and the applicable transfer
              arrangements or safeguards for Countrydle's processing.
            </p>
          </section>

          <section>
            <h2 className="mb-4">6. Data Retention and Rights</h2>
            <p className="mb-4">
              Browser-cookie expiry is not a server-deletion schedule. Account data, daily game history and
              participation, daily answer reports, suggestions and the persistent planner cache currently have
              no general automatic time-based deletion. They can remain after inactivity or after you clear
              browser storage. Requests for access or deletion are handled through the contact address below,
              not a self-service account-deletion control.
            </p>
            <p className="mb-4">
              Completed friend-duel records are normally removed after 30 days. Reviewed or reported records are normally
              retained for 90 days after the latest completion, report or review. Unreviewed reports and pending or running
              AI work defer deletion until resolved; cleanup runs periodically. These limits are separate from account
              retention and the guest-seat cookie lifetime.
            </p>
            <p className="mb-4">
              The separate daily fallback-answer cache is normally cleared of prior-day entries at startup and
              during daily cleanup. This does not delete the original question, report or planner-cache record.
              Aggregate AI-cost counters have no automatic expiry and do not contain question text or player
              identifiers. Browser storage lifetimes are listed in the <a href="/cookie-policy">Cookie Policy</a>.
            </p>
            <p>
              Depending on applicable law, you may request access, correction, erasure, restriction or portability
              of your personal data, and object to processing based on legitimate interests. You can withdraw
              consent where processing relies on it. Contact <a href="mailto:melzacki.jakub@gmail.com">melzacki.jakub@gmail.com</a>;
              we may need information to verify your identity and locate the relevant records, especially for
              guest play. These rights are subject to legal conditions and exceptions. You may complain to your
              local data-protection authority, including Poland's <a href="https://uodo.gov.pl/" target="_blank" rel="noopener noreferrer">President of the Personal Data Protection Office (UODO)</a>.
            </p>
          </section>

          <section>
            <h2 className="mb-4">7. Security</h2>
            <p>
              We use measures such as password hashing and access controls for administrative records. No method of
              transmission or storage is completely secure. Do not share passwords or guest-seat credentials, and
              contact us if you believe your account or data has been compromised.
            </p>
          </section>

          <section>
            <h2 className="mb-4">8. Children's Privacy</h2>
            <p>
              Countrydle is not intended for children under 13. Its educational purpose and references to classroom
              use do not remove this restriction or applicable requirements for children's data. Teachers and
              guardians should consider age suitability and avoid submitting children's personal information.
              If you believe we have collected personal information from a child under 13, contact us so we can
              investigate and take appropriate steps, including deletion where required. An age statement alone
              does not replace protections required by applicable law.
            </p>
          </section>

          <section>
            <h2 className="mb-4">9. Contact Us</h2>
            <p>
              For privacy questions, complaints, or access, correction and deletion requests, contact:<br />
              <strong>Jakub Melzacki — Countrydle</strong><br />
              Email: <a href="mailto:melzacki.jakub@gmail.com">melzacki.jakub@gmail.com</a>
            </p>
          </section>
    </LegalDocument>
  );
}
