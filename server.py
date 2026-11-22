"""Local HTTP API and operator site for the ceramic tile production system."""
import argparse
import csv
import hashlib
import hmac
import io
import json
import math
import secrets
import sqlite3
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "ceramika.sqlite3"
HTTP_ERRORS = {
    "recipe_create_draft": "Сначала создайте черновик рецептуры.",
    "recipe_total": "Сумма долей компонентов должна составлять 100%.",
    "recipe_locked": "Утверждённую или архивную версию нельзя редактировать.",
    "card_create_draft": "Сначала создайте черновик технологической карты.",
    "card_required_step": "У технологической карты должен быть обязательный шаг.",
    "card_locked": "Утверждённую или архивную карту нельзя редактировать.",
    "batch_norms": "Партия должна использовать версии нормативов для продукта заказа.",
    "raw_blocked": "Эта партия сырья заблокирована лабораторией.",
    "steps_pending": "Сначала завершите все обязательные операции.",
}


class BusinessError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def require(condition, message, status=400):
    if not condition:
        raise BusinessError(message, status)


def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def rows(db, sql, args=()):
    return [dict(row) for row in db.execute(sql, args)]


def one(db, sql, args=()):
    row = db.execute(sql, args).fetchone()
    return dict(row) if row else None


def entity(db, table, key):
    result = one(db, f"SELECT * FROM {table} WHERE id=?", (key,))
    require(result, "Запись не найдена.", 404)
    return result


def insert(db, table, data):
    fields = ",".join(data)
    marks = ",".join("?" for _ in data)
    return db.execute(f"INSERT INTO {table}({fields}) VALUES({marks})", tuple(data.values())).lastrowid


def update(db, table, key, data):
    if data:
        fields = ",".join(f"{field}=?" for field in data)
        db.execute(f"UPDATE {table} SET {fields} WHERE id=?", (*data.values(), key))


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310000)
    return salt.hex() + "$" + digest.hex()


def text(data, field):
    value = str(data.get(field) or "").strip()
    require(value, f"Заполните поле «{LABELS.get(field, field)}».")
    return value


LABELS = {
    "name": "Наименование", "code": "Код", "description": "Описание", "comment": "Комментарий",
    "resolution": "Решение", "value": "Значение", "line": "Линия", "notes": "Комментарий",
    "type": "Тип", "format": "Формат", "collection": "Коллекция", "surface": "Поверхность",
    "due": "Срок", "quantity": "Количество", "supplier": "Поставщик",
    "password": "Пароль", "login": "Логин", "current": "Текущий пароль",
}


def number(value):
    require(not isinstance(value, bool) and value not in ("", None), "Введите число.")
    result = float(str(value).replace(",", "."))
    require(math.isfinite(result), "Введите конечное число.")
    return result


def integer(value):
    result = number(value)
    require(result.is_integer() and abs(result) < 2**53, "Введите целое число.")
    return int(result)


def audit(db, user, action, table, key, detail="", batch_id=None, alert=False):
    event = insert(db, "events", dict(user_id=user, action=action, entity=table, entity_id=key,
                                     detail=detail, batch_id=batch_id))
    if alert:
        db.execute("""INSERT INTO notifications(user_id,event_id)
            SELECT u.id,? FROM users u JOIN roles r ON r.id=u.role_id
            WHERE r.code IN ('technologist','operator','lab','manager')""", (event,))
    return event


USER_QUERY = """SELECT u.id,u.login,u.name,u.shift,r.code role,r.name role_name,d.name department,
 u.password_hash FROM users u JOIN roles r ON r.id=u.role_id JOIN departments d ON d.id=u.department_id"""
BATCH_QUERY = """SELECT b.*,o.code order_code,p.id product_id,p.name product,p.code product_code,
 m.version mass_version,g.version glaze_version,t.version card_version,
 COALESCE(cs.name,'') current_step,COALESCE(e.status,'') step_status,
 (SELECT COUNT(*) FROM incidents i WHERE i.batch_id=b.id AND i.state='open' AND i.severity='warning')
 + (SELECT COUNT(*) FROM deviations d JOIN executions ex ON ex.id=d.execution_id WHERE ex.batch_id=b.id) warning,
 (SELECT COUNT(*) FROM incidents i WHERE i.batch_id=b.id AND i.state='open' AND i.severity='critical') critical,
 (SELECT COUNT(*) FROM executions ex WHERE ex.batch_id=b.id AND ex.status='done') done,
 (SELECT COUNT(*) FROM executions ex WHERE ex.batch_id=b.id) total
 FROM batches b JOIN orders o ON o.id=b.order_id JOIN products p ON p.id=o.product_id
 JOIN recipes m ON m.id=b.mass_recipe_id JOIN recipes g ON g.id=b.glaze_recipe_id
 JOIN tech_cards t ON t.id=b.card_id LEFT JOIN executions e ON e.batch_id=b.id AND e.status IN ('ready','running')
 LEFT JOIN card_steps cs ON cs.id=e.step_id"""


def list_batches(db, active=False):
    where = " WHERE b.status IN ('planned','in_progress','quality','blocked')" if active else ""
    return rows(db, BATCH_QUERY + where + " ORDER BY b.id DESC")


def batch_detail(db, key):
    result = one(db, BATCH_QUERY + " WHERE b.id=?", (key,))
    require(result, "Партия не найдена.", 404)
    result["steps"] = rows(db, """SELECT e.*,s.position,s.kind,s.name,s.instructions,s.required,
        s.equipment_id,q.name equipment,q.status equipment_status
        FROM executions e JOIN card_steps s ON s.id=e.step_id LEFT JOIN equipment q ON q.id=s.equipment_id
        WHERE e.batch_id=? ORDER BY s.position""", (key,))
    for step in result["steps"]:
        step["parameters"] = rows(db, """SELECT p.*,v.value FROM step_parameters p LEFT JOIN step_values v
            ON v.parameter_id=p.id AND v.execution_id=? WHERE p.step_id=? ORDER BY p.id""",
                                  (step["id"], step["step_id"]))
    result["raw"] = rows(db, """SELECT l.id,l.code,m.name material,b.quantity,l.unit,l.status FROM batch_raw b
        JOIN raw_lots l ON l.id=b.raw_lot_id JOIN materials m ON m.id=l.material_id WHERE b.batch_id=?""", (key,))
    result["programs"] = rows(db, """SELECT p.*,e.name equipment FROM batch_programs b
        JOIN equipment_programs p ON p.id=b.program_id JOIN equipment e ON e.id=p.equipment_id WHERE b.batch_id=?""", (key,))
    result["incidents"] = rows(db, "SELECT * FROM incidents WHERE batch_id=? ORDER BY id DESC", (key,))
    result["deviations"] = rows(db, """SELECT d.*,s.name step,p.name parameter,p.target,p.unit
        FROM deviations d JOIN executions e ON e.id=d.execution_id JOIN card_steps s ON s.id=e.step_id
        JOIN step_parameters p ON p.id=d.parameter_id WHERE e.batch_id=? ORDER BY d.id DESC""", (key,))
    result["events"] = list_events(db, key)
    return result


