/**
 * AuraPage — Next.js App Router page (app/aura/page.tsx)
 *
 * Drop this file at:  app/aura/page.tsx  (or pages/aura.tsx for Pages Router)
 *
 * Install deps:  npm install  (no extra packages needed beyond React)
 */
import dynamic from 'next/dynamic';

// Disable SSR — camera access requires browser APIs
const AuraCamera = dynamic(() => import('@/components/AuraCamera'), { ssr: false });

export const metadata = {
    title: 'Aura 2.0 — AI Accessibility Companion',
    description: 'Autonomous context intelligence for visually impaired users.',
};

export default function AuraPage() {
    return (
        <main style={{
            minHeight: '100vh',
            background: '#090910',
            color: '#e2e8f0',
            padding: '24px 16px',
        }}>
            <header style={{ marginBottom: 24, borderBottom: '1px solid #1e1e30', paddingBottom: 16 }}>
                <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>
                    AURA <span style={{ color: '#7c3aed' }}>2.0</span>
                </h1>
                <p style={{ fontSize: 13, color: '#64748b', margin: '4px 0 0' }}>
                    Autonomous Context Intelligence · Visually Impaired Companion
                </p>
            </header>

            <AuraCamera
                apiBase={process.env.NEXT_PUBLIC_AURA_API ?? 'http://localhost:8000'}
                sessionId={`aura-${typeof window !== 'undefined' ? Date.now() : 'ssr'}`}
                intervalMs={2000}
                voice="nova"
            />
        </main>
    );
}
