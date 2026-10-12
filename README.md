# ⚽ Futsal Highlights AI

MVP en Streamlit para detectar posibles goles y mejores jugadas en un vídeo de fútbol sala grabado con cámara móvil, revisar propuestas y exportar un resumen MP4.

## Desplegar en Streamlit Community Cloud

1. Abre https://share.streamlit.io/ e inicia sesión con GitHub.
2. Crea una app desde este repositorio (rama `main`; archivo principal `app.py`).
3. Streamlit instalará `requirements.txt` y `packages.txt` (FFmpeg).
4. Abre la URL asignada, introduce una clave de Gemini obtenida en https://aistudio.google.com/apikey y prueba con un MP4 corto (<200 MB y 5–10 minutos).

La clave se introduce mediante campo oculto en Streamlit y **no se almacena en GitHub**. El vídeo se envía temporalmente a Gemini para su análisis y se elimina del servicio de archivos tras el análisis (según funcionamiento de la API); el vídeo y los cortes temporales permanecen en la instancia hasta que se reinicie la sesión o el servidor. Evita contenido sensible y revisa los términos de Google.

## Limitaciones MVP

- El reconocimiento automático de goles no es fiable al 100 %; siempre hay que revisar.
- Límite de subida de Streamlit configurado en 200 MB. Memoria/CPU y tiempos de ejecución del hosting gratuito son limitados.
- Los costes/cuotas de Gemini varían por plan; compruébalos antes de enviar partidos.
- Los cortes se generan en CPU y pueden tardar; no hay trabajos persistentes en segundo plano.
- Este prototipo no incluye autenticación ni almacenamiento permanente; no publiques vídeos confidenciales en una app abierta.
