---
name: Reporte de Bugs
about: Usá esta plantilla para reportar errores, fallas visuales o comportamientos
  inesperados en la plataforma.
title: ''
labels: bug
assignees: ''
type: Bug

---

## 🐛 Descripción del Bug
Ejemplo: Al intentar enviar el formulario de contacto en la Landing Page con un email sin el "@", la página se queda cargando infinitamente y no muestra error.

## 🔄 Pasos para reproducirlo
1. Entrar a 'vetween.com/landing'
2. Scrollear hasta la sección de Contacto.
3. Escribir "Juan" en el campo Nombre.
4. Escribir "juan.gmail.com" en el campo Email.
5. Hacer clic en el botón "Enviar".
6. Ver el error (el botón gira infinitamente).

## ✅ Comportamiento Esperado
El formulario debería rechazar el envío y mostrar un texto en rojo que diga: "Por favor, ingresa un correo válido".

## ❌ Comportamiento Actual
No aparece ningún mensaje de validación y la página queda bloqueada.

## 📸 Capturas de Pantalla o Video
[Arrastrar imagen aquí]

## 🖥️ Entorno de Pruebas
* **Dispositivo:** [ej. PC de escritorio, iPhone 13, Samsung S22]
* **Sistema Operativo:** [ej. Windows 11, iOS 16, Android 13]
* **Navegador:** [ej. Chrome, Safari, Edge]
* **Versión:** [ej. 114.0.5]

## 🚨 Gravedad del Error
- [ ] **Baja:** Un error visual menor (un color mal, un texto desalineado).
- [ ] **Media:** Algo no funciona bien pero el usuario puede seguir usando la página.
- [ ] **Alta:** Bloquea una función principal (ej. no se puede enviar el formulario).
- [ ] **Crítica:** La página se cae, tira error 500 o expone datos.
