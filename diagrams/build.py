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
    s = Sheet("uc", "UML · Прецеденты", "Диаграмма вариантов использования", 2180, 2050)
    s.box("", 430, 130, 1510, 1810, fill="#F8FBFC", stroke="#9FB3BD", shape="rounded=0;")
    s.label("Граница системы Ceramika", 465, 145, 1000, 36, 22, True)

    def actor(label, x, y):
        return s.box(label, x, y, 94, 116, fill="#FFFFFF", stroke=INK, size=17,
                     shape="shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;")

    def case(label, x, y, color=TEAL, shade=TEAL_BG):
        return s.box(label, x, y, 350, 86, fill=shade, stroke=color, size=16, shape="ellipse;")

    def section(label, y, color):
        s.label(label, 490, y, 1350, 28, 17, True, color=color)
        s.box("", 490, y+34, 1390, 2, fill="#DCE7E8", stroke="none", size=1)

    employee = actor("Сотрудник", 215, 195)
    tech = actor("Технолог", 215, 490)
    lab = actor("Лаборант", 215, 905)
    operator = actor("Оператор линии", 215, 1310)
    master = actor("Мастер смены", 215, 1695)
    sensor = actor("Источник телеметрии", 2015, 1760)

    login = case("Войти в систему", 530, 210, BLUE, BLUE_BG)
    section("01 · Нормативы и производство", 325, BLUE)
    recipe = case("Утвердить версии рецептур<br>и технологической карты", 530, 385, BLUE, BLUE_BG)
    launch = case("Сформировать<br>и запустить партию", 530, 500, BLUE, BLUE_BG)
    monitor = case("Анализировать журнал<br>и обработать инцидент", 530, 615, BLUE, BLUE_BG)
    check_ready = case("Проверить готовность партии<br>и действующие нормативы", 1080, 500, BLUE, BLUE_BG)
    report = case("Экспортировать отчёт<br>о выпуске партии", 1080, 615, BLUE, BLUE_BG)

    section("02 · Лабораторный контроль", 745, TEAL)
    appoint = case("Назначить испытание", 530, 805)
    measure_lab = case("Внести измерения<br>и завершить испытание", 530, 920)
    decision = case("Допустить или<br>заблокировать партию", 530, 1035)
    check_lab = case("Проверить готовность<br>испытания и нормативы", 1080, 1035)

    section("03 · Исполнение технологического маршрута", 1165, TEAL)
    browse = case("Открыть маршрут партии", 530, 1225)
    execute = case("Начать и завершить<br>операцию", 530, 1340)
    incident = case("Зарегистрировать инцидент", 530, 1455, GOLD, GOLD_BG)
    values = case("Проверить факт<br>и записать событие", 1080, 1340)
    live = case("Просмотреть температуру<br>по зонам печи", 1080, 1225, GOLD, GOLD_BG)

    section("04 · Мобильный обход и телеметрия", 1575, GOLD)
    inspect = case("Выполнить обход линии", 530, 1635)
    readings = case("Внести показания<br>контрольных точек", 1080, 1635)
    issue = case("Добавить замечание", 1080, 1750, GOLD, GOLD_BG)
    finish = case("Завершить обход<br>и сформировать отчёт", 530, 1780)
    telemetry = case("Передать показания печи", 1530, 1775, GOLD, GOLD_BG)

    assoc = "strokeWidth=1.7;endArrow=none;"
    dependency = "dashed=1;endArrow=open;endFill=0;strokeWidth=1.6;fontSize=14;"
    general = "endArrow=block;endFill=0;endSize=16;strokeWidth=1.6;"
    # A common actor inherits authentication; specialised roles use their own operations.
    s.edge(employee, login, style=assoc, exit_at=(1,.5), entry_at=(0,.5))
    for actor_id, y, lane, entry in (
        (tech,548,175,.64), (lab,963,145,.52),
        (operator,1368,115,.40), (master,1753,85,.28)
    ):
        s.edge(actor_id, employee, style=general, exit_at=(0,.5), entry_at=(0,entry),
               points=[(lane,y),(lane,195+116*entry)])

    for source, targets in (
        (tech,(recipe,launch,monitor)), (lab,(appoint,measure_lab,decision)),
        (operator,(browse,execute,incident)), (master,(inspect,finish))
    ):
        for target in targets:
            s.edge(source,target,style=assoc,exit_at=(1,.5),entry_at=(0,.5))
    s.edge(tech, report, style=assoc, exit_at=(1,.80), entry_at=(0,.5),
           points=[(365,583),(365,730),(1000,730),(1000,658)])
    s.edge(operator, live, style=assoc, exit_at=(1,.15), entry_at=(0,.5),
           points=[(385,1327),(385,1205),(1010,1205),(1010,1268)])
    s.edge(operator, inspect, style=assoc, exit_at=(1,.85), entry_at=(0,.5),
           points=[(375,1409),(375,1678)])
    s.edge(sensor,telemetry,style=assoc,exit_at=(0,.5),entry_at=(1,.5))
    for source,target in ((launch,check_ready),(decision,check_lab),(execute,values),(inspect,readings)):
        s.edge(source,target,value="«include»",style=dependency,exit_at=(1,.5),entry_at=(0,.5))
    s.edge(issue,readings,value="«extend»",style=dependency,exit_at=(.5,0),entry_at=(.5,1))
    s.label("Сплошная линия — участие актёра  ·  Пустой треугольник — обобщение  ·  «include» — обязательный сценарий  ·  «extend» — условное расширение",
            40, 1970, 2100, 32, 15, color=MUTED)


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
    # Use a spacious grid and route each relationship between its actual key rows.
    # Orthogonal routing avoids table interiors and penalizes shared wire segments.
    from heapq import heappush, heappop
    marks = {"one": "ERmandOne", "optional": "ERzeroToOne", "many": "ERzeroToMany"}
    for key, tab, title, positions, w, h in layouts:
        positions = {t: (round(x * 1.35 / 10) * 10 + 60,
                         round((y - 140) * 1.45 / 10) * 10 + 180)
                     for t, (x, y) in positions.items()}
        width = 330
        info = {t: db.execute(f"PRAGMA table_info({t})").fetchall() for t in positions}
        rects = {t: (x, y, width, 50 + 20 * len(info[t])) for t, (x,y) in positions.items()}
        w = max(x + tw for x,y,tw,th in rects.values()) + 140
        h = max(y + th for x,y,tw,th in rects.values()) + 160
        sheet = Sheet(key, tab, title, w, h, "Физическая схема SQLite · связи между ключами")
        vertices, references, rows = {}, [], {}
        for table, (x, y, tw, th) in rects.items():
            fields = info[table]
            fks = {fk[3]:fk for fk in db.execute(f"PRAGMA foreign_key_list({table})")}
            header = "#284651" if table not in repeated else "#426786"
            body = sheet.box("", x, y, tw, th, fill="#FFFFFF", stroke="#9CB5BD",
                             shape="rounded=0;")
            vertices[table] = body
            sheet.box("<b>"+table+"</b>", x, y, tw, 33, fill=header, stroke=header, size=14,
                      shape="rounded=0;", extra="align=left;spacingLeft=10;fontColor=#FFFFFF;")
            for i, (_, col, datatype, not_null, _, primary) in enumerate(fields):
                fk = fks.get(col)
                target = fk[2] if fk else None
                kind = ("PK" if primary else "") + (" / " if primary and fk else "") + ("FK" if fk else "")
                desc = (" → " + target) if target and target not in positions else ""
                suffix = " ?" if not not_null and not primary else ""
                row_y = y + 40 + i * 20
                rows[table,col] = (row_y + 10, (row_y + 10 - y) / th)
                label = f'<b style="color:{BLUE}">{kind}</b> {col} <span style="color:{MUTED}">{datatype}{suffix}{escape(desc)}</span>'
                sheet.box(label, x+1, row_y, tw-2, 20, fill="#F2F7FA" if kind else "#FFFFFF",
                          stroke="none", size=12, shape="rounded=0;",
                          extra="align=left;spacingLeft=10;spacing=0;connectable=0;")
                if target in positions and fk[1] == 0:
                    parent_col = fk[4] or next(f[1] for f in info[target] if f[5] == 1)
                    composite = [f[3] for f in fks.values() if f[0] == fk[0]]
                    label = " + ".join(reversed(composite)) if len(composite)>1 else col
                    references.append((target, table, parent_col, col, bool(not_null),label))
        # Grid coordinates are integer multiples of ten pixels. Leave a clear
        # corridor around all cards, including the endpoints of each connector.
        blocked = set()
        for x,y,tw,th in rects.values():
            for gx in range(x//10-2,(x+tw)//10+3):
                for gy in range(y//10-2,(y+th)//10+3):
                    blocked.add((gx,gy))
        used = set()
        segments = set()
        def port(table, col, side):
            x,y,tw,th = rects[table]
            py, fraction = rows[table,col]
            px = x if side == 0 else x+tw
            return (px//10 + (-3 if side == 0 else 3), py//10), (side,fraction)
        def route(start, end):
            q = [(0,0,start, -1)]
            costs = {(start,-1):0}
            prev = {}
            while q:
                _, g, pos, direction = heappop(q)
                state = (pos,direction)
                if g != costs.get(state):
                    continue
                if pos == end:
                    path = [pos]
                    while state in prev:
                        state = prev[state]
                        path.append(state[0])
                    return g, path[::-1]
                for d,(dx,dy) in enumerate(((1,0),(-1,0),(0,1),(0,-1))):
                    nxt = (pos[0]+dx,pos[1]+dy)
                    if not (3 <= nxt[0] <= w//10-3 and 14 <= nxt[1] <= h//10-9) or nxt in blocked:
                        continue
                    seg = tuple(sorted((pos,nxt)))
                    ng = g+1+(8 if direction not in (-1,d) else 0)+(30 if seg in segments else 0)+(9 if nxt in used else 0)
                    ns = (nxt,d)
                    if ng >= costs.get(ns,float("inf")):
                        continue
                    costs[ns] = ng
                    prev[ns] = state
                    heuristic = abs(nxt[0]-end[0])+abs(nxt[1]-end[1])
                    heappush(q,(ng+heuristic,ng,nxt,d))
            return float("inf"), []
        for source,target,pk,fk,mandatory,label in references:
            opts = []
            for a in (0,1):
                for b in (0,1):
                    start, exit_at = port(source,pk,a)
                    end, entry_at = port(target,fk,b)
                    cost,path = route(start,end)
                    opts.append((cost,path,exit_at,entry_at))
            cost,path,exit_at,entry_at = min(opts,key=lambda o:o[0])
            assert path, (source,target,fk)
            used.update(path)
            segments.update(tuple(sorted((a,b))) for a,b in zip(path,path[1:]))
            bends = [path[0]] + [p for a,p,b in zip(path,path[1:],path[2:])
                           if (p[0]-a[0],p[1]-a[1]) != (b[0]-p[0],b[1]-p[1])] + [path[-1]]
            end_mark = marks["optional" if (target,fk)==("lab_decisions","test_id") else "many"]
            start_mark = marks["one" if mandatory else "optional"]
            sheet.edge(vertices[source],vertices[target],value=label if " + " in label else "",
                       exit_at=exit_at,entry_at=entry_at,points=[(x*10,y*10) for x,y in bends],
                       style=f"edgeStyle=segmentEdgeStyle;rounded=0;jettySize=auto;jumpStyle=arc;jumpSize=8;startArrow={start_mark};endArrow={end_mark};startSize=11;endSize=11;strokeWidth=1.5;fontSize=11;")
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

