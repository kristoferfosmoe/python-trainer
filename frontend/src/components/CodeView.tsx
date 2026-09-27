// Read-only code with highlighting, per-line run counts and notes. Used by the
// step-by-step visualizer and to show code in quizzes.

import { python } from "@codemirror/lang-python";
import { syntaxHighlighting, defaultHighlightStyle } from "@codemirror/language";
import { EditorState, RangeSetBuilder, StateEffect, StateField } from "@codemirror/state";
import {
  Decoration, type DecorationSet, EditorView, GutterMarker, WidgetType, gutter, lineNumbers,
} from "@codemirror/view";
import { useEffect, useRef } from "react";

export type NoteTone = "info" | "yes" | "no" | "loop";

export interface Annotations {
  activeLine: number | null;
  errorLine: number | null;
  counts: Map<number, number>;
  notes: Map<number, { text: string; tone: NoteTone }>;
}

const EMPTY: Annotations = { activeLine: null, errorLine: null, counts: new Map(), notes: new Map() };

const setAnnotations = StateEffect.define<Annotations>();

const annotationsField = StateField.define<Annotations>({
  create: () => EMPTY,
  update(value, tr) {
    for (const effect of tr.effects) if (effect.is(setAnnotations)) return effect.value;
    return value;
  },
});

class NoteWidget extends WidgetType {
  constructor(readonly text: string, readonly tone: NoteTone) {
    super();
  }
  eq(other: NoteWidget) {
    return other.text === this.text && other.tone === this.tone;
  }
  toDOM() {
    const el = document.createElement("span");
    el.className = `cm-note cm-note-${this.tone}`;
    el.textContent = this.text;
    return el;
  }
}

const decorations = EditorView.decorations.compute([annotationsField], (state) => {
  const a = state.field(annotationsField);
  const builder = new RangeSetBuilder<Decoration>();
  const lines = new Set<number>([...a.notes.keys()]);
  if (a.activeLine) lines.add(a.activeLine);
  if (a.errorLine) lines.add(a.errorLine);
  for (const n of [...lines].sort((x, y) => x - y)) {
    if (n < 1 || n > state.doc.lines) continue;
    const line = state.doc.line(n);
    const classes = [n === a.activeLine ? "cm-play-line" : "", n === a.errorLine ? "cm-error-line" : ""].filter(Boolean);
    if (classes.length) builder.add(line.from, line.from, Decoration.line({ class: classes.join(" ") }));
    const note = a.notes.get(n);
    if (note) builder.add(line.to, line.to, Decoration.widget({ widget: new NoteWidget(note.text, note.tone), side: 1 }));
  }
  return builder.finish() as DecorationSet;
});

class CountMarker extends GutterMarker {
  constructor(readonly count: number) {
    super();
  }
  eq(other: CountMarker) {
    return other.count === this.count;
  }
  toDOM() {
    const el = document.createElement("span");
    el.textContent = this.count ? `×${this.count}` : "";
    el.title = this.count ? `This line has run ${this.count} time${this.count === 1 ? "" : "s"}` : "";
    return el;
  }
}

const countGutter = gutter({
  class: "cm-count-gutter",
  lineMarker(view, line) {
    const n = view.state.doc.lineAt(line.from).number;
    const count = view.state.field(annotationsField).counts.get(n);
    return count ? new CountMarker(count) : null;
  },
  lineMarkerChange: (update) => update.transactions.some((tr) => tr.effects.some((e) => e.is(setAnnotations))),
  initialSpacer: () => new CountMarker(88),
});

const theme = EditorView.theme({
  "&": { fontSize: "15px" },
  ".cm-scroller": { fontFamily: "var(--mono)", lineHeight: "1.6" },
  ".cm-content": { padding: "8px 0" },
  ".cm-gutters": { background: "var(--editor-gutter)", border: "none", color: "var(--muted)" },
  ".cm-play-line": { background: "var(--play-line)", boxShadow: "inset 4px 0 0 var(--accent)" },
  ".cm-error-line": { background: "var(--error-line)", boxShadow: "inset 4px 0 0 var(--danger)" },
});

interface Props {
  code: string;
  annotations?: Annotations;
  counts?: boolean; // show the run-count gutter
  label?: string;
}

export function CodeView({ code, annotations = EMPTY, counts = false, label = "Code" }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);

  useEffect(() => {
    const editor = new EditorView({
      parent: host.current!,
      state: EditorState.create({
        doc: code.replace(/\n+$/, ""),
        extensions: [
          lineNumbers(),
          ...(counts ? [countGutter] : []),
          python(),
          syntaxHighlighting(defaultHighlightStyle),
          annotationsField,
          decorations,
          theme,
          EditorView.lineWrapping,
          EditorState.readOnly.of(true),
          EditorView.editable.of(false),
          EditorView.contentAttributes.of({ "aria-label": label }),
        ],
      }),
    });
    view.current = editor;
    return () => editor.destroy();
  }, [code, counts, label]);

  useEffect(() => {
    view.current?.dispatch({ effects: setAnnotations.of(annotations) });
  }, [annotations, code, counts]);

  return <div className="code-view" ref={host} />;
}
