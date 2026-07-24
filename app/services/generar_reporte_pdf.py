import os
import sys

# 1. Buscamos las rutas de instalación más comunes de GTK en Windows
rutas_gtk = [
    r"D:\GTK3-Runtime Win64\bin",
    r"C:\Program Files (x86)\GTK3-RuntimeWin64\bin",
    r"C:\GTK\bin" # Por si lo descomprimiste en la raíz
]

# 2. Le inyectamos la ruta correcta a Python antes de cargar WeasyPrint
if os.name == "nt":  # Solo aplica para Windows
    for ruta in rutas_gtk:
        if os.path.exists(ruta):
            # Agrega las DLLs para Python 3.8+
            os.add_dll_directory(ruta)
            # Agrega al PATH por compatibilidad con librerías más viejas
            os.environ['PATH'] = ruta + os.path.pathsep + os.environ['PATH']
            break

import weasyprint
from fastapi.responses import FileResponse
def crear_reporte_clinico_pdf(id_paciente: str, paciente_info: dict, ia_data: dict, file_path: str):
    """
    Genera un archivo PDF estilizado combinando los datos demográficos del paciente
    y el análisis devuelto por la IA.
    """
    # Extracción de datos del paciente
    nombre_mascota = paciente_info.get("nombre", "Mascota")
    especie_mascota = paciente_info.get("especie", "-")
    raza_mascota = paciente_info.get("raza", "-")
    edad_mascota = paciente_info.get("edad", "-")
    peso_mascota = paciente_info.get("peso", "-")
    sexo_mascota = paciente_info.get("sexo", "-")

    # Extracción de datos de la IA
    resumen_texto = ia_data.get("descripcion_clinica", "Sin descripción clínica disponible.")
    estado_general = ia_data.get("estado_general", "Estable")
    tipo_consulta = ia_data.get("tipo_paciente", "Consulta General")
    
    sintesis_visitas = ia_data.get("sintesis_visitas", [])
    historial_vacunas = ia_data.get("historial_vacunas", [])
    proximos = ia_data.get("puntos_clave_proximas_consultas", [])

    # Renderizado dinámico de Visitas
    visitas_html = ""
    for v in sintesis_visitas:
        visitas_html += f"""
        <tr>
            <td>{v.get('fecha', '-')}</td>
            <td>{v.get('motivo', '-')}</td>
            <td>{v.get('diagnostico', '-')}</td>
            <td>{v.get('tratamiento', '-')}</td>
        </tr>
        """

    # Renderizado dinámico de Vacunas
    vacunas_html = ""
    for vac in historial_vacunas:
        vacunas_html += f"""
        <tr>
            <td>{vac.get('fecha_aplicacion', '-')}</td>
            <td>{vac.get('nombre', '-')}</td>
            <td><span class="badge">{vac.get('estado', '-')}</span></td>
        </tr>
        """

    # Renderizado de Próximos pasos
    proximos_html = "".join([f"<li>{item}</li>" for item in proximos])

    # Template HTML
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4; margin: 20mm 15mm;
                @bottom-right {{ content: "Página " counter(page); font-family: Arial; font-size: 8pt; color: #888888; }}
                @bottom-left {{ content: "Vetween - Reporte Clínico Oficial"; font-family: Arial; font-size: 8pt; color: #888888; }}
            }}
            body {{ font-family: 'Arial', sans-serif; color: #2c3e50; line-height: 1.4; font-size: 10pt; }}
            .header {{ border-bottom: 3px solid #3498db; padding-bottom: 10px; margin-bottom: 20px; }}
            .title {{ font-size: 20pt; margin: 0; font-weight: bold; color: #2c3e50; }}
            .meta-table {{ width: 100%; margin-bottom: 20px; border-collapse: collapse; }}
            .meta-label {{ font-weight: bold; color: #34495e; width: 18%; padding: 6px 0; font-size: 9.5pt; }}
            .meta-value {{ color: #555555; width: 32%; padding: 6px 0; font-size: 9.5pt; }}
            h2 {{ font-size: 11pt; color: #2980b9; border-left: 4px solid #3498db; padding-left: 8px; margin-top: 25px; text-transform: uppercase; }}
            .data-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            .data-table th {{ background-color: #f4f6f7; color: #34495e; padding: 8px; border-bottom: 2px solid #bdc3c7; text-align: left; font-size: 9pt; }}
            .data-table td {{ padding: 8px; border-bottom: 1px solid #ecf0f1; font-size: 9pt; vertical-align: top; }}
            .resumen-box {{ background-color: #f7f9fa; border: 1px solid #e2e8f0; border-radius: 4px; padding: 12px; margin-top: 10px; text-align: justify; }}
            .badge {{ background-color: #e8f4fd; color: #2980b9; padding: 2px 6px; border-radius: 3px; font-size: 8pt; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1 class="title">Vetween</h1>
            <p style="margin: 5px 0 0 0; color: #7f8c8d; font-size: 10pt;">Reporte Clínico y Resumen Automatizado de IA</p>
        </div>

        <table class="meta-table">
            <tr>
                <td class="meta-label">Mascota:</td>
                <td class="meta-value"><strong>{nombre_mascota}</strong></td>
                <td class="meta-label">ID Paciente:</td>
                <td class="meta-value">{id_paciente}</td>
            </tr>
            <tr>
                <td class="meta-label">Especie:</td>
                <td class="meta-value">{especie_mascota}</td>
                <td class="meta-label">Raza:</td>
                <td class="meta-value">{raza_mascota}</td>
            </tr>
            <tr>
                <td class="meta-label">Edad / Sexo:</td>
                <td class="meta-value">{edad_mascota} años / {sexo_mascota}</td>
                <td class="meta-label">Peso Corporal:</td>
                <td class="meta-value">{peso_mascota} Kg</td>
            </tr>
            <tr>
                <td class="meta-label">Estado General:</td>
                <td class="meta-value"><span class="badge">{estado_general}</span></td>
                <td class="meta-label">Tipo Consulta:</td>
                <td class="meta-value">{tipo_consulta}</td>
            </tr>
        </table>

        <h2>1. Descripción Clínica General (IA)</h2>
        <div class="resumen-box">
            <p style="margin: 0;">{resumen_texto}</p>
        </div>

        <h2>2. Síntesis de Visitas Procesadas</h2>
        <table class="data-table">
            <thead>
                <tr>
                    <th style="width: 15%;">Fecha</th>
                    <th style="width: 25%;">Motivo</th>
                    <th style="width: 30%;">Diagnóstico</th>
                    <th style="width: 30%;">Tratamiento</th>
                </tr>
            </thead>
            <tbody>
                {visitas_html if visitas_html else '<tr><td colspan="4">No se encontraron visitas sintetizadas en este periodo.</td></tr>'}
            </tbody>
        </table>

        <h2>3. Control de Inmunización (Vacunas del Informe)</h2>
        <table class="data-table">
            <thead>
                <tr>
                    <th style="width: 20%;">Fecha Aplicación</th>
                    <th style="width: 60%;">Vacuna / Componente</th>
                    <th style="width: 20%;">Estado</th>
                </tr>
            </thead>
            <tbody>
                {vacunas_html if vacunas_html else '<tr><td colspan="3">No hay registros de vacunas procesados en el resumen.</td></tr>'}
            </tbody>
        </table>

        <h2>4. Próximos Pasos e Indicaciones Médicas</h2>
        <ul style="margin-top: 10px; padding-left: 20px; line-height: 1.6;">
            {proximos_html if proximos_html else '<li>Seguir indicaciones generales provistas por el profesional a cargo.</li>'}
        </ul>
    </body>
    </html>
    """

    tmp_html = f"tmp_{id_paciente}.html"
    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    weasyprint.HTML(tmp_html).write_pdf(file_path)
    
    if os.path.exists(tmp_html):
        os.remove(tmp_html)