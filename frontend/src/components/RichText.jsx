import { Fragment } from "react";
import { Link } from "react-router";
import { formatPrice } from "../lib/format";

// Renders assistant replies: line breaks, "- " bullet lists, **bold**,
// and [[product:ID]] references turned into small product links.
// Everything is rendered as React text nodes - no HTML injection is possible.

function inline(text, products, keyPrefix) {
  const parts = text.split(/(\[\[product:\d+\]\]|\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    const ref = part.match(/^\[\[product:(\d+)\]\]$/);
    if (ref) {
      const product = products?.[ref[1]];
      if (!product) return null;
      return (
        <Link
          key={key}
          to={`/product/${product.id}`}
          className="mx-0.5 inline-flex items-center gap-1 rounded-md bg-indigo-50 px-1.5 py-0.5 align-baseline text-xs font-semibold text-indigo-700 hover:bg-indigo-100"
        >
          {formatPrice(product.best_price)}
        </Link>
      );
    }
    const bold = part.match(/^\*\*([^*]+)\*\*$/);
    if (bold) return <strong key={key}>{bold[1]}</strong>;
    return <Fragment key={key}>{part}</Fragment>;
  });
}

export default function RichText({ text, products }) {
  const lines = text.split("\n");
  const blocks = [];
  let list = [];
  const flush = () => {
    if (list.length) {
      blocks.push(
        <ul key={`ul-${blocks.length}`} className="my-1 list-disc space-y-1 ps-5">
          {list.map((item, i) => (
            <li key={i}>{inline(item, products, `li-${blocks.length}-${i}`)}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };
  lines.forEach((line, i) => {
    const bullet = line.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)$/);
    if (bullet) {
      list.push(bullet[1]);
      return;
    }
    flush();
    if (line.trim() === "") return;
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    blocks.push(
      <p key={`p-${i}`} className={heading ? "mt-2 font-semibold" : ""}>
        {inline(heading ? heading[1] : line, products, `p-${i}`)}
      </p>,
    );
  });
  flush();
  return <div className="space-y-2 leading-relaxed">{blocks}</div>;
}
