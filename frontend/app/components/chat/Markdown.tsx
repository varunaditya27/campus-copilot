import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const components: Components = {
  p: ({ children }) => (
    <p className="mb-3 text-[15px] leading-relaxed text-ink last:mb-0">{children}</p>
  ),
  strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,

  h1: ({ children }) => (
    <h1 className="mb-2.5 mt-4 text-lg font-medium text-ink first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-2 mt-4 text-base font-medium text-ink first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1.5 mt-3 text-[15px] font-semibold text-ink first:mt-0">
      {children}
    </h3>
  ),

  ul: ({ children }) => (
    <ul className="mb-3 ml-4.5 list-disc space-y-1 text-[15px] leading-relaxed text-ink marker:text-muted last:mb-0">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-3 ml-4.5 list-decimal space-y-1 text-[15px] leading-relaxed text-ink marker:text-muted last:mb-0">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="pl-1">{children}</li>,

  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-ink underline underline-offset-2 hover:decoration-2"
    >
      {children}
    </a>
  ),

  blockquote: ({ children }) => (
    <blockquote className="mb-3 bg-surface px-3 py-2 text-ink italic last:mb-0">
      {children}
    </blockquote>
  ),

  hr: () => <hr className="my-6 border-0" />,

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
      <code className="bg-surface px-1 py-0.5 font-mono text-[13px] text-ink">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="thin-scroll mb-3 overflow-x-auto bg-surface px-3 py-2.5 last:mb-0">
      {children}
    </pre>
  ),

  table: ({ children }) => (
    <div className="thin-scroll mb-3 overflow-x-auto last:mb-0">
      <table className="w-full border-collapse text-[14px]">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="border-b border-muted">{children}</thead>,
  th: ({ children }) => (
    <th className="px-2.5 py-1.5 text-left text-[13px] font-medium text-muted">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-t border-surface px-2.5 py-1.5 align-top text-ink">{children}</td>
  ),
};

export default function Markdown({ content }: { content: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  );
}
