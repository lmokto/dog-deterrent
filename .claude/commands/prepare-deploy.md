Prepara el proyecto para desplegar en Raspberry Pi 5.

1. Revisa todos los archivos en src/ y verifica compatibilidad RPi:
   - ¿Usa picamera2 con fallback a cv2.VideoCapture?
   - ¿Los imports de GPIO están en try/except?
   - ¿El formato de cámara es RGB888?
2. Genera un script deploy.sh que:
   - Copie los archivos necesarios vía scp
   - Instale dependencias en la RPi (con --break-system-packages)
   - Configure un servicio systemd para arranque automático
3. Actualiza config/settings.yaml con camera_source: "picamera2"
4. Verifica que los pines GPIO están correctos
5. Lista los cambios necesarios antes del deploy
