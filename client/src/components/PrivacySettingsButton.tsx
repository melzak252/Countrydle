import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import toast from 'react-hot-toast';
import { openPrivacySettings } from '../advertising';

export function PrivacySettingsButton({ className }: { className?: string }) {
  const { t, i18n } = useTranslation();
  const isPl = i18n?.language?.startsWith('pl');
  const [opening, setOpening] = useState(false);
  const unavailableMessage = isPl
    ? 'Nie udało się otworzyć ustawień prywatności Google. Mogą być niedostępne lub blokowane przez przeglądarkę. Żadne ustawienia nie zostały zmienione. Spróbuj ponownie później.'
    : t('privacySettings.unavailable');

  useEffect(() => {
    const unavailable = () => toast.error(unavailableMessage, { id: 'privacy-settings-unavailable' });
    window.addEventListener('countrydle:privacy-unavailable', unavailable);
    return () => window.removeEventListener('countrydle:privacy-unavailable', unavailable);
  }, [unavailableMessage]);

  const open = async () => {
    setOpening(true);
    try {
      await openPrivacySettings();
    } catch {
      toast.error(unavailableMessage, { id: 'privacy-settings-unavailable' });
    } finally {
      setOpening(false);
    }
  };

  return (
    <button type="button" onClick={open} disabled={opening} aria-busy={opening} className={className}>
      {isPl ? 'Ustawienia prywatności' : t('privacySettings.label')}
    </button>
  );
}
