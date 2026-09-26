import { motion } from 'framer-motion';
import { PrivacySettingsButton } from '../components/PrivacySettingsButton';

export default function CookiePolicyPage() {
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
          Cookie Policy
        </h1>
        
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-8 shadow-xl">
          <p className="mb-6 text-zinc-400 italic text-sm text-right">Last updated: {lastUpdated}</p>
          
          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">1. What Are Cookies?</h2>
            <p className="text-zinc-300 leading-relaxed">
              Cookies are small text files placed on your device to help the website function properly, analyze usage, and provide a personalized experience. They can be "session" cookies (deleted when you close your browser) or "persistent" cookies (remain until they expire or are deleted).
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">2. How We Use Cookies</h2>
            <p className="text-zinc-300 mb-4">We use cookies for the following purposes:</p>
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-medium text-white mb-2">a. Strictly Necessary Cookies</h3>
                <p className="text-zinc-300">Essential for the website to function, such as maintaining your login session and security.</p>
              </div>
              <div>
                <h3 className="text-lg font-medium text-white mb-2">b. Analytics Cookies</h3>
                <p className="text-zinc-300">Help us understand how visitors interact with the website, allowing us to improve performance and user experience.</p>
              </div>
              <div>
                <h3 className="text-lg font-medium text-white mb-2">c. Advertising Cookies (Google AdSense)</h3>
                <p className="text-zinc-300">Google AdSense may use cookies or similar technologies for advertising, including personalized advertising, according to your choices and applicable settings. Advertising choices are managed separately from essential cookies needed for the website to function.</p>
              </div>
            </div>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">3. Third-Party Cookies</h2>
            <p className="text-zinc-300 leading-relaxed">
              Google provides a consent message through its certified consent management platform (CMP) where a message applies. Google and other third parties may use cookies or similar technologies according to the choices made there and applicable settings.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">4. Managing Cookies and Advertising Choices</h2>
            <p className="text-zinc-300 leading-relaxed mb-4">
              You can use Privacy settings to reopen Google’s consent message and review or change your advertising choices when those settings are available:
            </p>
            <div className="mb-4">
              <PrivacySettingsButton />
            </div>
            <p className="text-zinc-300 leading-relaxed mb-4">
              If no consent message applies, there may be no message to display. If Google’s consent services are unavailable, the button reports that settings cannot be opened; it does not save or change an advertising choice. You can also block or delete cookies through your browser, though doing so may prevent login or other features from working. Browser cookie controls are separate from the Privacy settings for your advertising choices.
            </p>
          </section>

          <section className="mb-8 border-t border-zinc-800 pt-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">5. Contact Us</h2>
            <p className="text-zinc-300 leading-relaxed">
              If you have any questions about our use of cookies, please contact us at:<br />
              Email: <strong>melzacki.jakub@gmail.com</strong>
            </p>
          </section>
        </div>
      </motion.div>
    </div>
  );
}
