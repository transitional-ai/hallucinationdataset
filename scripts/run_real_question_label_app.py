import argparse
import csv
import html
import json
import mimetypes
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = ROOT / "hitl_real_question_review"

FIELDS = [
    "reviewer_id",
    "question_id",
    "clip_id",
    "vhd_category",
    "task",
    "stimulus_type",
    "stimulus_path",
    "long_video_name",
    "long_video_start_sec_planned",
    "long_video_end_sec_planned",
    "question_text",
    "option_A",
    "option_B",
    "draft_correct_answer",
    "draft_A_language_prior",
    "draft_A_vision",
    "draft_uncertainty_label",
    "question_valid",
    "final_correct_answer",
    "final_A_language_prior",
    "final_A_vision",
    "final_uncertainty_label",
]


class ReviewStore:
    def __init__(self, reviewer: int):
        self.path = REVIEW_DIR / f"real_question_reviewer_{reviewer}.csv"
        self.lock = threading.Lock()
        self.rows = self._read_rows()
        self._write_rows()

    def _read_rows(self):
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = []
            for row in reader:
                cleaned = {field: row.get(field, "") for field in FIELDS}
                rows.append(cleaned)
            return rows

    def _write_rows(self):
        with self.path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(self.rows)

    def stats(self):
        filled = 0
        for row in self.rows:
            if row.get("question_valid") in {"yes", "no"}:
                filled += 1
        return {"total": len(self.rows), "filled": filled, "remaining": len(self.rows) - filled}

    def get(self, index: int):
        if index < 0 or index >= len(self.rows):
            return None
        row = dict(self.rows[index])
        row["index"] = index
        row["media_exists"] = (ROOT / row["stimulus_path"]).exists()
        return row

    def next_unreviewed(self, start: int = 0):
        total = len(self.rows)
        for offset in range(total):
            index = (start + offset) % total
            if self.rows[index].get("question_valid", "") not in {"yes", "no"}:
                return index
        return 0

    def save(self, payload):
        index = int(payload["index"])
        with self.lock:
            row = self.rows[index]
            row["question_valid"] = clean_choice(payload.get("question_valid", ""))
            row["final_correct_answer"] = clean_choice(payload.get("final_correct_answer", ""))
            row["final_A_language_prior"] = clean_choice(payload.get("final_A_language_prior", ""))
            row["final_A_vision"] = clean_choice(payload.get("final_A_vision", ""))
            row["final_uncertainty_label"] = clean_uncertainty(payload.get("final_uncertainty_label", ""))
            self._write_rows()
        return self.get(index)


def clean_choice(value):
    value = str(value or "").strip()
    if value in {"A", "B", "yes", "no"}:
        return value
    return ""


def clean_uncertainty(value):
    value = str(value or "").strip().lower()
    if value in {"none", "not_applicable", "na", "n/a"}:
        return ""
    if value == "uncertain":
        return "uncertain"
    return ""


def json_response(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler, body, status=200, content_type="text/html; charset=utf-8"):
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def serve_file(handler, rel_path):
    rel_path = urllib.parse.unquote(rel_path).replace("/", "\\")
    path = (ROOT / rel_path).resolve()
    if not str(path).startswith(str(ROOT.resolve())) or not path.exists():
        handler.send_error(404, "media not found")
        return

    file_size = path.stat().st_size
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    range_header = handler.headers.get("Range")
    start = 0
    end = file_size - 1
    status = 200
    if range_header and range_header.startswith("bytes="):
        status = 206
        requested = range_header.replace("bytes=", "", 1)
        left, _, right = requested.partition("-")
        if left:
            start = int(left)
        if right:
            end = int(right)
        end = min(end, file_size - 1)

    length = max(0, end - start + 1)
    handler.send_response(status)
    handler.send_header("Content-Type", mime)
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("Content-Length", str(length))
    if status == 206:
        handler.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
    handler.end_headers()
    with path.open("rb") as handle:
        handle.seek(start)
        remaining = length
        while remaining > 0:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            handler.wfile.write(chunk)
            remaining -= len(chunk)


