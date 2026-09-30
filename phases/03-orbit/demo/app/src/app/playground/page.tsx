"use client";
import { useState } from 'react';

type ContextChunk = {
  score?: number;
  content?: string;
  page_content?: string;
  metadata?: {
    title?: string;
    source?: string;
    page?: string | number;
  };
};

type AskResult = {
  answer: string;
  context: ContextChunk[];
  error?: boolean;
};

export default function PlaygroundPage() {
  const [query, setQuery] = useState('¿Qué misión busca señales de vida antigua en el cráter Jezero?');
  const [loading, setLoading] = useState(false);
  const [resultSimple, setResultSimple] = useState<AskResult | null>(null);
  const [resultRerank, setResultRerank] = useState<AskResult | null>(null);

  const askLocal = async (useRerank: boolean): Promise<AskResult> => {
    const res = await fetch('http://localhost:8000/api/ask/local', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, top_k: 3, use_rerank: useRerank })
    });

    const data: { answer?: string; detail?: string; context?: unknown } = await res.json();
    if (!res.ok) {
      return {
        answer: data.detail || 'Error al consultar el backend.',
        context: [],
        error: true
      };
    }

    return {
      answer: data.answer || '',
      context: Array.isArray(data.context) ? data.context : []
    };
  };

  const getChunkText = (chunk: ContextChunk) => chunk.content || chunk.page_content || '';

  const runComparison = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setResultSimple(null);
    setResultRerank(null);

    try {
      // Petición RAG Simple (sin rerank)
      const p1 = askLocal(false);

      // Petición RAG con Semantic Reranker
      const p2 = askLocal(true);

      const [resSimple, resRerank] = await Promise.all([p1, p2]);
      setResultSimple(resSimple);
      setResultRerank(resRerank);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto', paddingTop: '1rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2rem' }}>Playground: Impacto del Semantic Reranker</h1>
        <p style={{ color: 'var(--text-secondary)' }}>
          Escribe una pregunta problemática (ej. palabras clave engañosas) y observa cómo el Reranker Semántico de Azure ordena los documentos vs. la Búsqueda Vectorial Simple.
        </p>
      </header>

      <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
        <input 
          type="text" 
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Escribe tu pregunta..." 
          style={{ flex: 1, background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-glass)', color: 'white', padding: '14px 20px', borderRadius: '8px', outline: 'none', fontSize: '1.1rem' }}
        />
        <button className="btn-primary" onClick={runComparison} disabled={loading} style={{ padding: '0 30px' }}>
          {loading ? 'Comparando...' : 'Comparar Resultados'}
        </button>
      </div>

      <div style={{ display: 'flex', gap: '2rem', minHeight: '500px' }}>
        
        {/* COLUMNA IZQUIERDA: Simple */}
        <div className="glass-panel" style={{ flex: 1, padding: '2rem', borderTop: '4px solid #ff7675' }}>
          <h2 style={{ fontSize: '1.25rem', color: '#ff7675', marginBottom: '1rem' }}>❌ Búsqueda Vectorial Pura (Sin Rerank)</h2>
          
          {resultSimple && (
            <>
              <div style={{ background: 'rgba(255,118,117,0.1)', padding: '1.5rem', borderRadius: '8px', marginBottom: '2rem', border: '1px solid rgba(255,118,117,0.2)' }}>
                <strong>Respuesta del LLM:</strong>
                <p style={{ marginTop: '0.5rem', lineHeight: 1.5 }}>{resultSimple.answer}</p>
              </div>
              
              <h4 style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>Fragmentos Recuperados (Top 3)</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {resultSimple.context.map((c, i) => (
                  <div key={i} style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '8px', fontSize: '0.85rem' }}>
                    <div style={{ color: '#ff7675', fontWeight: 'bold', marginBottom: '4px' }}>Rank #{i+1}</div>
                    <p style={{ color: 'var(--text-secondary)' }}>{getChunkText(c).substring(0, 200)}...</p>
                  </div>
                ))}
                {resultSimple.context.length === 0 && (
                  <p style={{ color: 'var(--text-secondary)' }}>No se recuperaron fragmentos.</p>
                )}
              </div>
            </>
          )}
        </div>

        {/* COLUMNA DERECHA: Rerank */}
        <div className="glass-panel" style={{ flex: 1, padding: '2rem', borderTop: '4px solid var(--secondary-accent)' }}>
          <h2 style={{ fontSize: '1.25rem', color: 'var(--secondary-accent)', marginBottom: '1rem' }}>✅ Híbrido + Semantic Reranker</h2>
          
          {resultRerank && (
            <>
              <div style={{ background: 'rgba(0,210,211,0.1)', padding: '1.5rem', borderRadius: '8px', marginBottom: '2rem', border: '1px solid rgba(0,210,211,0.2)' }}>
                <strong>Respuesta del LLM:</strong>
                <p style={{ marginTop: '0.5rem', lineHeight: 1.5 }}>{resultRerank.answer}</p>
              </div>
              
              <h4 style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>Fragmentos Recuperados (Top 3)</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {resultRerank.context.map((c, i) => (
                  <div key={i} style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '8px', fontSize: '0.85rem' }}>
                    <div style={{ color: 'var(--secondary-accent)', fontWeight: 'bold', marginBottom: '4px' }}>Rank #{i+1}</div>
                    <p style={{ color: 'var(--text-secondary)' }}>{getChunkText(c).substring(0, 200)}...</p>
                  </div>
                ))}
                {resultRerank.context.length === 0 && (
                  <p style={{ color: 'var(--text-secondary)' }}>No se recuperaron fragmentos.</p>
                )}
              </div>
            </>
          )}
        </div>

      </div>
    </div>
  );
}
