import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/", label: "Library", end: true },
  { to: "/search", label: "Search", end: false },
  { to: "/collections", label: "Collections", end: false },
  { to: "/evaluation", label: "Evaluation", end: false },
];

export function Layout() {
  return (
    <div className="min-h-screen bg-ink text-cream">
      <a href="#content" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-amber focus:px-3 focus:py-2 focus:text-ink">
        Skip to content
      </a>
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-4">
          <NavLink to="/" className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-md border border-amber text-amber" aria-hidden="true">▶</span>
            <span>
              <span className="block font-serif text-xl leading-none">Clip-It</span>
              <span className="text-xs text-muted">Search inside your videos</span>
            </span>
          </NavLink>
          <nav aria-label="Primary" className="flex gap-1">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  `rounded-full px-3 py-1.5 text-sm ${isActive ? "bg-amber text-ink" : "text-muted hover:text-cream"}`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main id="content" className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
