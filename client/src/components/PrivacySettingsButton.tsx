import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import toast from 'react-hot-toast';
import { openPrivacySettings, usePrivacySettingsState } from '../advertising';

export function PrivacySettingsButton({ className }: { className?: string }) {
  const { t, i18n } = useTranslation();
  const isPl = i18n?.language?.startsWith('pl');
  const state = usePrivacySettingsState();
  const opening = state === 'opening';
  const unavailableMessage = isPl
    ? 'Nie udało się otworzyć ustawień prywatności Google. Mogą być niedostępne lub blokowane przez przeglądarkę. Żadne ustawienia nie zostały zmienione. Spróbuj ponownie później.'
    : t('privacySettings.unavailable');

  useEffect(() => {
    if (state === 'unavailable') toast.error(unavailableMessage, { id: 'privacy-settings-unavailable' });
    else toast.dismiss('privacy-settings-unavailable');
  }, [state, unavailableMessage]);

  const open = () => {
    void openPrivacySettings().catch(() => { /* The subscribed error state surfaces the failure. */ });
  };

  return (
    <button type="button" onClick={open} disabled={opening} aria-busy={opening} className={className}>
      {isPl ? 'Ustawienia prywatności' : t('privacySettings.label')}
    </button>
  );
}
