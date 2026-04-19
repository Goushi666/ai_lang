import DOMPurify from "dompurify";
import MarkdownIt from "markdown-it";

const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
});

/**
 * 将 Markdown 转为可安全插入 v-html 的 HTML（防 XSS）。
 */
export function renderMarkdown(text) {
  if (text == null || text === "") return "";
  const raw = md.render(String(text));
  return DOMPurify.sanitize(raw, {
    ADD_ATTR: ["target"],
  });
}
