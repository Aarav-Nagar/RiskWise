import { useState } from "react";
import styled from "styled-components";
import api from "../lib/api.js";
import { Card, Eyebrow, Header, HeaderText, Page, Subtitle, Title } from "../components/PagePrimitives.jsx";

const ChatShell = styled(Card)`
  display: grid;
  grid-template-rows: 1fr auto;
  min-height: 540px;
`;

const Messages = styled.div`
  display: grid;
  align-content: start;
  gap: 14px;
  max-height: 420px;
  overflow: auto;
  padding-right: 8px;
`;

const Bubble = styled.div`
  justify-self: ${({ role }) => (role === "user" ? "end" : "start")};
  max-width: min(80%, 640px);
  padding: 14px 16px;
  border-radius: 20px;
  background: ${({ role }) =>
    role === "user"
      ? "linear-gradient(135deg, var(--accent), #4194df)"
      : "rgba(20, 34, 56, 0.95)"};
  color: ${({ role }) => (role === "user" ? "#08111f" : "var(--text)")};
  line-height: 1.65;
`;

const Composer = styled.form`
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  margin-top: 18px;
`;

const Input = styled.input`
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: rgba(6, 14, 25, 0.8);
  color: var(--text);
`;

const Button = styled.button`
  padding: 14px 18px;
  border: 0;
  border-radius: 16px;
  color: #08111f;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  font-weight: 800;
  cursor: pointer;
`;

export default function ChatPage() {
  const [messages, setMessages] = useState([
    {
      id: crypto.randomUUID(),
      role: "assistant",
      text: "Ask me about P/E ratio, beta, implied volatility, moving averages, momentum, or the Sharpe ratio."
    }
  ]);
  const [draft, setDraft] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    if (!draft.trim()) {
      return;
    }

    const userMessage = { id: crypto.randomUUID(), role: "user", text: draft.trim() };
    setMessages((current) => [...current, userMessage]);
    setDraft("");

    const response = await api.post("/chat", { message: userMessage.text });
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "assistant", text: response.data.message }
    ]);
  }

  return (
    <Page>
      <Header>
        <HeaderText>
          <Eyebrow>Page 4</Eyebrow>
          <Title>Finance Chat</Title>
          <Subtitle>
            This chat route is intentionally backend-driven so you can swap the hardcoded knowledge
            base for an OpenAI-powered assistant later without redesigning the UI contract.
          </Subtitle>
        </HeaderText>
      </Header>

      <ChatShell>
        <Messages>
          {messages.map((message) => (
            <Bubble key={message.id} role={message.role}>
              {message.text}
            </Bubble>
          ))}
        </Messages>

        <Composer onSubmit={handleSubmit}>
          <Input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="What is implied volatility?"
          />
          <Button type="submit">Send</Button>
        </Composer>
      </ChatShell>
    </Page>
  );
}
