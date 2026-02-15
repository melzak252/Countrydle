import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Cookie, X } from "lucide-react";
import { Link } from "react-router-dom";
import { cn } from "../lib/utils";

export default function CookieConsent() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Check if user has already made a choice
    const consent = localStorage.getItem("cookie-consent");
    if (!consent) {
      // Delay showing the banner slightly for better UX
      const timer = setTimeout(() => setIsVisible(true), 1000);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleAccept = () => {
    localStorage.setItem("cookie-consent", "accepted");
    setIsVisible(false);
  };

  const handleDecline = () => {
    localStorage.setItem("cookie-consent", "declined");
    setIsVisible(false);
  };

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ y: 100, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 100, opacity: 0 }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
          className={cn(
            "fixed bottom-4 left-4 right-4 z-50",
            "md:left-auto md:right-4 md:max-w-md",
            "p-6 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl"
          )}
        >
          <div className="flex flex-col gap-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <Cookie className="h-6 w-6 text-yellow-500" />
                <h3 className="text-lg font-semibold text-white">
                  We use cookies
                </h3>
              </div>
              <button
                onClick={handleDecline}
                className="text-zinc-400 hover:text-white transition-colors"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            
            <p className="text-sm text-zinc-400">
              We use cookies to enhance your browsing experience, serve personalized content (including ads via Google AdSense), and analyze our traffic. By clicking "Accept All", you consent to our use of cookies. Read our{" "}
              <Link to="/cookie-policy" className="text-blue-400 hover:underline">
                Cookie Policy
              </Link>{" "}
              for more details.
            </p>
            
            <div className="flex gap-3 mt-2">
              <button
                onClick={handleDecline}
                className="flex-1 px-4 py-2 text-sm font-medium text-zinc-300 bg-zinc-800 hover:bg-zinc-700 rounded-md transition-colors"
              >
                Decline
              </button>
              <button
                onClick={handleAccept}
                className="flex-1 px-4 py-2 text-sm font-medium text-black bg-white hover:bg-zinc-200 rounded-md transition-colors"
              >
                Accept All
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
