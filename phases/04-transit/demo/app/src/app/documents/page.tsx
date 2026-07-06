"use client";
import { useEffect, useState } from 'react';

type DocumentChunk = {
  id: string;
  content?: string;
  metadata?: {
    title?: string;
    source?: string;
    page?: string | number;
    line?: string | number;
  };
};

function formatPage(value: DocumentChunk['metadata']['page']) {
  if (value === undefined || value === null || value === '') return '';
  if (Array.isArray(value)) {
    return '';
  }

  const text = String(value).trim();
  if (!text) return '';
  if (text.includes(',')) {
    return '';
  }

  return text;
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentChunk[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch('http://localhost:8000/api/documents')
      .then((res) => {
        if (!res.ok) throw new Error('Error al conectar con la API');
        return res.json();
      })
      .then((data) => {
        setDocuments(data.documents);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', paddingTop: '2rem' }}>
      <h1 style={{ marginBottom: '1rem' }}>Explorador de Documentos</h1>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '3rem' }}>
        Fragmentos (chunks) almacenados en tu índice vectorial de Azure AI Search.
      </p>

      {loading && <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--primary-accent)' }}>Cargando documentos de Azure...</div>}
      {error && <div style={{ background: 'rgba(255,0,0,0.1)', padding: '1rem', borderRadius: '8px', color: '#ff7675' }}>{error}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.5rem' }}>
        {documents.map((doc, i) => {
          const location = formatPage(doc.metadata?.page);

          return (
          <div key={i} className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', marginBottom: '1rem' }}>
              <span 
                title={doc.metadata?.source}
                style={{ 
                  background: 'rgba(108, 92, 231, 0.2)', 
                  color: '#a29bfe', 
                  padding: '4px 10px', 
                  borderRadius: '4px', 
                  fontSize: '0.75rem', 
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  maxWidth: '75%',
                  display: 'inline-block'
                }}
              >
                {doc.metadata?.source ? doc.metadata.source.split('/').pop() : 'Fuente Desconocida'}
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>ID: {doc.id.substring(0,8)}...</span>
            </div>
            
            <h4 style={{ marginBottom: '0.75rem', color: 'white', fontSize: '1.1rem' }}>
              {doc.metadata?.title || 'Fragmento de Documento'}
            </h4>
            
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: 1.5, flex: 1, marginBottom: '1rem' }}>
              &quot;{doc.content}&quot;
            </p>
            
            {location && (
              <div style={{ borderTop: '1px solid var(--border-glass)', paddingTop: '1rem', marginTop: 'auto' }}>
                <div style={{ display: 'flex', gap: '1rem', fontSize: '0.75rem', color: 'var(--text-secondary)', minWidth: 0 }}>
                  <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    <strong>Ubicación:</strong> {location}
                  </span>
                </div>
              </div>
            )}
          </div>
          );
        })}
      </div>
    </div>
  );
}
