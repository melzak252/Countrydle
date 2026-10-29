import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import toast from 'react-hot-toast';
import { openPrivacySettings, usePrivacySettingsState } from '../advertising';

export function PrivacySettingsButton({ className }: { className?: string }) {
  const { t } = useTranslation();
  
  const state = usePrivacySettingsState();
  const opening = state === 'opening';
  const unavailableMessage = t('privacySettings.unavailable');

  useEffect(() => {
    if (state === 'unavailable') toast.error(unavailableMessage, { id: 'privacy-settings-unavailable' });
    else toast.dismiss('privacy-settings-unavailable');
  }, [state, unavailableMessage]);

  const open = () => {
    void openPrivacySettings().catch(() => { /* The subscribed error state surfaces the failure. */ });
  };

  return (
    <button type="button" onClick={open} disabled={opening} aria-busy={opening} className={className}>
      {t('privacySettings.label')}
    </button>
  );
}
