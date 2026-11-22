"""Generate the editable draw.io workbook from the project workflow and schema."""
from collections import defaultdict
from html import escape
from pathlib import Path
import sqlite3
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
file = ET.Element("mxfile", host="app.diagrams.net", type="device")
INK = "#20343D"
MUTED = "#58707A"
LINE = "#607D87"
TEAL = "#126854"
TEAL_BG = "#E8F4EF"
GOLD = "#B98134"
GOLD_BG = "#FFF3DA"
RED = "#A14747"
RED_BG = "#FCECEC"
BLUE = "#446886"
BLUE_BG = "#EDF4FA"
FONT = "fontFamily=Segoe UI;fontColor=" + INK + ";"
VARIANT = "Вариант • Сопровождение производственной партии керамической плитки"


class Sheet:
    def __init__(self, key, name, title, width, height, subtitle=VARIANT):
        diagram = ET.SubElement(file, "diagram", id=key, name=name)
        graph = ET.SubElement(diagram, "mxGraphModel", grid="1", gridSize="10", guides="1", tooltips="1",
                              connect="1", arrows="1", fold="1", page="1", pageScale="1",
                              pageWidth=str(width), pageHeight=str(height), background="#FFFFFF")
        self.root = ET.SubElement(graph, "root")
        ET.SubElement(self.root, "mxCell", id="0")
        ET.SubElement(self.root, "mxCell", id="1", parent="0")
        self.index = 0
        self.label(title, 40, 23, width - 80, 38, 30, True)
        self.label(subtitle, 40, 68, width - 80, 25, 14, color=MUTED)
        self.box("", 40, 105, width - 80, 2, fill="#DCE7E8", stroke="none", size=1)

    def key(self):
        self.index += 1
        return f"c{self.index}"

    def cell(self, value, x, y, w, h, style, parent="1"):
        ident = self.key()
        cell = ET.SubElement(self.root, "mxCell", id=ident, value=value, style=style, vertex="1", parent=parent)
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), attrib={"as": "geometry"})
        return ident

    def label(self, value, x, y, w, h, size=13, bold=False, color=INK, align="left"):
        return self.cell(value, x, y, w, h, FONT + f"text;html=1;align={align};verticalAlign=middle;"
                         f"fontSize={size};fontStyle={1 if bold else 0};fontColor={color};whiteSpace=wrap;spacing=0;")

    def box(self, value, x, y, w, h, *, fill=TEAL_BG, stroke=TEAL, size=14, shape="rounded=1;arcSize=12;",
            extra="", parent="1"):
        return self.cell(value, x, y, w, h, FONT + f"{shape}html=1;whiteSpace=wrap;fillColor={fill};"
                         f"strokeColor={stroke};fontSize={size};strokeWidth=1.3;spacing=5;{extra}", parent)

    def edge(self, source=None, target=None, *, value="", style="", points=(), start=None, end=None,
             exit_at=None, entry_at=None, multiplicities=()):
        ident = self.key()
        base = FONT + f"html=1;strokeColor={LINE};strokeWidth=1.25;fontSize=12;"
        base += "labelBackgroundColor=#FFFFFF;endArrow=none;"
        if exit_at:
            base += f"exitX={exit_at[0]};exitY={exit_at[1]};exitDx=0;exitDy=0;"
        if entry_at:
            base += f"entryX={entry_at[0]};entryY={entry_at[1]};entryDx=0;entryDy=0;"
        attrs = dict(id=ident, value=value, style=base + style, edge="1", parent="1")
        if source:
            attrs["source"] = source
        if target:
            attrs["target"] = target
        cell = ET.SubElement(self.root, "mxCell", attrs)
        geo = ET.SubElement(cell, "mxGeometry", relative="1", attrib={"as": "geometry"})
        for point, name in ((start, "sourcePoint"), (end, "targetPoint")):
            if point:
                ET.SubElement(geo, "mxPoint", x=str(point[0]), y=str(point[1]), attrib={"as": name})
        if points:
            arr = ET.SubElement(geo, "Array", attrib={"as": "points"})
            for x, y in points:
                ET.SubElement(arr, "mxPoint", x=str(x), y=str(y))
        for location, label in zip((-.82,.82), multiplicities):
            endpoint = ET.SubElement(self.root, "mxCell", id=self.key(), value=label, vertex="1", connectable="0",
                                     parent=ident, style=FONT+"edgeLabel;html=1;fontSize=12;labelBackgroundColor=#FFFFFF;")
            label_geo = ET.SubElement(endpoint, "mxGeometry", x=str(location), y="10", relative="1", attrib={"as":"geometry"})
            ET.SubElement(label_geo, "mxPoint", attrib={"as":"offset"})
        return ident


