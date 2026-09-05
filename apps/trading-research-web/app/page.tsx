const modules = [
  { name: "PM + Previous Day", status: "Foundation ready", detail: "Signals, factors, outcomes, and V5 research." },
  { name: "Second 1-Minute", status: "Security review", detail: "OSI, Trade Health, and Alternative C2 research." },
  { name: "Trade Review", status: "Planned", detail: "Individual trade timelines and execution analysis." },
  { name: "Cross-Indicator Research", status: "Planned", detail: "Compare factors, regimes, and performance across systems." },
];

export default function Home() {
  return (
    <main>
      <section className="hero">
        <p className="eyebrow">TRADING RESEARCH PLATFORM</p>
        <h1>Research data, organized for decisions.</h1>
        <p className="lede">
          A private interface for the PM+PD, Second1M, Trade Review, and shared research platform.
        </p>
        <div className="status"><span /> Application foundation online</div>
      </section>

      <section className="grid" aria-label="Research modules">
        {modules.map((module) => (
          <article className="card" key={module.name}>
            <div className="cardHeader">
              <h2>{module.name}</h2>
              <span className="pill">{module.status}</span>
            </div>
            <p>{module.detail}</p>
          </article>
        ))}
      </section>

      <section className="next">
        <p className="eyebrow">V0.1 FOUNDATION</p>
        <h2>Next connection</h2>
        <p>Supabase authentication and a protected read-only database health check.</p>
      </section>
    </main>
  );
}
