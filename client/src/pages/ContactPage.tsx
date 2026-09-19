import { useState } from 'react';
import { motion } from 'framer-motion';
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
    <div className="max-w-4xl mx-auto px-4 py-12 md:py-16">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="space-y-12"
      >
        {/* Header */}
        <div className="text-center space-y-4">
          <h1 className="text-4xl md:text-5xl font-black tracking-tight bg-gradient-to-r from-blue-400 via-teal-300 to-green-400 text-transparent bg-clip-text">
            {t('contact.title', 'Contact & Feedback')}
          </h1>
          <p className="text-zinc-400 max-w-xl mx-auto text-base md:text-lg">
            {t('contact.subtitle', 'Have a suggestion, noticed a geographic discrepancy, or want to report a bug? We would love to hear from you.')}
          </p>
        </div>

        {/* Direct Channels Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-2xl flex items-start gap-4 shadow-lg">
            <div className="p-3 rounded-xl bg-blue-500/10 text-blue-400 shrink-0">
              <Mail size={24} />
            </div>
            <div className="space-y-1">
              <h3 className="text-lg font-bold text-white">Direct Email Support</h3>
              <p className="text-zinc-400 text-xs leading-relaxed">
                For general inquiries, partnerships, and account support:
              </p>
              <a 
                href="mailto:jakub.melzacki@jmelzacki.com" 
                className="text-blue-400 hover:text-blue-300 transition-colors text-sm font-semibold inline-block pt-1"
              >
                jakub.melzacki@jmelzacki.com
              </a>
            </div>
          </div>

          <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-2xl flex items-start gap-4 shadow-lg">
            <div className="p-3 rounded-xl bg-teal-500/10 text-teal-400 shrink-0">
              <Github size={24} />
            </div>
            <div className="space-y-1">
              <h3 className="text-lg font-bold text-white">GitHub Issue Tracker</h3>
              <p className="text-zinc-400 text-xs leading-relaxed">
                Report technical bugs or submit fact correction pull requests:
              </p>
              <a 
                href="https://github.com/melzak252/Countrydle/issues" 
                target="_blank" 
                rel="noreferrer"
                className="text-teal-400 hover:text-teal-300 transition-colors text-sm font-semibold inline-block pt-1"
              >
                github.com/melzak252/Countrydle
              </a>
            </div>
          </div>
        </div>

        {/* Contact Form */}
        <div className="p-8 bg-zinc-900 border border-zinc-800 rounded-3xl shadow-xl space-y-6">
          <div className="space-y-1 border-b border-zinc-800 pb-4">
            <h2 className="text-2xl font-bold text-white">Send a Message</h2>
            <p className="text-zinc-400 text-xs">Fill in your feedback and it will prepare an email directly to our team.</p>
          </div>

          {submitted ? (
            <div className="p-8 text-center space-y-4 bg-zinc-800/40 rounded-2xl border border-zinc-700/50">
              <CheckCircle2 size={48} className="text-green-400 mx-auto" />
              <h3 className="text-xl font-bold text-white">Message Prepared!</h3>
              <p className="text-zinc-300 text-sm max-w-md mx-auto">
                Thank you for helping us improve Countrydle. If your mail app didn't open automatically, you can email us directly at <strong>jakub.melzacki@jmelzacki.com</strong>.
              </p>
              <button
                onClick={() => setSubmitted(false)}
                className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-xl text-white text-xs font-semibold transition-colors cursor-pointer"
              >
                Send Another Note
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Category Pills */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Topic</label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {(
                    [
                      { id: 'feedback', label: 'General Feedback', icon: <MessageSquare size={14} /> },
                      { id: 'data', label: 'Data Correction', icon: <Lightbulb size={14} /> },
                      { id: 'bug', label: 'Bug Report', icon: <Bug size={14} /> },
                      { id: 'feature', label: 'Feature Request', icon: <Send size={14} /> },
                    ] as const
                  ).map((cat) => (
                    <button
                      key={cat.id}
                      type="button"
                      onClick={() => setTopic(cat.id)}
                      className={`flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${
                        topic === cat.id
                          ? 'bg-blue-600 text-white border-blue-500 shadow-md'
                          : 'bg-zinc-800/60 text-zinc-400 border-zinc-700 hover:bg-zinc-800 hover:text-white'
                      }`}
                    >
                      {cat.icon}
                      <span>{cat.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Name & Email Fields */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Your Name (Optional)</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Alex"
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Your Email (Optional)</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="e.g. alex@example.com"
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                  />
                </div>
              </div>

              {/* Message */}
              <div className="space-y-1">
                <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Message *</label>
                <textarea
                  required
                  rows={5}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Describe your question, observation, or suggestion in detail..."
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors resize-y"
                />
              </div>

              <button
                type="submit"
                className="w-full sm:w-auto px-8 py-3 bg-gradient-to-r from-blue-600 to-teal-600 hover:from-blue-500 hover:to-teal-500 rounded-xl text-white font-bold text-sm shadow-lg transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                <Send size={16} />
                <span>Send via Email Client</span>
              </button>
            </form>
          )}
        </div>
      </motion.div>
    </div>
  );
}