def list_events(db, batch=None, table=None, key=None):
    sql = """SELECT e.*,COALESCE(u.name,'Система') author FROM events e LEFT JOIN users u ON e.user_id=u.id"""
    if table:
        return rows(db, sql + " WHERE e.entity=? AND e.entity_id=? ORDER BY e.id DESC", (table, key))
    if batch:
        return rows(db, sql + " WHERE e.batch_id=? ORDER BY e.id DESC", (batch,))
    return rows(db, sql + " ORDER BY e.id DESC LIMIT 100")


def recipe_detail(db, key):
    rec = entity(db, "recipes", key)
    rec["components"] = rows(db, """SELECT i.*,m.name material,i.basis_points/100.0 share
        FROM recipe_items i JOIN materials m ON m.id=i.material_id WHERE recipe_id=? ORDER BY position""", (key,))
    rec["history"] = list_events(db, table="recipes", key=key)
    return rec


def recipe_write(db, key, data, actor):
    if key:
        recipe = entity(db, "recipes", key)
        require(recipe["status"] == "draft", "Состав можно редактировать в черновике.")
        update(db, "recipes", key, {"notes": str(data.get("notes", ""))})
    else:
        product = integer(data["product_id"])
        kind = data["kind"]
        version = db.execute("SELECT COALESCE(MAX(version),0)+1 FROM recipes WHERE product_id=? AND kind=?",
                             (product, kind)).fetchone()[0]
        key = insert(db, "recipes", dict(product_id=product, kind=kind, version=version, author_id=actor,
                                         notes=str(data.get("notes", ""))))
    db.execute("DELETE FROM recipe_items WHERE recipe_id=?", (key,))
    for position, item in enumerate(data.get("components", []), 1):
        share = round(number(item["share"]) * 100, 8)
        require(share.is_integer(), "Доли задаются с точностью до 0,01%.")
        insert(db, "recipe_items", dict(recipe_id=key, material_id=integer(item["material_id"]),
                                        basis_points=int(share), position=position, tolerance=number(item.get("tolerance", 0))))
    audit(db, actor, "Сохранена рецептура", "recipes", key)
    return recipe_detail(db, key)


def publish(db, table, key, action, actor):
    target = {"approve": "active", "review": "review", "archive": "archived", "rework": "draft"}[action]
    record = entity(db, table, key)
    transitions = {
        "recipes": {"draft": {"review", "active", "archived"}, "review": {"active", "draft", "archived"},
                    "active": {"archived"}},
        "tech_cards": {"draft": {"active", "archived"}, "active": {"archived"}},
    }
    require(target in transitions[table].get(record["status"], ()), "Этот переход статуса недоступен.")
    if target == "active":
        if table == "recipes":
            others = rows(db, "SELECT id FROM recipes WHERE product_id=? AND kind=? AND status='active'",
                          (record["product_id"], record["kind"]))
        else:
            require(one(db, "SELECT id FROM card_steps WHERE card_id=? AND required=1", (key,)),
                    "Добавьте хотя бы один обязательный шаг.")
            others = rows(db, "SELECT id FROM tech_cards WHERE product_id=? AND status='active'", (record["product_id"],))
        for other in others:
            update(db, table, other["id"], {"status": "archived"})
            audit(db, actor, "Архивирована предыдущая версия", table, other["id"])
    update(db, table, key, {"status": target})
    audit(db, actor, {"active": "Версия утверждена", "review": "Отправлено на согласование",
                      "archived": "Версия архивирована", "draft": "Возвращено на доработку"}[target], table, key)
    return entity(db, table, key)


def card_detail(db, key):
    card = entity(db, "tech_cards", key)
    card["steps"] = rows(db, """SELECT s.*,e.name equipment FROM card_steps s LEFT JOIN equipment e ON e.id=s.equipment_id
        WHERE s.card_id=? ORDER BY s.position""", (key,))
    for step in card["steps"]:
        step["parameters"] = rows(db, "SELECT * FROM step_parameters WHERE step_id=? ORDER BY id", (step["id"],))
    card["history"] = list_events(db, table="tech_cards", key=key)
    return card


def card_write(db, key, data, actor):
    name = text(data, "name")
    if key:
        require(entity(db, "tech_cards", key)["status"] == "draft", "Редактировать можно только черновик карты.")
        update(db, "tech_cards", key, {"name": name})
        db.execute("DELETE FROM step_parameters WHERE step_id IN (SELECT id FROM card_steps WHERE card_id=?)", (key,))
        db.execute("DELETE FROM card_steps WHERE card_id=?", (key,))
    else:
        product = integer(data["product_id"])
        version = db.execute("SELECT COALESCE(MAX(version),0)+1 FROM tech_cards WHERE product_id=?", (product,)).fetchone()[0]
        key = insert(db, "tech_cards", dict(product_id=product, version=version, name=name))
    for pos, step in enumerate(data.get("steps", []), 1):
        step_id = insert(db, "card_steps", dict(card_id=key, position=pos, kind=text(step, "kind"), name=text(step, "name"),
                    instructions=step.get("instructions", ""), required=integer(step.get("required", 1)),
                    equipment_id=integer(step["equipment_id"]) if step.get("equipment_id") else None))
        for param in step.get("parameters", []):
            insert(db, "step_parameters", dict(step_id=step_id, name=text(param, "name"), unit=text(param, "unit"),
                target=number(param["target"]), minimum=number(param["minimum"]), maximum=number(param["maximum"]),
                required=integer(param.get("required", 1))))
    audit(db, actor, "Сохранена технологическая карта", "tech_cards", key)
    return card_detail(db, key)


def create_batch(db, data, actor):
    order = entity(db, "orders", integer(data["order_id"]))
    require(order["status"] in ("planned", "in_progress"), "Заказ закрыт.")
    recipes = {row["kind"]: row["id"] for row in rows(db, "SELECT id,kind FROM recipes WHERE product_id=? AND status='active'",
                                                       (order["product_id"],))}
    card = one(db, "SELECT id FROM tech_cards WHERE product_id=? AND status='active'", (order["product_id"],))
    require(card and set(recipes) == {"mass", "glaze"}, "Утвердите обе рецептуры и технологическую карту.")
    line = text(data, "line")
    require(not one(db, """SELECT e.id FROM card_steps s JOIN equipment e ON e.id=s.equipment_id
        WHERE s.card_id=? AND e.line<>? LIMIT 1""", (card["id"], line)),
        "Оборудование технологической карты относится к другой линии.")
    key = insert(db, "batches", dict(code=text(data, "code"), order_id=order["id"], mass_recipe_id=recipes["mass"],
                 glaze_recipe_id=recipes["glaze"], card_id=card["id"], line=line,
                 quantity=integer(data["quantity"])))
    for raw in data.get("raw", []):
        add_raw(db, key, raw)
    for program_id in data.get("programs", []):
        add_program(db, key, program_id)
    db.execute("INSERT INTO executions(batch_id,step_id) SELECT ?,id FROM card_steps WHERE card_id=?", (key, card["id"]))
    audit(db, actor, "Сформирована партия", "batches", key, batch_id=key)
    return batch_detail(db, key)


def add_raw(db, key, data):
    raw = entity(db, "raw_lots", integer(data["raw_lot_id"]))
    require(raw["status"] == "released", "Сырьё должно иметь допуск лаборатории.")
    insert(db, "batch_raw", dict(batch_id=key, raw_lot_id=raw["id"], quantity=number(data["quantity"])))


