from flask import Flask, request, jsonify
from flask_cors import CORS
from db import get_db, query, execute
import os
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)   # <--- HABILITA CORS


# Crear DB al iniciar
with app.app_context():
    if not os.path.exists("instance"):
        os.makedirs("instance")
    if not os.path.exists("instance/natura.db"):
        db = sqlite3.connect("instance/natura.db")
        with open("sql/create_tables.sql", "r") as f:
            db.executescript(f.read())
        db.close()

@app.get("/buscar-producto")
def buscar_producto():
    q = request.args.get("q", "")
    productos = query("""
        SELECT * FROM productos
        WHERE nombre LIKE ? OR codigo LIKE ? ORDER BY codigo
    """, (f"%{q}%", f"%{q}%"))
    return jsonify([dict(p) for p in productos])

@app.get("/buscarProductoExact")
def buscar_producto_exacto():
    q = request.args.get("q", "")
    productos = query("""
        SELECT * FROM productos
        WHERE codigo = ? ORDER BY codigo LIMIT 1
    """, (q,))
    return jsonify([dict(p) for p in productos])

@app.post("/crear-pedido")
def crear_pedido():
    data = request.json
    cliente_id = data["cliente_id"]
    items = data["items"]
    print(items)


    # Crear pedido
    fecha = datetime.now().isoformat()
    execute("INSERT INTO pedidos (cliente_id, fecha) VALUES (?, ?)",
            (cliente_id, fecha))

    pedido_id = query("SELECT last_insert_rowid() AS id", one=True)["id"]

    # Insertar items
    for item in items:
        execute("""
            INSERT INTO pedido_items (pedido_id, producto_cod, cantidad,precio, tipo)
            VALUES (?, ?, ?, ?,?)
        """, (
            pedido_id,
            item["codigo"],
            item["cantidad"],
            item["precio"],
            item["tipo"]
        ))

    return jsonify({"message": "Pedido creado", "pedido_id": pedido_id})

@app.get("/pedidos")
def listar_pedidos():
    rows = query("""
        SELECT 
            pe.id,
            pe.fecha,
            c.nombre AS cliente
        FROM pedidos pe
        LEFT JOIN clientes c ON c.id = pe.cliente_id
        ORDER BY pe.id DESC
    """)

    return jsonify([
        {
            "id": r["id"],
            "cliente": r["cliente"],
            "fecha": r["fecha"]
        }
        for r in rows
    ])

@app.get("/pedidos/<int:pedido_id>")
def ver_pedido(pedido_id):
    pedido = query("SELECT * FROM pedidos WHERE id = ?", (pedido_id,), one=True)

    if pedido is None:
        return jsonify({"error": "Pedido no encontrado"}), 404

    items = query("""
        SELECT pi.*, p.nombre AS producto_nombre
        FROM pedido_items pi
        JOIN productos p ON p.codigo = pi.producto_cod
        WHERE pi.pedido_id = ?
    """, (pedido_id,))

    return jsonify({
        "id": pedido["id"],
        "cliente_id": pedido["cliente_id"],
        "fecha": pedido["fecha"],
        "items": [
            {
                "producto_cod": item["producto_cod"],
                "nombre": item["producto_nombre"],
                "cantidad": item["cantidad"],
                "precio": item["precio"],
                "tipo": item["tipo"]
            }
            for item in items
        ]
    })

@app.get("/pedidos/cliente/<int:cliente_id>")
def pedidos_por_cliente(cliente_id):
    pedidos = query("""
        SELECT 
            pe.id,
            pe.fecha,
            c.nombre AS cliente
        FROM pedidos pe
        JOIN clientes c ON c.id = pe.cliente_id
        WHERE pe.cliente_id = ?
        ORDER BY pe.id DESC
    """, (cliente_id,))

    if not pedidos:
        return jsonify({"error": "El cliente no tiene pedidos"}), 404

    respuesta = []

    for p in pedidos:
        items = query("""
            SELECT 
                pi.producto_cod,
                pi.cantidad,
                pi.tipo,
                pr.nombre
            FROM pedido_items pi
            JOIN productos pr ON pr.codigo = pi.producto_cod
            WHERE pi.pedido_id = ?
        """, (p["id"],))

        respuesta.append({
            "id": p["id"],
            "cliente": p["cliente"],
            "fecha": p["fecha"],
            "total_items": sum(i["cantidad"] for i in items),
            "items": [
                {
                    "producto_cod": i["producto_cod"],
                    "nombre": i["nombre"],
                    "cantidad": i["cantidad"],
                    "tipo": i["tipo"]
                }
                for i in items
            ]
        })

    return jsonify(respuesta)

