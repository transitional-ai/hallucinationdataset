from __future__ import annotations

import argparse
import gc
import importlib.metadata
import json
import math
import os
import platform
import random
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch


MODEL_SPECS = {
    "qwen": {
        "model_id": "Qwen/Qwen2.5-Omni-3B",
        "slug": "qwen2_5_omni_3b",
    },
    "qwen7": {
        "model_id": "Qwen/Qwen2.5-Omni-7B",
        "slug": "qwen2_5_omni_7b",
    },
    "minicpm": {
        "model_id": "openbmb/MiniCPM-o-2_6",
        "int4_model_id": "openbmb/MiniCPM-o-2_6-int4",
        "slug": "minicpm_o_2_6",
    },
}

MANIFEST_COLUMNS = [
    "video_split",
    "release_video_path",
    "question_id",
    "clip_id",
    "vhd_category",
    "task",
    "stimulus_type",
    "long_video_name",
    "long_video_start_sec_planned",
    "long_video_end_sec_planned",
    "question_text",
    "option_A",
    "option_B",
    "option_C",
    "option_D",
    "final_correct_answer",
    "final_A_language_prior",
    "final_A_vision",
    "final_uncertainty_label",
]

RESULT_COLUMNS = MANIFEST_COLUMNS + [
    "model_key",
    "model_id",
    "model_revision",
    "quantization",
    "input_mode",
    "audio_policy",
    "audio_stream_present",
    "audio_used",
    "sampling_fps",
    "max_frames",
    "max_pixels",
    "generation_mode",
    "max_new_tokens",
    "seed",
    "selected_choice",
    "confidence",
    "parse_status",
    "refusal",
    "is_correct",
    "is_language_prior_choice",
    "is_vision_grounded_choice",
    "uncertainty_expression_correct",
    "raw_response_attempt_1",
    "raw_response_attempt_2",
    "attempt_count",
    "latency_seconds",
    "error_type",
    "error_message",
    "completed_at_utc",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def choose_dtype() -> torch.dtype:
    major, _ = torch.cuda.get_device_capability(0)
    return torch.bfloat16 if major >= 8 else torch.float16


def gpu_memory_gib() -> float:
    return torch.cuda.get_device_properties(0).total_memory / 1024**3


def available_choices(row: pd.Series) -> list[str]:
    choices = []
    for letter in "ABCD":
        value = str(row.get(f"option_{letter}", "")).strip()
        if value and value.lower() != "nan":
            choices.append(letter)
    return choices


def row_requires_confidence(row: pd.Series) -> bool:
    value = str(row.get("requires_confidence", "")).strip().lower()
    if value in {"yes", "true", "1"}:
        return True
    if value in {"no", "false", "0"}:
        return False
    return str(row.get("task", "")) == "vhd_ii_hce"


def build_prompt(row: pd.Series, audio_used: bool, strict_retry: bool = False) -> str:
    choices = available_choices(row)
    option_lines = [
        f"{letter}. {str(row[f'option_{letter}']).strip()}" for letter in choices
    ]
    evidence = "visual and audible evidence" if audio_used else "visual evidence"
    retry = "Your previous response did not follow the output format. " if strict_retry else ""
    base = (
        f"{retry}Inspect the video carefully and answer using only its {evidence}.\n"
        f"Question: {str(row['question_text']).strip()}\n"
        + "\n".join(option_lines)
    )
    if row_requires_confidence(row):
        return (
            base
            + "\nReturn exactly one JSON object and no explanation. "
            + 'Use this schema: {"choice":"<one allowed option>","confidence_percent":<integer percentage>}. '
            + f"The allowed choice values are {choices}. confidence_percent must represent "
            + "the estimated probability that the selected choice is correct."
        )
    return (
        base
        + "\nReturn exactly one JSON object and no explanation. "
        + 'Use this schema: {"choice":"<one allowed option>"}. '
        + f"The allowed choice values are {choices}."
    )


def normalise_confidence(value: Any) -> float | None:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if 1 < confidence <= 100:
        confidence /= 100.0
    return confidence if 0 <= confidence <= 1 else None


def parse_response(
    text: str, allowed: list[str], require_confidence: bool
) -> tuple[str, float | None, str]:
    cleaned = text.strip()
    for candidate in reversed(re.findall(r"\{[^{}]*\}", cleaned, flags=re.DOTALL)):
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        choice = str(payload.get("choice", "")).strip().upper()
        confidence = normalise_confidence(
            payload.get("confidence_percent", payload.get("confidence"))
        )
        if choice in allowed and (confidence is not None or not require_confidence):
            return choice, confidence, "json"

    choice_match = re.search(
        r"(?:choice|answer)\s*[:=]\s*[\"']?([A-D])\b", cleaned, re.IGNORECASE
    )
    confidence_match = re.search(
        r"confidence(?:_percent)?\s*[:=]\s*[\"']?([0-9]*\.?[0-9]+)",
        cleaned,
        re.IGNORECASE,
    )
    choice = choice_match.group(1).upper() if choice_match else ""
    confidence = normalise_confidence(confidence_match.group(1)) if confidence_match else None
    if choice in allowed and (confidence is not None or not require_confidence):
        return choice, confidence, "regex"
    if choice in allowed:
        return choice, None, "choice_only"
    return "", None, "unparsed"


def is_refusal(text: str) -> bool:
    lowered = text.lower()
    phrases = (
        "i cannot comply",
        "i can't comply",
        "unable to comply",
        "i am not able to answer",
        "i'm not able to answer",
    )
    return any(phrase in lowered for phrase in phrases)


def ffprobe_value(video_path: Path, args: list[str]) -> str:
    command = ["ffprobe", "-v", "error", *args, str(video_path)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def has_audio_stream(video_path: Path) -> bool:
    try:
        value = ffprobe_value(
            video_path,
            ["-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0"],
        )
        return bool(value)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def video_duration(video_path: Path) -> float:
    value = ffprobe_value(
        video_path,
        ["-show_entries", "format=duration", "-of", "default=nw=1:nk=1"],
    )
    return float(value)


def audio_allowed(policy: str, row: pd.Series, stream_present: bool) -> bool:
    if not stream_present or policy == "none":
        return False
    if policy == "except_masked" and row["task"] == "vhd_ii_hce":
        return False
    return True


class QwenOmniAdapter:
    def __init__(
        self,
        model_id: str,
        fps: float,
        max_frames: int,
        max_pixels: int,
        max_new_tokens: int,
        quantization: str,
    ):
        from qwen_omni_utils import process_mm_info
        from transformers import (
            BitsAndBytesConfig,
            Qwen2_5OmniForConditionalGeneration,
            Qwen2_5OmniProcessor,
        )

        self.process_mm_info = process_mm_info
        self.dtype = choose_dtype()
        self.fps = fps
        self.max_frames = max_frames
        self.max_pixels = max_pixels
        self.max_new_tokens = max_new_tokens
        self.quantization = "4bit" if quantization == "auto" and gpu_memory_gib() < 22 else quantization
        if self.quantization == "auto":
            self.quantization = "none"

        load_kwargs: dict[str, Any] = {
            "device_map": "auto",
            "torch_dtype": self.dtype,
            "low_cpu_mem_usage": True,
            "attn_implementation": "sdpa",
        }
        if self.quantization == "4bit":
            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=self.dtype,
                bnb_4bit_use_double_quant=True,
            )
        self.model = Qwen2_5OmniForConditionalGeneration.from_pretrained(
            model_id, **load_kwargs
        ).eval()
        self.model.disable_talker()
        self.processor = Qwen2_5OmniProcessor.from_pretrained(model_id)
        self.revision = getattr(self.model.config, "_commit_hash", "") or "unknown"

    def generate(self, video_path: Path, prompt: str, use_audio: bool) -> str:
        conversation = [
            {
                "role": "system",
                "content": [{"type": "text", "text": "You are a careful video question-answering assistant."}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "video",
                        "video": str(video_path.resolve()),
                        "fps": self.fps,
                        "max_pixels": self.max_pixels,
                    },
                    {"type": "text", "text": prompt},
                ],
            },
        ]
        text = self.processor.apply_chat_template(
            conversation, add_generation_prompt=True, tokenize=False
        )
        audios, images, videos = self.process_mm_info(
            conversation, use_audio_in_video=use_audio
        )
        inputs = self.processor(
            text=text,
            audio=audios,
            images=images,
            videos=videos,
            return_tensors="pt",
            padding=True,
            use_audio_in_video=use_audio,
        )
        inputs = inputs.to(self.model.device).to(self.model.dtype)
        with torch.inference_mode():
            text_ids = self.model.generate(
                **inputs,
                use_audio_in_video=use_audio,
                return_audio=False,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
            )
        response = self.processor.batch_decode(
            text_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0].strip()
        del inputs, text_ids, audios, images, videos
        torch.cuda.empty_cache()
        return response


