import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

export default function Landing() {
  const [navScrolled, setNavScrolled] = useState(false)

  useEffect(() => {
    const handleScroll = () => {
      setNavScrolled(window.scrollY > 100)
    }
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <>
      <style>{`
        .landing-bold * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }

        .landing-bold {
          --bg-primary: #FCFCFA;
          --bg-warm: #F8F7F4;
          --text-primary: #1A1A1A;
          --text-secondary: #5C5C5C;
          --text-muted: #9A9A9A;
          --accent: #1a4a4a;
          --accent-light: #e8eeee;
          --border: #E8E7E4;

          font-family: 'DM Sans', -apple-system, sans-serif;
          background-color: var(--bg-primary);
          color: var(--text-primary);
          line-height: 1.6;
          overflow-x: hidden;
        }

        /* Navigation - minimal */
        .landing-bold nav {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          padding: 2rem 4rem;
          display: flex;
          justify-content: space-between;
          align-items: center;
          z-index: 100;
          mix-blend-mode: difference;
        }

        .landing-bold nav.scrolled {
          background: rgba(252, 252, 250, 0.95);
          backdrop-filter: blur(10px);
          mix-blend-mode: normal;
          border-bottom: 1px solid var(--border);
        }

        .landing-bold .logo {
          font-family: 'Instrument Serif', serif;
          font-size: 1.3rem;
          color: white;
          text-decoration: none;
          letter-spacing: -0.01em;
        }

        .landing-bold nav.scrolled .logo {
          color: var(--text-primary);
        }

        .landing-bold .nav-cta {
          color: white;
          text-decoration: none;
          font-size: 0.9rem;
          font-weight: 500;
          padding: 0.6rem 1.25rem;
          border: 1px solid rgba(255,255,255,0.3);
          border-radius: 3px;
          transition: all 0.2s;
        }

        .landing-bold nav.scrolled .nav-cta {
          color: var(--text-primary);
          border-color: var(--border);
        }

        .landing-bold .nav-cta:hover {
          background: rgba(255,255,255,0.1);
        }

        .landing-bold nav.scrolled .nav-cta:hover {
          background: var(--bg-warm);
        }

        /* Hero - The Bold One */
        .landing-bold .hero {
          min-height: 100vh;
          position: relative;
          display: flex;
          flex-direction: column;
          justify-content: flex-end;
          padding: 4rem;
          padding-bottom: 8rem;
          overflow: hidden;
        }

        .landing-bold .hero-backdrop {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          z-index: 0;
        }

        .landing-bold .hero-backdrop img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          object-position: top left;
          opacity: 0.12;
          filter: contrast(1.1);
        }

        .landing-bold .hero-backdrop::after {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: linear-gradient(
            to bottom,
            rgba(252, 252, 250, 0) 0%,
            rgba(252, 252, 250, 0.2) 60%,
            rgba(252, 252, 250, 0.9) 85%,
            rgba(252, 252, 250, 1) 100%
          );
        }

        .landing-bold .hero-content {
          position: relative;
          z-index: 1;
          max-width: 1200px;
          animation: fadeIn 1s ease-out;
        }

        .landing-bold .hero h1 {
          font-family: 'Instrument Serif', serif;
          font-size: clamp(3rem, 5.5vw, 4.5rem);
          font-weight: 400;
          line-height: 1.2;
          letter-spacing: -0.03em;
          margin-bottom: 2rem;
          color: var(--text-primary);
        }

        .landing-bold .hero h1 .line {
          display: block;
        }

        .landing-bold .hero h1 .light {
          color: var(--text-muted);
        }

        .landing-bold .hero-subtitle {
          font-size: 1.25rem;
          color: var(--text-secondary);
          max-width: 600px;
          line-height: 1.7;
          font-weight: 400;
        }

        .landing-bold .hero-meta-badges {
          display: flex;
          gap: 2rem;
          margin-top: 2.5rem;
        }

        .landing-bold .hero-meta-badges .hero-meta-item {
          text-align: left;
        }

        .landing-bold .hero-meta-badges .hero-meta-item strong {
          display: block;
          font-family: 'DM Sans', monospace;
          font-size: 0.85rem;
          font-weight: 600;
          color: var(--text-primary);
          letter-spacing: 0.02em;
        }

        .landing-bold .hero-meta-badges .hero-meta-item span {
          font-size: 0.8rem;
          color: var(--text-muted);
        }

        .landing-bold .hero-meta-item {
          font-size: 0.85rem;
          color: var(--text-muted);
        }

        .landing-bold .hero-meta-item strong {
          display: block;
          font-size: 1.1rem;
          color: var(--text-primary);
          font-weight: 500;
          margin-bottom: 0.25rem;
        }

        .landing-bold .scroll-hint {
          position: absolute;
          bottom: 4rem;
          right: 4rem;
          font-size: 0.8rem;
          color: var(--text-muted);
          display: flex;
          align-items: center;
          gap: 0.75rem;
          letter-spacing: 0.05em;
        }

        .landing-bold .scroll-hint::before {
          content: '';
          width: 40px;
          height: 1px;
          background: var(--border);
        }

        /* Statement Section */
        .landing-bold .statement {
          padding: 12rem 4rem;
          max-width: 1000px;
          margin: 0 auto;
        }

        .landing-bold .spec-sheet-header {
          margin-bottom: 3rem;
          padding-bottom: 2rem;
          border-bottom: 1px solid var(--border);
        }

        .landing-bold .spec-sheet-label {
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.15em;
          color: var(--text-muted);
          margin-bottom: 1rem;
        }

        .landing-bold .spec-sheet-title {
          font-family: 'Instrument Serif', serif;
          font-size: clamp(1.5rem, 3vw, 2rem);
          font-weight: 400;
          color: var(--text-primary);
          letter-spacing: -0.01em;
        }

        .landing-bold .spec-grid {
          display: grid;
          grid-template-columns: 160px 1fr;
          gap: 0;
          border: 1px solid var(--border);
          background: var(--bg-primary);
        }

        .landing-bold .spec-label {
          padding: 1.25rem 1.5rem;
          font-size: 0.7rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          color: var(--text-muted);
          background: var(--bg-warm);
          border-bottom: 1px solid var(--border);
          display: flex;
          align-items: flex-start;
        }

        .landing-bold .spec-value {
          padding: 1.25rem 1.5rem;
          font-size: 1rem;
          color: var(--text-primary);
          border-bottom: 1px solid var(--border);
        }

        .landing-bold .spec-label:last-of-type,
        .landing-bold .spec-value:last-of-type {
          border-bottom: none;
        }

        .landing-bold .spec-value strong {
          font-weight: 600;
        }

        .landing-bold .spec-value-row {
          display: flex;
          gap: 4rem;
        }

        .landing-bold .spec-value-item {
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
        }

        .landing-bold .spec-value-main {
          font-weight: 500;
          color: var(--text-primary);
        }

        .landing-bold .spec-value-sub {
          font-size: 0.85rem;
          color: var(--text-secondary);
        }

        .landing-bold .spec-highlight {
          background: var(--accent-light);
        }

        .landing-bold .spec-highlight .spec-value-main {
          color: var(--accent);
          font-weight: 600;
        }

        .landing-bold .spec-status {
          margin-top: 2.5rem;
          display: flex;
          gap: 2.5rem;
        }

        .landing-bold .status-item {
          display: flex;
          align-items: center;
          gap: 0.6rem;
          font-size: 0.85rem;
          color: var(--text-secondary);
        }

        .landing-bold .status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--accent);
        }

        /* Process Section */
        .landing-bold .process {
          padding: 8rem 4rem;
          background: var(--bg-warm);
          border-top: 1px solid var(--border);
          border-bottom: 1px solid var(--border);
        }

        .landing-bold .process-inner {
          max-width: 1400px;
          margin: 0 auto;
        }

        .landing-bold .process-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-end;
          margin-bottom: 6rem;
        }

        .landing-bold .process-title {
          font-family: 'Instrument Serif', serif;
          font-size: clamp(2rem, 4vw, 3rem);
          font-weight: 400;
          letter-spacing: -0.02em;
        }

        .landing-bold .process-subtitle {
          color: var(--text-secondary);
          font-size: 1rem;
          max-width: 400px;
          text-align: right;
        }

        .landing-bold .process-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 1px;
          background: var(--border);
        }

        .landing-bold .process-item {
          background: var(--bg-primary);
          padding: 3rem;
        }

        .landing-bold .process-number {
          font-family: 'Instrument Serif', serif;
          font-size: 3rem;
          color: var(--border);
          margin-bottom: 2rem;
          line-height: 1;
        }

        .landing-bold .process-item h3 {
          font-size: 1.1rem;
          font-weight: 600;
          margin-bottom: 1rem;
          color: var(--text-primary);
        }

        .landing-bold .process-item p {
          font-size: 0.95rem;
          color: var(--text-secondary);
          line-height: 1.7;
        }

        /* Output Section */
        .landing-bold .output {
          padding: 12rem 4rem;
          max-width: 1400px;
          margin: 0 auto;
        }

        .landing-bold .output-header {
          margin-bottom: 6rem;
        }

        .landing-bold .output-eyebrow {
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--accent);
          text-transform: uppercase;
          letter-spacing: 0.15em;
          margin-bottom: 1.5rem;
        }

        .landing-bold .output-title {
          font-family: 'Instrument Serif', serif;
          font-size: clamp(2rem, 4vw, 3rem);
          font-weight: 400;
          letter-spacing: -0.02em;
          max-width: 500px;
        }

        .landing-bold .output-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 2rem;
        }

        .landing-bold .output-card {
          border: 1px solid var(--border);
          padding: 3rem;
          background: var(--bg-primary);
          transition: all 0.3s;
        }

        .landing-bold .output-card:hover {
          border-color: var(--accent);
        }

        .landing-bold .output-format {
          font-family: 'DM Sans', monospace;
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          color: var(--accent);
          margin-bottom: 1.5rem;
          padding: 0.5rem 0.75rem;
          background: var(--accent-light);
          display: inline-block;
        }

        .landing-bold .output-card h3 {
          font-family: 'Instrument Serif', serif;
          font-size: 1.75rem;
          font-weight: 400;
          margin-bottom: 1rem;
        }

        .landing-bold .output-card p {
          color: var(--text-secondary);
          font-size: 0.95rem;
          line-height: 1.7;
        }

        /* CTA Section */
        .landing-bold .cta {
          padding: 10rem 4rem;
          background: var(--text-primary);
          color: white;
        }

        .landing-bold .cta-inner {
          max-width: 800px;
          margin: 0 auto;
        }

        .landing-bold .cta h2 {
          font-family: 'Instrument Serif', serif;
          font-size: clamp(2.5rem, 5vw, 4rem);
          font-weight: 400;
          margin-bottom: 1.5rem;
          letter-spacing: -0.02em;
          line-height: 1.1;
        }

        .landing-bold .cta p {
          color: rgba(255,255,255,0.6);
          font-size: 1.15rem;
          margin-bottom: 3rem;
          line-height: 1.7;
          max-width: 500px;
        }

        .landing-bold .btn-light {
          background: white;
          color: var(--text-primary);
          padding: 1rem 2rem;
          border-radius: 3px;
          text-decoration: none;
          font-weight: 500;
          font-size: 0.95rem;
          transition: all 0.2s;
          display: inline-block;
        }

        .landing-bold .btn-light:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        /* Footer */
        .landing-bold footer {
          padding: 3rem 4rem;
          border-top: 1px solid var(--border);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .landing-bold .footer-logo {
          font-family: 'Instrument Serif', serif;
          font-size: 1.1rem;
          color: var(--text-primary);
        }

        .landing-bold .footer-text {
          color: var(--text-muted);
          font-size: 0.8rem;
        }

        /* Responsive */
        @media (max-width: 1024px) {
          .landing-bold nav {
            padding: 1.5rem 2rem;
          }

          .landing-bold .hero {
            padding: 2rem;
          }

          .landing-bold .hero h1 {
            font-size: clamp(3rem, 12vw, 5rem);
          }

          .landing-bold .hero-row {
            flex-direction: column;
            align-items: flex-start;
            gap: 2rem;
          }

          .landing-bold .scroll-hint {
            display: none;
          }

          .landing-bold .statement {
            padding: 8rem 2rem;
          }

          .landing-bold .process {
            padding: 6rem 2rem;
          }

          .landing-bold .process-header {
            flex-direction: column;
            align-items: flex-start;
            gap: 1rem;
          }

          .landing-bold .process-subtitle {
            text-align: left;
          }

          .landing-bold .process-grid {
            grid-template-columns: 1fr;
          }

          .landing-bold .output {
            padding: 8rem 2rem;
          }

          .landing-bold .output-grid {
            grid-template-columns: 1fr;
          }

          .landing-bold .cta {
            padding: 6rem 2rem;
          }

          .landing-bold footer {
            padding: 2rem;
            flex-direction: column;
            gap: 1rem;
          }
        }

        /* Smooth animations */
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div className="landing-bold">
        <nav className={navScrolled ? 'scrolled' : ''}>
          <Link to="/" className="logo">MetExtractor</Link>
        </nav>

        <section className="hero">
          <div className="hero-backdrop">
            <img src="/images/hero-table.png" alt="Calibration specification table" />
          </div>
          <div className="hero-content">
            <h1>
              <span className="line">Data entry shouldn't require expertise.</span>
              <span className="line light">Validation does.</span>
            </h1>
            <p className="hero-subtitle">
              Your team reviews procedures. MetExtractor builds them. PDF specs to .acc and .msf in minutes.
            </p>
            <div className="hero-meta-badges">
              <div className="hero-meta-item">
                <strong>.acc</strong>
                <span>Fluke Met/Cal</span>
              </div>
              <div className="hero-meta-item">
                <strong>.msf</strong>
                <span>MOXPage</span>
              </div>
            </div>
          </div>
          <div className="scroll-hint">Scroll</div>
        </section>

        <section className="statement" style={{ padding: '8rem 4rem', maxWidth: '1100px', margin: '0 auto' }}>
          <div className="spec-sheet-header">
            <div className="spec-sheet-label">What it is</div>
            <h2 className="spec-sheet-title">MetExtractor converts equipment manuals into calibration procedure files.</h2>
          </div>

          <div className="spec-grid">
            <div className="spec-label">Input</div>
            <div className="spec-value">
              <div className="spec-value-row">
                <div className="spec-value-item">
                  <span className="spec-value-main">PDF specification tables</span>
                  <span className="spec-value-sub">Any manufacturer</span>
                </div>
              </div>
            </div>

            <div className="spec-label">Output</div>
            <div className="spec-value">
              <div className="spec-value-row">
                <div className="spec-value-item">
                  <span className="spec-value-main">.acc files</span>
                  <span className="spec-value-sub">Fluke Met/Cal</span>
                </div>
                <div className="spec-value-item">
                  <span className="spec-value-main">.msf files</span>
                  <span className="spec-value-sub">MOXPage</span>
                </div>
              </div>
            </div>

            <div className="spec-label">Time</div>
            <div className="spec-value spec-highlight">
              <div className="spec-value-row">
                <div className="spec-value-item">
                  <span className="spec-value-main" style={{ textDecoration: 'line-through', color: 'var(--text-muted)', fontWeight: 400 }}>40+ hours</span>
                  <span className="spec-value-sub">Manual process</span>
                </div>
                <div className="spec-value-item">
                  <span className="spec-value-main">&lt;10 minutes</span>
                  <span className="spec-value-sub">With MetExtractor + review</span>
                </div>
              </div>
            </div>

            <div className="spec-label">Validation</div>
            <div className="spec-value">
              <div className="spec-value-row">
                <div className="spec-value-item">
                  <span className="spec-value-main">Side-by-side editor</span>
                  <span className="spec-value-sub">Source PDF + generated output</span>
                </div>
              </div>
            </div>

            <div className="spec-label">Why</div>
            <div className="spec-value" style={{ fontStyle: 'italic', color: 'var(--text-secondary)' }}>
              <div className="spec-value-item">
                <span style={{ fontStyle: 'normal', color: 'var(--text-primary)' }}>Transcription shouldn't require expertise. Validation does.</span>
              </div>
            </div>
          </div>

          <div className="spec-status">
            <div className="status-item">
              <span className="status-dot"></span>
              Validated on Fluke 5700A
            </div>
            <div className="status-item">
              <span className="status-dot"></span>
              Pilot program active
            </div>
          </div>
        </section>

        <section className="process">
          <div className="process-inner">
            <div className="process-header">
              <h2 className="process-title">How it works</h2>
              <p className="process-subtitle">
                Six-phase pipeline. Vision-first extraction.
                Format-agnostic canonical model.
              </p>
            </div>
            <div className="process-grid">
              <div className="process-item">
                <div className="process-number">01</div>
                <h3>Upload</h3>
                <p>Drop in any manufacturer's equipment manual. Fluke, Keysight, whoever. The system handles the rest.</p>
              </div>
              <div className="process-item">
                <div className="process-number">02</div>
                <h3>Extract</h3>
                <p>AI analyzes specification tables, detects calibration intervals, pulls tolerances and ranges with high accuracy.</p>
              </div>
              <div className="process-item">
                <div className="process-number">03</div>
                <h3>Validate</h3>
                <p>Side-by-side editor shows source PDF and generated output. Review, adjust, export. Confidence scores on every value.</p>
              </div>
            </div>
          </div>
        </section>

        <section className="output">
          <div className="output-header">
            <div className="output-eyebrow">Output Formats</div>
            <h2 className="output-title">Direct to your calibration software</h2>
          </div>
          <div className="output-grid">
            <div className="output-card">
              <div className="output-format">.acc</div>
              <h3>Fluke Met/Cal</h3>
              <p>Native accuracy files for Met/Cal calibration software. One file per calibration interval. Drops directly into your existing procedures.</p>
            </div>
            <div className="output-card">
              <div className="output-format">.msf</div>
              <h3>MOXPage</h3>
              <p>Production-ready MSF XML for MOX calibration management. Full specification data with all intervals in a single file.</p>
            </div>
          </div>
        </section>

        <section className="cta">
          <div className="cta-inner">
            <h2>Ready to stop transcribing?</h2>
            <p>
              We're onboarding select calibration labs for our pilot program.
              Test the extraction on your own manuals.
            </p>
            <a href="mailto:pilot@metextractor.com?subject=Pilot%20Program%20Interest" className="btn-light">Request Access</a>
          </div>
        </section>

        <footer>
          <div className="footer-logo">MetExtractor</div>
          <div className="footer-text">Calibration spec extraction for metrology professionals. &copy; 2025</div>
        </footer>
      </div>
    </>
  )
}
