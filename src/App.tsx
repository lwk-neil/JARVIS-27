import { useState, type ReactNode } from 'react'
import { DotSphere } from './DotSphere'
import {
  controlPoints,
  faqs,
  features,
  footerLinks,
  navigation,
  steps,
} from './content'

type IconName = 'wave' | 'key' | 'spark' | 'window' | 'nodes' | 'shield'

function Icon({ name }: { name: IconName }) {
  const paths: Record<IconName, ReactNode> = {
    wave: (
      <>
        <path d="M2 12h3l2-7 4 14 3-10 2 3h6" />
      </>
    ),
    key: (
      <>
        <circle cx="8" cy="15" r="5" />
        <path d="m11.5 11.5 8-8 2 2-2 2 2 2-3 3-2-2-3.5 3.5" />
      </>
    ),
    spark: (
      <>
        <path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" />
        <path d="m19 15 .9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z" />
      </>
    ),
    window: (
      <>
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M3 9h18M8 4v5" />
      </>
    ),
    nodes: (
      <>
        <circle cx="6" cy="6" r="2" />
        <circle cx="18" cy="6" r="2" />
        <circle cx="12" cy="18" r="2" />
        <path d="m8 7 3 9m5-9-3 9m-5-9h8" />
      </>
    ),
    shield: (
      <>
        <path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" />
        <path d="m9 12 2 2 4-4" />
      </>
    ),
  }

  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  )
}

function Arrow({ diagonal = false }: { diagonal?: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none">
      {diagonal ? (
        <path d="M5 15 15 5M6 5h9v9" />
      ) : (
        <path d="M3 10h13m-5-5 5 5-5 5" />
      )}
    </svg>
  )
}

