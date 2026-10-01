import { useState } from 'react';
import { Mail, MessageSquare, Bug, Lightbulb, Send, CheckCircle2, Github } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { suggestionService } from '../services/api';
import type { SuggestionTopic } from '../types';

const CONTACT_EMAIL = 'melzacki.jakub@gmail.com';
const MESSAGE_MAX_LENGTH = 5000;
const NAME_MAX_LENGTH = 100;
const EMAIL_MAX_LENGTH = 254;

export default function ContactPage() {
  const { t } = useTranslation();
  const [topic, setTopic] = useState<SuggestionTopic>('feedback');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSubmitting) return;

    const trimmedMessage = message.trim();
    const trimmedName = name.trim();
    const trimmedEmail = email.trim();
    if (!trimmedMessage || trimmedMessage.length > MESSAGE_MAX_LENGTH || trimmedName.length > NAME_MAX_LENGTH || trimmedEmail.length > EMAIL_MAX_LENGTH) {
      setError(t('suggestion.validationError'));
      return;
    }
    if (trimmedEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      setError(t('suggestion.emailError'));
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      await suggestionService.submit({
        topic,
        message: trimmedMessage,
        name: trimmedName || null,
        email: trimmedEmail || null,
      });
      setMessage('');
      setName('');
      setEmail('');
      setSubmitted(true);
    } catch {
      setError(t('suggestion.submitError'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-8 bg-obsidian-950 pb-8">
      <header className="border-b border-white/10 pb-8">
        <div className="mb-4 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-emerald-400">
          <MessageSquare size={15} aria-hidden="true" />
          {t('suggestion.badge')}
        </div>
        <h1 className="font-serif text-4xl leading-tight tracking-tight text-sand-100 sm:text-5xl">
          {t('suggestion.title')}
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-zinc-400">{t('suggestion.subtitle')}</p>
      </header>

      <div className="grid min-w-0 gap-8 lg:grid-cols-[1fr_2fr] lg:gap-10">
        <aside aria-label={t('suggestion.contactChannels')} className="min-w-0 space-y-6">
          <section className="space-y-3 border-b border-white/10 pb-6">
            <h2 className="flex items-center gap-2 text-base font-medium text-sand-100">
              <Mail size={18} className="text-emerald-400" aria-hidden="true" />
              {t('suggestion.directSupport')}
            </h2>
            <p className="text-sm leading-6 text-zinc-400">{t('suggestion.directSupportDescription')}</p>
            <a href={`mailto:${CONTACT_EMAIL}`} className="inline-block break-all text-sm text-emerald-300 underline decoration-emerald-400/30 underline-offset-4 transition-colors hover:text-emerald-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400">
              {CONTACT_EMAIL}
            </a>
          </section>

          <section className="space-y-3">
            <h2 className="flex items-center gap-2 text-base font-medium text-sand-100">
              <Github size={18} className="text-emerald-400" aria-hidden="true" />
              {t('suggestion.githubTitle')}
            </h2>
            <p className="text-sm leading-6 text-zinc-400">{t('suggestion.githubDescription')}</p>
            <a href="https://github.com/melzak252/Countrydle/issues" target="_blank" rel="noreferrer" className="inline-block break-all text-sm text-emerald-300 underline decoration-emerald-400/30 underline-offset-4 transition-colors hover:text-emerald-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400">
              github.com/melzak252/Countrydle
            </a>
          </section>
        </aside>

        <section aria-labelledby="suggestion-form-heading" className="min-w-0 space-y-6 rounded-md border border-white/10 bg-obsidian-900 p-5 sm:p-7">
          <div className="space-y-2 border-b border-white/10 pb-5">
            <h2 id="suggestion-form-heading" className="font-serif text-2xl text-sand-100">{t('suggestion.formTitle')}</h2>
            <p className="text-sm leading-6 text-zinc-400">{t('suggestion.formDescription')}</p>
          </div>

          {submitted ? (
            <div className="space-y-4 py-6">
              <div role="status" className="space-y-3">
                <CheckCircle2 size={28} className="text-emerald-400" aria-hidden="true" />
                <h3 className="text-xl font-medium text-sand-100">{t('suggestion.successTitle')}</h3>
                <p className="text-sm leading-7 text-zinc-400">{t('suggestion.successMessage')}</p>
              </div>
              <button type="button" onClick={() => setSubmitted(false)} className="rounded-sm border border-white/15 px-4 py-2.5 text-sm font-medium text-sand-100 transition-colors hover:border-emerald-400/40 hover:text-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400">
                {t('suggestion.sendAnother')}
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6" noValidate>
              {error && <p role="alert" className="rounded-sm border border-red-400/30 bg-red-400/5 px-3 py-2 text-sm text-red-200">{error}</p>}
              <fieldset className="min-w-0" disabled={isSubmitting}>
                <legend className="mb-3 text-sm font-medium text-sand-100">{t('suggestion.topic')}</legend>
                <div className="flex flex-wrap gap-2">
                  {([
                    { id: 'feedback', label: t('suggestion.topics.feedback'), icon: <MessageSquare size={14} aria-hidden="true" /> },
                    { id: 'data', label: t('suggestion.topics.data'), icon: <Lightbulb size={14} aria-hidden="true" /> },
                    { id: 'bug', label: t('suggestion.topics.bug'), icon: <Bug size={14} aria-hidden="true" /> },
                    { id: 'feature', label: t('suggestion.topics.feature'), icon: <Send size={14} aria-hidden="true" /> },
                  ] satisfies { id: SuggestionTopic; label: string; icon: React.ReactNode }[]).map((category) => (
                    <button key={category.id} type="button" aria-pressed={topic === category.id} onClick={() => setTopic(category.id)} className={`flex items-center gap-2 rounded-sm border px-3 py-2.5 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 ${topic === category.id ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300' : 'border-white/10 text-zinc-400 hover:border-white/20 hover:text-sand-100'}`}>
                      {category.icon}<span>{category.label}</span>
                    </button>
                  ))}
                </div>
              </fieldset>

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <div className="space-y-2">
                  <label htmlFor="suggestion-name" className="text-sm font-medium text-sand-100">{t('suggestion.name')} <span className="font-normal text-zinc-400">{t('suggestion.optional')}</span></label>
                  <input id="suggestion-name" type="text" maxLength={NAME_MAX_LENGTH} value={name} onChange={(event) => setName(event.target.value)} placeholder={t('suggestion.namePlaceholder')} disabled={isSubmitting} className="w-full rounded-sm border border-white/15 bg-obsidian-950 px-3 py-3 text-base text-sand-100 placeholder:text-zinc-500 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400 disabled:opacity-60" />
                  <p className="text-right text-xs text-zinc-500">{name.length}/{NAME_MAX_LENGTH}</p>
                </div>
                <div className="space-y-2">
                  <label htmlFor="suggestion-email" className="text-sm font-medium text-sand-100">{t('suggestion.email')} <span className="font-normal text-zinc-400">{t('suggestion.optional')}</span></label>
                  <input id="suggestion-email" type="email" maxLength={EMAIL_MAX_LENGTH} value={email} onChange={(event) => setEmail(event.target.value)} placeholder={t('suggestion.emailPlaceholder')} disabled={isSubmitting} className="w-full rounded-sm border border-white/15 bg-obsidian-950 px-3 py-3 text-base text-sand-100 placeholder:text-zinc-500 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400 disabled:opacity-60" />
                  <p className="text-right text-xs text-zinc-500">{email.length}/{EMAIL_MAX_LENGTH}</p>
                </div>
              </div>

              <div className="space-y-2">
                <label htmlFor="suggestion-message" className="text-sm font-medium text-sand-100">{t('suggestion.message')} <span className="font-normal text-zinc-400">{t('suggestion.required')}</span></label>
                <textarea id="suggestion-message" required minLength={1} maxLength={MESSAGE_MAX_LENGTH} rows={5} value={message} onChange={(event) => setMessage(event.target.value)} placeholder={t('suggestion.messagePlaceholder')} disabled={isSubmitting} aria-describedby="suggestion-message-limit" className="w-full resize-y rounded-sm border border-white/15 bg-obsidian-950 px-3 py-3 text-base text-sand-100 placeholder:text-zinc-500 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400 disabled:opacity-60" />
                <p id="suggestion-message-limit" className="text-right text-xs text-zinc-500">{t('suggestion.characterCount', { count: message.length, max: MESSAGE_MAX_LENGTH })}</p>
              </div>

              <button type="submit" disabled={isSubmitting} className="flex w-full items-center justify-center gap-2 rounded-sm bg-emerald-400 px-5 py-3 text-sm font-semibold text-obsidian-950 transition-colors hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 disabled:cursor-wait disabled:opacity-60 sm:w-auto">
                <Send size={16} aria-hidden="true" />
                <span>{isSubmitting ? t('suggestion.submitting') : t('suggestion.submit')}</span>
              </button>
            </form>
          )}
        </section>
      </div>
    </div>
  );
}
