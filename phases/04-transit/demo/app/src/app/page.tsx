"use client";
import Link from 'next/link';
import './page.module.css';

export default function Home() {
  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', paddingTop: '4rem' }}>
      <header style={{ textAlign: 'center', marginBottom: '4rem' }}>
        <div style={{ display: 'inline-flex', padding: '6px 16px', background: 'rgba(0, 210, 211, 0.1)', border: '1px solid rgba(0, 210, 211, 0.3)', borderRadius: '20px', color: 'var(--secondary-accent)', fontSize: '0.875rem', fontWeight: 600, marginBottom: '1.5rem', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
          Azure AI Foundry
        </div>
        <h1>Plataforma de Demostración RAG</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1.25rem', lineHeight: 1.6, maxWidth: '700px', margin: '0 auto' }}>
          Explora visualmente las capacidades de Retrieval-Augmented Generation utilizando Azure AI Search y Agentes Nativos de Foundry.
        </p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '2rem' }}>
        
        <Link href="/documents" className="glass-panel" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1rem', transition: 'transform 0.3s ease', cursor: 'pointer' }} onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-5px)'} onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}>
          <div style={{ fontSize: '2.5rem' }}>📄</div>
          <h3>Explorador de Documentos</h3>
          <p style={{ color: 'var(--text-secondary)', flex: 1 }}>Visualiza todos los chunks almacenados en el índice vectorial de Azure AI Search, junto con sus metadatos.</p>
          <div style={{ color: 'var(--primary-accent)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '8px' }}>
            Explorar →
          </div>
        </Link>

        <Link href="/chat" className="glass-panel" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1rem', transition: 'transform 0.3s ease', cursor: 'pointer' }} onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-5px)'} onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}>
          <div style={{ fontSize: '2.5rem' }}>💬</div>
          <h3>Agente Nativo Foundry</h3>
          <p style={{ color: 'var(--text-secondary)', flex: 1 }}>Chatea con el Agente desplegado nativamente y observa en tiempo real los fragmentos que recupera para formular su respuesta.</p>
          <div style={{ color: 'var(--primary-accent)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '8px' }}>
            Iniciar Chat →
          </div>
        </Link>

        <Link href="/playground" className="glass-panel" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1rem', transition: 'transform 0.3s ease', cursor: 'pointer' }} onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-5px)'} onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}>
          <div style={{ fontSize: '2.5rem' }}>⚖️</div>
          <h3>Playground Rerank</h3>
          <p style={{ color: 'var(--text-secondary)', flex: 1 }}>Compara lado a lado el desempeño de una búsqueda vectorial estándar vs. la potencia del Semantic Reranker de Azure.</p>
          <div style={{ color: 'var(--primary-accent)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '8px' }}>
            Comparar →
          </div>
        </Link>

      </div>
    </div>
  );
}
