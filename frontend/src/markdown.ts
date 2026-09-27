// Markdown for lesson text, with Python code blocks syntax-highlighted.
// Lesson text can come from teachers (the admin), so the HTML is sanitized.

import DOMPurify from "dompurify";
import { classHighlighter, highlightCode } from "@lezer/highlight";
import { parser } from "@lezer/python";
import { Marked } from "marked";

const escape = (text: string) =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export function highlightPython(code: string): string {
  let html = "";
  highlightCode(
    code,
    parser.parse(code),
    classHighlighter,
    (text, classes) => {
      html += classes ? `<span class="${classes}">${escape(text)}</span>` : escape(text);
    },
    () => {
      html += "\n";
    },
  );
  return html;
}

const marked = new Marked({
  renderer: {
    code({ text, lang }) {
      const body = !lang || lang === "python" || lang === "py" ? highlightPython(text) : escape(text);
      return `<pre class="code-block"><code>${body}</code></pre>`;
    },
  },
});

export function markdown(text: string) {
  return { __html: DOMPurify.sanitize(marked.parse(text, { async: false })) };
}