class MiniCPMOmniAdapter:
    def __init__(
        self,
        model_id: str,
        int4_model_id: str,
        fps: float,
        max_frames: int,
        max_pixels: int,
        max_new_tokens: int,
        quantization: str,
    ):
        from transformers import AutoModel, AutoTokenizer, BitsAndBytesConfig

        self.dtype = choose_dtype()
        self.fps = fps
        self.max_frames = max_frames
        self.max_pixels = max_pixels
        self.max_new_tokens = max_new_tokens
        self.quantization = "4bit" if quantization == "auto" and gpu_memory_gib() < 22 else quantization
        if self.quantization == "auto":
            self.quantization = "none"

        def load_minicpm(load_kwargs: dict[str, Any]) -> Any:
            errors: list[str] = []
            for attn_impl in ("sdpa", "eager"):
                try:
                    return AutoModel.from_pretrained(
                        self.loaded_model_id,
                        trust_remote_code=True,
                        attn_implementation=attn_impl,
                        **load_kwargs,
                    ).eval()
                except Exception as exc:
                    message = str(exc).lower()
                    errors.append(f"{attn_impl}: {exc}")
                    if "flash-attn" not in message and "flash_attn" not in message:
                        raise
            raise RuntimeError(
                "MiniCPM loading failed after sdpa/eager fallback. "
                + " | ".join(errors)
            )

        if self.quantization == "4bit":
            self.loaded_model_id = model_id
            self.model = load_minicpm(
                {
                    "torch_dtype": self.dtype,
                    "device_map": "auto",
                    "low_cpu_mem_usage": True,
                    "init_vision": True,
                    "init_audio": True,
                    "init_tts": False,
                    "quantization_config": BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=self.dtype,
                        bnb_4bit_use_double_quant=True,
                    ),
                }
            )
        else:
            self.loaded_model_id = model_id
            self.model = load_minicpm(
                {
                    "torch_dtype": self.dtype,
                    "init_vision": True,
                    "init_audio": True,
                    "init_tts": False,
                }
            ).cuda()
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.loaded_model_id, trust_remote_code=True
        )
        self.revision = getattr(self.model.config, "_commit_hash", "") or "unknown"

    def _load_audio(self, video_path: Path, duration: float, use_audio: bool) -> np.ndarray:
        sample_count = max(1, int(math.ceil(duration * 16000)))
        if not use_audio:
            return np.zeros(sample_count, dtype=np.float32)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            wav_path = Path(handle.name)
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error", "-i", str(video_path),
                    "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav_path),
                ],
                check=True,
            )
            import soundfile as sf

            audio, sample_rate = sf.read(wav_path, dtype="float32", always_2d=False)
            if sample_rate != 16000:
                raise ValueError(f"Expected 16 kHz audio, received {sample_rate} Hz")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if len(audio) < sample_count:
                audio = np.pad(audio, (0, sample_count - len(audio)))
            return audio[:sample_count]
        finally:
            wav_path.unlink(missing_ok=True)

    def _video_audio_units(self, video_path: Path, use_audio: bool) -> list[Any]:
        from decord import VideoReader, cpu
        from PIL import Image

        duration = video_duration(video_path)
        reader = VideoReader(str(video_path), ctx=cpu(0))
        source_fps = float(reader.get_avg_fps())
        unit_count = min(self.max_frames, max(1, math.ceil(duration * self.fps)))
        audio = self._load_audio(video_path, duration, use_audio)
        contents: list[Any] = []
        for unit in range(unit_count):
            timestamp = min((unit + 0.5) / self.fps, max(duration - 0.001, 0.0))
            frame_index = min(int(timestamp * source_fps), len(reader) - 1)
            image = Image.fromarray(reader[frame_index].asnumpy().astype(np.uint8))
            start = int(unit * 16000 / self.fps)
            end = int((unit + 1) * 16000 / self.fps)
            audio_chunk = audio[start:end]
            expected = end - start
            if len(audio_chunk) < expected:
                audio_chunk = np.pad(audio_chunk, (0, expected - len(audio_chunk)))
            contents.extend(["<unit>", image, audio_chunk.astype(np.float32)])
        return contents

    def generate(self, video_path: Path, prompt: str, use_audio: bool) -> str:
        sys_msg = self.model.get_sys_prompt(mode="omni", language="en")
        contents = self._video_audio_units(video_path, use_audio)
        contents.append(prompt)
        result = self.model.chat(
            msgs=[sys_msg, {"role": "user", "content": contents}],
            tokenizer=self.tokenizer,
            sampling=False,
            max_new_tokens=self.max_new_tokens,
            omni_input=True,
            use_tts_template=False,
            generate_audio=False,
            max_slice_nums=1,
            use_image_id=False,
            return_dict=False,
        )
        if isinstance(result, str):
            response = result
        elif isinstance(result, dict):
            response = str(result.get("text") or result.get("response") or result)
        elif hasattr(result, "text"):
            response = str(result.text)
        else:
            response = str(result)
        del contents, result
        torch.cuda.empty_cache()
        return response.strip()


