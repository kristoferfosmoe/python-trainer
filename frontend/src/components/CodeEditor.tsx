import { autocompletion } from "@codemirror/autocomplete";
import { indentWithTab } from "@codemirror/commands";
import { python, pythonLanguage } from "@codemirror/lang-python";
import { indentUnit } from "@codemirror/language";
import { EditorState, RangeSetBuilder, StateEffect, StateField } from "@codemirror/state";
import { Decoration, type DecorationSet, EditorView, keymap } from "@codemirror/view";
import { basicSetup } from "codemirror";
import { useEffect, useRef } from "react";
import { pybricksCompletions } from "./pybricksCompletions";

interface Marks {
  playLine: number | null;
  errorLine: number | null;
  warningLines: number[];
}

const setMarks = StateEffect.define<Marks>();

const marksField = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(decorations, tr) {
    for (const effect of tr.effects) {
      if (effect.is(setMarks)) return buildMarks(tr.state, effect.value);
    }
    return tr.docChanged ? Decoration.none : decorations;
  },
  provide: (field) => EditorView.decorations.from(field),
});

function buildMarks(state: EditorState, marks: Marks): DecorationSet {
  const byLine = new Map<number, string[]>();
  const add = (line: number | null, cls: string) => {
    if (!line || line < 1 || line > state.doc.lines) return;
    byLine.set(line, [...(byLine.get(line) ?? []), cls]);
  };
  marks.warningLines.forEach((line) => add(line, "cm-warning-line"));
  add(marks.playLine, "cm-play-line");
  add(marks.errorLine, "cm-error-line");
  const builder = new RangeSetBuilder<Decoration>();
  [...byLine.keys()].sort((a, b) => a - b).forEach((line) => {
    const from = state.doc.line(line).from;
    builder.add(from, from, Decoration.line({ class: byLine.get(line)!.join(" ") }));
  });
  return builder.finish();
}

// Scroll only the editor (not the whole page) so the highlighted line is visible.
function scrollLineIntoEditor(editor: EditorView, line: number) {
  const block = editor.lineBlockAt(editor.state.doc.line(line).from);
  const scroller = editor.scrollDOM;
  const top = block.top;
  const bottom = block.bottom;
  const margin = 40;
  if (top < scroller.scrollTop + margin) {
    scroller.scrollTop = Math.max(0, top - margin);
  } else if (bottom > scroller.scrollTop + scroller.clientHeight - margin) {
    scroller.scrollTop = bottom - scroller.clientHeight + margin;
  }
}

const theme = EditorView.theme({
  "&": { fontSize: "15px", height: "100%" },
  ".cm-scroller": { fontFamily: "var(--mono)", lineHeight: "1.55" },
  ".cm-content": { padding: "10px 0" },
  ".cm-gutters": { background: "var(--editor-gutter)", border: "none", color: "var(--muted)" },
  ".cm-play-line": { background: "var(--play-line)", boxShadow: "inset 4px 0 0 var(--accent)" },
  ".cm-error-line": { background: "var(--error-line)", boxShadow: "inset 4px 0 0 var(--danger)" },
  ".cm-warning-line": { background: "var(--warning-line)" },
});

interface Props {
  value: string;
  onChange: (code: string) => void;
  onRun: () => void;
  playLine: number | null;
  errorLine: number | null;
  warningLines: number[];
  editorRef?: React.RefObject<EditorView | null>;
}

export function CodeEditor({ value, onChange, onRun, playLine, errorLine, warningLines, editorRef }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const callbacks = useRef({ onChange, onRun });
  callbacks.current = { onChange, onRun };

  useEffect(() => {
    const editor = new EditorView({
      parent: host.current!,
      state: EditorState.create({
        doc: value,
        extensions: [
          basicSetup,
          python(),
          pythonLanguage.data.of({ autocomplete: pybricksCompletions }),
          autocompletion({ activateOnTyping: true }),
          indentUnit.of("    "),
          keymap.of([
            { key: "Mod-Enter", run: () => (callbacks.current.onRun(), true) },
            indentWithTab,
          ]),
          marksField,
          theme,
          EditorView.lineWrapping,
          EditorView.contentAttributes.of({ "aria-label": "Python code editor" }),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) callbacks.current.onChange(update.state.doc.toString());
          }),
        ],
      }),
    });
    view.current = editor;
    if (editorRef) editorRef.current = editor;
    return () => editor.destroy();
    // The editor is created once; later value changes are pushed in below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Replace the document when the challenge (or a reset) changes the code.
  useEffect(() => {
    const editor = view.current;
    if (editor && editor.state.doc.toString() !== value) {
      editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: value } });
    }
  }, [value]);

  useEffect(() => {
    const editor = view.current;
    if (!editor) return;
    editor.dispatch({ effects: setMarks.of({ playLine, errorLine, warningLines }) });
    const line = errorLine ?? playLine;
    if (line && line <= editor.state.doc.lines) scrollLineIntoEditor(editor, line);
  }, [playLine, errorLine, warningLines]);

  return <div className="editor" ref={host} />;
}
