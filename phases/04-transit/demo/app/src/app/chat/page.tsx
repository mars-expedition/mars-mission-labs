"use client";
import { useState } from 'react';

type ContextChunk = {
  rank?: number;
  score?: number | null;
  score_type?: string;
  content?: string;
  metadata?: {
    title?: string;
    source?: string;
    page?: string | number;
  };
};

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  msgChunks?: ContextChunk[];
  isComplete?: boolean;
};

type FoundryStreamPayload = {
  delta?: string;
  answer?: string;
  detail?: string;
  context?: ContextChunk[];
};

type ParsedSseEvent = {
  event: string;
  data: FoundryStreamPayload;
};

const API_BASE_URL = 'http://localhost:8000';

const createId = (prefix: string) =>
  `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;

const escapeHtml = (text: string) =>
  text.replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[char] || char));

const parseSseEvent = (rawEvent: string): ParsedSseEvent | null => {
  const lines = rawEvent.split(/\r?\n/);
  let event = 'message';
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (dataLines.length === 0) return null;

  try {
    return {
      event,
      data: JSON.parse(dataLines.join('\n')) as FoundryStreamPayload,
    };
  } catch {
    return null;
  }
};

const formatScore = (score?: number | null) => {
  if (typeof score !== 'number' || !Number.isFinite(score)) {
    return 'Sin score';
  }
  return score.toFixed(4);
};

const scoreLabel = (scoreType?: string) => {
  if (scoreType === 'reranker_score') return 'Rerank';
  if (scoreType === 'search_score') return 'Search';
  return 'Score';
};

const SUGGESTED_QUERIES = [
  {
    tag: 'Caso 1: RAG Conceptual',
    label: '🔬 Instrumentos y vida en rocas',
    query: '¿Qué instrumentos lleva Perseverance para detectar rastros de vida en las rocas?',
  },
  {
    tag: 'Intro',
    label: '🚀 ¿Qué es el Perseverance?',
    query: '¿Qué es el Perseverance?',
  },
  {
    tag: 'Caso 2: Cráter Jezero',
    label: '🪐 Misión en cráter Jezero',
    query: '¿Qué misión busca señales de vida antigua en el cráter Jezero?',
  },
  {
    tag: 'Caso 3: Fuera de Dominio',
    label: '🍕 Menú de la NASA (Límites)',
    query: '¿Cuál es el menú del comedor de la NASA?',
  },
];

export default function ChatPage() {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chunks, setChunks] = useState<ContextChunk[]>([]);
  const [loading, setLoading] = useState(false);

  const updateAssistantMessage = (
    messageId: string,
    update: Partial<ChatMessage> | ((message: ChatMessage) => ChatMessage)
  ) => {
    setMessages((prev) => prev.map((message) => {
      if (message.id !== messageId) return message;
      return typeof update === 'function' ? update(message) : { ...message, ...update };
    }));
  };

  const handleSend = async (overrideQuery?: string) => {
    const userMsg = (typeof overrideQuery === 'string' ? overrideQuery : query).trim();
    if (!userMsg || loading) return;

    const assistantId = createId('assistant');
    setQuery('');
    setMessages((prev) => [
      ...prev,
      { id: createId('user'), role: 'user', content: userMsg },
      { id: assistantId, role: 'assistant', content: '', msgChunks: [], isComplete: false },
    ]);
    setLoading(true);
    setChunks([]);

    let streamedAnswer = '';
    let latestChunks: ContextChunk[] = [];
    let previewChunksShown = false;
    let answerMarkedComplete = false;
    let sourcesShownAtAnswerDone = false;

    try {
      const res = await fetch(`${API_BASE_URL}/api/ask/foundry/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg, top_k: 3 }),
      });

      if (!res.ok || !res.body) {
        throw new Error('No se pudo abrir el stream del agente.');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      const handleEvent = (rawEvent: string) => {
        const parsed = parseSseEvent(rawEvent);
        if (!parsed) return;

        if (parsed.event === 'context') {
          const newChunks = Array.isArray(parsed.data.context) ? parsed.data.context : [];
          if (newChunks.length > 0) {
            latestChunks = newChunks;
            previewChunksShown = true;
            setChunks(newChunks);
          }
          return;
        }

        if (parsed.event === 'delta' && parsed.data.delta) {
          streamedAnswer += parsed.data.delta;
          updateAssistantMessage(assistantId, { content: streamedAnswer });
          return;
        }

        if (parsed.event === 'answer_done') {
          const doneChunks = Array.isArray(parsed.data.context) && parsed.data.context.length > 0
            ? parsed.data.context
            : latestChunks;
          answerMarkedComplete = true;
          sourcesShownAtAnswerDone = doneChunks.length > 0;
          updateAssistantMessage(assistantId, {
            msgChunks: doneChunks,
            isComplete: true,
          });
          return;
        }

        if (parsed.event === 'final') {
          const newChunks = Array.isArray(parsed.data.context) ? parsed.data.context : [];
          const answer = parsed.data.answer || streamedAnswer || 'No se recibió respuesta del agente.';
          streamedAnswer = answer;
          latestChunks = newChunks.length > 0 ? newChunks : latestChunks;
          if (!previewChunksShown) {
            setChunks(latestChunks);
          }
          if (answerMarkedComplete) {
            updateAssistantMessage(assistantId, sourcesShownAtAnswerDone
              ? { content: answer }
              : { content: answer, msgChunks: latestChunks, isComplete: true }
            );
          } else {
            answerMarkedComplete = true;
            updateAssistantMessage(assistantId, {
              content: answer,
              msgChunks: latestChunks,
              isComplete: true,
            });
          }
          return;
        }

        if (parsed.event === 'error') {
          throw new Error(parsed.data.detail || 'Error al consultar Foundry.');
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split(/\r?\n\r?\n/);
        buffer = events.pop() || '';
        events.forEach(handleEvent);
      }

      if (buffer.trim()) {
        handleEvent(buffer);
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'Error al conectar con Foundry.';
      updateAssistantMessage(assistantId, {
        content: `Error al conectar con Foundry. ${detail}`,
        msgChunks: [],
        isComplete: true,
      });
      setChunks([]);
    } finally {
      setLoading(false);
    }
  };

  const lastAssistant = [...messages].reverse().find((message) => message.role === 'assistant');
  const showThinking = loading && !lastAssistant?.isComplete;

  return (
    <div style={{ height: 'calc(100vh - 4rem)', display: 'flex', gap: '2rem' }}>
      
      {/* LEFT PANEL: Chat */}
      <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--border-glass)' }}>
          <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '1.5rem' }}>🤖</span> Agente Nativo (Foundry)
          </h2>
        </div>
        
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {messages.length === 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '1.25rem', textAlign: 'center', padding: '1rem' }}>
              <div style={{ fontSize: '2.5rem' }}>🪐</div>
              <div>
                <h3 style={{ fontSize: '1.3rem', color: 'var(--text-primary)', marginBottom: '0.4rem' }}>Asistente RAG con Azure AI Foundry</h3>
                <p style={{ color: 'var(--text-secondary)', maxWidth: '520px', fontSize: '0.9rem', lineHeight: 1.5 }}>
                  Haz clic en una de las preguntas de prueba preparadas para la demo o escribe una consulta personalizada:
                </p>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.75rem', width: '100%', maxWidth: '640px', marginTop: '0.5rem' }}>
                {SUGGESTED_QUERIES.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    disabled={loading}
                    onClick={() => handleSend(item.query)}
                    className="glass-panel"
                    style={{
                      padding: '0.85rem 1rem',
                      textAlign: 'left',
                      cursor: loading ? 'not-allowed' : 'pointer',
                      border: '1px solid var(--border-glass)',
                      background: 'rgba(255,255,255,0.03)',
                      color: 'var(--text-primary)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                      transition: 'all 0.2s ease',
                      outline: 'none',
                    }}
                    onMouseEnter={(e) => {
                      if (!loading) {
                        e.currentTarget.style.transform = 'translateY(-2px)';
                        e.currentTarget.style.borderColor = 'var(--secondary-accent)';
                        e.currentTarget.style.background = 'rgba(0, 210, 211, 0.08)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'translateY(0)';
                      e.currentTarget.style.borderColor = 'var(--border-glass)';
                      e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
                    }}
                  >
                    <span style={{ fontSize: '0.68rem', color: 'var(--secondary-accent)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                      {item.tag}
                    </span>
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {item.label}
                    </span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.3 }}>
                      {item.query}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => {
            let counter = 1;
            const uniqueCitations = new Map<string, number>();
            
            const formatContent = (text: string) => {
              let formatted = escapeHtml(text).replace(/【\d+:\d+†source】/g, (match) => {
                if (!uniqueCitations.has(match)) {
                  uniqueCitations.set(match, counter++);
                }
                const num = uniqueCitations.get(match);
                return `<sup style="color: var(--secondary-accent); font-weight: bold; margin: 0 2px;">[${num}]</sup>`;
              });
              formatted = formatted.replace(/\n/g, '<br/>');
              return formatted;
            };

            const htmlContent = formatContent(m.content);
            const citationsCount = uniqueCitations.size;
            const messageChunks = m.msgChunks || [];
            const hasSourceList = m.role === 'assistant' && m.isComplete && (messageChunks.length > 0 || citationsCount > 0);

            return (
              <div key={m.id} style={{ alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '80%' }}>
                <div style={{ 
                  background: m.role === 'user' ? 'linear-gradient(135deg, var(--primary-accent), #8c7ae6)' : 'rgba(255,255,255,0.05)',
                  padding: '1rem 1.25rem',
                  borderRadius: m.role === 'user' ? '16px 16px 0 16px' : '16px 16px 16px 0',
                  border: m.role === 'user' ? 'none' : '1px solid var(--border-glass)',
                  lineHeight: 1.5
                }}>
                  <div dangerouslySetInnerHTML={{ __html: htmlContent || (loading && m.role === 'assistant' ? 'Conectando con Foundry...' : '') }} />
                  
                  {hasSourceList && (
                    <div style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.1)', fontSize: '0.8rem' }}>
                      <strong style={{ color: 'var(--text-secondary)' }}>Fuentes referenciadas:</strong>
                      <ul style={{ paddingLeft: '1.5rem', marginTop: '0.5rem', color: 'var(--text-secondary)' }}>
                        {(messageChunks.length > 0 ? messageChunks : Array.from(uniqueCitations.values()).map(() => null)).map((chunk, idx) => {
                          const num = idx + 1;
                          const title = chunk?.metadata?.title || 'Documento recuperado de la base de datos';
                          const url = chunk?.metadata?.source || '#';
                          const page = chunk?.metadata?.page ? `, pág. ${chunk.metadata.page}` : '';
                          return (
                            <li key={idx} style={{ marginBottom: '4px' }}>
                              <span style={{ color: 'var(--secondary-accent)' }}>[{num}]</span>{' '}
                              <a href={url} target="_blank" rel="noreferrer" style={{ color: '#a29bfe', textDecoration: 'none' }}>
                                {title}{page}
                              </a>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          {showThinking && (
            <div style={{ alignSelf: 'flex-start', color: 'var(--secondary-accent)' }}>El agente está pensando...</div>
          )}
        </div>

        <div style={{ padding: '1rem 1.5rem', borderTop: '1px solid var(--border-glass)', background: 'rgba(15, 17, 26, 0.5)' }}>
          {/* Burbujas de acceso rápido para la demo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--secondary-accent)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              💡 Demo:
            </span>
            {SUGGESTED_QUERIES.map((item, idx) => (
              <button
                key={idx}
                type="button"
                disabled={loading}
                onClick={() => handleSend(item.query)}
                style={{
                  background: 'rgba(108, 92, 231, 0.15)',
                  border: '1px solid rgba(108, 92, 231, 0.35)',
                  color: '#e4e7eb',
                  borderRadius: '20px',
                  padding: '5px 12px',
                  fontSize: '0.78rem',
                  fontWeight: 500,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  transition: 'all 0.2s ease',
                  opacity: loading ? 0.6 : 1,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  outline: 'none',
                }}
                onMouseEnter={(e) => {
                  if (!loading) {
                    e.currentTarget.style.background = 'rgba(108, 92, 231, 0.35)';
                    e.currentTarget.style.borderColor = 'var(--secondary-accent)';
                    e.currentTarget.style.color = '#ffffff';
                    e.currentTarget.style.transform = 'translateY(-1px)';
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'rgba(108, 92, 231, 0.15)';
                  e.currentTarget.style.borderColor = 'rgba(108, 92, 231, 0.35)';
                  e.currentTarget.style.color = '#e4e7eb';
                  e.currentTarget.style.transform = 'translateY(0)';
                }}
                title={item.query}
              >
                {item.label}
              </button>
            ))}
          </div>

          <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} style={{ display: 'flex', gap: '1rem' }}>
            <input 
              type="text" 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Pregúntale algo al agente..." 
              style={{ flex: 1, background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-glass)', color: 'white', padding: '12px 16px', borderRadius: '8px', outline: 'none' }}
            />
            <button type="submit" className="btn-primary" disabled={loading}>Enviar</button>
          </form>
        </div>
      </div>

      {/* RIGHT PANEL: Chunks Visualizer */}
      <div className="glass-panel" style={{ width: '400px', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'rgba(15, 17, 26, 0.4)' }}>
        <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--border-glass)' }}>
          <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--secondary-accent)' }}>Fragmentos Recuperados</h3>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>Lo que el agente ve en su base de datos</p>
        </div>
        
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {chunks.length === 0 && !loading && (
            <div style={{ textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '2rem' }}>
              Los fragmentos aparecerán aquí al enviar una pregunta.
            </div>
          )}
          {chunks.map((chunk, i) => (
            <div key={`${chunk.metadata?.source || 'chunk'}-${chunk.metadata?.page || i}-${i}`} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', gap: '8px' }}>
                <span style={{ fontSize: '0.7rem', color: '#00d2d3', background: 'rgba(0,210,211,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
                  {scoreLabel(chunk.score_type)}: {formatScore(chunk.score)}
                </span>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                  Pág: {chunk.metadata?.page || '-'}
                </span>
              </div>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '8px' }}>
                {chunk.content || 'Sin contenido de fragmento.'}
              </p>
              <div style={{ fontSize: '0.75rem' }}>
                <a href={chunk.metadata?.source} target="_blank" rel="noreferrer" style={{ color: '#a29bfe', textDecoration: 'none' }}>
                  🔗 {chunk.metadata?.title || 'Documento Original'}
                </a>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
