import os
import json
import hashlib
import zipfile
from datetime import datetime
import tkinter as tk
from tkinter import messagebox


CARPETA = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(CARPETA, "contactos.dat")
INDICE = os.path.join(CARPETA, "indice.json")
HASH = os.path.join(CARPETA, "contactos.sha256")
EXPORTADO = os.path.join(CARPETA, "contactos.json")
REPORTE = os.path.join(CARPETA, "reporte.pdf")
RESPALDO = os.path.join(CARPETA, "respaldo.zip")

CAMPOS = ["id", "nombre", "telefono", "correo", "ciudad"]
LARGOS = [6, 30, 15, 40, 25]
TAMANO = sum(LARGOS) + 1
indice = {}


def convertir(contacto):
    partes = []
    for campo, largo in zip(CAMPOS, LARGOS):
        texto = str(contacto[campo]).strip()
        dato = texto.encode("utf-8")
        if len(dato) > largo:
            raise ValueError("El campo " + campo + " es demasiado largo.")
        partes.append(dato.ljust(largo, b" "))
    return b"".join(partes) + b"\n"


def separar(bloque):
    if len(bloque) != TAMANO or not bloque.endswith(b"\n"):
        raise ValueError("El archivo tiene un registro incompleto.")
    contacto = {}
    inicio = 0
    for campo, largo in zip(CAMPOS, LARGOS):
        contacto[campo] = bloque[inicio:inicio + largo].decode("utf-8").strip()
        inicio += largo
    contacto["id"] = int(contacto["id"])
    return contacto


def leer(numero):
    with open(DATOS, "rb") as archivo:
        archivo.seek(numero * TAMANO)
        posicion = archivo.tell()
        contacto = separar(archivo.read(TAMANO))
    return contacto, posicion


def todos():
    cantidad = os.path.getsize(DATOS)
    if cantidad % TAMANO != 0:
        raise ValueError("El tamaño del archivo de contactos es incorrecto.")
    lista = []
    for numero in range(cantidad // TAMANO):
        contacto, _ = leer(numero)
        lista.append(contacto)
    return lista


def guardar_indice():
    with open(INDICE, "w", encoding="utf-8") as archivo:
        json.dump(indice, archivo, indent=4)


def calcular_hash():
    with open(DATOS, "rb") as archivo:
        return hashlib.sha256(archivo.read()).hexdigest()


def guardar_hash():
    with open(HASH, "w", encoding="utf-8") as archivo:
        archivo.write(calcular_hash())


def comprobar_hash():
    if not os.path.exists(HASH):
        return False
    with open(HASH, "r", encoding="utf-8") as archivo:
        anterior = archivo.read().strip()
    return anterior == calcular_hash()


def preparar():
    global indice
    avisos = []
    if not os.path.exists(DATOS):
        with open(DATOS, "wb"):
            pass
        avisos.append("Se creó el archivo contactos.dat.")

    if os.path.exists(HASH):
        try:
            if not comprobar_hash():
                avisos.append("El archivo de contactos fue modificado fuera del programa.")
        except (OSError, UnicodeError):
            avisos.append("No se pudo revisar el archivo SHA-256.")
    else:
        guardar_hash()

    try:
        with open(INDICE, "r", encoding="utf-8") as archivo:
            indice = json.load(archivo)
        if not isinstance(indice, dict) or any(
            not isinstance(n, int) or n < 0 for n in indice.values()
        ):
            raise ValueError("Índice incorrecto")
    except (FileNotFoundError, ValueError, UnicodeError, OSError):
        indice = {}
        try:
            for numero, contacto in enumerate(todos()):
                indice[str(contacto["id"])] = numero
            guardar_indice()
            avisos.append("Se creó o reconstruyó el índice.")
        except (OSError, ValueError, UnicodeError):
            avisos.append("No se pudo recuperar el índice.")
    return avisos


def agregar(contacto):
    numero_id = contacto["id"]
    if str(numero_id) in indice:
        raise ValueError("Ese ID ya existe.")
    bloque = convertir(contacto)
    with open(DATOS, "ab") as archivo:
        posicion = archivo.tell()
        if posicion % TAMANO != 0:
            raise ValueError("El archivo está dañado.")
        archivo.write(bloque)
    indice[str(numero_id)] = posicion // TAMANO
    guardar_indice()
    guardar_hash()
    return posicion


def buscar(numero_id):
    if str(numero_id) not in indice:
        raise ValueError("No existe un contacto con ese ID.")
    contacto, posicion = leer(indice[str(numero_id)])
    if contacto["id"] != numero_id:
        raise ValueError("El índice no coincide con el archivo.")
    return contacto, posicion


def modificar(contacto):
    numero_id = contacto["id"]
    buscar(numero_id)
    posicion = indice[str(numero_id)] * TAMANO
    bloque = convertir(contacto)
    with open(DATOS, "r+b") as archivo:
        archivo.seek(posicion)
        posicion = archivo.tell()
        archivo.write(bloque)
    guardar_hash()
    return posicion


def exportar_json():
    with open(EXPORTADO, "w", encoding="utf-8") as archivo:
        json.dump(todos(), archivo, indent=4, ensure_ascii=False)


def exportar_pdf():
    from fpdf import FPDF
    exportar_json()
    with open(EXPORTADO, "r", encoding="utf-8") as archivo:
        contactos = json.load(archivo)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "Reporte de contactos", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 9, "Fecha: " + datetime.now().strftime("%d/%m/%Y"), new_x="LMARGIN", new_y="NEXT")
    for contacto in contactos:
        pdf.ln(3)
        for campo in CAMPOS:
            texto = campo.capitalize() + ": " + str(contacto[campo])
            texto = texto.encode("latin-1", "replace").decode("latin-1")
            pdf.multi_cell(0, 7, texto, new_x="LMARGIN", new_y="NEXT")
    pdf.output(REPORTE)


