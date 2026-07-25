import { Component } from "react";
import { RefreshCw } from "lucide-react";

/**
 * Catches render-time errors anywhere below it (e.g. the app reading
 * r.panchang.vara or r.rahu_kaal.start on a payload missing that key) and
 * shows a real card instead of a blank white page. This doesn't replace
 * fixing the underlying optional-chaining gaps — it's the backstop for
 * whatever gap gets missed next.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("Compass Astro — caught render error:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center px-6" style={{ background: "var(--jai-bg)" }}>
          <div className="modal-surface max-w-md w-full p-8 text-center">
            <h1 className="font-serif-display text-2xl text-[color:var(--jai-green-deep)] mb-3">
              Something went wrong
            </h1>
            <p className="text-sm text-[color:var(--jai-text-muted)] mb-6">
              This page hit an unexpected error. Reloading usually fixes it — if it keeps happening,
              let us know on the Contact page.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="gold-btn rounded-full px-6 py-3 font-serif-display text-lg inline-flex items-center justify-center gap-2 mx-auto"
            >
              <RefreshCw size={16} /> Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
