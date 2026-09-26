import { useTranslation } from 'react-i18next';
import toast from 'react-hot-toast';

interface GooglePrivacyMessaging {
  callbackQueue?: {
    push: (callback: { CONSENT_API_READY: () => void }) => number;
  };
  showRevocationMessage?: () => void;
}

declare global {
  interface Window {
    googlefc?: GooglePrivacyMessaging;
  }
}

export function PrivacySettingsButton({ className }: { className?: string }) {
  const { t } = useTranslation();

  const openPrivacySettings = () => {
    const messaging = window.googlefc;
    const showMessage = messaging?.showRevocationMessage;

    if (!messaging?.callbackQueue || !showMessage) {
      toast.error(t('privacySettings.unavailable'));
      return;
    }

    messaging.callbackQueue.push({
      CONSENT_API_READY: () => showMessage.call(messaging),
    });
  };

  return (
    <button type="button" onClick={openPrivacySettings} className={className}>
      {t('privacySettings.label')}
    </button>
  );
}