def add_program(db, key, program_id):
    program = entity(db, "equipment_programs", integer(program_id))
    batch = entity(db, "batches", key)
    equipment = entity(db, "equipment", program["equipment_id"])
    require(equipment["line"] == batch["line"], "Программа должна относиться к оборудованию линии партии.")
    db.execute("""DELETE FROM batch_programs WHERE batch_id=? AND program_id IN
        (SELECT id FROM equipment_programs WHERE equipment_id=?)""", (key, equipment["id"]))
    insert(db, "batch_programs", dict(batch_id=key, program_id=program["id"]))


def launch_batch(db, key, actor):
    batch = entity(db, "batches", key)
    require(batch["status"] == "planned", "Партия уже запускалась.")
    require(not one(db, """SELECT l.id FROM batch_raw r JOIN raw_lots l ON l.id=r.raw_lot_id
        WHERE r.batch_id=? AND l.status<>'released'""", (key,)), "В составе есть сырьё без допуска.")
    missing = rows(db, """SELECT DISTINCT m.name FROM recipe_items i JOIN materials m ON m.id=i.material_id
        WHERE i.recipe_id IN (?,?) AND NOT EXISTS(SELECT 1 FROM batch_raw r JOIN raw_lots l ON l.id=r.raw_lot_id
        WHERE r.batch_id=? AND l.material_id=i.material_id AND l.status='released') ORDER BY m.name""",
        (batch["mass_recipe_id"], batch["glaze_recipe_id"], key))
    require(not missing, "Добавьте допущенное сырьё: " + ", ".join(m["name"] for m in missing))
    first = one(db, """SELECT e.id FROM executions e JOIN card_steps s ON s.id=e.step_id
        WHERE e.batch_id=? ORDER BY s.position LIMIT 1""", (key,))
    require(first, "В технологической карте отсутствуют шаги.")
    db.execute("UPDATE batches SET status='in_progress',started=CURRENT_TIMESTAMP WHERE id=?", (key,))
    db.execute("UPDATE orders SET status='in_progress' WHERE id=? AND status='planned'", (batch["order_id"],))
    update(db, "executions", first["id"], {"status": "ready"})
    audit(db, actor, "Партия запущена", "batches", key, batch_id=key)
    return batch_detail(db, key)


def run_step(db, key, execution_id, action, data, actor):
    execution = entity(db, "executions", execution_id)
    batch = entity(db, "batches", key)
    require(execution["batch_id"] == key and batch["status"] == "in_progress", "Шаг недоступен.")
    step = entity(db, "card_steps", execution["step_id"])
    if action in ("finish", "skip"):
        require(not one(db, "SELECT id FROM incidents WHERE batch_id=? AND severity='critical' AND state='open'", (key,)),
                "Технолог должен закрыть критический инцидент перед завершением шага.")
    if action == "start":
        require(execution["status"] == "ready", "Начать можно текущий шаг со статусом «Готов к запуску».")
        db.execute("UPDATE executions SET status='running',started=CURRENT_TIMESTAMP,started_by=? WHERE id=?",
                   (actor, execution_id))
        audit(db, actor, "Шаг начат", "executions", execution_id, step["name"], key)
        return batch_detail(db, key)
    if action == "skip":
        require(not step["required"] and execution["status"] == "ready", "Пропустить можно только необязательный шаг.")
        db.execute("UPDATE executions SET status='skipped',finished=CURRENT_TIMESTAMP,finished_by=? WHERE id=?", (actor, execution_id))
        audit(db, actor, "Шаг пропущен", "executions", execution_id, step["name"], key)
    else:
        require(execution["status"] == "running", "Сначала начните шаг.")
        supplied = data.get("values", {})
        comment = str(data.get("comment", "")).strip()
        params = rows(db, "SELECT * FROM step_parameters WHERE step_id=?", (step["id"],))
        for p in params:
            raw = supplied.get(str(p["id"]))
            if raw in (None, ""):
                require(action != "finish" or not p["required"], f"Заполните параметр «{p['name']}».")
                db.execute("DELETE FROM step_values WHERE execution_id=? AND parameter_id=?", (execution_id, p["id"]))
                continue
            actual = number(raw)
            outside = not p["minimum"] <= actual <= p["maximum"]
            require(not outside or comment, f"Укажите причину отклонения «{p['name']}».")
            db.execute("""INSERT INTO step_values(execution_id,parameter_id,value) VALUES(?,?,?)
                ON CONFLICT(execution_id,parameter_id) DO UPDATE SET value=excluded.value""", (execution_id, p["id"], actual))
            if outside and action == "finish":
                insert(db, "deviations", dict(execution_id=execution_id, parameter_id=p["id"], value=actual, comment=comment))
                audit(db, actor, "Зафиксировано отклонение", "executions", execution_id, p["name"], key, alert=True)
        update(db, "executions", execution_id, {"comment": comment})
        if action == "save":
            audit(db, actor, "Сохранены фактические параметры", "executions", execution_id, step["name"], key)
            return batch_detail(db, key)
        db.execute("UPDATE executions SET status='done',finished=CURRENT_TIMESTAMP,finished_by=? WHERE id=?",
                   (actor, execution_id))
        audit(db, actor, "Шаг завершён", "executions", execution_id, step["name"], key)
    next_step = one(db, """SELECT e.id FROM executions e JOIN card_steps s ON s.id=e.step_id
        WHERE e.batch_id=? AND e.status='pending' ORDER BY s.position LIMIT 1""", (key,))
    if next_step:
        update(db, "executions", next_step["id"], {"status": "ready"})
    else:
        update(db, "batches", key, {"status": "quality"})
        audit(db, actor, "Партия передана на контроль качества", "batches", key, batch_id=key, alert=True)
    return batch_detail(db, key)


def test_detail(db, key):
    lab = one(db, """SELECT t.*,u.name analyst FROM lab_tests t JOIN users u ON u.id=t.analyst_id WHERE t.id=?""", (key,))
    require(lab, "Испытание не найдено.", 404)
    lab["parameters"] = rows(db, """SELECT s.*,r.value FROM lab_results r JOIN lab_specs s ON s.id=r.spec_id
        WHERE r.test_id=? ORDER BY s.id""", (key,))
    lab["decisions"] = rows(db, """SELECT d.*,u.name author FROM lab_decisions d JOIN users u ON u.id=d.author_id
        WHERE d.test_id=? ORDER BY d.id DESC""", (key,))
    return lab


def lab_queue(db, kind):
    if kind == "raw":
        return rows(db, """SELECT r.*,m.name material,m.category,
            (SELECT MAX(created) FROM lab_tests WHERE raw_lot_id=r.id) last_test
            FROM raw_lots r JOIN materials m ON m.id=r.material_id ORDER BY r.id DESC""")
    require(kind in ("mass", "glaze", "finished"), "Неизвестная очередь контроля.")
    return rows(db, """SELECT b.id,b.code,p.name product,b.line,b.status,
        (SELECT d.decision FROM lab_decisions d JOIN lab_tests t ON t.id=d.test_id
          WHERE t.batch_id=b.id AND t.kind=? ORDER BY d.id DESC LIMIT 1) decision,
        (SELECT MAX(created) FROM lab_tests WHERE batch_id=b.id AND kind=?) last_test
        FROM batches b JOIN orders o ON o.id=b.order_id JOIN products p ON p.id=o.product_id
        WHERE b.status IN ('in_progress','quality','completed','blocked')
        AND (?<>'finished' OR b.status IN ('quality','completed','blocked')) ORDER BY b.id DESC""", (kind,kind,kind))


