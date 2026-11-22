"""Fictional production data used by the demo startup."""
from datetime import date, timedelta

from server import (
    audit, card_write, create_batch, create_test, hash_password, insert, lab_action,
    launch_batch, publish, recipe_write, rows, run_step,
)


def seed(db):
    if db.execute("SELECT 1 FROM roles LIMIT 1").fetchone():
        return
    for name in ("Технологический отдел", "Производственный цех", "Лаборатория", "ИТ-служба"):
        insert(db, "departments", {"name": name})
    for index, (role, label, login, name, department) in enumerate((
        ("technologist", "Технолог", "tech", "Анна Соколова", 1),
        ("operator", "Оператор линии", "operator", "Илья Орлов", 2),
        ("lab", "Лаборант", "lab", "Мария Белова", 3),
        ("admin", "Администратор", "admin", "Алексей Волков", 4),
        ("manager", "Мастер смены", "master", "Денис Власов", 2),
    ), 1):
        insert(db, "roles", dict(code=role, name=label))
        insert(db, "users", dict(login=login, password_hash=hash_password("Ceramika2026"), name=name,
                                 role_id=index, department_id=department, shift="Смена А" if department == 2 else None))
    products = (
        ("CL-6060", "Сланец графит", "Керамогранит", "600 × 600", "Сланец", "Матовая"),
        ("SA-3060", "Песчаник светлый", "Глазурованная плитка", "300 × 600", "Песчаник", "Сатиновая"),
    )
    for code, name, kind, size, collection, surface in products:
        insert(db, "products", dict(code=code, name=name, type=kind, format=size, collection=collection, surface=surface))
    for name, category in (("Глина ПЛ-1", "Глина"), ("Каолин КА-2", "Каолин"), ("Фритта ФР-12", "Фритта"), ("Пигмент ПГ-4", "Пигмент")):
        insert(db, "materials", dict(name=name, category=category))
    for i, material in enumerate((1, 2, 3, 4, 1, 2), 1):
        insert(db, "raw_lots", dict(code=f"СЫР-{260+i}", supplier_code=f"SUP-{421+i}", material_id=material,
            supplier="УралМинерал" if material < 3 else "КерамСырьё",
            received=(date.today() - timedelta(days=7-i)).isoformat(), quantity=1000 + 150 * i, location=f"Склад А / {i}"))
    for line in (1, 2):
        for name in ("Пресс", "Сушилка", "Печь"):
            id_ = insert(db, "equipment", dict(name=f"{name} {line:02}", kind=name, line=f"Линия {line:02}"))
            insert(db, "equipment_programs", dict(equipment_id=id_, name=f"{name} · профиль {line:02}",
                temperature={"Пресс": None, "Сушилка": 175, "Печь": 1120}[name],
                duration={"Пресс": 4, "Сушилка": 45, "Печь": 38}[name], pressure=320 if name == "Пресс" else None))
    for kind, name, unit, low, high in (
        ("raw", "Влажность", "%", 3, 8), ("raw", "Остаток на сите", "%", 0, 2),
        ("mass", "Влажность массы", "%", 5, 7), ("mass", "Плотность", "г/см³", 1.65, 1.95),
        ("glaze", "Вязкость", "с", 23, 33), ("glaze", "Плотность", "г/см³", 1.45, 1.7),
        ("finished", "Водопоглощение", "%", 0, 0.5), ("finished", "Отклонение размера", "мм", -0.5, 0.5),
        ("finished", "Прочность", "МПа", 32, 65),
    ):
        insert(db, "lab_specs", dict(kind=kind, name=name, unit=unit, minimum=low, maximum=high))

    def qualify(kind, key, decision="released"):
        candidate = create_test(db, dict(kind=kind, target=key, type="Основное", priority="Обычный"), 3)
        values = {str(p["id"]): (p["minimum"] + p["maximum"]) / 2 for p in candidate["parameters"]}
        if decision == "blocked":
            p = candidate["parameters"][0]
            values[str(p["id"])] = p["maximum"] + 1
        lab_action(db, candidate["id"], "finish", {"values": values}, 3)
        lab_action(db, candidate["id"], "decide", {"decision": decision, "comment": "Превышен допуск влажности" if decision == "blocked" else ""}, 3)

    for key in (1, 2, 3, 4):
        qualify("raw", key)
    qualify("raw", 5, "blocked")

    def param(name, unit, target, minimum, maximum):
        return dict(name=name, unit=unit, target=target, minimum=minimum, maximum=maximum)

    for p in (1, 2):
        for kind, materials, share in (("mass", (1, 2), 65 if p == 1 else 60), ("glaze", (3, 4), 90)):
            rec = recipe_write(db, None, dict(product_id=p, kind=kind, notes="Демонстрационная рецептура",
                components=[dict(material_id=m, share=percent, tolerance=1) for m, percent in zip(materials,(share,100-share))]), 1)
            publish(db, "recipes", rec["id"], "approve", 1)
        steps = [
            ("Смешивание", "Подготовка массы", "Проверьте допуск сырья. Загрузите компоненты по порядку рецептуры. Снимите показание влажности.", None, [param("Влажность", "%", 6, 5, 7)]),
            ("Формование", "Прессование", "Установите матрицу нужного формата и запишите рабочее давление пресса.", 1, [param("Давление", "бар", 320, 300, 340)]),
            ("Сушка", "Сушка плитки", "Проверьте температуру сушилки и остаточную влажность заготовки.", 2, [param("Температура", "°C", 175, 165, 185), param("Влажность", "%", 1, 0, 2)]),
            ("Глазурование", "Нанесение глазури", "Проверьте вязкость глазури и равномерность покрытия.", None, [param("Вязкость", "с", 28, 23, 33)]),
            ("Обжиг", "Обжиг плитки", "Проверьте температуру в зонах печи и длительность цикла. Зафиксируйте фактические значения.", 3, [param("Температура", "°C", 1120, 1100, 1140), param("Длительность", "мин", 38, 34, 42)]),
            ("Контроль", "Осмотр перед лабораторией", "Осмотрите контрольную выборку. После завершения партия поступит в лабораторию.", None, [param("Размер образца", "мм", 600 if p == 1 else 300, 599.5 if p == 1 else 299.5, 600.5 if p == 1 else 300.5)]),
        ]
        card = card_write(db, None, dict(product_id=p, name="Маршрут производства плитки", steps=[
            dict(kind=kind, name=name, instructions=instructions, equipment_id=equipment + (p-1)*3 if equipment else None,
                 parameters=parameters) for kind, name, instructions, equipment, parameters in steps]), 1)
        publish(db, "tech_cards", card["id"], "approve", 1)
        insert(db, "orders", dict(code=f"ЗК-{2026+p}", product_id=p, quantity=6000,
            due=(date.today() + timedelta(days=4+p)).isoformat(), author_id=1))

    def batch(code, product, steps, start_next=True):
        row = create_batch(db, dict(code=code, order_id=product, line=f"Линия 0{product}", quantity=1200,
            raw=[dict(raw_lot_id=i, quantity=q) for i, q in ((1,90),(2,40),(3,22),(4,4))],
            programs=list(range(1+(product-1)*3, 4+(product-1)*3))), 1)
        key = row["id"]
        if steps is None:
            return key
        launch_batch(db, key, 1)
        for pos, step in enumerate(row["steps"]):
            if pos > steps or (pos == steps and not start_next):
                break
            run_step(db, key, step["id"], "start", {}, 2)
            if pos < steps:
                values = {str(p["id"]): p["target"] for p in step["parameters"]}
                run_step(db, key, step["id"], "finish", {"values": values}, 2)
        return key

    complete = batch("ПР-26041", 2, 6)
    qualify("finished", complete)
    batch("ПР-26042", 1, 6)
    batch("ПР-26043", 2, 1)
    firing = batch("ПР-26044", 1, 4)
    batch("ПР-26045", 2, None)
    first = rows(db, "SELECT id FROM executions WHERE batch_id=? AND status='running'", (firing,))[0]["id"]
    incident = insert(db, "incidents", dict(batch_id=firing, execution_id=first, author_id=2,
                    severity="warning", description="Проверить показание датчика во второй зоне печи."))
    audit(db, 2, "Предупреждение", "incidents", incident, "Проверить датчик зоны 2", firing, alert=True)
    for tick in range(12):
        for zone in range(1,4):
            db.execute("""INSERT INTO telemetry(equipment_id,batch_id,zone,temperature,recorded)
                VALUES(3,?,?,?,datetime('now',?))""", (firing,f"Зона {zone}",1110+zone*4+(tick%5-2)*1.2,f"-{(12-tick)*5} seconds"))
