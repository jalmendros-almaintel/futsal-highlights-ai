import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

import streamlit as st
from google import genai

st.set_page_config(page_title="Futsal Highlights AI", page_icon="⚽", layout="wide")
st.title("⚽ Futsal Highlights AI")
st.caption("MVP · Detecta posibles goles y mejores jugadas, revisa los cortes y descarga un resumen.")
st.info("Primera prueba: usa un MP4 corto (idealmente 5–10 minutos y menos de 200 MB). La IA puede confundir goles y ocasiones. Revisa siempre los resultados.")

def duration(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                       capture_output=True, text=True, check=True)
    return float(p.stdout.strip())

def timestamp(t):
    seconds = max(0, int(t))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"

def to_seconds(value):
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    parts = s.split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    raise ValueError("Timestamp inválido: " + s)

def detect(video_path, api_key, total):
    client = genai.Client(api_key=api_key)
    remote = None
    try:
        remote = client.files.upload(file=str(video_path))
        deadline = time.monotonic() + 360
        while not remote.state or remote.state.name != "ACTIVE":
            if remote.state and remote.state.name == "FAILED":
                raise RuntimeError("Google no pudo procesar el vídeo.")
            if time.monotonic() > deadline:
                raise TimeoutError("Gemini tardó demasiado en procesar el archivo.")
            time.sleep(5)
            remote = client.files.get(name=remote.name)
        prompt = f"""Analiza este partido de fútbol sala grabado por una cámara que sigue el balón.
Duración total: {total:.1f} segundos.
Busca GOLES CONFIRMADOS, PARADAS DESTACADAS, OCASIONES CLARAS y JUGADAS DESTACADAS.
Solo marca un gol si es visualmente evidente; si no, clasifica como OCASION.
Devuelve únicamente JSON con esta forma:
{{"events":[{{"start":"MM:SS","end":"MM:SS","type":"GOL|PARADA|OCASION|JUGADA","description":"breve descripción","confidence":"alta|media|baja"}}]}}
Los tiempos son posiciones en el vídeo original, no el reloj del marcador.
Incluye unos segundos previos y posteriores a cada acción (clips de 8 a 22 segundos).
No inventes jugadas ni hagas referencias a eventos fuera del vídeo.
Máximo 20 eventos, ordenados cronológicamente.
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[remote, prompt],
            config={"response_mime_type": "application/json"},
        )
        raw = response.text or "{}"
        data = json.loads(raw)
        cleaned = []
        for item in data.get("events", []):
            try:
                start = max(0.0, to_seconds(item["start"]))
                end = min(total, to_seconds(item["end"]))
                if end <= start:
                    continue
                kind = str(item.get("type", "JUGADA")).upper()
                if kind not in ("GOL", "PARADA", "OCASION", "JUGADA"):
                    kind = "JUGADA"
                cleaned.append({"start": start, "end": end, "type": kind,
                                "description": str(item.get("description", ""))[:200],
                                "confidence": str(item.get("confidence", "baja"))})
            except (KeyError, ValueError, TypeError):
                continue
        return cleaned
    finally:
        if remote is not None:
            try:
                client.files.delete(name=remote.name)
            except Exception:
                pass

def render(video_path, events, output):
    with tempfile.TemporaryDirectory() as work:
        segments = []
        for i, ev in enumerate(events):
            clip = Path(work) / f"clip_{i:03d}.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", str(ev["start"]), "-i", str(video_path),
                "-t", str(ev["end"] - ev["start"]),
                "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-r", "25", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25",
                "-c:a", "aac", "-ar", "44100", "-ac", "2", str(clip)
            ], check=True, capture_output=True, timeout=180)
            segments.append(clip)
        listing = Path(work) / "concat.txt"
        listing.write_text("".join(f"file '{clip.as_posix()}'\n" for clip in segments))
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", str(output)],
                       check=True, capture_output=True, timeout=180)

key = st.text_input("Gemini API key (solo para esta sesión)", type="password")
st.markdown("[Crear API key en Google AI Studio](https://aistudio.google.com/apikey)")
upload = st.file_uploader("Sube tu partido en MP4", type=["mp4"])
if upload is not None:
    signature = (upload.name, upload.size)
    if st.session_state.get("signature") != signature:
        old = st.session_state.get("workdir")
        if old:
            old.cleanup()
        st.session_state["workdir"] = tempfile.TemporaryDirectory()
        path = Path(st.session_state["workdir"].name) / "partido.mp4"
        path.write_bytes(upload.getvalue())
        st.session_state["path"] = str(path)
        st.session_state["signature"] = signature
        st.session_state["events"] = None
        st.session_state["result"] = None
    try:
        total = duration(st.session_state["path"])
        st.video(st.session_state["path"])
        st.write(f"Duración: **{timestamp(total)}**")
        if st.button("🔍 Analizar partido", type="primary", disabled=not key):
            with st.spinner("Subiendo y analizando vídeo con Gemini..."):
                st.session_state["events"] = detect(st.session_state["path"], key, total)
                st.session_state["result"] = None
        events = st.session_state.get("events")
        if events is not None:
            st.subheader(f"Jugadas propuestas: {len(events)}")
            if not events:
                st.warning("La IA no ha encontrado jugadas. Prueba con otro vídeo.")
            selected = []
            for i, ev in enumerate(events):
                with st.container(border=True):
                    col1, col2 = st.columns([1, 3])
                    keep = col1.checkbox(f"Incluir #{i+1}", value=True, key=f"keep_{i}")
                    col2.write(f"**{ev['type']}** · {timestamp(ev['start'])}–{timestamp(ev['end'])} · Confianza: {ev['confidence']}")
                    st.caption(ev["description"])
                    a, b = st.columns(2)
                    start = a.number_input(f"Inicio #{i+1} (seg)", min_value=0.0, max_value=float(total),
                                           value=float(ev["start"]), step=1.0, key=f"start_{i}")
                    end = b.number_input(f"Final #{i+1} (seg)", min_value=0.0, max_value=float(total),
                                         value=float(ev["end"]), step=1.0, key=f"end_{i}")
                    if keep and end > start:
                        selected.append({**ev, "start": start, "end": end})
            if st.button("🎬 Generar resumen", disabled=not selected):
                outfile = Path(st.session_state["workdir"].name) / "futsal_highlights.mp4"
                try:
                    with st.spinner("Generando MP4 con FFmpeg..."):
                        render(st.session_state["path"], selected, outfile)
                    st.session_state["result"] = outfile.read_bytes()
                except (subprocess.SubprocessError, OSError) as exc:
                    st.error(f"Error generando el vídeo: {exc}")
            if st.session_state.get("result"):
                st.success("¡Resumen listo!")
                st.video(st.session_state["result"])
                st.download_button("⬇️ Descargar highlights MP4", st.session_state["result"],
                                   file_name="futsal_highlights.mp4", mime="video/mp4")
    except (subprocess.SubprocessError, OSError, ValueError) as exc:
        st.error(f"No se pudo leer el vídeo: {exc}")
    except Exception as exc:
        st.error(f"No se pudo completar el análisis: {exc}")
