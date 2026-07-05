"use client";
import { useState } from 'react';

type ContextChunk = {
  score?: number;
  content?: string;
  metadata?: {
    title?: string;
    source?: string;
    page?: string | number;
  };
};

type ChatMessage = {
  role: string;
  content: string;
  msgChunks?: ContextChunk[];
};

export default function ChatPage() {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chunks, setChunks] = useState<ContextChunk[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!query.trim()) return;
    
    const userMsg = query;
    setQuery('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);
    setChunks([]);

    try {
      const res = await fetch('http://localhost:8000/api/ask/foundry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg })
      });
      
      const data: { answer?: string; detail?: string; context?: ContextChunk[] } = await res.json();
      const newChunks = Array.isArray(data.context) ? data.context : [];
      const answer = data.answer || data.detail || 'No se recibió respuesta del agente.';
      setMessages(prev => [...prev, { role: 'assistant', content: answer, msgChunks: newChunks }]);
      setChunks(newChunks);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Error al conectar con Foundry.' }]);
    } finally {
      setLoading(false);
    }
  };

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
            <div style={{ textAlign: 'center', color: 'var(--text-secondary)', marginTop: '2rem' }}>
              Escribe una pregunta sobre la misión a Marte para comenzar.
            </div>
          )}
          {messages.map((m, i) => {
            let counter = 1;
            const uniqueCitations = new Map();
            
            const formatContent = (text: string) => {
              let formatted = text.replace(/【\d+:\d+†source】/g, (match) => {
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
            const hasSourceList = m.role === 'assistant' && (messageChunks.length > 0 || citationsCount > 0);

            return (
              <div key={i} style={{ alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '80%' }}>
                <div style={{ 
                  background: m.role === 'user' ? 'linear-gradient(135deg, var(--primary-accent), #8c7ae6)' : 'rgba(255,255,255,0.05)',
                  padding: '1rem 1.25rem',
                  borderRadius: m.role === 'user' ? '16px 16px 0 16px' : '16px 16px 16px 0',
                  border: m.role === 'user' ? 'none' : '1px solid var(--border-glass)',
                  lineHeight: 1.5
                }}>
                  <div dangerouslySetInnerHTML={{ __html: htmlContent }} />
                  
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
          {loading && (
            <div style={{ alignSelf: 'flex-start', color: 'var(--secondary-accent)' }}>El agente está pensando...</div>
          )}
        </div>

        <div style={{ padding: '1.5rem', borderTop: '1px solid var(--border-glass)' }}>
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
            <div key={i} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.7rem', color: '#00d2d3', background: 'rgba(0,210,211,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
                  Score: {chunk.score ? chunk.score.toFixed(4) : 'N/A'}
                </span>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
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
