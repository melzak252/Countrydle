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
  const { t, i18n } = useTranslation();
  const isPl = i18n?.language?.startsWith('pl');

  const openPrivacySettings = () => {
    const messaging = window.googlefc;
    const showMessage = messaging?.showRevocationMessage;

    if (!messaging?.callbackQueue || !showMessage) {
      toast.error(isPl
        ? 'Nie udało się otworzyć ustawień prywatności Google. Mogą być niedostępne lub blokowane przez przeglądarkę. Żadne ustawienia nie zostały zmienione. Spróbuj ponownie później.'
        : t('privacySettings.unavailable'));
      return;
    }

    messaging.callbackQueue.push({
      CONSENT_API_READY: () => showMessage.call(messaging),
    });
  };

  return (
    <button type="button" onClick={openPrivacySettings} className={className}>
      {isPl ? 'Ustawienia prywatności' : t('privacySettings.label')}
    </button>
  );
}
