# Frontend — web estática (PWA) servida por nginx.
# nginx además hace proxy de las rutas de la API hacia el backend (mismo origen para el navegador),
# así el front no necesita conocer el host del backend. Ver web/nginx.conf.
FROM nginx:1.27-alpine

# BACKEND_URL se sustituye en la plantilla al arrancar (mecanismo estándar de la imagen nginx)
ENV BACKEND_URL=http://backend:8080

RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY index.html simulador.html manifest.webmanifest sw.js /usr/share/nginx/html/
COPY css/ /usr/share/nginx/html/css/
COPY js/ /usr/share/nginx/html/js/

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/index.html || exit 1