def load_manifest(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    optional_columns = {"option_C", "option_D"}
    missing = [
        column
        for column in MANIFEST_COLUMNS
        if column not in frame.columns and column not in optional_columns
    ]
    if missing:
        raise ValueError(f"Manifest is missing columns: {missing}")
    for column in optional_columns:
        if column not in frame.columns:
            frame[column] = ""
    if frame["question_id"].duplicated().any():
        raise ValueError("Manifest contains duplicate question_id values")
    if len(frame) != 807:
        raise ValueError(f"Expected 807 validated questions, found {len(frame)}")
    return frame[MANIFEST_COLUMNS].copy()


def locate_dataset_root(download_root: Path, manifest: pd.DataFrame) -> Path:
    sample = Path(manifest.iloc[0]["release_video_path"])
    candidates = [download_root, download_root / "VHD_pilot_dataset"]
    candidates.extend(path.parent.parent for path in download_root.rglob("vhd_questions.csv"))
    for candidate in candidates:
        if (candidate / sample).is_file():
            return candidate
    raise FileNotFoundError(
        f"Could not locate {sample} under downloaded Kaggle directory {download_root}"
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Ignoring incomplete JSONL line {line_number}")
    return records


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_csv_atomic(path: Path, records: list[dict[str, Any]], order: dict[str, int]) -> None:
    if not records:
        return
    latest = {record["question_id"]: record for record in records}
    ordered = sorted(latest.values(), key=lambda item: order.get(item["question_id"], 10**9))
    frame = pd.DataFrame(ordered)
    for column in RESULT_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    temp_path = path.with_suffix(".tmp.csv")
    frame[RESULT_COLUMNS].to_csv(temp_path, index=False, encoding="utf-8")
    os.replace(temp_path, path)


def score_record(record: dict[str, Any]) -> None:
    selected = record.get("selected_choice", "")
    correct = record.get("final_correct_answer", "")
    prior = record.get("final_A_language_prior", "")
    vision = record.get("final_A_vision", "")
    record["is_correct"] = int(selected == correct) if selected and correct else ""
    record["is_language_prior_choice"] = int(selected == prior) if selected and prior else ""
    record["is_vision_grounded_choice"] = int(selected == vision) if selected and vision else ""
    record["uncertainty_expression_correct"] = (
        record["is_correct"] if record.get("task") == "vhd_ii_hce" else ""
    )


def write_run_metadata(
    path: Path, args: argparse.Namespace, adapter: Any, loaded_model_id: str
) -> None:
    metadata = {
        "created_at_utc": utc_now(),
        "model_key": args.model_key,
        "model_id": loaded_model_id,
        "model_revision": adapter.revision,
        "quantization": adapter.quantization,
        "input_mode": "native_video_with_available_audio",
        "audio_policy": args.audio_policy,
        "sampling_fps": args.fps,
        "max_frames": args.max_frames,
        "max_pixels": args.max_pixels,
        "generation_mode": "greedy",
        "max_new_tokens": args.max_new_tokens,
        "seed": args.seed,
        "gpu": torch.cuda.get_device_name(0),
        "gpu_memory_gib": round(gpu_memory_gib(), 2),
        "cuda": torch.version.cuda,
        "torch": torch.__version__,
        "python": sys.version,
        "platform": platform.platform(),
        "transformers": package_version("transformers"),
        "accelerate": package_version("accelerate"),
        "decord": package_version("decord"),
        "bitsandbytes": package_version("bitsandbytes"),
        "auto-gptq": package_version("auto-gptq"),
    }
    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("A CUDA GPU runtime is required")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)

    manifest = load_manifest(args.manifest)
    dataset_root = locate_dataset_root(args.dataset_root, manifest)
    missing_videos = [
        rel for rel in manifest["release_video_path"] if not (dataset_root / rel).is_file()
    ]
    if missing_videos:
        raise FileNotFoundError(f"Missing {len(missing_videos)} videos; first: {missing_videos[0]}")

    spec = MODEL_SPECS[args.model_key]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / f"{spec['slug']}_responses.jsonl"
    csv_path = args.output_dir / f"{spec['slug']}_responses.csv"
    metadata_path = args.output_dir / f"{spec['slug']}_run_metadata.json"

    if args.model_key == "qwen":
        adapter = QwenOmniAdapter(
            spec["model_id"], args.fps, args.max_frames, args.max_pixels,
            args.max_new_tokens, args.quantization,
        )
        loaded_model_id = spec["model_id"]
    else:
        adapter = MiniCPMOmniAdapter(
            spec["model_id"], spec["int4_model_id"], args.fps, args.max_frames,
            args.max_pixels, args.max_new_tokens, args.quantization,
        )
        loaded_model_id = adapter.loaded_model_id
    write_run_metadata(metadata_path, args, adapter, loaded_model_id)

    records = read_jsonl(ledger_path)
    completed = {record["question_id"] for record in records}
    order = {question_id: index for index, question_id in enumerate(manifest["question_id"])}
    print(f"Dataset root: {dataset_root}")
    print(f"Output CSV: {csv_path}")
    print(f"Resuming with {len(completed)} of {len(manifest)} questions complete")

    new_since_csv = 0
    try:
        for _, row in manifest.iterrows():
            question_id = row["question_id"]
            if question_id in completed:
                continue
            if args.limit and len(completed) >= args.limit:
                break
            start = time.perf_counter()
            video_path = dataset_root / row["release_video_path"]
            stream_present = has_audio_stream(video_path)
            use_audio = audio_allowed(args.audio_policy, row, stream_present)
            record = {column: row[column] for column in MANIFEST_COLUMNS}
            record.update(
                {
                    "model_key": args.model_key,
                    "model_id": loaded_model_id,
                    "model_revision": adapter.revision,
                    "quantization": adapter.quantization,
                    "input_mode": "native_video_with_available_audio",
                    "audio_policy": args.audio_policy,
                    "audio_stream_present": stream_present,
                    "audio_used": use_audio,
                    "sampling_fps": args.fps,
                    "max_frames": args.max_frames,
                    "max_pixels": args.max_pixels,
                    "generation_mode": "greedy",
                    "max_new_tokens": args.max_new_tokens,
                    "seed": args.seed,
                    "selected_choice": "",
                    "confidence": "",
                    "parse_status": "",
                    "refusal": False,
                    "raw_response_attempt_1": "",
                    "raw_response_attempt_2": "",
                    "attempt_count": 0,
                    "error_type": "",
                    "error_message": "",
                }
            )
            allowed = available_choices(row)
            require_confidence = row_requires_confidence(row)
            try:
                for attempt in (1, 2):
                    prompt = build_prompt(row, use_audio, strict_retry=(attempt == 2))
                    response = adapter.generate(video_path, prompt, use_audio)
                    record[f"raw_response_attempt_{attempt}"] = response
                    record["attempt_count"] = attempt
                    choice, confidence, parse_status = parse_response(
                        response, allowed, require_confidence
                    )
                    record["refusal"] = record["refusal"] or is_refusal(response)
                    record["selected_choice"] = choice
                    record["confidence"] = "" if confidence is None else confidence
                    record["parse_status"] = parse_status
                    if choice and (confidence is not None or not require_confidence):
                        break
            except Exception as exc:
                record["error_type"] = type(exc).__name__
                record["error_message"] = str(exc)[:2000]
                torch.cuda.empty_cache()
                gc.collect()

            record["latency_seconds"] = round(time.perf_counter() - start, 4)
            record["completed_at_utc"] = utc_now()
            score_record(record)
            append_jsonl(ledger_path, record)
            records.append(record)
            completed.add(question_id)
            new_since_csv += 1

            if new_since_csv >= args.save_every:
                write_csv_atomic(csv_path, records, order)
                new_since_csv = 0
            print(
                f"[{len(completed):03d}/{len(manifest)}] {question_id}: "
                f"choice={record['selected_choice'] or '-'} "
                f"confidence={record['confidence'] if record['confidence'] != '' else '-'} "
                f"audio={int(use_audio)} status={record['parse_status'] or record['error_type']}"
            )
    finally:
        write_csv_atomic(csv_path, records, order)
        print(f"Checkpoint saved: {csv_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-key", choices=MODEL_SPECS, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--quantization", choices=("auto", "none", "4bit"), default="auto")
    parser.add_argument("--audio-policy", choices=("all", "except_masked", "none"), default="except_masked")
    parser.add_argument("--fps", type=float, default=1.0)
    parser.add_argument("--max-frames", type=int, default=16)
    parser.add_argument("--max-pixels", type=int, default=151200)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--save-every", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
