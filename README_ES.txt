DENYER DR — SERVIDOR DE SUBTÍTULOS AUTOMÁTICOS (BASE)

QUÉ HACE
- Recibe un video en POST /v1/transcribe.
- Extrae el audio con FFmpeg.
- Divide audios largos en segmentos.
- Solicita transcripción en español al servicio de voz.
- Devuelve segmentos con inicio, fin y texto en JSON.

IMPORTANTE
- Este paquete es el servidor base; todavía NO está conectado a la APK.
- No contiene ninguna clave real.
- No está desplegado en Internet ni probado con una cuenta API real.
- La API key se configura como variable privada OPENAI_API_KEY en el servidor.
- APP_ACCESS_TOKEN protege el endpoint para que no quede abierto al público.
- El servidor recibe el video completo. Usa HTTPS al desplegarlo.
- Los límites de tamaño y tiempo se pueden ajustar en las variables de entorno.

DESPLIEGUE
1. Sube esta carpeta a un servicio de hosting que permita Docker.
2. Configura OPENAI_API_KEY y APP_ACCESS_TOKEN como variables secretas del servicio.
3. Despliega el contenedor.
4. Comprueba GET /health.
5. La ruta que conectaremos desde DENYER DR será POST https://TU-DOMINIO/v1/transcribe.
6. La app enviará el archivo como multipart/form-data, campo "video", y el token en "X-App-Token".

RESPUESTA ESPERADA
{
  "language": "es",
  "segments": [
    {"start": 0.0, "end": 2.4, "text": "Hola, bienvenidos."}
  ],
  "count": 1,
  "format": "denyer-dr-subtitles-v1"
}

REQUISITOS DEL HOST
- Docker.
- FFmpeg instalado (incluido en Dockerfile).
- Acceso HTTPS público.
- Variables de entorno secretas.
- Capacidad para subir y procesar archivos de video.

NOTAS DE IMPLEMENTACIÓN
- El código usa el modelo gpt-4o-transcribe-diarize y normaliza los segmentos al formato de DENYER DR.
- Los segmentos se compensan con el tiempo de cada fragmento de audio.
- Antes de usar en producción deben añadirse límites por usuario, cuotas, limpieza/retención explícita y pruebas con distintos formatos de video.
