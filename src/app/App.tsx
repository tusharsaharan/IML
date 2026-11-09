import { NavLink, Route, Routes } from 'react-router-dom';
import { CompressionPage } from '@/features/compression/CompressionPage';
import { RoutingPage } from '@/features/routing/RoutingPage';
import { CachePage } from '@/features/cache/CachePage';
import { InsightsPage } from '@/features/insights/InsightsPage';
import { StudioPage } from '@/app/StudioPage';

const links = [
  ['/', 'Studio'],
  ['/compression', 'Compression'],
  ['/routing', 'Routing'],
  ['/cache', 'Cache'],
  ['/insights', 'Insights'],
] as const;

export function App() {
  return (
    <div className="min-h-screen px-4 py-5 sm:px-6 lg:px-8">
      <header className="mx-auto mb-6 flex max-w-7xl flex-col gap-4 rounded-[2rem] border border-line bg-panel/80 p-4 shadow-panel backdrop-blur lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="eyebrow">IML course application</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink">Token Optimiser</h1>
        </div>
        <nav className="flex flex-wrap gap-2">
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `rounded-full px-4 py-2 text-sm font-medium transition ${isActive ? 'bg-accent text-white' : 'bg-white/70 text-ink hover:bg-white'}`}>
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-7xl">
        <Routes>
          <Route path="/" element={<StudioPage />} />
          <Route path="/compression" element={<CompressionPage />} />
          <Route path="/routing" element={<RoutingPage />} />
          <Route path="/cache" element={<CachePage />} />
          <Route path="/insights" element={<InsightsPage />} />
        </Routes>
      </main>
    </div>
  );
}
