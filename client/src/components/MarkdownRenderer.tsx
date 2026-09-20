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
        <strong key={index} className="font-bold text-white">
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
          className="text-blue-400 hover:text-blue-300 underline underline-offset-2 transition-colors"
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
        <ul key={`list-${key}`} className="space-y-2.5 my-4">
          {currentList.items.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2.5 text-zinc-300 text-sm md:text-base leading-relaxed">
              <span className="w-1.5 h-1.5 rounded-full bg-teal-400 mt-2 shrink-0" />
              <div>{parseInlineFormatting(item)}</div>
            </li>
          ))}
        </ul>
      );
    } else {
      elements.push(
        <ol key={`list-${key}`} className="space-y-2.5 my-4 pl-4 list-decimal text-zinc-300 text-sm md:text-base leading-relaxed">
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
      elements.push(<hr key={idx} className="border-zinc-800 my-8" />);
      return;
    }

    // Headings
    if (trimmed.startsWith('### ')) {
      flushList(idx);
      elements.push(
        <h3 key={idx} className="text-xl md:text-2xl font-bold text-teal-300 mt-8 mb-3 tracking-tight">
          {parseInlineFormatting(trimmed.slice(4))}
        </h3>
      );
      return;
    }

    if (trimmed.startsWith('## ')) {
      flushList(idx);
      elements.push(
        <h2 key={idx} className="text-2xl md:text-3xl font-black text-white mt-10 mb-4 tracking-tight border-b border-zinc-800/80 pb-2">
          {parseInlineFormatting(trimmed.slice(3))}
        </h2>
      );
      return;
    }

    if (trimmed.startsWith('# ')) {
      flushList(idx);
      elements.push(
        <h1 key={idx} className="text-3xl md:text-4xl font-black text-white mt-10 mb-4 tracking-tight">
          {parseInlineFormatting(trimmed.slice(2))}
        </h1>
      );
      return;
    }

    // Blockquote
    if (trimmed.startsWith('> ')) {
      flushList(idx);
      elements.push(
        <blockquote key={idx} className="border-l-4 border-blue-500 pl-4 py-2 my-4 italic text-zinc-300 bg-blue-500/5 rounded-r-xl">
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
      <p key={idx} className="text-zinc-300 text-sm md:text-base leading-relaxed my-4">
        {parseInlineFormatting(trimmed)}
      </p>
    );
  });

  flushList(lines.length);

  return <div className="space-y-2">{elements}</div>;
}