function App() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="SYKE home">
          <span className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <span>SYKE</span>
        </a>
        <button
          className="menu-toggle"
          type="button"
          aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span />
          <span />
        </button>
        <nav className={menuOpen ? 'main-nav is-open' : 'main-nav'} aria-label="Main navigation">
          {navigation.map((item) => (
            <a key={item.href} href={item.href} onClick={() => setMenuOpen(false)}>
              {item.label}
            </a>
          ))}
          <a className="nav-cta" href="#download" onClick={() => setMenuOpen(false)}>
            Get started <Arrow diagonal />
          </a>
        </nav>
      </header>

      <main>
        <section className="hero section-wrap" id="top">
          <div className="hero-copy">
            <div className="eyebrow"><span className="live-dot" /> PERSONAL AI, ON YOUR DESKTOP</div>
            <h1>Your computer,<br />ready when<br /><span>you are.</span></h1>
            <p className="hero-intro">
              Meet SYKE: a voice-first desktop assistant that listens, speaks, and
              helps you get things done—on your terms.
            </p>
            <div className="hero-actions">
              <a className="button button-primary" href="#download">
                Explore getting started <Arrow />
              </a>
              <a className="button button-quiet" href="#features">
                See what it can do
              </a>
            </div>
            <div className="platform-line">
              <span>MADE FOR YOUR DESKTOP</span>
              <i />
              <span>WINDOWS</span>
              <i />
              <span>MACOS</span>
              <i />
              <span>LINUX</span>
            </div>
          </div>

          <div className="hero-art" role="img" aria-label="Animated magenta-to-orange point-cloud sphere">
            <div className="orb-glow" />
            <div className="orb-ring orb-ring--one" />
            <div className="orb-ring orb-ring--two" />
            <DotSphere className="hero-sphere" />
            <div className="hero-art-caption">
              <span className="caption-mark">✳</span>
              <span><strong>HERE, WHEN YOU NEED IT</strong><small>Voice, visuals, and your own controls</small></span>
              <span className="caption-signal">●</span>
            </div>
            <div className="orb-coordinate">01 / 03<br />VOICE INTERFACE</div>
          </div>

          <div className="hero-footnote">
            <span>01</span>
            <span className="footnote-rule" />
            <span>AN ASSISTANT THAT MEETS YOU AT YOUR DESK</span>
          </div>
        </section>

        <section className="intro-strip">
          <p>
            Not another tab to keep open. <span>A capable companion that lives on your computer.</span>
          </p>
          <a href="#how-it-works">Meet your new workflow <Arrow diagonal /></a>
        </section>

        <section className="section-wrap feature-section" id="features">
          <div className="section-heading">
            <div>
              <div className="eyebrow">THOUGHTFUL BY DESIGN <span>— 01</span></div>
              <h2>More than a voice<br />in the room.</h2>
            </div>
            <p>
              A desktop assistant with a real interface, practical controls, and
              room to make it your own.
            </p>
          </div>
          <div className="feature-grid">
            {features.map((feature) => (
              <article className={`feature-card ${feature.className}`} key={feature.number}>
                <div className="feature-card-top">
                  <span className="feature-icon"><Icon name={feature.icon as IconName} /></span>
                  <span className="feature-number">{feature.number}</span>
                </div>
                <div className="feature-card-copy">
                  <span className="card-tag">{feature.tag}</span>
                  <h3>{feature.title}</h3>
                  <p>{feature.description}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="workflow-section" id="how-it-works">
          <div className="section-wrap workflow-inner">
            <div className="workflow-heading">
              <div className="eyebrow">A SIMPLE START <span>— 02</span></div>
              <h2>Set it up.<br /><span>Make it yours.</span></h2>
              <p>Begin with what you need. Change the setup whenever you do.</p>
              <a className="text-link" href="#download">Explore setup <Arrow /></a>
            </div>
            <div className="steps-list">
              {steps.map((step) => (
                <article className="step-row" key={step.number}>
                  <span className="step-index">{step.number}</span>
                  <div>
                    <h3>{step.title}</h3>
                    <p>{step.description}</p>
                  </div>
                  <span className="step-arrow"><Arrow diagonal /></span>
                </article>
              ))}
            </div>
            <div className="workflow-orbit" aria-hidden="true"><DotSphere density={800} /></div>
          </div>
        </section>

        <section className="section-wrap control-section" id="control">
          <div className="control-intro">
            <div className="eyebrow">YOUR COMPUTER. YOUR CALL. <span>— 03</span></div>
            <h2>Helpful should<br />still feel <span>in your hands.</span></h2>
            <p>
              You decide how SYKE listens, which engine it uses, and what
              permissions to grant. The details depend on your setup.
            </p>
            <div className="control-note">
              <span className="note-icon"><Icon name="shield" /></span>
              <span><strong>Designed around your choices</strong><small>Capabilities are shaped by your configuration and operating system.</small></span>
            </div>
          </div>
          <div className="control-list">
            {controlPoints.map((point) => (
              <article className="control-row" key={point.number}>
                <span className="control-number">{point.number}</span>
                <div className="control-row-copy">
                  <span>{point.label}</span>
                  <h3>{point.title}</h3>
                  <p>{point.description}</p>
                </div>
                <span className="control-check" aria-hidden="true">↗</span>
              </article>
            ))}
          </div>
        </section>

        <section className="faq-section" id="faq">
          <div className="section-wrap faq-inner">
            <div className="faq-heading">
              <div className="eyebrow">GOOD TO KNOW <span>— 04</span></div>
              <h2>A few things<br />you might wonder.</h2>
              <p>Clear answers, before you invite SYKE to your desktop.</p>
            </div>
            <div className="faq-list">
              {faqs.map((faq, index) => (
                <details className="faq-item" key={faq.question} open={index === 0}>
                  <summary>
                    <span>{faq.question}</span>
                    <span className="faq-toggle" aria-hidden="true" />
                  </summary>
                  <p>{faq.answer}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="download-section section-wrap" id="download">
          <div className="download-orb"><DotSphere density={1000} /></div>
          <div className="eyebrow"><span className="live-dot" /> YOUR NEXT CONVERSATION STARTS HERE</div>
          <h2>Make a little room<br />for <span>what’s next.</span></h2>
          <p>
            SYKE is a desktop assistant for Windows, macOS, and Linux. Take a
            look at the setup, choose your engine, and decide how you want to use it.
          </p>
          <div className="download-actions">
            <a className="button button-primary" href="#how-it-works">Explore the setup <Arrow /></a>
            <span>DESKTOP APP <i /> WINDOWS · MACOS · LINUX</span>
          </div>
          <small className="download-honesty">Download links will appear here when a public release is available.</small>
        </section>
      </main>

      <footer className="site-footer">
        <div className="footer-top">
          <a className="brand" href="#top" aria-label="SYKE home">
            <span className="brand-mark" aria-hidden="true"><span /><span /><span /></span>
            <span>SYKE</span>
          </a>
          <p>A voice-first assistant for the computer you call yours.</p>
          <nav aria-label="Footer navigation">
            {footerLinks.map((link) => <a key={link.label} href={link.href}>{link.label}</a>)}
          </nav>
          <a className="back-top" href="#top" aria-label="Back to top"><Arrow diagonal /></a>
        </div>
        <div className="footer-bottom">
          <span>© 2026 Neil Ahmed & SYKE. Made for your desktop.</span>
          <span>YOU’RE IN CONTROL <i /> ALWAYS</span>
        </div>
      </footer>
    </>
  )
}

export default App