def use_cases():
    s = Sheet("uc", "UML · Прецеденты", "Диаграмма вариантов использования", 1380, 980)
    s.box("", 205, 130, 972, 705, fill="#F8FBFC", stroke="#9FB3BD", shape="rounded=0;")
    s.label("Граница системы Ceramika", 229, 147, 490, 30, 18, True)

    def actor(label, x, y):
        return s.box(label, x, y, 72, 88, fill="#FFFFFF", stroke=INK, size=14,
                     shape="shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;")

    def case(label, x, y, color=TEAL, shade=TEAL_BG, width=226):
        return s.box(label, x, y, width, 69, fill=shade, stroke=color, shape="ellipse;")

    tech = actor("Технолог", 76, 234)
    operator = actor("Оператор линии", 1232, 249)
    lab = actor("Лаборант", 76, 548)
    oven = actor("Источник телеметрии", 1232, 628)
    recipe = case("Утвердить версии рецептур<br>и технологической карты", 274, 195, BLUE, BLUE_BG)
    launch = case("Сформировать<br>и запустить партию", 274, 292, BLUE, BLUE_BG)
    monitor = case("Анализировать журнал<br>и обработать инцидент", 274, 388, BLUE, BLUE_BG)
    appoint = case("Назначить испытание<br>и внести измерения", 274, 555)
    decision = case("Допустить<br>или заблокировать партию", 274, 670)
    check_lab = case("Проверить готовность<br>испытания и нормативы", 592, 670)
    browse = case("Открыть маршрут партии", 900, 191)
    execute = case("Начать и завершить<br>операцию", 900, 294)
    values = case("Проверить факт<br>и записать событие", 592, 294)
    incident = case("Зарегистрировать инцидент", 900, 397, GOLD, GOLD_BG)
    live = case("Просмотреть температуру<br>по зонам печи", 900, 522, GOLD, GOLD_BG)
    measure = case("Передать показания печи", 900, 662, GOLD, GOLD_BG)
    for a, items in ((tech, (recipe, launch, monitor)), (lab, (appoint, decision)),
                     (operator, (browse, execute, incident, live)), (oven, (measure,))):
        for item in items:
            s.edge(a, item)
    dependency = "dashed=1;endArrow=open;endFill=0;"
    s.edge(execute, values, value="«include»", style=dependency)
    s.edge(decision, check_lab, value="«include»", style=dependency)
    s.label("Доступ участников к операциям определяется ролью. Результат процесса — выпуск или блокировка партии.",
            40, 870, 1280, 34, 14, color=MUTED)