def respaldo():
    original = os.path.getsize(DATOS) + os.path.getsize(INDICE)
    with zipfile.ZipFile(RESPALDO, "w", zipfile.ZIP_DEFLATED) as comprimido:
        comprimido.write(DATOS, "contactos.dat")
        comprimido.write(INDICE, "indice.json")
    return original, os.path.getsize(RESPALDO)


def informacion():
    datos = os.stat(DATOS)
    fecha = datetime.fromtimestamp(datos.st_mtime).strftime("%d/%m/%Y %H:%M")
    lectura = "Sí" if os.access(DATOS, os.R_OK) else "No"
    escritura = "Sí" if os.access(DATOS, os.W_OK) else "No"
    return ("Tamaño: " + str(datos.st_size) + " bytes\n"
            + "Última modificación: " + fecha + "\n"
            + "Permiso de lectura: " + lectura + "\n"
            + "Permiso de escritura: " + escritura)


def ejecutar(funcion):
    try:
        funcion()
    except (OSError, ValueError, UnicodeError, ImportError) as error:
        messagebox.showerror("Error", str(error))


def datos_formulario():
    contacto = {}
    for campo in CAMPOS:
        texto = entradas[campo].get().strip()
        if not texto:
            raise ValueError("Llena todos los campos.")
        contacto[campo] = texto
    try:
        contacto["id"] = int(contacto["id"])
    except ValueError:
        raise ValueError("El ID debe ser un número entero.")
    if contacto["id"] <= 0:
        raise ValueError("El ID debe ser positivo.")
    return contacto


def accion_agregar():
    posicion = agregar(datos_formulario())
    estado.config(text="Agregado en la posición " + str(posicion) + " (tell).")
    messagebox.showinfo("Contactos", "Contacto agregado.")


def accion_buscar():
    numero_id = int(entradas["id"].get())
    contacto, posicion = buscar(numero_id)
    for campo in CAMPOS:
        entradas[campo].delete(0, tk.END)
        entradas[campo].insert(0, str(contacto[campo]))
    estado.config(text="Encontrado en la posición " + str(posicion) + " (tell).")


def accion_modificar():
    posicion = modificar(datos_formulario())
    estado.config(text="Modificado en la posición " + str(posicion) + " (tell).")
    messagebox.showinfo("Contactos", "Contacto modificado.")