def tests_for(db, kind, key):
    id_field = "raw_lot_id" if kind == "raw" else "batch_id"
    return rows(db, f"""SELECT t.*,u.name analyst FROM lab_tests t JOIN users u ON u.id=t.analyst_id
        WHERE t.{id_field}=? AND t.kind=? ORDER BY t.id DESC""", (key, kind))


def create_test(db, data, actor):
    kind, target = data["kind"], integer(data["target"])
    target_row = entity(db, "raw_lots" if kind == "raw" else "batches", target)
    if kind == "finished":
        require(target_row["status"] in ("quality", "blocked"), "Готовая продукция ещё не передана лаборатории.")
    elif kind != "raw":
        require(target_row["status"] == "in_progress", "Промежуточный контроль доступен в производстве.")
    require(not any(t["status"] == "open" for t in tests_for(db, kind, target)), "Откройте уже назначенное испытание.")
    specs = rows(db, "SELECT id,required FROM lab_specs WHERE kind=?", (kind,))
    chosen = {integer(x) for x in data.get("spec_ids", [spec["id"] for spec in specs])}
    require(chosen and chosen <= {x["id"] for x in specs} and {x["id"] for x in specs if x["required"]} <= chosen,
            "Выберите все обязательные параметры из спецификации.")
    analyst = integer(data.get("analyst_id") or actor)
    person = one(db, USER_QUERY + " WHERE u.id=?", (analyst,))
    require(person and person["role"] == "lab", "Исполнителем должен быть лаборант.")
    info = dict(kind=kind, raw_lot_id=target if kind == "raw" else None, batch_id=target if kind != "raw" else None,
                type=text(data, "type"), analyst_id=analyst, priority=text(data, "priority"), comment=data.get("comment", ""))
    if data.get("appointed"):
        info["appointed"] = data["appointed"]
    key = insert(db, "lab_tests", info)
    for spec in chosen:
        insert(db, "lab_results", dict(test_id=key, spec_id=spec))
    audit(db, actor, "Назначено лабораторное испытание", "lab_tests", key, batch_id=info["batch_id"])
    return test_detail(db, key)


def lab_action(db, key, action, data, actor):
    lab = test_detail(db, key)
    if action == "decide":
        decision = data["decision"]
        comment = str(data.get("comment", "")).strip()
        require(decision in ("released", "blocked"), "Выберите решение.")
        require(decision != "blocked" or comment, "Укажите причину блокировки.")
        target = lab["raw_lot_id"] or lab["batch_id"]
        require(lab["status"] == "done" and all(not p["required"] or p["value"] is not None for p in lab["parameters"]),
                "Завершите испытание и заполните обязательные параметры.")
        other = tests_for(db, lab["kind"], target)
        require(not any(t["status"] == "open" for t in other), "Есть незавершённое испытание этой партии.")
        require(other[0]["id"] == key, "Примите решение по последнему испытанию.")
        require(not lab["decisions"], "Решение уже принято. Для повторной оценки создайте испытание.")
        require(decision != "released" or lab["result"] == "pass", "Обнаружено несоответствие нормативам.")
        if lab["kind"] == "raw":
            update(db, "raw_lots", target, {"status": decision})
        elif lab["kind"] == "finished":
            state = "completed" if decision == "released" else "blocked"
            batch = entity(db, "batches", target)
            require(batch["status"] in ("quality", "blocked"), "Партия недоступна для итогового решения.")
            db.execute("UPDATE batches SET status=?,finished=CURRENT_TIMESTAMP WHERE id=?", (state, target))
            if state == "completed":
                db.execute("""UPDATE orders SET status='completed' WHERE id=? AND
                    (SELECT COALESCE(SUM(quantity),0) FROM batches WHERE order_id=orders.id AND status='completed')>=orders.quantity""",
                           (batch["order_id"],))
        insert(db, "lab_decisions", dict(test_id=key, author_id=actor, decision=decision, comment=comment))
        audit(db, actor, "Лабораторная блокировка" if decision == "blocked" else "Лабораторный допуск",
              "lab_tests", key, comment, lab["batch_id"], alert=True)
    else:
        require(lab["status"] == "open", "Протокол завершён и доступен для просмотра.")
        values = data.get("values", {})
        passed = True
        for spec in lab["parameters"]:
            value = values.get(str(spec["id"]), spec["value"])
            actual = None if value in (None, "") else number(value)
            require(action != "finish" or not spec["required"] or actual is not None, f"Заполните параметр «{spec['name']}».")
            if actual is not None and not spec["minimum"] <= actual <= spec["maximum"]:
                passed = False
            db.execute("UPDATE lab_results SET value=? WHERE spec_id=? AND test_id=?", (actual, spec["id"], key))
        if action == "finish":
            db.execute("UPDATE lab_tests SET status='done',result=?,finished=CURRENT_TIMESTAMP WHERE id=?",
                       ("pass" if passed else "fail", key))
        audit(db, actor, "Испытание завершено" if action == "finish" else "Промежуточные результаты сохранены",
              "lab_tests", key, batch_id=lab["batch_id"])
    return test_detail(db, key)