def classes():
    s = Sheet("classes", "UML · Классы", "Диаграмма классов", 1510, 1010)

    def cls(name, attrs, operations, x, y, w=230, tint=TEAL_BG, stroke=TEAL):
        h = 33 + 22 * (len(attrs) + len(operations)) + 15
        body = ('<b>' + escape(name) + '</b><hr>' + '<br>'.join(escape(a) for a in attrs) + '<hr>'
                + '<br>'.join(escape(o) for o in operations))
        return s.box(body, x, y, w, h, fill=tint, stroke=stroke, size=13, shape="rounded=0;",
                     extra="align=left;verticalAlign=top;spacingTop=7;spacingLeft=9;")

    product = cls("Продукт", ["код: String", "наименование: String"], ["архивировать()"], 55, 162, tint=BLUE_BG, stroke=BLUE)
    recipe = cls("ВерсияРецептуры", ["тип: Масса | Глазурь", "версия: Integer", "статус: СтатусРецептуры"],
                 ["утвердить()"], 379, 142, tint=BLUE_BG, stroke=BLUE)
    card = cls("ТехнологическаяКарта", ["версия: Integer", "статус: СтатусКарты"], ["опубликовать()"],
               763, 142, tint=BLUE_BG, stroke=BLUE)
    step = cls("НормативныйШаг", ["порядок: Integer", "обязательный: Boolean"], ["параметрыДопуска()"],
               1190, 142, tint=BLUE_BG, stroke=BLUE)
    order = cls("ПроизводственныйЗаказ", ["номер: String", "объём: Integer"], ["сформироватьПартию()"], 55, 401)
    batch = cls("ПроизводственнаяПартия", ["номер: String", "линия: String", "статус: СтатусПартии"],
                ["запустить()", "передатьНаКонтроль()", "применитьРешение()"], 524, 387, 254)
    op = cls("ВыполнениеШага", ["статус: СтатусШага", "начало: DateTime", "окончание: DateTime?"],
             ["начать()", "сохранитьФакт()", "завершить()"], 963, 399)
    event = cls("СобытиеПартии", ["действие: String", "дата: DateTime", "исполнитель: Пользователь?"],
                ["отметитьВЖурнале()"], 1227, 705, tint=BLUE_BG, stroke=BLUE)
    value = cls("ФактическийПараметр", ["параметр: ПараметрШага", "значение: Decimal"], ["проверитьДопуск()"],
                948, 708, tint=GOLD_BG, stroke=GOLD)
    lab = cls("ЛабораторноеИспытание", ["вид: ВидКонтроля", "статус: СтатусИспытания", "итог: Оценка?"],
              ["сохранитьИзмерения()", "завершить()"], 529, 711, 242, GOLD_BG, GOLD)
    decision = cls("РешениеЛаборатории", ["решение: Допуск | Блокировка", "комментарий: String", "дата: DateTime"],
                   ["зарегистрировать()"], 90, 716, 251, GOLD_BG, GOLD)
    s.edge(product, recipe, multiplicities=("1","0..*"), exit_at=(1,.48), entry_at=(0,.50))
    s.edge(product, order, multiplicities=("1","0..*"), exit_at=(.50,1), entry_at=(.50,0))
    s.edge(product, card, multiplicities=("1","0..*"), exit_at=(.80,0), entry_at=(.35,0), points=[(239,119),(843,119)])
    s.edge(order, batch, multiplicities=("1","0..*"), exit_at=(1,.49), entry_at=(0,.42))
    s.edge(batch, recipe, value="масса", multiplicities=("0..*","1"), exit_at=(.10,0), entry_at=(.58,1))
    s.edge(batch, recipe, value="глазурь", multiplicities=("0..*","1"), exit_at=(.39,0), entry_at=(.95,1))
    s.edge(batch, card, multiplicities=("0..*","1"), exit_at=(.85,0), entry_at=(.25,1))
    s.edge(card, step, multiplicities=("1","1..*"), style="startArrow=diamond;startFill=1;", exit_at=(1,.5), entry_at=(0,.5))
    s.edge(step, op, multiplicities=("1","0..*"), exit_at=(.42,1), entry_at=(.78,0))
    s.edge(batch, op, multiplicities=("1","1..*"), style="startArrow=diamond;startFill=1;", exit_at=(1,.45), entry_at=(0,.41))
    s.edge(op, value, multiplicities=("1","0..*"), style="startArrow=diamond;startFill=1;", exit_at=(.40,1), entry_at=(.47,0))
    s.edge(batch, lab, multiplicities=("0..1","0..*"), exit_at=(.49,1), entry_at=(.5,0))
    s.edge(lab, decision, multiplicities=("1","0..1"), exit_at=(0,.48), entry_at=(1,.48))
    s.edge(batch, event, value="журнал", multiplicities=("1","0..*"), exit_at=(.88,1), entry_at=(.45,0), points=[(747,630),(1331,630)])
    s.label("Карты и рецептуры хранят версии. Партия закрепляет нормативы на момент формирования.",
            40, 909, 1400, 31, 14, color=MUTED)


