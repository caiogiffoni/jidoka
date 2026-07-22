import ReactMarkdown from "react-markdown";

// Hand-rolled prose styling (no @tailwindcss/typography dependency) for
// rendering Markdown body text - kept in the same minimal, no-extra-library
// spirit as the hand-rolled chart in weekly-bar-chart.tsx.
export function MarkdownText({ text }: { text: string }) {
  return (
    <div
      className="text-sm leading-relaxed break-words
        [&_h1]:mt-3 [&_h1]:text-base [&_h1]:font-semibold [&_h1]:first:mt-0
        [&_h2]:mt-3 [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:first:mt-0
        [&_h3]:mt-2 [&_h3]:text-sm [&_h3]:font-medium [&_h3]:first:mt-0
        [&_p]:mt-2 [&_p]:first:mt-0
        [&_ul]:mt-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:mt-2 [&_ol]:list-decimal [&_ol]:pl-5
        [&_li]:mt-0.5
        [&_a]:text-primary [&_a]:underline [&_a]:underline-offset-3 [&_a:hover]:text-foreground
        [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-xs
        [&_pre]:mt-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-muted [&_pre]:p-2.5 [&_pre_code]:bg-transparent [&_pre_code]:p-0
        [&_blockquote]:mt-2 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground [&_blockquote]:italic
        [&_hr]:my-3 [&_hr]:border-border"
    >
      <ReactMarkdown>{text}</ReactMarkdown>
    </div>
  );
}