CATALOGS = {
    "products": ("code", "name", "type", "format", "collection", "surface", "status"),
    "materials": ("name", "category"),
    "equipment": ("name", "kind", "line", "status"),
    "roles": ("code", "name"),
    "orders": ("code", "product_id", "quantity", "due", "status"),
    "equipment_programs": ("equipment_id", "name", "temperature", "duration", "pressure", "notes"),
}
LISTS = {
    "products": """SELECT p.*,(SELECT version FROM recipes WHERE product_id=p.id AND kind='mass' AND status='active') mass,
        (SELECT version FROM recipes WHERE product_id=p.id AND kind='glaze' AND status='active') glaze,
        (SELECT version FROM tech_cards WHERE product_id=p.id AND status='active') card FROM products p""",
    "recipes": "SELECT r.*,p.name product,u.name author FROM recipes r JOIN products p ON p.id=r.product_id JOIN users u ON u.id=r.author_id",
    "tech_cards": "SELECT c.*,p.name product FROM tech_cards c JOIN products p ON p.id=c.product_id",
    "orders": "SELECT o.*,p.name product FROM orders o JOIN products p ON p.id=o.product_id",
    "equipment_programs": "SELECT p.*,e.name equipment,e.line,q.id assigned FROM equipment_programs p JOIN equipment e ON e.id=p.equipment_id LEFT JOIN (SELECT MIN(program_id) id FROM batch_programs GROUP BY program_id) q ON q.id=p.id",
    "incidents": "SELECT i.*,b.code batch,u.name author FROM incidents i JOIN batches b ON b.id=i.batch_id JOIN users u ON u.id=i.author_id",
    "users": """SELECT u.id,u.login,u.name,u.role_id,u.department_id,u.shift,r.name role,d.name department
        FROM users u JOIN roles r ON r.id=u.role_id JOIN departments d ON d.id=u.department_id""",
}
REPORTS = {
    "batches": """SELECT b.code,p.name product,b.created,b.status,
         (EXISTS(SELECT 1 FROM incidents i WHERE i.batch_id=b.id) OR EXISTS(SELECT 1 FROM deviations d JOIN executions e ON e.id=d.execution_id WHERE e.batch_id=b.id)) deviation,
         (SELECT d.decision FROM lab_decisions d JOIN lab_tests t ON t.id=d.test_id WHERE t.batch_id=b.id AND t.kind='finished' ORDER BY d.id DESC LIMIT 1) decision
         FROM batches b JOIN orders o ON o.id=b.order_id JOIN products p ON p.id=o.product_id WHERE date(b.created) BETWEEN ? AND ?""",
    "deviations": """SELECT b.code batch,s.name step,p.name parameter,p.target,d.value,
         'warning' severity,d.comment,d.created FROM deviations d
         JOIN executions e ON e.id=d.execution_id JOIN batches b ON b.id=e.batch_id JOIN card_steps s ON s.id=e.step_id
         JOIN step_parameters p ON p.id=d.parameter_id WHERE date(d.created) BETWEEN ? AND ?""",
    "recipes": """SELECT p.name product,r.kind,r.version,COUNT(*) batches,SUM(b.quantity) quantity
         FROM batches b JOIN recipes r ON r.id=b.mass_recipe_id OR r.id=b.glaze_recipe_id
         JOIN products p ON p.id=r.product_id WHERE date(b.created) BETWEEN ? AND ? GROUP BY r.id""",
    "firing": """WITH period(start_date,end_date) AS (VALUES(?,?))
         SELECT b.code batch,t.zone,'Температура' parameter,t.temperature value,
         p.target,ROUND(t.temperature-p.target,1) deviation,t.recorded created FROM telemetry t JOIN batches b ON b.id=t.batch_id
         LEFT JOIN card_steps s ON s.id=(SELECT ss.id FROM card_steps ss WHERE ss.card_id=b.card_id AND ss.kind='Обжиг' ORDER BY ss.position LIMIT 1)
         LEFT JOIN step_parameters p ON p.id=(SELECT pp.id FROM step_parameters pp WHERE pp.step_id=s.id AND pp.unit='°C' ORDER BY pp.id LIMIT 1)
         CROSS JOIN period WHERE date(t.recorded) BETWEEN start_date AND end_date
         UNION ALL
         SELECT b.code,'Цикл',p.name,v.value,p.target,ROUND(v.value-p.target,1),e.finished
         FROM step_values v JOIN executions e ON e.id=v.execution_id
         JOIN batches b ON b.id=e.batch_id JOIN card_steps s ON s.id=e.step_id
         JOIN step_parameters p ON p.id=v.parameter_id CROSS JOIN period
         WHERE s.kind='Обжиг' AND e.status='done' AND date(e.finished) BETWEEN start_date AND end_date
         ORDER BY created DESC""",
    "blocks": """SELECT COALESCE(b.code,l.code) batch,COALESCE(p.name,m.name) product,d.created,d.comment,u.name author
         FROM lab_decisions d JOIN lab_tests t ON t.id=d.test_id JOIN users u ON u.id=d.author_id
         LEFT JOIN batches b ON b.id=t.batch_id LEFT JOIN orders o ON o.id=b.order_id
         LEFT JOIN products p ON p.id=o.product_id LEFT JOIN raw_lots l ON l.id=t.raw_lot_id
         LEFT JOIN materials m ON m.id=l.material_id
         WHERE d.decision='blocked' AND date(d.created) BETWEEN ? AND ?""",
}


def write_catalog(db, group, key, data, actor):
    result = {}
    for field in CATALOGS[group]:
        if field not in data:
            continue
        if field in ("product_id", "equipment_id", "quantity"):
            result[field] = integer(data[field])
        elif field in ("temperature", "duration", "pressure"):
            result[field] = None if data[field] in ("", None) else number(data[field])
        elif field == "notes":
            result[field] = str(data[field])
        else:
            result[field] = text(data, field)
    if "due" in result:
        result["due"] = date.fromisoformat(result["due"]).isoformat()
    if key:
        entity(db, group, key)
        if group == "orders":
            require(not result or not one(db, "SELECT id FROM batches WHERE order_id=?", (key,)),
                    "По заказу уже сформированы партии.")
        if group == "equipment_programs":
            require(not one(db, "SELECT batch_id FROM batch_programs WHERE program_id=?", (key,)),
                    "Создайте новую программу. Эта версия назначена партии.")
        update(db, group, key, result)
    else:
        if group == "orders":
            result["author_id"] = actor
            require(entity(db, "products", result["product_id"])["status"] == "active", "Продукт в архиве.")
        key = insert(db, group, result)
    audit(db, actor, "Запись справочника сохранена", group, key, result.get("status", ""))
    return entity(db, group, key)


def telemetry(db, key, simulated):
    if key:
        batch = entity(db, "batches", key)
        ovens = rows(db, "SELECT * FROM equipment WHERE kind='Печь' AND line=?", (batch["line"],))
    else:
        ovens = rows(db, "SELECT * FROM equipment WHERE kind='Печь'")
    result = []
    for oven in ovens:
        latest = rows(db, """SELECT t.* FROM telemetry t WHERE equipment_id=? AND (? IS NULL OR batch_id=?)
            ORDER BY id DESC LIMIT 48""", (oven["id"], key, key))
        result.append({"equipment": oven, "source": "simulation" if simulated else "database", "samples": latest})
    return result


def record_simulation(db, key):
    ticking = rows(db, """SELECT b.id batch_id,q.id equipment_id,e.id execution,
        COALESCE((SELECT target FROM step_parameters WHERE step_id=s.id AND unit='°C' LIMIT 1),1120) target
        FROM batches b JOIN executions e ON e.batch_id=b.id AND e.status='running'
        JOIN card_steps s ON s.id=e.step_id AND s.kind='Обжиг'
        JOIN equipment q ON q.line=b.line AND q.kind='Печь' WHERE b.id=?""", (key,))
    for item in ticking:
        if one(db, "SELECT id FROM telemetry WHERE batch_id=? AND recorded>=datetime('now','-4 seconds')", (key,)):
            continue
        for zone in range(1, 4):
            value = item["target"] + (zone - 2) * 8 + 4 * math.sin(time.time() / 12 + zone)
            insert(db, "telemetry", dict(equipment_id=item["equipment_id"], batch_id=key,
                                         zone=f"Зона {zone}", temperature=round(value, 1)))


def inspection_detail(db, key, actor):
    run = one(db, """SELECT i.*,r.line,r.name,u.name inspector FROM inspections i
        JOIN inspection_routes r ON r.id=i.route_id JOIN users u ON u.id=i.user_id
        WHERE i.id=? AND i.user_id=?""", (key, actor))
    require(run, "Обход не найден.", 404)
    points = rows(db, """SELECT p.*,e.name equipment,e.kind,c.checked,c.severity,c.note FROM inspection_points p
        JOIN equipment e ON e.id=p.equipment_id LEFT JOIN inspection_checks c
        ON c.point_id=p.id AND c.inspection_id=? WHERE p.route_id=? ORDER BY p.position""", (key, run["route_id"]))
    for point in points:
        point["parameters"] = rows(db, """SELECT p.*,v.value FROM inspection_parameters p LEFT JOIN
            inspection_readings v ON v.parameter_id=p.id AND v.inspection_id=? WHERE p.point_id=? ORDER BY p.id""",
                                    (key, point["id"]))
    return dict(run, points=points)


