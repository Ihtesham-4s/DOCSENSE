import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const API_BASE = 'http://localhost:8000';

const starterPrompts = [
  'Summarize the key points',
  'What are the main topics?',
  'Explain the conclusion',
];

function App() {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Upload a PDF and ask a question. DocSense will answer from the document and show the source chunks it used.',
      sources: [],
      createdAt: new Date(),
    },
  ]);
  const [question, setQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState('Ready');
  const [uploading, setUploading] = useState(false);
  const [uploadingFileName, setUploadingFileName] = useState('');
  const [openSources, setOpenSources] = useState({});
  const [errorBanner, setErrorBanner] = useState('');
  const fileInputRef = useRef(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, isLoading, uploading]);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(`${API_BASE}/health`);
        if (!response.ok) {
          setStatus('Backend is up, but the vector store is not ready yet');
          return;
        }

        const data = await response.json();
        setStatus(data.vector_store_ready ? 'Backend connected' : 'Backend ready, upload a PDF to begin');
      } catch {
        setStatus('Backend offline');
      }
    };

    checkHealth();
  }, []);

  const canSend = useMemo(() => question.trim().length > 0 && !isLoading && !uploading, [question, isLoading, uploading]);

  const addMessage = (message) => {
    setMessages((current) => [...current, message]);
  };

  const sendQuestion = async (nextQuestion) => {
    const text = (nextQuestion ?? question).trim();
    if (!text || isLoading) {
      return;
    }

    setErrorBanner('');
    addMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      sources: [],
      createdAt: new Date(),
    });
    setQuestion('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text }),
      });

      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        const detail = payload.detail || 'The question could not be answered right now.';
        addMessage({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: detail,
          sources: [],
          createdAt: new Date(),
          isError: true,
        });
        return;
      }

      addMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: payload.answer || 'I could not find the answer in the document.',
        sources: payload.sources || [],
        createdAt: new Date(),
      });
    } catch {
      setErrorBanner('The backend is not reachable. Start the FastAPI server and try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setUploading(true);
    setUploadingFileName(file.name);
    setErrorBanner('');
    setStatus(`Uploading ${file.name}...`);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      });

      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(payload.detail || 'Upload failed');
      }

      addMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `Upload complete. ${file.name} was indexed into Chroma (${payload.chunks_created} chunks created).`,
        sources: [],
        createdAt: new Date(),
      });
      setStatus(`Upload complete: ${file.name}`);
    } catch (error) {
      setErrorBanner(error instanceof Error ? error.message : 'Upload failed');
      setStatus('Upload failed');
    } finally {
      setUploading(false);
      setUploadingFileName('');
      event.target.value = '';
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">DocSense</div>
          <h1>Document chat</h1>
        </div>

        <div className="topbar-actions">
          <span className={`status-pill ${status.includes('offline') ? 'is-warn' : ''}`}>{status}</span>
          <button className="ghost-button" type="button" onClick={() => fileInputRef.current?.click()}>
            Upload PDF
          </button>
          <input ref={fileInputRef} type="file" accept="application/pdf" className="hidden-input" onChange={handleUpload} />
        </div>
      </header>

      <main className="chat-panel">
        <section className="message-list" aria-live="polite">
          {messages.map((message) => (
            <MessageCard
              key={message.id}
              message={message}
              sourcesOpen={Boolean(openSources[message.id])}
              onToggleSources={() =>
                setOpenSources((current) => ({
                  ...current,
                  [message.id]: !current[message.id],
                }))
              }
            />
          ))}

          {isLoading ? <TypingIndicator /> : null}
          <div ref={bottomRef} />
        </section>
      </main>

      <footer className="composer">
        <div className="composer-inner">
          <div className="prompt-row">
            {starterPrompts.map((prompt) => (
              <button key={prompt} type="button" className="chip" onClick={() => sendQuestion(prompt)} disabled={isLoading || uploading}>
                {prompt}
              </button>
            ))}
          </div>

          {uploading ? (
            <article className="message is-assistant">
              <div className="message-bubble typing">
                <span>{uploadingFileName ? `Uploading ${uploadingFileName}` : 'Uploading PDF'}</span>
                <div className="dots" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </article>
          ) : null}

          {errorBanner ? <div className="error-banner">{errorBanner}</div> : null}

          <div className="composer-bar">
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask a question about the document..."
              rows={1}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  sendQuestion();
                }
              }}
            />

            <button type="button" className="send-button" onClick={() => sendQuestion()} disabled={!canSend}>
              Send
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
}

function MessageCard({ message, sourcesOpen, onToggleSources }) {
  const timestamp = new Intl.DateTimeFormat([], {
    hour: '2-digit',
    minute: '2-digit',
  }).format(message.createdAt);

  return (
    <article className={`message ${message.role === 'user' ? 'is-user' : 'is-assistant'} ${message.isError ? 'is-error' : ''}`}>
      <div className="message-bubble">
        <div className="message-text">{message.content}</div>
        <div className="message-meta">
          <span>{message.role === 'user' ? 'You' : 'DocSense'}</span>
          <span>{timestamp}</span>
        </div>

        {message.role === 'assistant' && message.sources?.length ? (
          <div className="sources-block">
            <button type="button" className="sources-toggle" onClick={onToggleSources}>
              <span>Sources used</span>
              <span>{sourcesOpen ? 'Hide' : `${message.sources.length}`}</span>
            </button>

            {sourcesOpen ? (
              <div className="sources-list">
                {message.sources.map((source, index) => (
                  <div key={`${message.id}-source-${index}`} className="source-card">
                    <div className="source-label">
                      {source.source ? source.source.split(/[/\\]/).pop() : 'Source'}
                      {typeof source.page === 'number' ? ` · Page ${source.page + 1}` : ''}
                    </div>
                    <p>{source.content}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </article>
  );
}

function TypingIndicator() {
  return (
    <article className="message is-assistant">
      <div className="message-bubble typing">
        <span>Thinking</span>
        <div className="dots" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </div>
    </article>
  );
}

createRoot(document.getElementById('root')).render(<App />);
