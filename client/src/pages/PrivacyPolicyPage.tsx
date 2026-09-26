import { motion } from 'framer-motion';

export default function PrivacyPolicyPage() {
  const lastUpdated = "September 26, 2026";

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="space-y-6"
      >
        <h1 className="text-4xl font-bold mb-8 text-center bg-clip-text text-transparent bg-gradient-to-r from-green-400 to-blue-500">
          Privacy Policy
        </h1>
        
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-8 shadow-xl">
          <p className="mb-6 text-zinc-400 italic text-sm text-right">Last updated: {lastUpdated}</p>
          
          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">1. Introduction</h2>
            <p className="text-zinc-300 leading-relaxed">
              At JMelzacki, we take your privacy seriously. This Privacy Policy explains how we collect, use, and share information when you visit <strong>Countrydle</strong> and play the game. It describes our information practices; using the Website or playing the Game does not by itself mean that you consent to optional advertising.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">2. Information We Collect</h2>
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-medium text-white mb-2">a. Personal Information</h3>
                <p className="text-zinc-300">When you register on our Website or log in using Google, we collect the following personal information:</p>
                <ul className="list-disc list-inside mt-2 text-zinc-300 space-y-1 ml-4">
                  <li><strong>Email Address:</strong> Used to create and manage your account.</li>
                  <li><strong>Google Profile Information:</strong> If you log in using Google, we may access your Google account’s basic information, such as your email address and name.</li>
                </ul>
              </div>
              
              <div>
                <h3 className="text-lg font-medium text-white mb-2">b. Non-Personal Information</h3>
                <p className="text-zinc-300">We may collect non-personal information automatically when you use the Website, including:</p>
                <ul className="list-disc list-inside mt-2 text-zinc-300 space-y-1 ml-4">
                  <li>IP Address</li>
                  <li>Browser type and version</li>
                  <li>Operating system</li>
                  <li>Game activity (e.g., how many times you have played, performance in the game)</li>
                </ul>
              </div>

              <div>
                <h3 className="text-lg font-medium text-white mb-2">c. Cookies and Similar Technologies</h3>
                <p className="text-zinc-300">
                  We use cookies to enhance your experience on the Website and manage sessions. Cookies are small text files stored on your device that allow us to maintain your login session and analyze usage.
                </p>
              </div>
              <div>
                <h3 className="text-lg font-medium text-white mb-2">d. Friend Duels</h3>
                <p className="text-zinc-300">
                  Friend duels store display names, chosen locations, questions, guesses, human answers and their revisions,
                  AI recommendations and explanations, timing and available evidence, and submitted reports. We retain
                  agreements as well as disagreements to verify and improve question answering. Avoid including personal
                  or sensitive information in questions, names or reports.
                </p>
                <p className="mt-2 text-zinc-300">
                  Your opponent sees your human answers, not your private AI advice or reports. Secret locations are revealed
                  when the duel ends. Authorized administrators can review completed-game evidence. A necessary HttpOnly
                  browser cookie preserves your guest seats for up to one year; clearing it can remove your access to them.
                </p>
              </div>
            </div>
          </section>

          <section className="mb-8 border-l-4 border-blue-500 pl-6 py-2 bg-blue-500/5 rounded-r-lg">
            <h2 className="text-2xl font-semibold mb-4 text-white">3. Google AdSense and Advertising</h2>
            <p className="text-zinc-300 leading-relaxed mb-4">
              We use <strong>Google AdSense</strong> to serve advertisements on our website. Advertising choices, including whether personalized advertising is allowed, are handled separately through the Google-certified consent message and its Privacy settings where those settings are available.
            </p>
            <p className="text-zinc-300 leading-relaxed">
              Essential cookies needed for site functionality are distinct from optional advertising cookies. Google and other advertising providers may use cookies or similar technologies as permitted by your choices and applicable settings.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">4. How We Use Your Information</h2>
            <ul className="list-disc list-inside text-zinc-300 space-y-2 ml-4">
              <li><strong>Account Management:</strong> To create and manage your account, including authentication and login using Google.</li>
              <li><strong>Game Functionality:</strong> To enable you to play the game and keep track of your daily participation and guesses.</li>
              <li><strong>Improving the Website:</strong> To analyze usage and improve the performance of our website.</li>
              <li><strong>Communication:</strong> To send you notifications related to your account or the Game.</li>
              <li><strong>Internal Analysis:</strong> We may use anonymized data for internal purposes such as machine learning and research to improve game performance and develop new features.</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">5. Sharing Your Information</h2>
            <p className="text-zinc-300 leading-relaxed">
              We will not sell or rent your personal information to third parties. However, we may share your information with trusted service providers (such as hosting or analytics), with Google to facilitate login and ads, or if required by law.
            </p>
            <p className="mt-3 text-zinc-300 leading-relaxed">
              Friend-duel questions and the relevant location facts are processed by Google Gemini.
              Recommendations remain private to the location owner and authorized reviewers; they never replace
              the human player's answer or decide the duel.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">6. Data Retention and Rights</h2>
            <p className="text-zinc-300 leading-relaxed mb-4">
              We retain your personal information for as long as your account is active. You have the right to access, rectify, or erase your data. 
            </p>
            <p className="text-zinc-300 leading-relaxed mb-4">
              Completed friend-duel records are normally removed after 30 days. Reviewed or reported records are normally
              retained for 90 days after the latest completion, report or review. Unreviewed reports and pending or running
              AI work defer deletion until resolved; cleanup runs periodically. These limits are separate from account
              retention and the guest-seat cookie lifetime.
            </p>
            <p className="text-zinc-300 leading-relaxed">
              If you are in the EU (GDPR jurisdiction), you have specific rights regarding data portability and withdrawing consent. To exercise these rights, please contact us at <strong>melzacki.jakub@gmail.com</strong>.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">7. Security</h2>
            <p className="text-zinc-300 leading-relaxed">
              We use industry-standard measures to protect your information, including encryption. However, no method of transmission or storage is 100% secure.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">8. Children's Privacy</h2>
            <p className="text-zinc-300 leading-relaxed">
              Our Website is not intended for children under 13. If we discover a child under 13 has provided personal information, we will delete it immediately.
            </p>
          </section>

          <section className="mb-8 border-t border-zinc-800 pt-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">9. Contact Us</h2>
            <p className="text-zinc-300 leading-relaxed">
              If you have any questions about this Privacy Policy, please contact us at:<br />
              Email: <strong>melzacki.jakub@gmail.com</strong>
            </p>
          </section>
        </div>
      </motion.div>
    </div>
  );
}