def dispatch_inspection(db, method, tail, data, actor):
    if method == "GET" and tail == ["routes"]:
        return rows(db, """SELECT r.*,
            (SELECT COUNT(*) FROM inspection_points WHERE route_id=r.id) total,
            (SELECT i.id FROM inspections i WHERE i.route_id=r.id AND i.user_id=? AND i.status='open') open_id,
            (SELECT i.id FROM inspections i WHERE i.route_id=r.id AND i.user_id=? AND i.status='done' ORDER BY i.id DESC LIMIT 1) last_id,
            (SELECT MAX(i.finished) FROM inspections i WHERE i.route_id=r.id AND i.user_id=?) last_finished
            FROM inspection_routes r ORDER BY r.line""", (actor, actor, actor))
    if method == "POST" and tail == ["start"]:
        route_id = integer(data["route_id"])
        entity(db, "inspection_routes", route_id)
        ongoing = one(db, "SELECT id FROM inspections WHERE route_id=? AND user_id=? AND status='open'", (route_id, actor))
        key = ongoing["id"] if ongoing else insert(db, "inspections", dict(route_id=route_id, user_id=actor))
        if not ongoing:
            audit(db, actor, "Обход линии начат", "inspections", key)
        return inspection_detail(db, key, actor)
    if tail and tail[0].isdigit():
        key = integer(tail[0])
        run = inspection_detail(db, key, actor)
        if method == "GET" and len(tail) == 1:
            return run
        if method == "POST":
            require(run["status"] == "open", "Обход завершён.")
            if len(tail) == 3 and tail[1] == "points":
                point_id = integer(tail[2])
                point = next((p for p in run["points"] if p["id"] == point_id), None)
                require(point, "Контрольная точка не найдена.", 404)
                supplied = data.get("values")
                require(isinstance(supplied, dict), "Укажите показания по точке.")
                values = {p["id"]: number(supplied.get(str(p["id"]))) for p in point["parameters"]}
                outside = any(not p["minimum"] <= values[p["id"]] <= p["maximum"] for p in point["parameters"])
                note = str(data.get("note") or "").strip()
                severity = data.get("severity") or ("warning" if note else None)
                require(severity in (None,"warning","critical"), "Выберите корректный уровень замечания.")
                require(not (outside or severity) or note, "Укажите замечание к отклонению.")
                require(len(note) <= 1000, "Сократите замечание до 1000 символов.")
                db.execute("""INSERT INTO inspection_checks(inspection_id,point_id,severity,note) VALUES(?,?,?,?)
                    ON CONFLICT(inspection_id,point_id) DO UPDATE SET severity=excluded.severity,note=excluded.note,checked=CURRENT_TIMESTAMP""",
                           (key, point_id, severity, note))
                db.executemany("""INSERT INTO inspection_readings(inspection_id,point_id,parameter_id,value)
                    VALUES(?,?,?,?) ON CONFLICT(inspection_id,parameter_id) DO UPDATE SET value=excluded.value""",
                               [(key, point_id, p, value) for p,value in values.items()])
                audit(db, actor, "Осмотрена контрольная точка", "inspections", key, point["equipment"])
                return inspection_detail(db, key, actor)
            if tail[1:] == ["finish"]:
                require(run["points"] and all(p["checked"] for p in run["points"]), "Сначала осмотрите все контрольные точки.")
                db.execute("UPDATE inspections SET status='done',finished=CURRENT_TIMESTAMP WHERE id=?", (key,))
                audit(db, actor, "Обход линии завершён", "inspections", key)
                return inspection_detail(db, key, actor)
    raise BusinessError("Метод обхода не найден.", 404)


