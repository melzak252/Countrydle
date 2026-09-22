import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Cookie, X } from "lucide-react";
import { Link } from "react-router-dom";
import { Trans, useTranslation } from 'react-i18next';
import { cn } from "../lib/utils";

export default function CookieConsent() {
  const [isVisible, setIsVisible] = useState(false);
  const { t } = useTranslation();

  useEffect(() => {
    try {
      if (localStorage.getItem("cookie-consent")) return;
    } catch {
      // Keep the choice available for this page even without storage.
    }
    const timer = setTimeout(() => setIsVisible(true), 1000);
    return () => clearTimeout(timer);
  }, []);

  const handleAccept = () => {
    try {
      localStorage.setItem("cookie-consent", "accepted");
    } catch {
      // The current page can still dismiss the banner.
    }
    setIsVisible(false);
  };

  const handleDecline = () => {
    try {
      localStorage.setItem("cookie-consent", "declined");
    } catch {
      // The current page can still dismiss the banner.
    }
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
            "p-6 bg-obsidian-900 border border-sand-200/20 shadow-xl"
          )}
        >
          <div className="flex flex-col gap-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <Cookie className="h-5 w-5 text-sand-400" />
                <h3 className="text-lg font-semibold text-sand-100">
                  {t('cookie.title')}
                </h3>
              </div>
              <button
                onClick={handleDecline}
                className="text-zinc-400 hover:text-white transition-colors"
                aria-label={t('cookie.close')}
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            
            <p className="text-sm text-zinc-400">
              <Trans
                i18nKey="cookie.message"
                values={{ policy: t('cookie.policy') }}
                components={{
                  policyLink: <Link to="/cookie-policy" className="text-emerald-300 underline underline-offset-4" />,
                }}
              />
            </p>
            
            <div className="flex gap-3 mt-2">
              <button
                onClick={handleDecline}
                className="flex-1 px-4 py-2 text-sm font-medium text-zinc-300 bg-zinc-800 hover:bg-zinc-700 rounded-md transition-colors"
              >
                {t('cookie.decline')}
              </button>
              <button
                onClick={handleAccept}
                className="flex-1 px-4 py-2 text-sm font-medium text-black bg-white hover:bg-zinc-200 rounded-md transition-colors"
              >
                {t('cookie.acceptAll')}
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
