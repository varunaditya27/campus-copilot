import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const components: Components = {
  p: ({ children }) => (
    <p className="mb-3 text-[15px] leading-relaxed text-ink last:mb-0">{children}</p>
  ),
  strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,

  h1: ({ children }) => (
    <h1 className="mb-2.5 mt-4 font-display text-lg font-medium text-navy first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-2 mt-4 font-display text-base font-medium text-navy first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1.5 mt-3 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-soft first:mt-0">
      {children}
    </h3>
  ),

  ul: ({ children }) => (
    <ul className="mb-3 ml-4.5 list-disc space-y-1 text-[15px] leading-relaxed text-ink marker:text-brass last:mb-0">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-3 ml-4.5 list-decimal space-y-1 text-[15px] leading-relaxed text-ink marker:text-brass marker:font-mono marker:text-[13px] last:mb-0">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="pl-1">{children}</li>,

  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-brass underline decoration-brass-line underline-offset-2 transition-colors duration-200 hover:text-navy"
    >
      {children}
    </a>
  ),

  blockquote: ({ children }) => (
    <blockquote className="mb-3 border-l-2 border-brass-line pl-3 text-ink-soft italic last:mb-0">
      {children}
    </blockquote>
  ),

  hr: () => <hr className="my-4 border-line" />,

  code: ({ className, children, ...props }) => {
    const isBlock = /language-/.test(className ?? "");
    if (isBlock) {
      return (
        <code className={`font-mono text-[13px] leading-relaxed ${className ?? ""}`} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code className="rounded-none bg-cream-sunken px-1 py-0.5 font-mono text-[13px] text-ink">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="thin-scroll mb-3 overflow-x-auto border border-line bg-cream-sunken px-3 py-2.5 last:mb-0">
      {children}
    </pre>
  ),

  table: ({ children }) => (
    <div className="thin-scroll mb-3 overflow-x-auto last:mb-0">
      <table className="w-full border-collapse text-[14px]">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="border-b border-line-strong">{children}</thead>,
  th: ({ children }) => (
    <th className="px-2.5 py-1.5 text-left font-mono text-[10.5px] uppercase tracking-[0.1em] text-ink-soft">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-t border-line px-2.5 py-1.5 align-top text-ink">{children}</td>
  ),
};

export default function Markdown({ content }: { content: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  );
}