def sequence():
    s = Sheet("seq", "UML · Последовательность", "Диаграмма последовательности", 1420, 1190)
    xs = [145, 405, 700, 1000, 1275]
    for x, name, tint, color in zip(xs, ["Технолог<br>WinForms", "Оператор<br>Web",
        "Сервер<br>HTTP API", "SQLite<br>Транзакция", "Лаборант<br>WinForms"],
        (BLUE_BG, TEAL_BG, TEAL_BG, BLUE_BG, GOLD_BG), (BLUE, TEAL, TEAL, BLUE, GOLD)):
        s.box(name, x-84, 142, 168, 56, fill=tint, stroke=color, extra="fontStyle=1;")
        s.edge(start=(x,198),end=(x,1113),style="dashed=1;strokeColor=#A6B9C0;")

    def msg(i, j, y, label, *, returned=False):
        arrow = "endArrow=open;endFill=0;dashed=1;" if returned else "endArrow=block;endFill=1;"
        s.edge(start=(xs[i],y),end=(xs[j],y), style=arrow)
        left, right = sorted((xs[i],xs[j]))
        s.label(label, left+6, y-22, right-left-12, 18, 12, color=MUTED if returned else INK, align="center")

    def frame(tag, body, x, y, w, h, cut):
        s.box("", x,y,w,h,fill="none",stroke="#8AA3AE",shape="rounded=0;")
        s.box(tag, x,y,64,26,fill=BLUE_BG,stroke="#8AA3AE",shape="rounded=0;",extra="fontStyle=1;")
        s.label(body,x+73,y+2,w-80,24,12,True)
        if cut:
            s.edge(start=(x,cut),end=(x+w,cut),style="dashed=1;strokeColor=#8AA3AE;")

    msg(0,2,236,"POST /batches/{id}/launch")
    msg(2,3,271,"Запустить партию и активировать первый шаг")
    msg(3,2,305,"Партия запущена", returned=True)
    msg(2,0,336,"200 · обновлённая карточка", returned=True)
    msg(1,2,378,"GET /batches/{id} · загрузить программу")
    msg(2,1,411,"200 · маршрут и допуски", returned=True)
    msg(1,2,448,"POST …/steps/{step}/start")
    msg(2,3,483,"Зафиксировать начало и оператора")
    msg(1,2,526,"POST …/steps/{step}/finish · факт и комментарий")
    frame("alt", "[поля заполнены и нет открытого критического инцидента]", 328, 548, 750, 219, 703)
    msg(2,3,608,"Сохранить факт, отклонения и исполнение")
    msg(3,2,643,"Активировать следующий шаг или передать в ОТК", returned=True)
    msg(2,1,679,"200 · обновлённая программа", returned=True)
    s.label("[нарушено условие завершения]", 341,706,342,18,12,True)
    msg(2,1,750,"400 · сообщение; шаг остаётся в работе", returned=True)
    msg(4,2,812,"POST /lab/tests · назначить итоговый контроль")
    msg(4,2,849,"POST …/finish · внести измерения")
    msg(2,3,882,"Проверить нормативы и закрыть протокол")
    msg(4,2,922,"POST …/decide · допуск или блокировка")
    frame("alt","[допуск и все обязательные шаги завершены]",610,944,754,161,1023)
    msg(2,3,1004,"Сохранить решение и статус «Завершена»")
    s.label("[блокировка с указанной причиной]",618,1028,388,21,12,True)
    msg(2,3,1084,"Сохранить причину и статус «Заблокирована»")
    s.label("Цикл выполнения повторяется до последней операции. Закрытие шага и решение лаборатории применяются транзакционно.",
            40,1120,1330,30,14,color=MUTED)


