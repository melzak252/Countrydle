import { useState } from 'react';
import { Mail, MessageSquare, Bug, Lightbulb, Send, CheckCircle2, Github } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import toast from 'react-hot-toast';

export default function ContactPage() {
  const { t } = useTranslation();
  const [topic, setTopic] = useState<'feedback' | 'bug' | 'feature' | 'data'>('feedback');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) {
      toast.error('Please enter your message.');
      return;
    }

    // In a production static/SPA setup, compose mailto or handle via backend
    const subject = encodeURIComponent(`[Countrydle ${topic.toUpperCase()}] from ${name || 'Player'}`);
    const body = encodeURIComponent(`Topic: ${topic}\nFrom: ${name} (${email || 'anonymous'})\n\nMessage:\n${message}`);
    window.location.href = `mailto:jakub.melzacki@jmelzacki.com?subject=${subject}&body=${body}`;

    setSubmitted(true);
    toast.success('Your message client has been opened!');
  };

  return (
    <div className="mx-auto max-w-5xl space-y-8 bg-obsidian-950 pb-8">
      <header className="border-b border-white/10 pb-8">
        <div className="mb-4 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-emerald-400">
          <MessageSquare size={15} aria-hidden="true" />
          Get in touch
        </div>
        <h1 className="font-serif text-4xl leading-tight tracking-tight text-sand-100 sm:text-5xl">
          {t('contact.title', 'Contact & Feedback')}
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-zinc-400">
          {t('contact.subtitle', 'Have a suggestion, noticed a geographic discrepancy, or want to report a bug? We would love to hear from you.')}
        </p>
      </header>

      <div className="grid min-w-0 gap-8 lg:grid-cols-[1fr_2fr] lg:gap-10">
        <aside aria-label="Contact channels" className="min-w-0 space-y-6">
          <section className="space-y-3 border-b border-white/10 pb-6">
            <h2 className="flex items-center gap-2 text-base font-medium text-sand-100">
              <Mail size={18} className="text-emerald-400" aria-hidden="true" />
              Direct Email Support
            </h2>
            <p className="text-sm leading-6 text-zinc-400">
              For general inquiries, partnerships, and account support:
            </p>
            <a
              href="mailto:jakub.melzacki@jmelzacki.com"
              className="inline-block break-all text-sm text-emerald-300 underline decoration-emerald-400/30 underline-offset-4 transition-colors hover:text-emerald-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400"
            >
              jakub.melzacki@jmelzacki.com
            </a>
          </section>

          <section className="space-y-3">
            <h2 className="flex items-center gap-2 text-base font-medium text-sand-100">
              <Github size={18} className="text-emerald-400" aria-hidden="true" />
              GitHub Issue Tracker
            </h2>
            <p className="text-sm leading-6 text-zinc-400">
              Report technical bugs or submit fact correction pull requests:
            </p>
            <a
              href="https://github.com/melzak252/Countrydle/issues"
              target="_blank"
              rel="noreferrer"
              className="inline-block break-all text-sm text-emerald-300 underline decoration-emerald-400/30 underline-offset-4 transition-colors hover:text-emerald-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400"
            >
              github.com/melzak252/Countrydle
            </a>
          </section>
        </aside>

        <section aria-labelledby="contact-form-heading" className="min-w-0 space-y-6 rounded-md border border-white/10 bg-obsidian-900 p-5 sm:p-7">
          <div className="space-y-2 border-b border-white/10 pb-5">
            <h2 id="contact-form-heading" className="font-serif text-2xl text-sand-100">Send a Message</h2>
            <p className="text-sm leading-6 text-zinc-400">Fill in your feedback and it will prepare an email directly to our team.</p>
          </div>

          {submitted ? (
            <div className="space-y-4 py-6">
              <div role="status" className="space-y-3">
                <CheckCircle2 size={28} className="text-emerald-400" aria-hidden="true" />
                <h3 className="text-xl font-medium text-sand-100">Message Prepared!</h3>
                <p className="text-sm leading-7 text-zinc-400">
                  Thank you for helping us improve Countrydle. If your mail app didn't open automatically, you can email us directly at <strong className="break-all font-medium text-sand-100">jakub.melzacki@jmelzacki.com</strong>.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSubmitted(false)}
                className="rounded-sm border border-white/15 px-4 py-2.5 text-sm font-medium text-sand-100 transition-colors hover:border-emerald-400/40 hover:text-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400"
              >
                Send Another Note
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              <fieldset className="min-w-0">
                <legend className="mb-3 text-sm font-medium text-sand-100">Topic</legend>
                <div className="flex flex-wrap gap-2">
                  {(
                    [
                      { id: 'feedback', label: 'General Feedback', icon: <MessageSquare size={14} aria-hidden="true" /> },
                      { id: 'data', label: 'Data Correction', icon: <Lightbulb size={14} aria-hidden="true" /> },
                      { id: 'bug', label: 'Bug Report', icon: <Bug size={14} aria-hidden="true" /> },
                      { id: 'feature', label: 'Feature Request', icon: <Send size={14} aria-hidden="true" /> },
                    ] as const
                  ).map((cat) => (
                    <button
                      key={cat.id}
                      type="button"
                      aria-pressed={topic === cat.id}
                      onClick={() => setTopic(cat.id)}
                      className={`flex items-center gap-2 rounded-sm border px-3 py-2.5 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 ${
                        topic === cat.id
                          ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'
                          : 'border-white/10 text-zinc-400 hover:border-white/20 hover:text-sand-100'
                      }`}
                    >
                      {cat.icon}
                      <span>{cat.label}</span>
                    </button>
                  ))}
                </div>
              </fieldset>

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <div className="space-y-2">
                  <label htmlFor="contact-name" className="text-sm font-medium text-sand-100">Your Name <span className="font-normal text-zinc-400">(Optional)</span></label>
                  <input
                    id="contact-name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Alex"
                    className="w-full rounded-sm border border-white/15 bg-obsidian-950 px-3 py-3 text-base text-sand-100 placeholder:text-zinc-500 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400"
                  />
                </div>

                <div className="space-y-2">
                  <label htmlFor="contact-email" className="text-sm font-medium text-sand-100">Your Email <span className="font-normal text-zinc-400">(Optional)</span></label>
                  <input
                    id="contact-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="e.g. alex@example.com"
                    className="w-full rounded-sm border border-white/15 bg-obsidian-950 px-3 py-3 text-base text-sand-100 placeholder:text-zinc-500 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label htmlFor="contact-message" className="text-sm font-medium text-sand-100">Message <span className="font-normal text-zinc-400">(Required)</span></label>
                <textarea
                  id="contact-message"
                  required
                  rows={5}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Describe your question, observation, or suggestion in detail..."
                  className="w-full resize-y rounded-sm border border-white/15 bg-obsidian-950 px-3 py-3 text-base text-sand-100 placeholder:text-zinc-500 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400"
                />
              </div>

              <button
                type="submit"
                className="flex w-full items-center justify-center gap-2 rounded-sm bg-emerald-400 px-5 py-3 text-sm font-semibold text-obsidian-950 transition-colors hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 sm:w-auto"
              >
                <Send size={16} aria-hidden="true" />
                <span>Send via Email Client</span>
              </button>
            </form>
          )}
        </section>
      </div>
    </div>
  );
}
