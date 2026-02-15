import { motion } from 'framer-motion';

export default function CookiePolicyPage() {
  const lastUpdated = "February 15, 2026";

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
                <p className="text-zinc-300">Used by Google to serve ads based on your previous visits to this or other websites. These cookies allow Google and its partners to serve relevant ads to you.</p>
              </div>
            </div>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">3. Third-Party Cookies</h2>
            <p className="text-zinc-300 leading-relaxed">
              In addition to our own cookies, we use third-party cookies from Google (for Login and AdSense). These third parties have their own privacy and cookie policies which we recommend you review.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">4. Managing Cookies</h2>
            <p className="text-zinc-300 leading-relaxed mb-4">
              Most web browsers allow you to control cookies through their settings. You can block or delete cookies, but doing so may prevent you from logging in or using certain features of Countrydle.
            </p>
            <ul className="list-disc list-inside text-zinc-300 space-y-2 ml-4">
              <li>To opt out of personalized advertising by Google, visit <a href="https://www.google.com/settings/ads" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline transition-colors">Google Ads Settings</a>.</li>
              <li>To manage other third-party cookies, visit <a href="https://www.aboutads.info" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline transition-colors">www.aboutads.info</a>.</li>
            </ul>
          </section>

          <section className="mb-8 border-t border-zinc-800 pt-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">5. Contact Us</h2>
            <p className="text-zinc-300 leading-relaxed">
              If you have any questions about our use of cookies, please contact us at:<br />
              Email: <strong>support@jmelzacki.com</strong>
            </p>
          </section>
        </div>
      </motion.div>
    </div>
  );
}
