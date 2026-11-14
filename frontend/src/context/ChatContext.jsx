import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { streamChat } from "../lib/api";

// Hội thoại với trợ lý AI — giữ nguyên khi chuyển trang.

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const conversationId = useRef(null);

  const ask = useCallback(async (question) => {
    const patch = (fn) => setMessages((list) => list.map((m, i) => (i === list.length - 1 ? fn(m) : m)));
    setBusy(true);
    setMessages((l) => [...l, { role: "user", content: question }, { role: "assistant", content: "", status: "Đang gửi câu hỏi…" }]);
    try {
      await streamChat(question, conversationId.current, (ev) => {
        if (ev.type === "stage") patch((m) => ({ ...m, status: ev.label + "…" }));
        else if (ev.type === "delta") patch((m) => ({ ...m, status: "", content: m.content + ev.text }));
        else if (ev.type === "done") {
          conversationId.current = ev.conversation_id;
          patch((m) => ({ ...m, content: ev.answer, citations: ev.citations, suggest: ev.suggest_extension, mode: ev.mode, status: "" }));
        } else if (ev.type === "error") throw new Error(ev.detail);
      });
    } catch (e) {
      patch((m) => ({ ...m, content: e.message, status: "" }));
    } finally {
      setBusy(false);
    }
  }, []);

  const value = useMemo(() => ({ messages, busy, ask }), [messages, busy, ask]);
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export const useChat = () => useContext(ChatContext);
