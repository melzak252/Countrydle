import LegalDocument from '../components/LegalDocument';

export default function PrivacyPolicyPage() {
  const lastUpdated = "October 1, 2026";

  return (
    <LegalDocument title="Privacy Policy" lastUpdated={lastUpdated}>
          <section>
            <h2 className="mb-4">1. Introduction</h2>
            <p>
              At Countrydle, we take your privacy seriously. This Privacy Policy explains how we collect, use, and share information when you visit <strong>Countrydle</strong> and play the game. It describes our information practices; using the Website or playing the Game does not by itself mean that you consent to optional advertising.
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
                  <li><strong>Google Profile Information:</strong> If you log in using Google, we may access your Google account’s basic information, such as your email address and name.</li>
                </ul>
              </div>
              
              <div>
                <h3>b. Non-Personal Information</h3>
                <p>We may collect non-personal information automatically when you use the Website, including:</p>
                <ul className="mt-2">
                  <li>IP Address</li>
                  <li>Browser type and version</li>
                  <li>Operating system</li>
                  <li>Game activity (e.g., how many times you have played, performance in the game)</li>
                </ul>
              </div>

              <div>
                <h3>c. Cookies and Similar Technologies</h3>
                <p>
                  We use cookies to enhance your experience on the Website and manage sessions. Cookies are small text files stored on your device that allow us to maintain your login session and analyze usage.
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
              We use <strong>Google AdSense</strong> to display advertisements to support our free educational platform. To comply with Google's Program Policies, we disclose the following regarding advertising cookies and tracking technologies:
            </p>
            <ul className="mb-4">
              <li>
                <strong>Third-party vendor cookies:</strong> Third party vendors, including Google, use cookies to serve ads based on a user's prior visits to our website or other websites across the Internet.
              </li>
              <li>
                <strong>Advertising cookies:</strong> Google's use of advertising cookies enables it and its partners to serve personalized advertisements to our users based on their visits to our site and/or other sites on the Internet.
              </li>
              <li>
                <strong>Opting out of personalized advertising:</strong> Users may opt out of personalized advertising at any time by visiting <a href="https://www.google.com/settings/ads" target="_blank" rel="noopener noreferrer">Google Ads Settings</a>. Alternatively, users can opt out of a third-party vendor's use of cookies for personalized advertising by visiting <a href="https://www.aboutads.info" target="_blank" rel="noopener noreferrer">www.aboutads.info</a>.
              </li>
              <li>
                <strong>Consent Management Platform (CMP):</strong> For visitors in the European Economic Area (EEA), United Kingdom (UK), and Switzerland, we implement a Google-certified Consent Management Platform (CMP) integrated with the IAB Transparency and Consent Framework (TCF v2.2) to collect and manage cookie consent preferences. You can adjust your consent choices at any time using the "Privacy Settings" button in our site footer.
              </li>
            </ul>
            <p>
              Essential cookies strictly necessary for core game mechanics (e.g. daily progress, streaks, local session preservation) operate independently from optional advertising cookies.
            </p>
          </section>

          <section>
            <h2 className="mb-4">4. How We Use Your Information</h2>
            <ul>
              <li><strong>Account Management:</strong> To create and manage your account, including authentication and login using Google.</li>
              <li><strong>Game Functionality:</strong> To enable you to play the game and keep track of your daily participation and guesses.</li>
              <li><strong>Improving the Website:</strong> To analyze usage and improve the performance of our website.</li>
              <li><strong>Communication:</strong> To send you notifications related to your account or the Game.</li>
              <li><strong>Internal Analysis:</strong> We may use anonymized data for internal purposes such as machine learning and research to improve game performance and develop new features.</li>
            </ul>
          </section>

          <section>
            <h2 className="mb-4">5. Sharing Your Information</h2>
            <p>
              We will not sell or rent your personal information to third parties. However, we may share your information with trusted service providers (such as hosting or analytics), with Google to facilitate login and ads, or if required by law.
            </p>
            <p className="mt-3">
              Friend-duel questions and the relevant location facts are processed by Google Gemini.
              Recommendations remain private to the location owner and authorized reviewers; they never replace
              the human player's answer or decide the duel.
            </p>
          </section>

          <section>
            <h2 className="mb-4">6. Data Retention and Rights</h2>
            <p className="mb-4">
              We retain your personal information for as long as your account is active. You have the right to access, rectify, or erase your data. 
            </p>
            <p className="mb-4">
              Completed friend-duel records are normally removed after 30 days. Reviewed or reported records are normally
              retained for 90 days after the latest completion, report or review. Unreviewed reports and pending or running
              AI work defer deletion until resolved; cleanup runs periodically. These limits are separate from account
              retention and the guest-seat cookie lifetime.
            </p>
            <p>
              If you are in the EU (GDPR jurisdiction), you have specific rights regarding data portability and withdrawing consent. To exercise these rights, please contact us at <strong>melzacki.jakub@gmail.com</strong>.
            </p>
          </section>

          <section>
            <h2 className="mb-4">7. Security</h2>
            <p>
              We use industry-standard measures to protect your information, including encryption. However, no method of transmission or storage is 100% secure.
            </p>
          </section>

          <section>
            <h2 className="mb-4">8. Children's Privacy</h2>
            <p>
              Our Website is not intended for children under 13. If we discover a child under 13 has provided personal information, we will delete it immediately.
            </p>
          </section>

          <section>
            <h2 className="mb-4">9. Contact Us</h2>
            <p>
              If you have any questions about this Privacy Policy, please contact us at:<br />
              Email: <strong>melzacki.jakub@gmail.com</strong>
            </p>
          </section>
    </LegalDocument>
  );
}