def route(db, method, parts, query, data, token, demo, mobile_only=False):
    def query_value(key, default=None):
        return query.get(key, [default])[0]

    def allow(*codes):
        require(user["role"] in codes, "У вашей роли нет доступа к этой операции.", 403)

    if parts == ["health"] and method == "GET":
        return {"status": "online", "mode": "demo" if demo else "local"}
    if parts == ["login"] and method == "POST":
        record = one(db, USER_QUERY + " WHERE u.login=?", (text(data, "login"),))
        supplied = text(data, "password")
        require(record and hmac.compare_digest(record["password_hash"],
                hash_password(supplied, bytes.fromhex(record["password_hash"].split("$")[0]))),
                "Проверьте логин и пароль.", 401)
        record.pop("password_hash")
        if mobile_only:
            require(record["role"] in ("operator", "manager"), "Вход доступен оператору и мастеру смены.", 403)
        require(not data.get("role") or data["role"] == record["role"], "Выберите рабочее место своей роли.", 403)
        new_token = secrets.token_urlsafe(32)
        db.execute("DELETE FROM sessions WHERE expires<=?", (int(time.time()),))
        insert(db, "sessions", dict(token=new_token, user_id=record["id"], expires=int(time.time()) + 43200))
        return dict(user=record, token=new_token)
    user = one(db, USER_QUERY + " JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?",
               (token, int(time.time())))
    require(user, "Сеанс завершён. Войдите снова.", 401)
    password_hash = user.pop("password_hash")
    if mobile_only:
        require(user["role"] in ("operator", "manager"), "Вход доступен оператору и мастеру смены.", 403)
    actor = user["id"]
    if not parts:
        raise BusinessError("Метод не найден.", 404)
    group, *tail = parts
    key = int(tail[0]) if tail and tail[0].isdigit() else None
    action = tail[-1] if tail else ""
    if group == "inspections":
        allow("operator", "manager")
        return dispatch_inspection(db, method, tail, data, actor)
    if group == "me" and method == "GET":
        return user
    if group == "logout" and method == "POST":
        db.execute("DELETE FROM sessions WHERE token=?", (token,))
        return {}
    if group == "password" and method == "POST":
        require(hmac.compare_digest(password_hash, hash_password(text(data, "current"), bytes.fromhex(password_hash.split("$")[0]))),
                "Текущий пароль неверен.")
        new = text(data, "password")
        require(len(new) >= 8, "Новый пароль должен содержать минимум 8 символов.")
        update(db, "users", actor, dict(password_hash=hash_password(new)))
        db.execute("DELETE FROM sessions WHERE user_id=? AND token<>?", (actor, token))
        audit(db, actor, "Изменён пароль", "users", actor)
        return {}
    if group == "lookups" and method == "GET":
        data = {x: rows(db, f"SELECT * FROM {x} ORDER BY name") for x in
                ("products", "materials", "equipment", "roles", "departments")}
        data["raw_lots"] = lab_queue(db, "raw")
        data["orders"] = rows(db, LISTS["orders"] + " ORDER BY o.id DESC")
        data["programs"] = rows(db, LISTS["equipment_programs"])
        data["analysts"] = rows(db, "SELECT u.id,u.name FROM users u JOIN roles r ON r.id=u.role_id WHERE r.code='lab'")
        return data
    if group == "notifications":
        if key and method == "POST":
            db.execute("UPDATE notifications SET read_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?", (key, actor))
            return {}
        if method == "GET":
            return rows(db, """SELECT n.id,n.read_at,e.action,e.detail,e.batch_id,e.created FROM notifications n
                JOIN events e ON e.id=n.event_id WHERE n.user_id=? ORDER BY n.id DESC LIMIT 40""", (actor,))
    if group == "events" and method == "GET":
        return list_events(db, key)
    if group == "telemetry" and method in ("GET", "POST"):
        if method == "POST":
            allow("technologist", "admin")
            equipment = entity(db, "equipment", integer(data["equipment_id"]))
            if data.get("batch_id"):
                batch = entity(db, "batches", integer(data["batch_id"]))
                require(batch["line"] == equipment["line"], "Оборудование и партия должны относиться к одной линии.")
            return {"id": insert(db, "telemetry", dict(equipment_id=equipment["id"],
                    batch_id=integer(data["batch_id"]) if data.get("batch_id") else None, zone=text(data, "zone"),
                    temperature=number(data["temperature"])))}
        batch = integer(query_value("batch")) if query_value("batch") else None
        if demo and batch:
            record_simulation(db, batch)
        return telemetry(db, batch, demo)
    if group == "batches":
        if method == "GET":
            return batch_detail(db, key) if key else list_batches(db, query_value("active") == "1")
        if method == "POST" and not tail:
            allow("technologist", "admin")
            return create_batch(db, data, actor)
        if method == "POST" and key:
            if action in ("launch", "raw", "program"):
                allow("technologist", "admin")
                if action == "launch":
                    return launch_batch(db, key, actor)
                require(entity(db, "batches", key)["status"] == "planned", "Состав можно менять до запуска партии.")
                if action == "raw":
                    add_raw(db, key, data)
                else:
                    add_program(db, key, data["program_id"])
                audit(db, actor, "Обновлена комплектация партии", "batches", key, batch_id=key)
                return batch_detail(db, key)
            if len(tail) == 4 and tail[1] == "steps" and action in ("start", "save", "finish", "skip"):
                allow("operator")
                return run_step(db, key, integer(tail[2]), action, data, actor)
            if action == "incident":
                allow("operator", "technologist")
                entity(db, "batches", key)
                execution = data.get("execution_id")
                if execution:
                    execution = entity(db, "executions", integer(execution))
                    require(execution["batch_id"] == key, "Шаг относится к другой партии.")
                new = insert(db, "incidents", dict(batch_id=key, execution_id=execution["id"] if execution else None,
                    author_id=actor, severity=data["severity"], description=text(data, "description")))
                audit(db, actor, "Критический инцидент" if data["severity"] == "critical" else "Предупреждение",
                      "incidents", new, data["description"], key, alert=True)
                return entity(db, "incidents", new)
    if group == "incidents" and method == "POST" and key and action == "resolve":
        allow("technologist", "admin")
        inc = entity(db, group, key)
        require(inc["state"] == "open", "Инцидент уже закрыт.")
        resolution = text(data, "resolution")
        update(db, group, key, dict(state="resolved", resolution=resolution, resolved_by=actor))
        audit(db, actor, "Инцидент закрыт", group, key, resolution, inc["batch_id"], alert=True)
        return entity(db, group, key)
    if group == "lab":
        allow("lab", "technologist", "manager", "admin")
        kind = tail[1] if len(tail) > 1 else ""
        if method == "GET" and tail and tail[0] in ("queue", "specs", "targets", "protocols", "tests"):
            if tail[0] == "queue":
                return lab_queue(db, kind)
            if tail[0] == "specs":
                return rows(db, "SELECT * FROM lab_specs WHERE kind=? ORDER BY id", (kind,))
            if tail[0] == "targets":
                target = integer(tail[2])
                target_info = next((info for info in lab_queue(db, kind) if info["id"] == target), None)
                require(target_info, "Объект контроля не найден.", 404)
                field = "raw_lot_id" if kind == "raw" else "batch_id"
                decisions = rows(db, f"""SELECT d.*,u.name author FROM lab_decisions d JOIN lab_tests t ON t.id=d.test_id
                    JOIN users u ON u.id=d.author_id WHERE t.{field}=? AND t.kind=? ORDER BY d.id DESC""", (target, kind))
                return dict(target=target_info, tests=tests_for(db, kind, target), decisions=decisions)
            if tail[0] == "protocols":
                return rows(db, """SELECT t.*,u.name analyst,COALESCE(r.code,b.code) target
                    FROM lab_tests t JOIN users u ON u.id=t.analyst_id LEFT JOIN raw_lots r ON r.id=t.raw_lot_id
                    LEFT JOIN batches b ON b.id=t.batch_id WHERE t.status='done' ORDER BY t.id DESC""")
            return test_detail(db, integer(kind))
        if method == "POST" and tail and tail[0] == "tests":
            allow("lab")
            if len(tail) == 1:
                return create_test(db, data, actor)
            if action in ("save", "finish", "decide"):
                return lab_action(db, integer(kind), action, data, actor)
    if group == "reports" and method == "GET" and action in REPORTS:
        allow("technologist", "manager", "admin")
        start = date.fromisoformat(query_value("from", "2000-01-01")).isoformat()
        end = date.fromisoformat(query_value("to", date.today().isoformat())).isoformat()
        require(start <= end, "Начало периода должно предшествовать окончанию.")
        return rows(db, REPORTS[action], (start, end))
    if group in ("recipes", "tech_cards"):
        allow("technologist", "manager", "admin")
        if method == "GET" and key:
            return (recipe_detail if group == "recipes" else card_detail)(db, key)
        if method in ("POST", "PATCH"):
            allow("technologist", "admin")
            if key and action in ("approve", "review", "archive", "rework"):
                return publish(db, group, key, action, actor)
            return (recipe_write if group == "recipes" else card_write)(db, key, data, actor)
    if group in CATALOGS or group in LISTS:
        if group == "users":
            allow("admin")
        if method == "GET":
            if key:
                require(len(tail) == 1, "Метод не найден.", 404)
                if group == "users":
                    record = one(db, LISTS[group] + " WHERE u.id=?", (key,))
                    require(record, "Запись не найдена.", 404)
                    return record
                record = entity(db, group, key)
                record["history"] = list_events(db, table=group, key=key)
                if group == "products":
                    record["related"] = dict(recipes=rows(db, LISTS["recipes"] + " WHERE r.product_id=?", (key,)),
                      cards=rows(db, LISTS["tech_cards"] + " WHERE c.product_id=?", (key,)),
                      batches=rows(db, BATCH_QUERY + " WHERE p.id=?", (key,)))
                return record
            sql = LISTS.get(group, f"SELECT * FROM {group}")
            return rows(db, f"SELECT * FROM ({sql}) ORDER BY id DESC")
        if group in CATALOGS and method in ("POST", "PATCH", "DELETE"):
            if group in ("materials", "equipment", "roles"):
                allow("admin")
            else:
                allow("technologist", "admin")
            if method == "DELETE":
                require(key, "Укажите запись.")
                if group == "products":
                    return write_catalog(db, group, key, {"status": "archived"}, actor)
                db.execute(f"DELETE FROM {group} WHERE id=?", (key,))
                audit(db, actor, "Запись удалена", group, key)
                return {}
            return write_catalog(db, group, key, data, actor)
        if group == "users" and method in ("POST", "PATCH", "DELETE"):
            if method == "DELETE":
                require(key and key != actor, "Текущую учётную запись нельзя удалить.")
                db.execute("DELETE FROM users WHERE id=?", (key,))
                audit(db, actor, "Пользователь удалён", "users", key)
                return {}
            fields = dict(login=text(data, "login"), name=text(data, "name"), role_id=integer(data["role_id"]),
                          department_id=integer(data["department_id"]), shift=data.get("shift"))
            if data.get("password"):
                require(len(data["password"]) >= 8, "Пароль должен содержать минимум 8 символов.")
                fields["password_hash"] = hash_password(data["password"])
            if key:
                update(db, group, key, fields)
                db.execute("DELETE FROM sessions WHERE user_id=?", (key,))
            else:
                require("password_hash" in fields, "Введите пароль.")
                key = insert(db, group, fields)
            audit(db, actor, "Пользователь сохранён", "users", key)
            return one(db, LISTS[group] + " WHERE u.id=?", (key,))
    raise BusinessError("Метод не найден.", 404)


