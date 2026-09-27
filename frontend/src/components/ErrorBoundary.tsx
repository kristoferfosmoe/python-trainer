// If a page crashes while drawing, show a way out instead of a blank screen.

import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** Changing this (for example, going to another page) tries drawing again. */
  resetKey: string;
}

interface State {
  error: Error | null;
  resetKey: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, resetKey: this.props.resetKey };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    return props.resetKey === state.resetKey ? null : { error: null, resetKey: props.resetKey };
  }

  componentDidCatch(error: Error) {
    console.error("A page crashed", error);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="card narrow" role="alert">
        <h1>Something went wrong on this page</h1>
        <p>Go back to the lessons, or reload the page to try again.</p>
        <p>
          <a className="button primary" href="#/">🗺️ Back to the lessons</a>{" "}
          <button className="secondary" onClick={() => window.location.reload()}>Reload</button>
        </p>
      </div>
    );
  }
}
