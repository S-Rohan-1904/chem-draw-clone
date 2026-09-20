export function ResultSkeleton() {
  return (
    <div className="skeleton" aria-busy="true" aria-label="Loading">
      <div className="result-bar">
        <span className="sk sk-text" style={{ width: 260 }} />
        <span className="sk sk-btn" />
      </div>
      <div className="grid2">
        <section className="card">
          <header className="card-head"><span className="sk sk-text" style={{ width: 110 }} /></header>
          <div className="sk sk-box" />
        </section>
        <section className="card">
          <header className="card-head">
            <span className="sk sk-text" style={{ width: 110 }} />
            <span className="sk sk-text" style={{ width: 180 }} />
          </header>
          <div className="sk sk-box" />
        </section>
      </div>
      <section className="card">
        <header className="card-head"><span className="sk sk-text" style={{ width: 140 }} /></header>
        <div className="chips">
          <span className="sk sk-chip" />
          <span className="sk sk-chip" />
        </div>
        <div className="sk-lines">
          <span className="sk sk-text" style={{ width: '40%' }} />
          <span className="sk sk-text" style={{ width: '70%' }} />
          <span className="sk sk-text" style={{ width: '30%' }} />
          <span className="sk sk-text" style={{ width: '55%' }} />
        </div>
      </section>
      <div className="downloads">
        <span className="sk sk-btn" />
        <span className="sk sk-btn" />
        <span className="sk sk-btn" />
        <span className="sk sk-btn" />
      </div>
    </div>
  )
}