def activity():
    s = Sheet("activity", "UML · Деятельность", "Диаграмма деятельности", 1420, 1230)
    for x, title, paint in ((40, "Технолог", BLUE_BG), (375, "Оператор линии", TEAL_BG),
                             (710, "Сервер и база данных", "#EFF5F6"), (1045, "Лаборатория", GOLD_BG)):
        s.box("",x,134,335,1029,fill="#FAFCFC",stroke="#BBCDD0",shape="rounded=0;")
        s.box(title,x,134,335,43,fill=paint,stroke="#BBCDD0",shape="rounded=0;",extra="fontStyle=1;")

    def act(text,x,y,w=225,tint=TEAL_BG, color=TEAL):
        return s.box(text,x,y,w,55,fill=tint,stroke=color,extra="fontStyle=1;")

    def flow(a,b,**kwargs):
        return s.edge(a,b,style="endArrow=block;endFill=1;",**kwargs)

    start=s.box("",199,200,22,22,fill=INK,stroke=INK,shape="ellipse;")
    plan=act("Выбрать нормативы<br>и сформировать партию",97,247,tint=BLUE_BG,color=BLUE)
    launch=act("Назначить сырьё<br>и запустить партию",97,332,tint=BLUE_BG,color=BLUE)
    init=act("Зафиксировать версии<br>и активировать первый шаг",765,332)
    run=act("Начать текущий шаг<br>и внести фактические данные",430,411)
    valid=s.box("Можно<br>завершить?",832,405,90,70,fill=GOLD_BG,stroke=GOLD,size=12,shape="rhombus;")
    clarify=act("Заполнить пропуски или<br>объяснить отклонение",430,510,tint=GOLD_BG,color=GOLD)
    write=act("Сохранить факт,<br>отклонения и журнал",765,516)
    next_=s.box("Ещё есть<br>шаги?",832,599,90,70,fill=GOLD_BG,stroke=GOLD,size=12,shape="rhombus;")
    activate=act("Активировать следующий шаг",430,605)
    quality=act("Перевести партию<br>на контроль качества",765,704)
    test=act("Провести испытание<br>и завершить протокол",1100,704,tint=GOLD_BG,color=GOLD)
    conform=s.box("Есть<br>допуск?",1168,792,90,70,fill=GOLD_BG,stroke=GOLD,size=12,shape="rhombus;")
    release=act("Подтвердить допуск",1100,900,tint=TEAL_BG,color=TEAL)
    block=act("Заблокировать партию<br>с указанием причины",1100,994,tint=RED_BG,color=RED)
    persist=act("Сохранить решение<br>и уведомить участников",765,994)
    end=s.box("",861,1090,28,28,fill="none",stroke=INK,shape="ellipse;")
    s.box("",867,1096,16,16,fill=INK,stroke=INK,shape="ellipse;")
    flow(start,plan)
    flow(plan,launch)
    flow(launch,init,exit_at=(1,.5),entry_at=(0,.5))
    flow(init,run,exit_at=(0,1),entry_at=(1,0),points=[(680,397)])
    flow(run,valid,exit_at=(1,.5),entry_at=(0,.5))
    flow(valid,clarify,value="[требуется исправление]",exit_at=(0,.76),entry_at=(1,.4),points=[(735,485)])
    flow(clarify,run,exit_at=(0,.45),entry_at=(0,.62),points=[(400,535),(400,445)])
    flow(valid,write,value="[да / внесено обоснование]",exit_at=(.5,1),entry_at=(.5,0))
    flow(write,next_)
    flow(next_,activate,value="[да]",exit_at=(0,.5),entry_at=(1,.5))
    flow(activate,run,exit_at=(0,.6),entry_at=(0,.36),points=[(389,638),(389,431)])
    flow(next_,quality,value="[нет]",exit_at=(.5,1),entry_at=(.5,0))
    flow(quality,test,exit_at=(1,.5),entry_at=(0,.5))
    flow(test,conform)
    flow(conform,release,value="[да]",exit_at=(.5,1),entry_at=(.5,0))
    flow(conform,block,value="[нет]",exit_at=(1,.5),entry_at=(1,.46),points=[(1350,827),(1350,1019)])
    flow(release,persist,exit_at=(0,.49),entry_at=(1,.12),points=[(1057,927),(1057,1001)])
    flow(block,persist,exit_at=(0,.65),entry_at=(1,.65))
    flow(persist,end)
    s.label("Условия завершения шага — обязательные параметры, обоснование отклонений и закрытые критические инциденты.",
            40,1176,1320,28,14,color=MUTED)