class Handler(BaseHTTPRequestHandler):
    def respond(self, body, status=200, mime="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def envelope(self, data=None, error=None, status=200, meta=None):
        packet = dict(success=error is None, data=data, error=error, meta=meta)
        self.respond(json.dumps(packet, ensure_ascii=False).encode(), status)

    def handle_request(self):
        url = urlsplit(self.path)
        mobile_only = self.server.mobile_only
        assets = {
            "/": ("index.html", "text/html"),
            "/style.css": ("style.css", "text/css"),
            "/app.js": ("app.js", "text/javascript"),
            "/mobile": ("mobile.html", "text/html"),
            "/mobile/": ("mobile.html", "text/html"),
            "/mobile.css": ("mobile.css", "text/css"),
            "/mobile.js": ("mobile.js", "text/javascript"),
        }
        if mobile_only:
            assets["/"] = assets["/mobile"]
            del assets["/app.js"]
            allowed_api = url.path in ("/api/health", "/api/login", "/api/logout", "/api/me") or url.path.startswith("/api/inspections/")
            if url.path not in assets and not allowed_api:
                self.envelope(error="Страница не найдена.", status=404)
                return
        if self.command == "GET" and url.path in assets:
            filename, mime = assets[url.path]
            asset = ROOT / "web" / filename
            if asset.is_file():
                self.respond(asset.read_bytes(), mime=mime + "; charset=utf-8")
            else:
                self.envelope(error="Файл не найден.", status=404)
            return
        if not url.path.startswith("/api/"):
            self.envelope(error="Страница не найдена.", status=404)
            return
        db = connect(self.server.db_path)
        try:
            length = int(self.headers.get("Content-Length", 0))
            require(0 <= length <= 1024 * 1024, "Запрос слишком большой.", 413)
            data = json.loads(self.rfile.read(length)) if length else {}
            require(isinstance(data, dict), "Ожидается объект JSON.")
            parts = url.path.removeprefix("/api/").strip("/").split("/")
            query = parse_qs(url.query)
            prefix = "Bearer "
            auth = self.headers.get("Authorization", "")
            if self.command != "GET" or (parts == ["telemetry"] and "batch" in query and self.server.demo):
                db.execute("BEGIN IMMEDIATE")
            result = route(db, self.command, parts, query, data, auth.removeprefix(prefix) if auth.startswith(prefix) else None,
                           self.server.demo, mobile_only)
            meta = None
            if self.command == "GET" and isinstance(result, list) and "limit" in query:
                limit = max(1, min(100, integer(query["limit"][0])))
                page = max(1, integer(query.get("page", [1])[0]))
                meta = dict(page=page, limit=limit, total=len(result))
                result = result[(page - 1) * limit:page * limit]
            db.commit()
            if parts[0] == "reports" and query.get("format") == ["csv"]:
                output = io.StringIO()
                if result:
                    writer = csv.DictWriter(output, fieldnames=result[0], delimiter=";")
                    writer.writeheader()
                    for row in result:
                        writer.writerow({k: ("'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v)
                                         for k, v in row.items()})
                self.respond(output.getvalue().encode("utf-8-sig"), mime="text/csv; charset=utf-8")
            else:
                self.envelope(result, meta=meta)
        except BusinessError as error:
            self.envelope(error=str(error), status=error.status)
        except sqlite3.IntegrityError as error:
            self.envelope(error=HTTP_ERRORS.get(str(error), "Запись конфликтует с существующими данными или нарушает ограничения."), status=409)
        except (ValueError, TypeError, KeyError, OverflowError):
            self.envelope(error="Проверьте формат и обязательные поля запроса.", status=400)
        except sqlite3.Error as error:
            self.log_error("SQLite: %s", error)
            self.envelope(error="Ошибка базы данных. Повторите запрос.", status=500)
        finally:
            db.close()

    do_GET = do_POST = do_PATCH = do_DELETE = handle_request


def seed_inspections(db):
    definitions = {
        "Пресс": ("Проверьте рабочее давление и отсутствие утечек.", [("Давление", "бар", 300, 340)]),
        "Сушилка": ("Проверьте температуру сушилки и остаточную влажность заготовки.",
                    [("Температура", "°C", 165, 185), ("Влажность", "%", 0, 2)]),
        "Печь": ("Проверьте температуру горячей зоны и запишите замечания по датчикам.",
                 [("Температура", "°C", 1100, 1140)]),
        "Глазуровочная линия": ("Проверьте вязкость глазури и равномерность подачи.",
                                [("Вязкость", "с", 23, 33)]),
    }
    for line in rows(db, "SELECT DISTINCT line FROM equipment ORDER BY line"):
        label = line["line"]
        if one(db, "SELECT id FROM inspection_routes WHERE line=?", (label,)):
            continue
        route_id = insert(db, "inspection_routes", dict(line=label, name="Ежедневный осмотр"))
        for position, (kind, (instruction, parameters)) in enumerate(definitions.items(), 1):
            equipment = one(db, "SELECT id FROM equipment WHERE line=? AND kind=? ORDER BY id", (label, kind))
            if not equipment and kind != "Глазуровочная линия":
                continue
            equipment_id = equipment["id"] if equipment else insert(db, "equipment", dict(
                name=f"Глазуровочная {label.lower()}", kind=kind, line=label))
            point_id = insert(db, "inspection_points", dict(route_id=route_id, equipment_id=equipment_id,
                position=position, location=f"{label} · зона {position}", instruction=instruction))
            for name, unit, low, high in parameters:
                insert(db, "inspection_parameters", dict(point_id=point_id, name=name, unit=unit, minimum=low, maximum=high))


def initialize(path, demo=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = connect(path)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
        if demo:
            from seed import seed
            with db:
                db.execute("BEGIN IMMEDIATE")
                seed(db)
                seed_inspections(db)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--no-demo", action="store_true", help="Skip demo fixtures and simulated telemetry")
    parser.add_argument("--mobile-lan", metavar="ADDRESS", help="Serve only mobile pages and inspections at the selected address")
    args = parser.parse_args()
    initialize(args.db, not args.no_demo)
    host = args.mobile_lan or "127.0.0.1"
    server = ThreadingHTTPServer((host, args.port), Handler)
    server.db_path = args.db
    server.demo = not args.no_demo
    server.mobile_only = args.mobile_lan is not None
    print(f"CERAMIKA | http://{host}:{server.server_port}" + ("/mobile" if server.mobile_only else ""), flush=True)
    server.serve_forever()
