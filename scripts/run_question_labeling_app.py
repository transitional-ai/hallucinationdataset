import csv
import json
import mimetypes
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = ROOT / "hitl_real_question_review"
DEFAULT_REVIEWER = REVIEW_DIR / "real_question_reviewer_1.csv"


def read_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def write_rows(path: Path, fields, rows):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def row_complete(row):
    if row.get("question_valid", "").strip().lower() == "no":
        return True
    if row.get("question_valid", "").strip().lower() != "yes":
        return False
    if row.get("final_correct_answer", "").strip() not in {"A", "B"}:
        return False
    task = row.get("task", "")
    if task == "vhd_i_pdi":
        return row.get("final_A_language_prior", "").strip() in {"A", "B"} and row.get("final_A_vision", "").strip() in {"A", "B"}
    if task == "vhd_ii_hce":
        return bool(row.get("final_uncertainty_label", "").strip())
    return True


def public_row(row, index, total):
    out = dict(row)
    out["index"] = index
    out["total"] = total
    out["complete"] = row_complete(row)
    return out


HTML = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>VHD Question Labeling</title>
  <style>
    body { margin: 0; font-family: Georgia, 'Times New Roman', serif; background: #f7f1e8; color: #221b15; }
    .wrap { display: grid; grid-template-columns: 58% 42%; min-height: 100vh; }
    .left { padding: 18px; background: #151515; color: #f6f1ea; }
    .right { padding: 22px 28px; }
    video { width: 100%; max-height: 72vh; background: #000; border-radius: 10px; }
    .meta { font-size: 14px; color: #d8cabb; margin: 10px 0; line-height: 1.45; }
    .card { background: #fff7eb; border: 1px solid #d9b98f; border-radius: 12px; padding: 18px; box-shadow: 0 8px 20px rgba(60,40,20,.08); }
    h1 { margin: 0 0 12px; font-size: 24px; }
    h2 { margin: 16px 0 8px; font-size: 18px; }
    .question { font-size: 20px; line-height: 1.38; margin: 12px 0; }
    .option { background: #fff; border: 1px solid #d7c0a2; padding: 12px; border-radius: 10px; margin: 10px 0; }
    button { border: 1px solid #8b6d4c; background: #f1dfc6; color: #24170d; padding: 9px 12px; border-radius: 9px; cursor: pointer; margin: 4px; font-size: 14px; }
    button:hover { background: #e5caa6; }
    button.primary { background: #8a5f3d; color: white; }
    button.danger { background: #7e2f2f; color: white; }
    button.selected { outline: 3px solid #2f6b47; background: #d5eadb; }
    .row { margin: 12px 0; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .small { font-size: 13px; color: #6b5a48; }
    textarea { width: 100%; min-height: 58px; border-radius: 8px; border: 1px solid #c9ad89; padding: 8px; background: #fffdf8; }
    .progress { font-size: 15px; margin-bottom: 10px; }
    .kbd { font-family: Consolas, monospace; background: #eee0ca; padding: 1px 5px; border-radius: 4px; }
    @media (max-width: 900px) { .wrap { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<div class="wrap">
  <div class="left">
    <video id="video" controls autoplay muted loop></video>
    <div class="meta" id="videoMeta"></div>
  </div>
  <div class="right">
    <div class="card">
      <div class="progress" id="progress"></div>
      <h1 id="qid"></h1>
      <div class="small" id="task"></div>
      <div class="question" id="question"></div>
      <div class="option"><b>A.</b> <span id="optA"></span></div>
      <div class="option"><b>B.</b> <span id="optB"></span></div>

      <div class="row">
        <button class="primary" onclick="acceptDraft()">Accept draft labels and next</button>
        <button onclick="markInvalid()">Invalid question</button>
      </div>

      <h2>Manual Labels</h2>
      <div class="row">
        <div class="small">question_valid</div>
        <button data-field="question_valid" data-value="yes" onclick="pick(this)">yes</button>
        <button data-field="question_valid" data-value="no" onclick="pick(this)">no</button>
      </div>
      <div class="grid">
        <div class="row">
          <div class="small">final_correct_answer</div>
          <button data-field="final_correct_answer" data-value="A" onclick="pick(this)">A</button>
          <button data-field="final_correct_answer" data-value="B" onclick="pick(this)">B</button>
        </div>
        <div class="row">
          <div class="small">final_uncertainty_label</div>
          <button data-field="final_uncertainty_label" data-value="uncertain" onclick="pick(this)">uncertain</button>
          <button data-field="final_uncertainty_label" data-value="not_uncertain" onclick="pick(this)">not_uncertain</button>
          <button data-field="final_uncertainty_label" data-value="" onclick="pick(this)">blank</button>
        </div>
        <div class="row">
          <div class="small">final_A_language_prior</div>
          <button data-field="final_A_language_prior" data-value="A" onclick="pick(this)">A</button>
          <button data-field="final_A_language_prior" data-value="B" onclick="pick(this)">B</button>
          <button data-field="final_A_language_prior" data-value="" onclick="pick(this)">blank</button>
        </div>
        <div class="row">
          <div class="small">final_A_vision</div>
          <button data-field="final_A_vision" data-value="A" onclick="pick(this)">A</button>
          <button data-field="final_A_vision" data-value="B" onclick="pick(this)">B</button>
          <button data-field="final_A_vision" data-value="" onclick="pick(this)">blank</button>
        </div>
      </div>

      <div class="row">
        <div class="small">reviewer_notes</div>
        <textarea id="notes"></textarea>
      </div>
      <div class="row">
        <button onclick="prev()">Previous</button>
        <button class="primary" onclick="save(false)">Save</button>
        <button class="primary" onclick="save(true)">Save and next</button>
        <button onclick="next()">Next</button>
      </div>
      <div class="small">
        Shortcuts: <span class="kbd">D</span> accept draft, <span class="kbd">S</span> save next,
        <span class="kbd">←</span>/<span class="kbd">→</span> navigate.
      </div>
    </div>
  </div>
</div>
<script>
let current = null;
let labels = {};

async function load(index = null) {
  const url = index === null ? '/api/next_unlabeled' : '/api/question?index=' + index;
  const res = await fetch(url);
  current = await res.json();
  if (current.done) {
    document.querySelector('.card').innerHTML = '<h1>All questions labeled.</h1>';
    return;
  }
  labels = {
    question_valid: current.question_valid || '',
    final_correct_answer: current.final_correct_answer || '',
    final_A_language_prior: current.final_A_language_prior || '',
    final_A_vision: current.final_A_vision || '',
    final_uncertainty_label: current.final_uncertainty_label || '',
  };
  document.getElementById('progress').textContent = `Question ${current.index + 1} / ${current.total}`;
  document.getElementById('qid').textContent = current.question_id;
  document.getElementById('task').textContent = `${current.task} | ${current.vhd_category} | ${current.stimulus_type}`;
  document.getElementById('question').textContent = current.question_text;
  document.getElementById('optA').textContent = current.option_A;
  document.getElementById('optB').textContent = current.option_B;
  document.getElementById('video').src = '/media/' + encodeURIComponent(current.stimulus_path);
  document.getElementById('videoMeta').innerHTML =
    `clip_id: ${current.clip_id}<br>video: ${current.stimulus_path}<br>` +
    `draft_correct: ${current.draft_correct_answer || '(blank)'}; ` +
    `draft_prior: ${current.draft_A_language_prior || '(blank)'}; ` +
    `draft_vision: ${current.draft_A_vision || '(blank)'}; ` +
    `draft_uncertainty: ${current.draft_uncertainty_label || '(blank)'}`;
  document.getElementById('notes').value = current.reviewer_notes || '';
  refreshButtons();
}

function refreshButtons() {
  document.querySelectorAll('button[data-field]').forEach(btn => {
    btn.classList.toggle('selected', labels[btn.dataset.field] === btn.dataset.value);
  });
}

function pick(btn) {
  labels[btn.dataset.field] = btn.dataset.value;
  refreshButtons();
}

async function save(goNext) {
  labels.reviewer_notes = document.getElementById('notes').value;
  const res = await fetch('/api/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({index: current.index, labels})
  });
  if (!res.ok) alert(await res.text());
  if (goNext) load(current.index + 1);
  else load(current.index);
}

function acceptDraft() {
  labels.question_valid = 'yes';
  labels.final_correct_answer = current.draft_correct_answer || '';
  labels.final_A_language_prior = current.draft_A_language_prior || '';
  labels.final_A_vision = current.draft_A_vision || '';
  labels.final_uncertainty_label = current.draft_uncertainty_label || '';
  save(true);
}

function markInvalid() {
  labels.question_valid = 'no';
  labels.final_correct_answer = '';
  labels.final_A_language_prior = '';
  labels.final_A_vision = '';
  labels.final_uncertainty_label = '';
  save(true);
}

function prev() { load(Math.max(0, current.index - 1)); }
function next() { load(Math.min(current.total - 1, current.index + 1)); }

document.addEventListener('keydown', e => {
  if (!current) return;
  if (e.key.toLowerCase() === 'd') acceptDraft();
  if (e.key.toLowerCase() === 's') save(true);
  if (e.key === 'ArrowLeft') prev();
  if (e.key === 'ArrowRight') next();
});

load();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    reviewer_path = DEFAULT_REVIEWER

    def send_json(self, data, status=200):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            payload = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if parsed.path == "/api/next_unlabeled":
            fields, rows = read_rows(self.reviewer_path)
            for index, row in enumerate(rows):
                if not row_complete(row):
                    self.send_json(public_row(row, index, len(rows)))
                    return
            self.send_json({"done": True})
            return
        if parsed.path == "/api/question":
            qs = urllib.parse.parse_qs(parsed.query)
            index = int(qs.get("index", ["0"])[0])
            fields, rows = read_rows(self.reviewer_path)
            index = max(0, min(index, len(rows) - 1))
            self.send_json(public_row(rows[index], index, len(rows)))
            return
        if parsed.path.startswith("/media/"):
            rel = urllib.parse.unquote(parsed.path[len("/media/"):])
            path = (ROOT / rel).resolve()
            if not str(path).startswith(str(ROOT.resolve())) or not path.exists():
                self.send_error(404)
                return
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(path.stat().st_size))
            self.end_headers()
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            return
        self.send_error(404)

    def do_POST(self):
        if self.path != "/api/save":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        fields, rows = read_rows(self.reviewer_path)
        index = int(data["index"])
        if index < 0 or index >= len(rows):
            self.send_json({"error": "index out of range"}, status=400)
            return
        for key, value in data.get("labels", {}).items():
            if key in fields:
                rows[index][key] = value
        write_rows(self.reviewer_path, fields, rows)
        self.send_json({"ok": True, "complete": row_complete(rows[index])})


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewer", default=str(DEFAULT_REVIEWER))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    Handler.reviewer_path = Path(args.reviewer).resolve()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Labeling app: http://{args.host}:{args.port}")
    print(f"Writing labels to: {Handler.reviewer_path}")
    server.serve_forever()


if __name__ == "__main__":
    main()