def app_html(reviewer):
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>VHD Question Label Review</title>
<style>
:root {{
  --bg:#f5efe4;
  --panel:#fffaf1;
  --ink:#261f18;
  --muted:#756653;
  --line:#d6c0a0;
  --accent:#8b5e3c;
  --accent2:#c48772;
  --bad:#9d3f32;
}}
body {{ margin:0; background:var(--bg); color:var(--ink); font-family: Georgia, 'Times New Roman', serif; }}
header {{ padding:18px 24px; border-bottom:1px solid var(--line); display:flex; justify-content:space-between; align-items:center; }}
main {{ display:grid; grid-template-columns:minmax(460px, 1.2fr) minmax(420px, .8fr); gap:18px; padding:18px 24px; }}
video {{ width:100%; max-height:68vh; background:#000; border:1px solid var(--line); }}
.panel {{ background:var(--panel); border:1px solid var(--line); padding:16px; }}
.meta {{ color:var(--muted); font-size:14px; line-height:1.5; }}
.question {{ font-size:20px; line-height:1.35; margin:14px 0; }}
.option {{ border:1px solid var(--line); background:#fff; padding:12px; margin:10px 0; }}
.group {{ margin:16px 0; }}
.group h3 {{ font-size:15px; margin:0 0 8px; color:var(--muted); }}
button {{ border:1px solid var(--line); background:#fff; color:var(--ink); padding:9px 12px; margin:4px; cursor:pointer; font-size:15px; }}
button.selected {{ background:var(--accent); color:white; border-color:var(--accent); }}
button.warn {{ border-color:var(--bad); color:var(--bad); }}
button.primary {{ background:var(--accent2); border-color:var(--accent2); color:white; }}
.row {{ display:flex; flex-wrap:wrap; align-items:center; gap:4px; }}
.path {{ font-family: Consolas, monospace; font-size:12px; color:var(--muted); word-break:break-all; }}
.error {{ color:var(--bad); font-weight:bold; }}
@media (max-width: 980px) {{ main {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<header>
  <div><strong>VHD Question Label Review</strong> <span class="meta">reviewer_{reviewer}</span></div>
  <div class="meta" id="progress"></div>
</header>
<main>
  <section class="panel">
    <video id="video" controls preload="metadata"></video>
    <p id="videoError" class="error"></p>
    <p class="path" id="path"></p>
  </section>
  <section class="panel">
    <div class="meta" id="meta"></div>
    <div class="question" id="question"></div>
    <div class="option"><strong>A.</strong> <span id="optionA"></span></div>
    <div class="option"><strong>B.</strong> <span id="optionB"></span></div>

    <div class="group">
      <h3>Question valid</h3>
      <div class="row" data-field="question_valid">
        <button data-value="yes">yes</button>
        <button data-value="no" class="warn">no</button>
      </div>
    </div>

    <div class="group">
      <h3>Correct answer</h3>
      <div class="row" data-field="final_correct_answer">
        <button data-value="A">A</button>
        <button data-value="B">B</button>
      </div>
    </div>

    <div class="group" id="priorGroup">
      <h3>Language-prior-consistent option</h3>
      <div class="row" data-field="final_A_language_prior">
        <button data-value="A">A</button>
        <button data-value="B">B</button>
        <button data-value="">not applicable</button>
      </div>
    </div>

    <div class="group" id="visionGroup">
      <h3>Vision-consistent option</h3>
      <div class="row" data-field="final_A_vision">
        <button data-value="A">A</button>
        <button data-value="B">B</button>
        <button data-value="">not applicable</button>
      </div>
    </div>

    <div class="group" id="uncertaintyGroup">
      <h3>Expected uncertainty label</h3>
      <div class="row" data-field="final_uncertainty_label">
        <button data-value="uncertain">uncertain</button>
        <button data-value="">none / not applicable</button>
      </div>
    </div>

    <div class="group">
      <button id="useDraft">Use draft labels</button>
      <button id="prev">Previous</button>
      <button id="save" class="primary">Save & Next</button>
      <button id="next">Skip / Next</button>
      <button id="nextUnreviewed">Next unanswered</button>
    </div>
  </section>
</main>
<script>
let index = Number(new URLSearchParams(location.search).get('index') || 0);
let current = null;
let labels = {{}};

function setSelected(field, value) {{
  labels[field] = value;
  document.querySelectorAll(`[data-field="${{field}}"] button`).forEach(btn => {{
    btn.classList.toggle('selected', btn.dataset.value === value);
  }});
}}

document.querySelectorAll('[data-field] button').forEach(btn => {{
  btn.addEventListener('click', () => setSelected(btn.parentElement.dataset.field, btn.dataset.value));
}});

async function loadQuestion(i) {{
  const response = await fetch(`/api/question?index=${{i}}`);
  if (!response.ok) return;
  current = await response.json();
  index = current.index;
  history.replaceState(null, '', `?index=${{index}}`);
  labels = {{
    question_valid: current.question_valid || '',
    final_correct_answer: current.final_correct_answer || '',
    final_A_language_prior: current.final_A_language_prior || '',
    final_A_vision: current.final_A_vision || '',
    final_uncertainty_label: current.final_uncertainty_label || ''
  }};
  document.getElementById('progress').textContent = `${{current.index + 1}} / ${{current.total}} reviewed: ${{current.filled}}`;
  document.getElementById('meta').innerHTML = `${{escapeHtml(current.question_id)}} | ${{escapeHtml(current.task)}} | ${{escapeHtml(current.vhd_category)}} | ${{escapeHtml(current.stimulus_type)}}`;
  document.getElementById('question').textContent = current.question_text;
  document.getElementById('optionA').textContent = current.option_A;
  document.getElementById('optionB').textContent = current.option_B;
  document.getElementById('path').textContent = current.stimulus_path;
  const video = document.getElementById('video');
  const videoError = document.getElementById('videoError');
  videoError.textContent = current.media_exists ? '' : 'Video file is missing on disk.';
  video.src = `/media/${{encodeURIComponent(current.stimulus_path)}}`;
  video.onerror = () => {{ videoError.textContent = 'Video failed to load. Check media path or codec.'; }};
  for (const [field, value] of Object.entries(labels)) setSelected(field, value);
}}

function escapeHtml(s) {{
  return String(s || '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
}}

document.getElementById('useDraft').onclick = () => {{
  setSelected('question_valid', 'yes');
  setSelected('final_correct_answer', current.draft_correct_answer || '');
  setSelected('final_A_language_prior', current.draft_A_language_prior || '');
  setSelected('final_A_vision', current.draft_A_vision || '');
  setSelected('final_uncertainty_label', current.draft_uncertainty_label || '');
}};
document.getElementById('prev').onclick = () => loadQuestion(Math.max(0, index - 1));
document.getElementById('next').onclick = () => loadQuestion(Math.min(current.total - 1, index + 1));
document.getElementById('nextUnreviewed').onclick = async () => {{
  const response = await fetch(`/api/next_unreviewed?start=${{index + 1}}`);
  const data = await response.json();
  loadQuestion(data.index);
}};
document.getElementById('save').onclick = async () => {{
  await fetch('/api/save', {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{index, ...labels}})
  }});
  loadQuestion(Math.min(current.total - 1, index + 1));
}};
loadQuestion(index);
</script>
</body>
</html>"""


def make_handler(store: ReviewStore, reviewer: int):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/":
                text_response(self, app_html(reviewer))
                return
            if parsed.path == "/api/question":
                params = urllib.parse.parse_qs(parsed.query)
                index = int(params.get("index", ["0"])[0])
                row = store.get(index)
                if not row:
                    json_response(self, {"error": "index out of range"}, 404)
                    return
                row.update(store.stats())
                json_response(self, row)
                return
            if parsed.path == "/api/next_unreviewed":
                params = urllib.parse.parse_qs(parsed.query)
                start = int(params.get("start", ["0"])[0])
                json_response(self, {"index": store.next_unreviewed(start)})
                return
            if parsed.path.startswith("/media/"):
                serve_file(self, parsed.path[len("/media/"):])
                return
            text_response(self, "not found", 404, "text/plain; charset=utf-8")

        def do_POST(self):
            if self.path != "/api/save":
                text_response(self, "not found", 404, "text/plain; charset=utf-8")
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            row = store.save(payload)
            row.update(store.stats())
            json_response(self, row)

        def log_message(self, fmt, *args):
            return

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewer", type=int, default=1, choices=[1, 2])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    store = ReviewStore(args.reviewer)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(store, args.reviewer))
    print(f"Open http://{args.host}:{args.port}/?index=0")
    print(f"Writing to {store.path}")
    server.serve_forever()


if __name__ == "__main__":
    main()