def erd():
    db = sqlite3.connect(":memory:")
    db.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    layouts = [
        ("erd-production", "ERD · Производство", "ERD Crow’s Foot · Производство и нормативы", {
            "materials": (55, 145), "recipe_items": (390, 145), "recipes": (725, 145), "products": (1130, 145),
            "raw_lots": (55, 463), "batch_raw": (390, 463), "batches": (725, 500), "orders": (1130, 480),
            "equipment": (55, 875), "equipment_programs": (390, 875), "batch_programs": (725, 895), "tech_cards": (1130, 875),
        }, 1515, 1210),
        ("erd-execution", "ERD · Исполнение", "ERD Crow’s Foot · Исполнение и события", {
            "tech_cards": (60, 149), "card_steps": (397, 149), "step_parameters": (767, 149), "step_values": (1143, 149),
            "equipment": (60, 420), "telemetry": (397, 444), "executions": (767, 527), "deviations": (1143, 508),
            "batches": (60, 735), "events": (397, 865), "incidents": (767, 866), "notifications": (1143, 887),
        }, 1530, 1240),
        ("erd-lab", "ERD · Лаборатория и доступ", "ERD Crow’s Foot · Контроль качества и доступ", {
            "raw_lots": (62, 148), "lab_tests": (492, 422), "lab_results": (948, 443), "lab_specs": (948, 146),
            "batches": (62, 481), "lab_decisions": (948, 708), "users": (492, 885), "sessions": (948, 1008),
            "departments": (62, 870), "roles": (62, 1058),
        }, 1330, 1295),
        ("erd-inspections", "ERD · Обходы линии", "ERD Crow’s Foot · Обходы линии", {
            "inspection_routes": (60, 150), "inspection_points": (410, 150), "inspection_parameters": (790, 150),
            "inspections": (60, 475), "inspection_checks": (410, 475), "inspection_readings": (790, 475),
        }, 1150, 825),
    ]
    repeated = {"batches", "raw_lots", "tech_cards", "equipment", "users"}
    pair_ports = {
        "erd-production": {
            ("materials","recipe_items"): ((1,.37),(0,.30)),
            ("materials","raw_lots"): ((.44,1),(.44,0)),
            ("recipes","recipe_items"): ((0,.37),(1,.35)),
            ("products","recipes"): ((0,.35),(1,.35)),
            ("products","orders"): ((.64,1),(.64,0)),
            ("products","tech_cards"): ((1,.40),(1,.45),[(1457,237),(1457,966)]),
            ("orders","batches"): ((0,.30),(1,.22)),
            ("raw_lots","batch_raw"): ((1,.36),(0,.43)),
            ("batches","batch_raw"): ((0,.36),(1,.65)),
            ("equipment","equipment_programs"): ((1,.32),(0,.30)),
            ("equipment_programs","batch_programs"): ((1,.39),(0,.47)),
            ("batches","batch_programs"): ((.55,1),(.55,0)),
            ("tech_cards","batches"): ((0,.34),(1,.76),[(1060,934),(1060,704)]),
        },
        "erd-execution": {
            ("tech_cards","card_steps"): ((1,.35),(0,.24)),
            ("tech_cards","batches"): ((0,.74),(0,.18),[(32,261),(32,788)]),
            ("card_steps","step_parameters"): ((1,.27),(0,.28)),
            ("step_parameters","step_values"): ((1,.29),(0,.30)),
            ("card_steps","executions"): ((1,.84),(0,.16),[(720,327),(720,564)]),
            ("equipment","card_steps"): ((.82,0),(.18,1),[(298,387),(449,387)]),
            ("equipment","telemetry"): ((1,.44),(0,.29)),
            ("batches","telemetry"): ((1,.15),(0,.68),[(372,779),(372,561)]),
            ("batches","executions"): ((1,.23),(0,.69),[(693,802),(693,687)]),
            ("batches","incidents"): ((1,.33),(.20,0),[(823,831)]),
            ("batches","events"): ((1,.64),(0,.28)),
            ("executions","step_values"): ((1,.12),(.51,1),[(1089,555),(1089,404),(1291,404)]),
            ("executions","deviations"): ((1,.52),(0,.38)),
            ("step_parameters","deviations"): ((.79,1),(.18,0),[(995,461),(1195,461)]),
            ("executions","incidents"): ((.48,1),(.48,0)),
            ("events","notifications"): ((.87,1),(0,.73),[(649,1150),(1105,1150),(1105,985)]),
        },
        "erd-lab": {
            ("raw_lots","lab_tests"): ((1,.48),(0,.20),[(436,289),(436,489)]),
            ("batches","lab_tests"): ((1,.40),(0,.48)),
            ("lab_tests","lab_results"): ((1,.19),(0,.40)),
            ("lab_specs","lab_results"): ((.55,1),(.55,0)),
            ("lab_tests","lab_decisions"): ((1,.76),(0,.35),[(867,675),(867,778)]),
            ("users","lab_decisions"): ((1,.32),(0,.77)),
            ("users","lab_tests"): ((.51,0),(.51,1)),
            ("users","sessions"): ((1,.73),(0,.50)),
            ("departments","users"): ((1,.51),(0,.22)),
            ("roles","users"): ((1,.53),(0,.69)),
        },
        "erd-inspections": {
            ("inspection_routes","inspection_points"): ((1,.46),(0,.28)),
            ("inspection_routes","inspections"): ((.52,1),(.52,0)),
            ("inspection_points","inspection_parameters"): ((1,.28),(0,.28)),
            ("inspection_points","inspection_checks"): ((.50,1),(.50,0)),
            ("inspections","inspection_checks"): ((1,.30),(0,.34)),
            ("inspection_checks","inspection_readings"): ((1,.24),(0,.36)),
            ("inspection_parameters","inspection_readings"): ((.50,1),(.50,0)),
        },
    }
    marks = {"one": "ERmandOne", "optional": "ERzeroToOne", "many": "ERzeroToMany"}
    for key, tab, title, positions, w, h in layouts:
        sheet = Sheet(key, tab, title, w, h, "Физическая схема SQLite · ключи и кратности связей")
        vertices, references = {}, []
        for table, (x, y) in positions.items():
            fields = db.execute(f"PRAGMA table_info({table})").fetchall()
            fks = {fk[3]:fk for fk in db.execute(f"PRAGMA foreign_key_list({table})")}
            header = "#284651" if table not in repeated else "#426786"
            attrs = []
            for _, col, datatype, not_null, _, primary in fields:
                fk = fks.get(col)
                target = fk[2] if fk else None
                kind = ("PK" if primary else "") + (" / " if primary and fk else "") + ("FK" if fk else "")
                desc = (" → " + target) if target and target not in positions else ""
                suffix = " ?" if not not_null and not primary else ""
                attrs.append(f'<span style="color:{BLUE}"><b>{kind}</b></span> {col} <span style="color:{MUTED}">{datatype}{suffix}{escape(desc)}</span>')
                if target in positions and fk[1] == 0:
                    references.append((target, table, col, bool(not_null)))
            content="<div style='line-height:20px'>" + "<br>".join(attrs) + "</div>"
            height = 38 + 20 * len(fields) + 14
            body = sheet.box(content, x, y, 290, height, fill="#FCFEFE", stroke="#9CB5BD", size=12,
                             shape="rounded=0;", extra="align=left;verticalAlign=top;spacingTop=35;spacingLeft=11;")
            sheet.box("<b>"+table+"</b>", x, y, 290, 33, fill=header, stroke=header, size=14,
                      shape="rounded=0;", extra="align=left;spacingLeft=10;fontColor=#FFFFFF;")
            vertices[table] = body
        groups = defaultdict(list)
        for source, target, field, mandatory in references:
            groups[source, target].append((field, mandatory))
        for (source, target), fields in groups.items():
            for i, (field, mandatory) in enumerate(fields):
                if len(fields) > 1:
                    if (source,target) == ("recipes","batches"):
                        ports = ((.31 + i*.36,1),(.31 + i*.36,0))
                    else:
                        # Multiple audit references share layout space while each FK stays visible in the table.
                        if i:
                            continue
                        ports = pair_ports[key].get((source,target), ((1,.58),(0,.60)))
                    label = field if (source,target) == ("recipes","batches") else " / ".join(f for f,_ in fields)
                else:
                    ports = pair_ports[key].get((source,target), ((.50,1),(.50,0)))
                    label = "партия сырья" if field == "raw_lot_id" and target == "lab_tests" else ""
                start = marks["one" if mandatory else "optional"]
                end = marks["optional" if (target, field) == ("lab_decisions", "test_id") else "many"]
                path = ports[2] if len(ports) > 2 else ()
                sheet.edge(vertices[source], vertices[target], value=label, exit_at=ports[0], entry_at=ports[1],
                           points=path, style=f"startArrow={start};endArrow={end};startSize=13;endSize=13;strokeWidth=1.3;fontSize=11;")
        sheet.label("PK — первичный ключ   ·   FK — внешний ключ   ·   ? — NULL   ·   → имя таблицы — связь на другом листе",
                    42,h-53,w-84,25,13,color=MUTED)
    db.close()