@app.get("/pedidos/detalle")
def pedidos_detalle():
    pedidos = query("""
        SELECT 
            pe.id,
            pe.fecha,
            c.nombre AS cliente
        FROM pedidos pe
        LEFT JOIN clientes c ON c.id = pe.cliente_id
        ORDER BY pe.id DESC
    """)

    respuesta = []

    for p in pedidos:
        items = query("""
            SELECT 
                pi.producto_cod,
                pi.cantidad,
                pi.tipo,
                pr.nombre
            FROM pedido_items pi
            JOIN productos pr ON pr.codigo = pi.producto_cod
            WHERE pi.pedido_id = ?
        """, (p["id"],))

        respuesta.append({
            "id": p["id"],
            "cliente": p["cliente"],
            "fecha": p["fecha"],
            "total_items": sum(i["cantidad"] for i in items),
            "items": [
                {
                    "producto_cod": i["producto_cod"],
                    "nombre": i["nombre"],
                    "cantidad": i["cantidad"],
                    "tipo": i["tipo"]
                }
                for i in items
            ]
        })

    return jsonify(respuesta)

@app.get("/pedidos/resumen")
def pedidos_resumen():
    rows = query("""
        SELECT 
            pe.id,
            pe.fecha,
            c.nombre AS cliente,
            COALESCE(SUM(pi.cantidad * pi.precio), 0) AS precio_total
        FROM pedidos pe
        LEFT JOIN clientes c ON c.id = pe.cliente_id
        LEFT JOIN pedido_items pi ON pi.pedido_id = pe.id
        GROUP BY pe.id, pe.fecha, c.nombre
        ORDER BY pe.id DESC
    """)

    return jsonify([dict(r) for r in rows])

@app.delete("/pedidos/<int:pedido_id>")
def eliminar_pedido(pedido_id):
    # Verificar que exista
    pedido = query("SELECT * FROM pedidos WHERE id = ?", (pedido_id,), one=True)
    if pedido is None:
        return jsonify({"error": "Pedido no encontrado"}), 404

    # Borrar items primero
    execute("DELETE FROM pedido_items WHERE pedido_id = ?", (pedido_id,))

    # Borrar pedido
    execute("DELETE FROM pedidos WHERE id = ?", (pedido_id,))

    return jsonify({"message": "Pedido eliminado"})

@app.put("/pedidos/<int:pedido_id>")
def editar_pedido(pedido_id):
    data = request.json
    cliente_id = data["cliente_id"]
    items = data["items"]

    # Verificar que exista
    pedido = query("SELECT * FROM pedidos WHERE id = ?", (pedido_id,), one=True)
    if pedido is None:
        return jsonify({"error": "Pedido no encontrado"}), 404

    # Actualizar pedido
    execute("""
        UPDATE pedidos
        SET cliente_id = ?
        WHERE id = ?
    """, (cliente_id, pedido_id))

    # Borrar items actuales
    execute("DELETE FROM pedido_items WHERE pedido_id = ?", (pedido_id,))

    # Insertar los nuevos
    for item in items:
        execute("""
            INSERT INTO pedido_items (pedido_id, producto_cod, cantidad, tipo, precio)
            VALUES (?, ?, ?, ?, ?)
        """, (
            pedido_id,
            item["producto_cod"],
            item["cantidad"],
            item["tipo"],
            item["precio"]
        ))

    return jsonify({"message": "Pedido actualizado"})

@app.get("/clientes")
def ver_clientes():
    rows = query("SELECT * FROM clientes")
    return jsonify([dict(r) for r in rows])

@app.post("/crear-cliente")
def crear_cliente():
    data = request.json
    nombre_cliente = data["nombre"]
    execute("INSERT INTO clientes (nombre) VALUES (?)",(nombre_cliente,))

    cliente_id = query("SELECT last_insert_rowid() AS id", one=True)["id"]

    return jsonify({"message": "Cliente agragado", "cliente_id": cliente_id})

@app.get("/clientes/<int:cliente_id>")
def ver_cliente(cliente_id):
    cliente = query("SELECT * FROM clientes WHERE id = ?", (cliente_id,), one=True)

    if cliente is None:
        return jsonify({"error": "Cliente no encontrado"}), 404
    return jsonify({
        "id": cliente["id"],
        "nombre": cliente["nombre"]
    })

@app.put("/clientes/<int:cliente_id>")
def editar_cliente(cliente_id):
    data = request.json
    cliente_id = data["cliente_id"]
    nombre = data["nombre"]

    # Verificar que exista
    pedido = query("SELECT * FROM clientes WHERE id = ?", (cliente_id,), one=True)
    if pedido is None:
        return jsonify({"error": "Cliente no encontrado"}), 404

    # Actualizar pedido
    execute("""
        UPDATE clientes
        SET nombre = ?
        WHERE id = ?
    """, (nombre, cliente_id))

    return jsonify({"message": "Cliente actualizado"})

@app.delete("/clientes/<int:cliente_id>")
def eliminar_cliente(cliente_id):
    # Verificar que exista
    cliente = query("SELECT * FROM clientes WHERE id = ?", (cliente_id,), one=True)
    if cliente is None:
        return jsonify({"error": "Cliente no encontrado"}), 404

    # Borrar pedido
    execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))

    return jsonify({"message": "Cliente eliminado"})

@app.get("/debug/items")
def debug_items():
    rows = query("SELECT * FROM pedido_items")
    return jsonify([dict(r) for r in rows])
