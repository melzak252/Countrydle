import React from 'react';

interface MarkdownRendererProps {
  content: string;
}

function parseInlineFormatting(text: string): React.ReactNode[] {
  // Regex to split by bold (**text**), italic (*text*), and links [label](url)
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g;
  const parts = text.split(regex);

  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={index} className="font-semibold text-sand-100">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return (
        <em key={index} className="italic text-zinc-200">
          {part.slice(1, -1)}
        </em>
      );
    }
    const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (linkMatch) {
      return (
        <a
          key={index}
          href={linkMatch[2]}
          className="break-words text-emerald-400 underline decoration-emerald-400/40 underline-offset-4 transition-colors hover:text-emerald-300"
          target={linkMatch[2].startsWith('http') ? '_blank' : '_self'}
          rel="noopener noreferrer"
        >
          {linkMatch[1]}
        </a>
      );
    }
    return part;
  });
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  if (!content) return null;

  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let currentList: { type: 'ul' | 'ol'; items: string[] } | null = null;

  const flushList = (key: number) => {
    if (!currentList) return;
    if (currentList.type === 'ul') {
      elements.push(
        <ul key={`list-${key}`} className="my-6 space-y-3">
          {currentList.items.map((item, idx) => (
            <li key={idx} className="flex items-start gap-3 text-base leading-8 text-zinc-300 md:text-lg md:leading-8">
              <span aria-hidden="true" className="mt-3.5 h-1 w-1 shrink-0 rounded-full bg-emerald-400" />
              <div className="min-w-0">{parseInlineFormatting(item)}</div>
            </li>
          ))}
        </ul>
      );
    } else {
      elements.push(
        <ol key={`list-${key}`} className="my-6 list-decimal space-y-3 pl-6 text-base leading-8 text-zinc-300 marker:text-emerald-400 md:text-lg md:leading-8">
          {currentList.items.map((item, idx) => (
            <li key={idx} className="pl-1">
              {parseInlineFormatting(item)}
            </li>
          ))}
        </ol>
      );
    }
    currentList = null;
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();

    // Empty line
    if (!trimmed) {
      flushList(idx);
      return;
    }

    // Horizontal Rule
    if (trimmed === '---' || trimmed === '***' || trimmed === '___') {
      flushList(idx);
      elements.push(<hr key={idx} className="my-10 border-white/10" />);
      return;
    }

    // Headings
    if (trimmed.startsWith('### ')) {
      flushList(idx);
      elements.push(
        <h3 key={idx} className="mb-4 mt-8 font-serif text-2xl leading-snug tracking-tight text-sand-100">
          {parseInlineFormatting(trimmed.slice(4))}
        </h3>
      );
      return;
    }

    if (trimmed.startsWith('## ')) {
      flushList(idx);
      elements.push(
        <h2 key={idx} className="mb-5 mt-12 font-serif text-3xl leading-tight tracking-tight text-sand-100 md:text-4xl">
          {parseInlineFormatting(trimmed.slice(3))}
        </h2>
      );
      return;
    }

    if (trimmed.startsWith('# ')) {
      flushList(idx);
      elements.push(
        <h1 key={idx} className="mb-5 mt-12 font-serif text-3xl leading-tight tracking-tight text-sand-100 md:text-4xl">
          {parseInlineFormatting(trimmed.slice(2))}
        </h1>
      );
      return;
    }

    // Blockquote
    if (trimmed.startsWith('> ')) {
      flushList(idx);
      elements.push(
        <blockquote key={idx} className="my-8 border-l-2 border-emerald-400/60 py-1 pl-6 font-serif text-xl italic leading-8 text-sand-100 md:text-2xl md:leading-9">
          {parseInlineFormatting(trimmed.slice(2))}
        </blockquote>
      );
      return;
    }

    // Bullet list item
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (!currentList || currentList.type !== 'ul') {
        flushList(idx);
        currentList = { type: 'ul', items: [] };
      }
      currentList.items.push(trimmed.slice(2));
      return;
    }

    // Ordered list item
    const orderedMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
    if (orderedMatch) {
      if (!currentList || currentList.type !== 'ol') {
        flushList(idx);
        currentList = { type: 'ol', items: [] };
      }
      currentList.items.push(orderedMatch[2]);
      return;
    }

    // Regular paragraph
    flushList(idx);
    elements.push(
      <p key={idx} className="my-5 text-base leading-8 text-zinc-300 md:text-lg md:leading-8">
        {parseInlineFormatting(trimmed)}
      </p>
    );
  });

  flushList(lines.length);

  return <div className="break-words [&>:first-child]:mt-0 [&>:last-child]:mb-0">{elements}</div>;
}
