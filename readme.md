# Control de Transferencias

Aplicación web sencilla para gestionar transferencias de dinero entre dos personas, con seguimiento mensual, objetivos y progreso visual.

---

## Demo

https://tu-app.onrender.com

---

## Funcionalidades

- Registro de transferencias (monto, fecha, descripción)
- Confirmación / desconfirmación de transferencias
- Cálculo automático del total confirmado
- Comparación contra objetivo mensual
- Cálculo de dinero pendiente por confirmar
- Barra de progreso visual
- Filtro por mes
- Soporte multi-moneda (EUR, USD, GBP)

---

## Tecnologías utilizadas

- **Backend:** Python (Flask)
- **Base de datos:** PostgreSQL (Render)
- **Frontend:** HTML, CSS, JavaScript
- **Deploy:** Render

---

## Arquitectura

- Aplicación web con backend en Flask
- Base de datos PostgreSQL en la nube
- API REST para comunicación frontend-backend
- Lógica de negocio centralizada en el servidor

---

## Seguridad

- Sistema de login con validación en backend
- Autenticación basada en sesión
- Protección de rutas sensibles
- Uso de variables de entorno (`SECRET_KEY`, `DATABASE_URL`)

---

## ¿Qué problema resuelve?

Permite llevar un control claro del dinero transferido mes a mes, evitando confusiones sobre:

- Cuánto dinero se ha enviado
- Cuánto falta para cumplir el objetivo mensual
- Qué transferencias aún no han sido confirmadas

---

## Instalación local

```bash
git clone https://github.com/Carlosdefaria/Transferencias-app.git
cd Transferencias-app
pip install -r requirements.txt

# Configurar variables de entorno (IMPORTANTE)
export DATABASE_URL=tu_database_url
export SECRET_KEY=tu_secret_key

# Ejecutar la app
python app.py
```

---

## Aprendizajes clave

Este proyecto fue desarrollado para aprender:

- Desarrollo backend real con Flask
- Integración con base de datos PostgreSQL
- Diseño de APIs REST
- Implementación de lógica de negocio real
- Mejores prácticas de UX/UI básicas
- Deploy en producción (Render)
- Uso de Git y GitHub en proyectos reales

---

## Estado del proyecto

- Versión 1.0 funcional desplegada en producción
- Lista para uso real
- Base sólida para futuras mejoras

---

## Mejoras futuras

- Autenticación con usuarios reales
- Dashboard con gráficos
- Notificaciones de progreso
- Versión móvil / PWA
- Mejoras de seguridad
