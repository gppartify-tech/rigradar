import { useEffect, useRef, useState } from "react";
import { Bot, RotateCcw, Send, Sparkles, User as UserIcon } from "lucide-react";
import BuildSummary from "../components/BuildSummary";
import RichText from "../components/RichText";
import { ProductCard } from "../components/ProductCard";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";

const KEY = "rigradar_chat";
const SUGGESTIONS = [
  "I want a gaming PC for about 1200 JOD, mostly Valorant and Warzone at 1440p",
  "What's the cheapest RTX 5060 right now?",
  "Build me a video editing PC for 2000 JD",
  "بدي جهاز ألعاب بميزانية 1000 دينار",
  "Is a Ryzen 7 7800X3D worth it over a Ryzen 5 7600 for gaming?",
];
const ARABIC = /[؀-ۿ]/;

function load() {
  try {
    return JSON.parse(sessionStorage.getItem(KEY)) || [];
  } catch {
    return [];
  }
}

function Message({ message }) {
  const isUser = message.role === "user";
  const dir = ARABIC.test(message.content) ? "rtl" : "ltr";
  const products = Object.fromEntries((message.products || []).map((p) => [String(p.id), p]));
  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${isUser ? "bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300" : "bg-indigo-600 text-white"}`}>
        {isUser ? <UserIcon className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div className={`min-w-0 max-w-[85%] space-y-3 ${isUser ? "items-end" : ""}`}>
        <div
          dir={dir}
          className={`rounded-2xl px-4 py-3 text-sm ${isUser ? "rounded-tr-sm bg-indigo-600 text-white" : "rounded-tl-sm border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 shadow-sm"}`}
        >
          {isUser ? <p className="whitespace-pre-wrap">{message.content}</p> : <RichText text={message.content} products={products} />}
        </div>
        {message.build && <BuildSummary build={message.build} />}
        {!message.build && message.products?.length > 0 && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {message.products.slice(0, 6).map((p) => <ProductCard key={p.id} product={p} />)}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Assistant() {
  const [messages, setMessages] = useState(load);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const bottom = useRef(null);
  const { data: meta } = useApi("/meta");

  useEffect(() => {
    try {
      sessionStorage.setItem(KEY, JSON.stringify(messages.slice(-30)));
    } catch {
      /* ignore */
    }
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  const send = async (text) => {
    const content = text.trim();
    if (!content || busy) return;
    const next = [...messages, { role: "user", content }];
    setMessages(next);
    setInput("");
    setBusy(true);
    setError(null);
    try {
      const res = await api("/chat", {
        method: "POST",
        body: { messages: next.map(({ role, content: c }) => ({ role, content: c })) },
      });
      setMessages([...next, { role: "assistant", content: res.reply, products: res.products, build: res.build, mode: res.mode }]);
    } catch (err) {
      setError(err.message);
      setMessages(next);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex h-[calc(100vh-4rem)] max-w-4xl flex-col px-4">
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 py-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-indigo-600 p-2 text-white"><Bot className="h-5 w-5" /></div>
          <div>
            <h1 className="font-bold">PC build assistant</h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {meta?.chat_ai_enabled ? "Powered by Claude · " : "Offline mode (rule-based) · "}
              uses live prices from 3 Jordanian stores
            </p>
          </div>
        </div>
        {messages.length > 0 && (
          <button className="btn btn-ghost btn-sm" onClick={() => setMessages([])}>
            <RotateCcw className="h-4 w-4" /> New chat
          </button>
        )}
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto py-6">
        {messages.length === 0 && (
          <div className="py-8 text-center">
            <Sparkles className="mx-auto h-10 w-10 text-indigo-500" />
            <h2 className="mt-3 text-xl font-bold">What are you building?</h2>
            <p className="mx-auto mt-1 max-w-md text-sm text-slate-500 dark:text-slate-400">
              Tell me your budget, what you'll use the PC for and any parts you already have. I'll suggest compatible parts
              with today's best prices. English or Arabic both work.
            </p>
            <div className="mx-auto mt-6 grid max-w-2xl gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  dir={ARABIC.test(s) ? "rtl" : "ltr"}
                  className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 py-3 text-left text-sm text-slate-700 dark:text-slate-200 shadow-sm transition hover:border-indigo-300 dark:hover:border-indigo-500/40 hover:bg-indigo-50/40 dark:hover:bg-indigo-500/10"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => <Message key={i} message={m} />)}
        {busy && (
          <div className="flex gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-600 text-white"><Bot className="h-4 w-4" /></div>
            <div className="flex items-center gap-1 rounded-2xl rounded-tl-sm border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 py-3" aria-label="Assistant is typing">
              <span className="typing-dot h-2 w-2 rounded-full bg-slate-400" />
              <span className="typing-dot h-2 w-2 rounded-full bg-slate-400" />
              <span className="typing-dot h-2 w-2 rounded-full bg-slate-400" />
            </div>
          </div>
        )}
        {error && <p className="text-center text-sm text-rose-600 dark:text-rose-400">{error}</p>}
        <div ref={bottom} />
      </div>

      <form
        className="border-t border-slate-200 dark:border-slate-800 py-4"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <div className="flex items-end gap-2 rounded-2xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 p-2 shadow-sm focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
            dir="auto"
            rows={1}
            maxLength={2000}
            placeholder="e.g. Gaming PC for 1500 JOD, I already have a case and SSD"
            className="max-h-40 flex-1 resize-none border-0 bg-transparent px-2 py-1.5 text-sm focus:outline-none"
            aria-label="Message"
          />
          <button className="btn btn-primary rounded-xl px-3" disabled={busy || !input.trim()} aria-label="Send">
            <Send className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-2 text-center text-xs text-slate-400">The assistant can make mistakes. Check prices and compatibility before you buy.</p>
      </form>
    </div>
  );
}
