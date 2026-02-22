import { motion } from 'framer-motion';

export default function TermsOfServicePage() {
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
          Terms of Service
        </h1>
        
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-8 shadow-xl">
          <p className="mb-6 text-zinc-400 italic text-sm text-right">Last updated: {lastUpdated}</p>
          
          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">1. Acceptance of Terms</h2>
            <p className="text-zinc-300 leading-relaxed">
              By accessing or using the Countrydle website, you agree to comply with and be bound by these Terms of Service and our Privacy Policy. If you do not agree to these terms, please do not use our services.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">2. Account Registration</h2>
            <p className="text-zinc-300 leading-relaxed mb-4">
              To participate in the Game, users must create an account by providing a valid email address or logging in using Google’s third-party service ("Google Login"). By registering, you agree to:
            </p>
            <ul className="list-disc list-inside text-zinc-300 space-y-2 ml-4">
              <li>Provide accurate, current, and complete information.</li>
              <li>Maintain the security of your login credentials.</li>
              <li>Notify us immediately of any unauthorized use of your account.</li>
              <li>We reserve the right to terminate accounts that violate these terms.</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">3. The Game and Fair Play</h2>
            <p className="text-zinc-300 leading-relaxed mb-4">
              Countrydle is a game of skill and knowledge. To maintain a fun and fair environment for everyone, you agree:
            </p>
            <ul className="list-disc list-inside text-zinc-300 space-y-2 ml-4">
              <li>Not to use bots, scripts, or any automated tools to play the game.</li>
              <li>Not to exploit bugs or vulnerabilities in the game engine.</li>
              <li>To play only one game per day as intended by the game rules.</li>
              <li>Cheating or manipulation may result in immediate suspension or banning.</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">4. Google Login and Third-Party Services</h2>
            <p className="text-zinc-300 leading-relaxed">
              You may log in using your Google account. By doing so, you also agree to Google's terms and privacy policies. We do not store your Google password; authentication is handled securely by Google.
            </p>
          </section>

          <section className="mb-8 border-l-4 border-yellow-500 pl-6 py-2 bg-yellow-500/5 rounded-r-lg">
            <h2 className="text-2xl font-semibold mb-4 text-white">5. Advertisements</h2>
            <p className="text-zinc-300 leading-relaxed">
              Our website displays advertisements served by Google AdSense. By using the website, you acknowledge and agree that cookies may be used to serve personalized ads as detailed in our Privacy Policy.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">6. User Conduct</h2>
            <p className="text-zinc-300 leading-relaxed">
              You agree to use the Website responsibly. Prohibited activities include harassment, attempting to access other users' accounts, transmitting malicious code, or engaging in any illegal activities through our platform.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">7. Disclaimer of Warranties</h2>
            <p className="text-zinc-300 leading-relaxed">
              The Website and Game are provided "as is" and "as available" without any warranties. We do not guarantee that the service will be uninterrupted or error-free.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">8. Limitation of Liability</h2>
            <p className="text-zinc-300 leading-relaxed">
              To the fullest extent permitted by law, JMelzacki shall not be liable for any indirect, incidental, or consequential damages resulting from your use of the website or game.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">9. Governing Law</h2>
            <p className="text-zinc-300 leading-relaxed">
              These Terms shall be governed by and construed in accordance with the laws of Poland. Any disputes will be subject to the exclusive jurisdiction of the courts in Poland.
            </p>
          </section>

          <section className="mb-8 border-t border-zinc-800 pt-8">
            <h2 className="text-2xl font-semibold mb-4 text-white">10. Contact Information</h2>
            <p className="text-zinc-300 leading-relaxed">
              If you have any questions about these Terms, please contact us at:<br />
              Email: <strong>support@jmelzacki.com</strong>
            </p>
          </section>
        </div>
      </motion.div>
    </div>
  );
}