def accion_json():
    exportar_json()
    messagebox.showinfo("Exportar", "Se creó contactos.json.")


def accion_pdf():
    exportar_pdf()
    messagebox.showinfo("Exportar", "Se creó reporte.pdf.")


def accion_hash():
    if comprobar_hash():
        messagebox.showinfo("Integridad", "El archivo no fue modificado.")
    else:
        messagebox.showwarning("Integridad", "El archivo fue modificado fuera del programa.")


def accion_zip():
    original, comprimido = respaldo()
    messagebox.showinfo("Respaldo", "Respaldo creado.\nTamaño original: "
                        + str(original) + " bytes\nTamaño ZIP: " + str(comprimido) + " bytes")


def limpiar():
    for entrada in entradas.values():
        entrada.delete(0, tk.END)
    estado.config(text="")


def iniciar():
    global entradas, estado
    ventana = tk.Tk()
    ventana.title("Agenda de contactos")
    ventana.geometry("410x340")
    ventana.resizable(False, False)

    menu = tk.Menu(ventana)
    contactos_menu = tk.Menu(menu, tearoff=0)
    contactos_menu.add_command(label="Agregar", command=lambda: ejecutar(accion_agregar))
    contactos_menu.add_command(label="Buscar por ID", command=lambda: ejecutar(accion_buscar))
    contactos_menu.add_command(label="Modificar", command=lambda: ejecutar(accion_modificar))
    menu.add_cascade(label="Contactos", menu=contactos_menu)

    exportar_menu = tk.Menu(menu, tearoff=0)
    exportar_menu.add_command(label="Exportar JSON", command=lambda: ejecutar(accion_json))
    exportar_menu.add_command(label="Reporte PDF", command=lambda: ejecutar(accion_pdf))
    menu.add_cascade(label="Exportar", menu=exportar_menu)

    herramientas = tk.Menu(menu, tearoff=0)
    herramientas.add_command(label="Verificar integridad", command=lambda: ejecutar(accion_hash))
    herramientas.add_command(label="Crear respaldo ZIP", command=lambda: ejecutar(accion_zip))
    herramientas.add_command(label="Información del archivo", command=lambda: ejecutar(lambda: messagebox.showinfo("Información", informacion())))
    menu.add_cascade(label="Herramientas", menu=herramientas)
    menu.add_command(label="Ayuda", command=lambda: messagebox.showinfo("Ayuda", "Opción de ayuda simulada."))
    ventana.config(menu=menu)

    tk.Label(ventana, text="Agenda de contactos", font=("Arial", 14)).pack(pady=12)
    formulario = tk.Frame(ventana)
    formulario.pack()
    entradas = {}
    for fila, campo in enumerate(CAMPOS):
        tk.Label(formulario, text=campo.capitalize() + ":", width=10, anchor="e").grid(row=fila, column=0, padx=5, pady=4)
        entrada = tk.Entry(formulario, width=30)
        entrada.grid(row=fila, column=1, padx=5, pady=4)
        entradas[campo] = entrada

    botones = tk.Frame(ventana)
    botones.pack(pady=16)
    tk.Button(botones, text="Agregar", width=10, command=lambda: ejecutar(accion_agregar)).pack(side="left", padx=3)
    tk.Button(botones, text="Buscar", width=10, command=lambda: ejecutar(accion_buscar)).pack(side="left", padx=3)
    tk.Button(botones, text="Modificar", width=10, command=lambda: ejecutar(accion_modificar)).pack(side="left", padx=3)
    tk.Button(botones, text="Limpiar", width=10, command=limpiar).pack(side="left", padx=3)
    estado = tk.Label(ventana, text="", fg="blue")
    estado.pack()

    try:
        avisos = preparar()
        for aviso in avisos:
            if "modificado" in aviso or "No se pudo" in aviso:
                ventana.after(200, lambda texto=aviso: messagebox.showwarning("Aviso", texto))
    except (OSError, ValueError, UnicodeError) as error:
        ventana.after(200, lambda texto=str(error): messagebox.showerror("Error", texto))
    ventana.mainloop()


if __name__ == "__main__":
    iniciar()
