# Control de Transferencias

Aplicación web sencilla para gestionar transferencias de dinero entre dos personas, con seguimiento mensual, objetivos y progreso visual.

---

## Funcionalidades

- Registro de transferencias (monto, fecha, descripción)
- Confirmación / desconfirmación de transferencias
- Cálculo automático del total confirmado
- Comparación contra objetivo mensual
- Cálculo de dinero pendiente por confirmar
- Barra de progreso visual
- Filtro por mes
- Sistema de backups automáticos de base de datos

---

## Tecnologías utilizadas

- **Backend:** Python (Flask)
- **Base de datos:** PostgreSQL (Render)
- **Frontend:** HTML, CSS, JavaScript
- **Deploy:** Render

---

##  Arquitectura

- Aplicación web con backend en Flask
- Base de datos PostgreSQL en la nube
- Comunicación vía API REST
- Backups automáticos mediante script (`backup.py`)

---

##  Seguridad

- Sistema de login validado en backend
- Protección básica de acceso mediante PIN
- Separación entre frontend y backend

---

##  ¿Qué problema resuelve?

Permite llevar un control claro del dinero transferido mes a mes, evitando confusiones sobre:

- Cuánto dinero se ha enviado
- Cuánto falta para cumplir el objetivo mensual
- Qué transferencias aún no han sido confirmadas

---

##  Aprendizajes clave

Este proyecto fue desarrollado para aprender:

- Desarrollo backend real con Flask
- Integración con base de datos PostgreSQL
- Diseño de una API simple
- Manejo de estado y lógica de negocio
- Mejores prácticas de UX/UI básicas
- Deploy en producción (Render)
- Automatización de backups
- Uso de Git y GitHub en proyectos reales

---

##  Instalación local

```bash
git clone https://github.com/Carlosdefaria/Transferencias-app.git
cd Transferencias-app
pip install -r requirements.txt
python app.py
```


---

##  Estado del proyecto

- Proyecto funcional en producción  
- En mejora continua


---

##  Mejoras futuras

- Autenticación con usuarios reales
- Dashboard con gráficos
- Notificaciones de progreso
- Versión móvil / PWA
- Mejoras de seguridad