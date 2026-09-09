import { Component } from 'react';
import { AlertOctagon } from 'lucide-react';

/**
 * მთელი აპლიკაციის ErrorBoundary.
 * React-ში ეს მხოლოდ class კომპონენტით შეიძლება.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
    this.handleReload = this.handleReload.bind(this);
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // TODO: connect backend — გაგზავნე შეცდომა მონიტორინგის სერვისში
    if (import.meta.env?.DEV) {
      // eslint-disable-next-line no-console
      console.error('ErrorBoundary:', error, info?.componentStack);
    }
  }

  handleReload() {
    this.setState({ error: null });
    window.location.assign('/');
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="flex min-h-screen items-center justify-center bg-ink-50 p-6">
        <div className="w-full max-w-md rounded-card border border-ink-200 bg-white p-8 text-center shadow-card">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-danger-50">
            <AlertOctagon className="h-7 w-7 text-danger-600" aria-hidden="true" />
          </div>
          <h1 className="text-xl font-bold text-ink-900">რაღაც შეიცვალა…</h1>
          <p className="mt-2 text-sm text-ink-600">
            აპლიკაციაში მოულოდნელი შეცდომა მოხდა. სცადეთ გვერდის განახლება — თუ პრობლემა
            გაგრძელდება, დაგვიკავშირდით.
          </p>
          {import.meta.env?.DEV && (
            <pre className="mt-4 overflow-x-auto rounded-control bg-ink-50 p-3 text-left text-xs text-danger-700">
              {String(error.message || error)}
            </pre>
          )}
          <button
            type="button"
            onClick={this.handleReload}
            className="mt-6 inline-flex h-11 w-full items-center justify-center rounded-control bg-primary-600 px-5 text-sm font-semibold text-white transition-colors hover:bg-primary-700"
          >
            მთავარ გვერდზე დაბრუნება
          </button>
        </div>
      </div>
    );
  }
}
