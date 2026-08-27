import { FormEvent, useState } from "react";
import "./App.css";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type ChatResponse = {
  message: string;
  interaction_id: string | null;
};

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: crypto.randomUUID(),
      role: "assistant",
      content:
        "Hello! I’m the dental practice assistant. I can help you register, find appointments, book, reschedule, or cancel.",
    },
  ]);

  const [input, setInput] = useState("");
  const [interactionId, setInteractionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedInput = input.trim();

    if (!trimmedInput || isLoading) {
      return;
    }

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmedInput,
    };

    setMessages((current) => [...current, userMessage]);
    setInput("");
    setError(null);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: trimmedInput,
          previous_interaction_id: interactionId,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ?? "The assistant could not process your request.",
        );
      }

      const chatResponse = data as ChatResponse;

      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: chatResponse.message,
        },
      ]);

      setInteractionId(chatResponse.interaction_id);
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "A network error occurred.";

      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  function startNewConversation() {
    setMessages([
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "How can I help you today?",
      },
    ]);
    setInteractionId(null);
    setInput("");
    setError(null);
  }

  return (
    <main className="app-shell">
      <section className="chat-card">
        <header className="chat-header">
          <div>
            <p className="eyebrow">Dental Practice</p>
            <h1>Patient Assistant</h1>
            <p className="status">
              <span className="status-dot" />
              Available now
            </p>
          </div>

          <button
            className="new-chat-button"
            type="button"
            onClick={startNewConversation}
          >
            New conversation
          </button>
        </header>

        <div className="messages" aria-live="polite">
          {messages.map((message) => (
            <div
              className={`message-row ${message.role}`}
              key={message.id}
            >
              <div className="message-bubble">{message.content}</div>
            </div>
          ))}

          {isLoading && (
            <div className="message-row assistant">
              <div className="message-bubble typing">Thinking…</div>
            </div>
          )}
        </div>

        {error && <div className="error-message">{error}</div>}

        <form className="message-form" onSubmit={sendMessage}>
          <label className="sr-only" htmlFor="message">
            Message
          </label>

          <textarea
            id="message"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask about appointments…"
            rows={2}
            disabled={isLoading}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
          />

          <button
            className="send-button"
            type="submit"
            disabled={!input.trim() || isLoading}
          >
            Send
          </button>
        </form>

        <p className="disclaimer">
          For trouble breathing or another life-threatening emergency, call
          911 immediately.
        </p>
      </section>
    </main>
  );
}

export default App;