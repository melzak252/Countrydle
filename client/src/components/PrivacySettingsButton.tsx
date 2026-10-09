import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import toast from 'react-hot-toast';
import { openPrivacySettings } from '../advertising';

export function PrivacySettingsButton({ className }: { className?: string }) {
  const { t } = useTranslation();
  const [opening, setOpening] = useState(false);

  useEffect(() => {
    const unavailable = () => toast.error(t('privacySettings.unavailable'), { id: 'privacy-settings-unavailable' });
    window.addEventListener('countrydle:privacy-unavailable', unavailable);
    return () => window.removeEventListener('countrydle:privacy-unavailable', unavailable);
  }, [t]);

  const open = async () => {
    setOpening(true);
    try {
      await openPrivacySettings();
    } catch {
      toast.error(t('privacySettings.unavailable'), { id: 'privacy-settings-unavailable' });
    } finally {
      setOpening(false);
    }
  };

  return (
    <button type="button" onClick={open} disabled={opening} aria-busy={opening} className={className}>
      {t('privacySettings.label')}
    </button>
  );
}