def wireframe():
    s = Sheet("wireframe", "Wireframe · Обход линии", "Мобильный wireframe обхода линии", 1770, 1080,
              "Вариант • Ежедневный осмотр оборудования оператором или мастером смены")
    width, height = 355, 388

    def screen(num, title, x, y, controls, buttons, nav="Маршруты  ·  Точки  ·  Отчёт"):
        base = s.box("",x,y,width,height,fill="#F8FAFC",stroke="#90A7AF",shape="rounded=1;arcSize=7;")
        s.box(f"{num:02}  {title}",x+12,y+12,width-24,45,fill="#26424D",stroke="#26424D",size=15,
              extra="fontColor=#FFFFFF;fontStyle=1;align=left;spacingLeft=12;")
        for row, control in enumerate(controls):
            text, kind = control
            color, border = {"text":("#FFFFFF","#C6D4DC"),"status":(TEAL_BG,TEAL),
                             "warn":(GOLD_BG,GOLD),"field":("#FFFFFF","#A4B9C3")}[kind]
            s.box(text,x+20,y+77+row*42,width-40,34,fill=color,stroke=border,size=12,
                  extra="align=left;spacingLeft=9;")
        button_y=y+282
        for label, primary in buttons:
            s.box(label,x+20,button_y,width-40,34,fill=TEAL if primary else "#FFFFFF",stroke=TEAL,
                  size=12,extra="fontStyle=1;" + ("fontColor=#FFFFFF;" if primary else ""))
            button_y+=38
        if nav:
            s.label(nav,x+20,y+357,width-40,24,11,color=MUTED,align="center")
        return base

    positions=[(40,145),(480,145),(920,145),(1360,145),(1360,591),(920,591),(480,591)]
    entries = [
        ("Вход", [("CERAMIKA · Обход линии","text"),("Логин","field"),("Пароль  ••••••••","field"),
                   ("Ошибки входа отображаются под полями","warn")],[("Войти",True)], ""),
        ("Маршруты обхода",[("Смена А · 22 ноября","text"),("Линия 01 · Пресс / Сушилка / Печь","text"),
                            ("Назначен · 4 контрольные точки","status"),("Линия 02 · Завершён в 07:45","text")],
         [("Открыть маршрут «Линия 01»",True)],"Маршруты  ·  Точки  ·  Отчёт"),
        ("Контрольные точки",[("Линия 01 · Готово 1 из 4","status"),("✓ Пресс 01 · осмотрен","text"),
                             ("Сушилка 01 · следующая точка","warn"),("Печь 01 / Глазуровочная линия","text")],
         [("Открыть сушилку",True),("Открыть итоговый отчёт",False)],"Маршруты  ·  Точки  ·  Отчёт"),
        ("Карточка точки",[("Сушилка 01 · Контрольная точка 2","text"),("Зона A3 · доступ с западного прохода","text"),
                          ("Проверить температуру и влажность","text"),("Осмотр выполняется","warn")],
         [("Ввести показания",True),("Добавить замечание",False)],"Маршруты  ·  Точки  ·  Отчёт"),
        ("Показания",[("Температура, °C    [  189  ]","field"),("Норма температуры 165–185 °C","warn"),
                     ("Влажность, %    [  1,2  ]","field"),("Результат: температура вне допуска","warn")],
         [("Сохранить показания",True),("Перейти к замечанию",False)],"Маршруты  ·  Точки  ·  Отчёт"),
        ("Замечание",[("Оборудование · Сушилка 01","text"),("Серьёзность  [ Предупреждение ]","field"),
                      ("Причина / наблюдение  [ Текст ]","field"),("Добавить фото (необязательно)","field")],
         [("Сохранить замечание",True),("К контрольным точкам",False)],"Маршруты  ·  Точки  ·  Отчёт"),
        ("Итоговый отчёт",[("Линия 01 · Готово 4 из 4","status"),("Сушилка 01 · 1 замечание","warn"),
                          ("Остальные точки · без замечаний","text"),("Подтверждение завершает обход","text")],
         [("Завершить обход",True),("Вернуться к точкам",False)],"Маршруты  ·  Точки  ·  Отчёт"),
    ]
    nodes=[]
    for num, ((x,y),(title,fields,buttons,nav)) in enumerate(zip(positions,entries),1):
        nodes.append(screen(num,title,x,y,fields,buttons,nav))
    style="endArrow=block;endFill=1;strokeColor=#506F7B;strokeWidth=1.5;"
    for i, j, label in ((0,1,"Вход"),(1,2,"Открыть"),(2,3,"Осмотреть")):
        s.edge(nodes[i],nodes[j],value=label,style=style,exit_at=(1,.5),entry_at=(0,.5))
    s.edge(nodes[3],nodes[4],value="Ввод показаний",style=style,exit_at=(.49,1),entry_at=(.49,0))
    s.edge(nodes[4],nodes[5],value="Вне нормы",style=style,exit_at=(0,.50),entry_at=(1,.50))
    s.edge(nodes[4],nodes[2],value="В норме",style=style,exit_at=(0,.24),entry_at=(1,.84),
           points=[(1319,684),(1319,471)])
    s.edge(nodes[5],nodes[2],value="После сохранения",style=style,exit_at=(.42,0),entry_at=(.42,1))
    s.edge(nodes[2],nodes[6],value="Все точки осмотрены",style=style,exit_at=(0,.88),entry_at=(.58,0),
           points=[(900,485),(900,554),(686,554)])
    s.label("Для каждой точки повторяются карточка, ввод показаний и, при необходимости, регистрация замечания.",
            44,1005,1680,30,14,color=MUTED)


if __name__ == "__main__":
    use_cases()
    classes()
    sequence()
    activity()
    erd()
    wireframe()
    ET.indent(file, space="  ")
    ET.ElementTree(file).write(ROOT / "diagrams" / "Ceramika.drawio", encoding="utf-8", xml_declaration=True)
