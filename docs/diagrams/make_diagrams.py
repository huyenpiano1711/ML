"""
make_diagrams.py - Sơ đồ phân tích thiết kế hệ thống cho báo cáo (mục 3.9).

Mỗi sơ đồ được viết bằng Graphviz DOT, xuất ra:
    <tên>.dot     mã nguồn (sửa được, chạy lại script để vẽ lại)
    <tên>.png     ảnh chèn vào báo cáo
    <tên>.drawio  bản mở được bằng draw.io / diagrams.net để chỉnh tay (vị trí lấy từ bố cục của Graphviz)

Chạy:  python docs/diagrams/make_diagrams.py       (cần Graphviz: lệnh `dot`)
"""
import html
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

OUT = Path(__file__).resolve().parent
FONT = "Inter"
RED, INK, MUTED, LIGHT, PINK = "#D7263D", "#18181B", "#6B6B74", "#F5F5F7", "#FDE8EB"

BASE = f'''  graph [fontname="{FONT}", fontsize=12, bgcolor="white", pad=0.3, nodesep=0.35, ranksep=0.5];
  node  [fontname="{FONT}", fontsize=11, color="{INK}", fontcolor="{INK}"];
  edge  [fontname="{FONT}", fontsize=9, color="{MUTED}", fontcolor="{MUTED}", arrowsize=0.7];
'''


def q(text):
    return '"' + text.replace('"', '\\"') + '"'


# ----------------------------------------------------------------------------------- 1. USE CASE
USER_UC = [("UC01", "Đăng ký tài khoản"), ("UC02", "Đăng nhập"), ("UC03", "Đăng xuất"), ("UC04", "Cập nhật hồ sơ"),
           ("UC05", "Đổi mật khẩu"), ("UC06", "Ước tính giá và\ntìm xe phù hợp"), ("UC07", "Xem chi tiết\nvà lưu xe"),
           ("UC08", "So sánh xe đã lưu"), ("UC09", "Xem / mở lại\nlịch sử phân tích"), ("UC10", "Xuất kết quả PDF")]
ADMIN_UC = [("UC11", "Xem dashboard\nthống kê"), ("UC12", "Quản lý người dùng"), ("UC13", "Huấn luyện và\nđánh giá mô hình"),
            ("UC14", "Quản lý phiên bản\nmô hình"), ("UC15", "Khám phá dữ liệu"), ("UC16", "Phân khúc xe\nK-Means"),
            ("UC17", "Xem nhật ký\nhoạt động")]


def use_case():
    uc = lambda i, t, fill="white": f'    {i} [label={q(i + chr(10) + t)}, shape=ellipse, style=filled, fillcolor="{fill}", width=2.1, height=0.75];\n'
    s = "digraph UseCase {\n  rankdir=LR; nodesep=0.18; ranksep=1.1; splines=true;\n" + BASE
    actor = 'shape=box, style="rounded,filled,bold", fillcolor="%s", color="%s", width=1.3, height=0.9'
    s += f'  User  [label="«actor»\\nNgười dùng", {actor % (PINK, RED)}];\n'
    s += f'  Admin [label="«actor»\\nQuản trị viên", {actor % (INK, INK)}, fontcolor="white"];\n'
    s += f'  ML    [label="«system»\\nMô hình giá\\n+ Hệ gợi ý", shape=box, style="rounded,dashed", width=1.3];\n'
    s += f'  subgraph cluster_sys {{ label=<<B>Hệ thống AutoWise AI</B>>; labeljust=l; style="rounded"; color="{RED}"; penwidth=1.6;\n'
    for title, items, fill in (("Người dùng", USER_UC[5:], "#FFF5F6"), ("Chức năng chung (User và Admin)", USER_UC[:5], "white"),
                               ("Quản trị viên", ADMIN_UC, LIGHT)):
        s += f'   subgraph cluster_{abs(hash(title)) % 999} {{ label="{title}"; style="rounded,dashed"; color="#BDBDC5"; fontcolor="#6B6B74";\n'
        for i, t in items:
            s += uc(i, t, fill)
        s += "   }\n"
    s += "  }\n"
    s += '  edge [arrowhead=none, color="#3F3F46"];\n'
    for i, _ in USER_UC:
        s += f"  User -> {i};\n"
    for i in ("UC02", "UC03", "UC04", "UC05"):
        s += f"  {i} -> Admin;\n"
    for i, _ in ADMIN_UC:
        s += f"  {i} -> Admin;\n"
    s += f'  edge [style=dashed, arrowhead=open, color="{RED}", fontcolor="{RED}", constraint=false];\n'
    s += '  UC06 -> UC02 [label="«include»"];\n  UC07 -> UC06 [label="«extend»"];\n  UC10 -> UC09 [label="«extend»"];\n'
    s += '  UC08 -> UC07 [label="«include»"];\n  UC14 -> UC13 [label="«extend»"];\n'
    s += f'  edge [style=dotted, arrowhead=none, color="{MUTED}", constraint=true];\n  UC06 -> ML; UC13 -> ML; UC16 -> ML;\n'
    s += "}\n"
    return s


# ----------------------------------------------------------------------------------- 2. BPMN
def lane_graph(name, title, lanes, nodes, edges):
    """lanes: [(id, label)]; nodes: {id: (lane, kind, label)}; kind: start, end, task, gw, data, msg."""
    shape = {"start": 'shape=circle, width=0.35, label="", style=filled, fillcolor="white", penwidth=1.5',
             "end": f'shape=doublecircle, width=0.3, label="", style=filled, fillcolor="{INK}"',
             "task": 'shape=box, style="rounded,filled", fillcolor="white", width=1.7, height=0.6',
             "gw": f'shape=diamond, style=filled, fillcolor="{PINK}", color="{RED}", width=0.55, height=0.55, fixedsize=true, fontsize=14',
             "data": f'shape=cylinder, style=filled, fillcolor="{LIGHT}", width=1.1',
             "doc": f'shape=note, style=filled, fillcolor="{LIGHT}", width=1.1'}
    s = f"digraph {name} {{\n  rankdir=LR; newrank=true; compound=true;\n" + BASE
    s += f'  label=<<B>{html.escape(title)}</B>>; labelloc=t; fontsize=14;\n'
    for lid, label in lanes:
        s += f'  subgraph cluster_{lid} {{ label=<<B>{html.escape(label)}</B>>; labeljust=l; style="filled"; fillcolor="{LIGHT}"; color="#D4D4DA";\n'
        for nid, (lane, kind, lab) in nodes.items():
            if lane == lid:
                extra = "" if kind in ("start", "end") else f", label={q(lab)}"
                s += f"    {nid} [{shape[kind]}{extra}];\n"
        s += "  }\n"
    for e in edges:
        a, b, *lab = e
        style = ", style=dashed" if nodes[a][1] in ("data", "doc") or nodes[b][1] in ("data", "doc") else ""
        s += f"  {a} -> {b}" + (f" [label={q(lab[0])}{style}]" if lab else (f" [{style[2:]}]" if style else "")) + ";\n"
    s += "}\n"
    return s


def bpmn_analysis():
    lanes = [("U", "Người dùng"), ("G", "Giao diện PyQt6"), ("B", "Backend (app_service)"), ("D", "CSDL / Mô hình")]
    n = {"s": ("U", "start", ""), "u1": ("U", "task", "Nhập thông số xe\nvà ngân sách"), "u2": ("U", "task", "Bấm ANALYZE &\nFIND CARS"),
         "g1": ("G", "task", "Kiểm tra dữ liệu nhập\n(bắt buộc, khoảng, dòng xe,\nsố dặm hợp lý)"), "g2": ("G", "gw", "×"),
         "g3": ("G", "task", "Hiện lỗi cụ thể\ntừng ô"), "b1": ("B", "task", "VehicleInput.check()"),
         "b2": ("B", "task", "Dự đoán giá +\nkhoảng giá 80%"), "b3": ("B", "task", "Lọc ngân sách,\nKNN xếp hạng Top 5"),
         "b4": ("B", "task", "Tìm xe cùng mức giá\n+ gắn ảnh"), "d1": ("D", "data", "final_pipeline\n.joblib"),
         "d2": ("D", "data", "recommendation\n_catalog.pkl"), "g4": ("G", "task", "Hiển thị giá, ngân sách,\nTop 5, xe cùng giá"),
         "d3": ("D", "data", "SQLite:\nsearches"), "u3": ("U", "gw", "+"), "u4": ("U", "task", "Xem chi tiết /\nlưu xe / so sánh"),
         "u5": ("U", "task", "Xuất PDF"), "e": ("U", "end", "")}
    e = [("s", "u1"), ("u1", "u2"), ("u2", "g1"), ("g1", "g2"), ("g2", "g3", "không hợp lệ"), ("g3", "u1"),
         ("g2", "b1", "hợp lệ"), ("b1", "b2"), ("d1", "b2"), ("b2", "b3"), ("d2", "b3"), ("b3", "b4"), ("b4", "g4"),
         ("g4", "d3", "lưu lịch sử"), ("g4", "u3"), ("u3", "u4"), ("u3", "u5"), ("u4", "e"), ("u5", "e")]
    return lane_graph("BpmnAnalysis", "BPMN 1 – Ước tính giá và tìm xe phù hợp", lanes, n, e)


def bpmn_login():
    lanes = [("U", "Người dùng / Quản trị viên"), ("G", "Cửa sổ đăng nhập"), ("D", "CSDL SQLite")]
    n = {"s": ("U", "start", ""), "u1": ("U", "task", "Nhập username\nvà mật khẩu"), "g1": ("G", "task", "Tìm tài khoản,\nkiểm tra khóa 5 phút"),
         "g2": ("G", "gw", "×"), "g3": ("G", "task", "So mật khẩu băm\nPBKDF2 + muối"), "g4": ("G", "gw", "×"),
         "g5": ("G", "task", "Tăng số lần sai;\nđủ 3 lần → khóa 5 phút"), "g6": ("G", "gw", "×"),
         "g7": ("G", "task", "Báo lỗi,\nsố lần còn lại"), "g8": ("G", "task", "Thông báo và\nthoát ứng dụng"),
         "g9": ("G", "task", "Đặt lại bộ đếm,\nghi lần đăng nhập"), "g10": ("G", "gw", "×"),
         "g11": ("G", "task", "Mở Admin console"), "g12": ("G", "task", "Mở màn hình\ntư vấn xe"),
         "d1": ("D", "data", "users"), "d2": ("D", "data", "login_history"), "e1": ("U", "end", ""), "e2": ("U", "end", "")}
    e = [("s", "u1"), ("u1", "g1"), ("d1", "g1"), ("g1", "g2"), ("g2", "g7", "đang khóa /\nbị cấm"), ("g2", "g3", "được phép"),
         ("g3", "g4"), ("g4", "g5", "sai"), ("g5", "d1"), ("g5", "g6"), ("g6", "g7", "< 3 lần\ntrong phiên"),
         ("g6", "g8", "3 lần liên tiếp"), ("g7", "u1"), ("g8", "e1"), ("g4", "g9", "đúng"), ("g9", "d2"), ("g9", "g10"),
         ("g10", "g11", "admin"), ("g10", "g12", "user"), ("g11", "e2"), ("g12", "e2")]
    return lane_graph("BpmnLogin", "BPMN 2 – Đăng nhập và phân quyền", lanes, n, e)


def bpmn_model():
    lanes = [("A", "Quản trị viên"), ("S", "Admin console"), ("M", "Kho mô hình / Ứng dụng")]
    n = {"s": ("A", "start", ""), "a1": ("A", "task", "Chọn thuật toán,\ntham số, tỷ lệ che"), "a2": ("A", "task", "TRAIN AND\nVALIDATE"),
         "s1": ("S", "task", "Nạp train/val\n(chia theo nhóm xe)"), "s2": ("S", "task", "Huấn luyện pipeline\ntrên train (luồng nền)"),
         "s3": ("S", "task", "Đánh giá trên validation:\nMAE app / đủ TT, R²,\nđộ phủ khoảng giá"),
         "a3": ("A", "gw", "×"), "a4": ("A", "task", "Ghi chú, SAVE VERSION"), "m1": ("M", "data", "registry/\n<version>.joblib"),
         "a5": ("A", "task", "So sánh các phiên bản,\nUSE THIS VERSION"), "m2": ("M", "task", "Chép thành\nfinal_pipeline.joblib,\ncập nhật metrics.json"),
         "m3": ("M", "task", "Xóa bộ đệm mô hình →\ndự đoán mới dùng ngay"), "m4": ("M", "data", "audit_log"), "e": ("A", "end", "")}
    e = [("s", "a1"), ("a1", "a2"), ("a2", "s1"), ("s1", "s2"), ("s2", "s3"), ("s3", "a3"), ("a3", "a1", "chưa tốt"),
         ("a3", "a4", "tốt hơn"), ("a4", "m1"), ("m1", "a5"), ("a5", "m2"), ("m2", "m3"), ("m2", "m4"), ("m3", "e")]
    return lane_graph("BpmnModel", "BPMN 3 – Huấn luyện lại và triển khai mô hình giá", lanes, n, e)


# ----------------------------------------------------------------------------------- 3. DFD
def dfd0():
    s = "digraph DFD0 {\n  rankdir=LR;\n" + BASE
    s += f'  P0 [label="0\\nHệ thống\\nAutoWise AI", shape=circle, style=filled, fillcolor="{PINK}", color="{RED}", penwidth=2, width=1.9, fixedsize=true];\n'
    s += f'  node [shape=box, style=filled, fillcolor="{LIGHT}", width=1.6];\n  U [label="Người dùng"]; A [label="Quản trị viên"]; K [label="Kaggle Craigslist\\n(dữ liệu gốc)"]; N [label="NHTSA vPIC\\n(giải mã VIN)"]; W [label="Wikimedia Commons\\n(ảnh minh họa)"];\n'
    flows = [("U", "P0", "thông tin tài khoản, thông số xe, ngân sách"), ("P0", "U", "giá ước tính, khoảng giá, Top 5, xe cùng giá, PDF"),
             ("A", "P0", "thao tác quản trị, tham số huấn luyện"), ("P0", "A", "thống kê, danh sách người dùng, kết quả đánh giá, nhật ký"),
             ("K", "P0", "426.880 tin đăng"), ("N", "P0", "thông số theo VIN"), ("W", "P0", "ảnh dòng xe")]
    for a, b, lab in flows:
        s += f"  {a} -> {b} [label={q(lab)}];\n"
    s += "  {rank=same; U; A;}\n  {rank=same; K; N; W;}\n}\n"
    return s


def dfd1():
    s = "digraph DFD1 {\n  rankdir=TB; nodesep=0.5; ranksep=0.6;\n" + BASE
    s += f'  node [shape=box, style="rounded,filled", fillcolor="{PINK}", color="{RED}", width=1.9, height=0.75];\n'
    procs = {"P1": "1.0\nXác thực và\nquản lý tài khoản", "P2": "2.0\nTiền xử lý và\nchia dữ liệu", "P3": "3.0\nHuấn luyện và\nquản lý mô hình",
             "P4": "4.0\nDự đoán giá", "P5": "5.0\nGợi ý xe", "P6": "6.0\nLưu lịch sử, xe yêu thích,\nxuất PDF", "P7": "7.0\nThống kê và\nphân khúc K-Means"}
    for k, v in procs.items():
        s += f"  {k} [label={q(v)}];\n"
    s += f'  node [shape=record, style=filled, fillcolor="white", color="{INK}", height=0.4];\n'
    stores = {"D1": "D1 | users", "D2": "D2 | login_history", "D3": "D3 | vehicles_filled + splits", "D4": "D4 | registry + final_pipeline",
              "D5": "D5 | recommendation_catalog", "D6": "D6 | searches", "D7": "D7 | favorites", "D8": "D8 | audit_log"}
    for k, v in stores.items():
        s += f"  {k} [label={q(v)}];\n"
    s += f'  node [shape=box, style=filled, fillcolor="{LIGHT}", color="{INK}", width=1.4];\n  U [label="Người dùng"]; A [label="Quản trị viên"]; K [label="Nguồn dữ liệu\\n(Kaggle, NHTSA, Wikimedia)"];\n'
    flows = [("U", "P1", "đăng ký/đăng nhập"), ("A", "P1", "đăng nhập, quản lý user"), ("P1", "D1", "tài khoản"), ("P1", "D2", "lần đăng nhập"),
             ("P1", "D8", "thao tác admin"), ("K", "P2", "tin đăng, VIN, ảnh"), ("P2", "D3", "dữ liệu sạch, train/val/test"),
             ("P2", "D5", "danh mục xe + ảnh"), ("D3", "P3", "train/val"), ("A", "P3", "thuật toán, tham số"), ("P3", "D4", "phiên bản, mô hình đang dùng"),
             ("U", "P4", "thông số xe"), ("D4", "P4", "pipeline"), ("P4", "P5", "giá ước tính"), ("U", "P5", "ngân sách, sở thích"),
             ("D5", "P5", "xe ứng viên"), ("P5", "P6", "kết quả phân tích"), ("P6", "D6", "phân tích"), ("P6", "D7", "xe đã lưu"),
             ("P6", "U", "kết quả, PDF"), ("D6", "P7", "lịch sử"), ("D1", "P7", "người dùng"), ("D3", "P7", "tin đăng"), ("P7", "A", "dashboard, phân khúc")]
    for a, b, lab in flows:
        s += f"  {a} -> {b} [label={q(lab)}];\n"
    s += "  {rank=same; U; A; K;}\n}\n"
    return s


# ----------------------------------------------------------------------------------- 4. ERD
def erd():
    tables = {
        "users": ["<b>PK</b> id INTEGER", "username TEXT UNIQUE", "password TEXT (salt$hash)", "full_name TEXT", "email TEXT",
                  "role TEXT (user | admin)", "is_banned INTEGER", "failed_count INTEGER", "locked_until TEXT", "last_login_at TEXT",
                  "created_at, updated_at TEXT"],
        "login_history": ["<b>PK</b> id INTEGER", "<b>FK</b> user_id → users.id", "username TEXT", "success INTEGER", "reason TEXT", "created_at TEXT"],
        "searches": ["<b>PK</b> id INTEGER", "<b>FK</b> user_id → users.id", "manufacturer, model_base TEXT", "year INTEGER", "odometer REAL",
                     "budget_max_usd REAL", "predicted_price, price_low, price_high REAL", "n_matches INTEGER", "success INTEGER",
                     "elapsed_ms REAL", "input_json TEXT", "result_json TEXT", "created_at TEXT"],
        "favorites": ["<b>PK</b> id INTEGER", "<b>FK</b> user_id → users.id", "listing_id INTEGER", "car_json TEXT", "note TEXT", "created_at TEXT",
                      "UNIQUE (user_id, listing_id)"],
        "audit_log": ["<b>PK</b> id INTEGER", "<b>FK</b> admin_id → users.id", "action TEXT", "target TEXT", "detail TEXT", "created_at TEXT"],
    }
    s = "digraph ERD {\n  rankdir=LR; nodesep=0.6;\n" + BASE + "  node [shape=plain];\n"
    for name, cols in tables.items():
        rows = "".join(f'<TR><TD ALIGN="LEFT" BALIGN="LEFT">{c}</TD></TR>' for c in cols)
        s += (f'  {name} [label=<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5" COLOR="{INK}">'
              f'<TR><TD BGCOLOR="{RED}"><FONT COLOR="white"><B>{name}</B></FONT></TD></TR>{rows}</TABLE>>];\n')
    s += f'  edge [arrowhead=crow, arrowtail=tee, dir=both, color="{INK}"];\n'
    for t, lab in (("login_history", "1 – n"), ("searches", "1 – n"), ("favorites", "1 – n"), ("audit_log", "1 – n (admin)")):
        s += f"  users -> {t} [label={q(lab)}];\n"
    s += "}\n"
    return s


# ----------------------------------------------------------------------------------- 5. ARCHITECTURE + SEQUENCE
def architecture():
    s = "digraph Arch {\n  rankdir=TB; nodesep=0.3; ranksep=0.45;\n" + BASE
    s += '  node [shape=box, style="rounded,filled", fillcolor="white", width=1.6];\n'
    layers = [("ui", "Tầng giao diện (desktop_app/UI – .ui → pyuic6 → *Ex.py)", ["Login\nMainWindowEx", "AutoWise\nMainWindowEx", "UserDialogsEx\n(Account, History,\nFavorites, Compare)", "Admin\nMainWindowEx", "CarDetails\nDialogEx"]),
              ("ctl", "Tầng điều khiển và tiện ích (controllers/, utils/)", ["vehicle_controller", "results_controller", "ChartUtil / TableUtil\n/ PdfUtil / UIUtil"]),
              ("dal", "Tầng truy cập dữ liệu (dal/, connectors/, models/)", ["UserDao, AuditDao", "SearchDao, FavoriteDao,\nStatsDao", "Connector\n(SQLite)"]),
              ("be", "Backend (backend/)", ["app_service.analyze()", "prediction_service", "recommendation_service", "alternative_service", "image_service"]),
              ("ml", "Học máy và dữ liệu (src/, scripts/, models/)", ["model_trainer\n(train, validate, registry)", "Recommender (KNN)", "final_pipeline.joblib\nregistry.json", "recommendation_catalog.pkl", "autowise.sqlite"])]
    fills = {"ui": "#FFF5F6", "ctl": "white", "dal": LIGHT, "be": "white", "ml": LIGHT}
    ids = {}
    for lid, label, items in layers:
        s += f'  subgraph cluster_{lid} {{ label=<<B>{html.escape(label)}</B>>; labeljust=l; style="rounded,filled"; fillcolor="{fills[lid]}"; color="#D4D4DA";\n'
        for i, it in enumerate(items):
            nid = f"{lid}{i}"
            ids.setdefault(lid, []).append(nid)
            shape = ", shape=cylinder" if it.endswith((".joblib\nregistry.json", "catalog.pkl", ".sqlite")) else ""
            s += f"    {nid} [label={q(it)}{shape}];\n"
        s += "  }\n"
    s += f'  edge [color="{RED}"];\n'
    pairs = [("ui1", "ctl0"), ("ui1", "ctl1"), ("ctl1", "be0"), ("ui2", "dal1"), ("ui0", "dal0"), ("ui3", "dal0"), ("ui3", "dal1"),
             ("ui3", "ml0"), ("dal0", "dal2"), ("dal1", "dal2"), ("dal2", "ml4"), ("be0", "be1"), ("be0", "be2"), ("be0", "be3"),
             ("be0", "be4"), ("be1", "ml2"), ("be2", "ml1"), ("ml1", "ml3"), ("ml0", "ml2"), ("ui1", "dal1")]
    for a, b in pairs:
        s += f"  {a} -> {b};\n"
    s += "}\n"
    return s


def sequence():
    """Sơ đồ tuần tự đơn giản bằng bảng HTML (Graphviz không có sơ đồ tuần tự gốc)."""
    actors = ["Người dùng", "AutoWiseMainWindowEx", "VehicleController", "app_service", "prediction_service", "recommendation_service", "SearchDao"]
    steps = [(0, 1, "nhập form, bấm ANALYZE"), (1, 2, "validatedInput()"), (2, 2, "kiểm tra ô, ràng buộc dòng xe, số dặm"),
             (2, 1, "VehicleInput"), (1, 3, "analyze(form)"), (3, 3, "VehicleInput.check()"), (3, 4, "predict_vehicle_price()"),
             (4, 3, "PriceResult (giá, khoảng 80%)"), (3, 5, "recommend(budget, sở thích)"), (5, 3, "Top 5 + điểm match"),
             (3, 3, "xe cùng mức giá, ảnh, cảnh báo"), (3, 1, "AnalysisResult"), (1, 6, "save(user_id, vehicle, result)"),
             (6, 1, "search_id"), (1, 0, "hiển thị Màn hình kết quả")]
    head = "".join(f'<TD BGCOLOR="{RED if i == 0 else INK}"><FONT COLOR="white"><B>{html.escape(a)}</B></FONT></TD>' for i, a in enumerate(actors))
    rows = ""
    for n, (a, b, msg) in enumerate(steps, 1):
        cells = []
        lo, hi = min(a, b), max(a, b)
        for i in range(len(actors)):
            if a == b and i == a:
                cells.append(f'<TD BGCOLOR="{PINK}">{n}. ↻ {html.escape(msg)}</TD>')
            elif lo <= i <= hi and a != b:
                arrow = "→" if b > a else "←"
                text = f"{n}. {html.escape(msg)} {arrow}" if i == (lo if b > a else hi) else ("─" * 6)
                cells.append(f'<TD BGCOLOR="{"#FFF5F6" if i in (a, b) else "white"}">{text}</TD>')
            else:
                cells.append('<TD><FONT COLOR="#D4D4DA">┊</FONT></TD>')
        rows += "<TR>" + "".join(cells) + "</TR>"
    s = "digraph Seq {\n" + BASE + "  node [shape=plain];\n"
    s += f'  t [label=<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="6" COLOR="#E4E4E9"><TR>{head}</TR>{rows}</TABLE>>];\n}}\n'
    return s


# ----------------------------------------------------------------------------------- draw.io export
def to_drawio(dot_text, path):
    """Bản draw.io: vị trí, kích thước và nhãn lấy từ bố cục Graphviz (dot -Tjson)."""
    layout = json.loads(subprocess.run(["dot", "-Tjson"], input=dot_text, capture_output=True, text=True, check=True).stdout)
    H = float(layout["bb"].split(",")[3])
    cells, gid = [], {}
    k = 2
    for obj in layout.get("objects", []):
        if "nodes" in obj or "subgraphs" in obj:            # cluster
            if "bb" in obj and str(obj.get("name", "")).startswith("cluster"):
                x0, y0, x1, y1 = map(float, obj["bb"].split(","))
                lab = html.unescape(str(obj.get("label", "")).replace("<B>", "").replace("</B>", ""))
                cells.append(f'<mxCell id="c{k}" value="{html.escape(lab)}" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F5F5F7;'
                             f'strokeColor=#D4D4DA;verticalAlign=top;align=left;spacingLeft=6;fontStyle=1;" vertex="1" parent="1">'
                             f'<mxGeometry x="{x0:.0f}" y="{H - y1:.0f}" width="{x1 - x0:.0f}" height="{y1 - y0:.0f}" as="geometry"/></mxCell>')
                k += 1
            continue
        if "pos" not in obj:
            continue
        x, y = map(float, obj["pos"].split(","))
        w, h = float(obj.get("width", 1)) * 72, float(obj.get("height", 0.5)) * 72
        shape = obj.get("shape", "box")
        style = {"ellipse": "ellipse;", "circle": "ellipse;", "doublecircle": "ellipse;fillColor=#18181B;", "diamond": "rhombus;fillColor=#FDE8EB;strokeColor=#D7263D;",
                 "cylinder": "shape=cylinder3;", "note": "shape=note;", "record": "", "plain": "text;", "plaintext": "text;"}.get(shape, "rounded=1;")
        label = obj.get("label", obj["name"])
        if label.startswith("<") or label == "\\N":
            label = obj["name"] if label == "\\N" else "".join(part for part in __import__("re").split(r"<[^>]+>", label))
        label = html.unescape(label).replace("\\n", "\n").replace("\\N", obj["name"])
        gid[obj["_gvid"]] = f"n{k}"
        cells.append(f'<mxCell id="n{k}" value="{html.escape(label).replace(chr(10), "&lt;br&gt;")}" style="{style}whiteSpace=wrap;html=1;fontFamily=Inter;" vertex="1" parent="1">'
                     f'<mxGeometry x="{x - w / 2:.0f}" y="{H - y - h / 2:.0f}" width="{w:.0f}" height="{h:.0f}" as="geometry"/></mxCell>')
        k += 1
    for e in layout.get("edges", []):
        if e["tail"] in gid and e["head"] in gid:
            lab = html.escape(html.unescape(e.get("label", "")).replace("\\n", " "))
            dashed = "dashed=1;" if e.get("style") in ("dashed", "dotted") else ""
            cells.append(f'<mxCell id="e{k}" value="{lab}" style="endArrow=open;html=1;{dashed}fontSize=9;" edge="1" parent="1" '
                         f'source="{gid[e["tail"]]}" target="{gid[e["head"]]}"><mxGeometry relative="1" as="geometry"/></mxCell>')
            k += 1
    xml = ('<mxfile host="AutoWise"><diagram name="' + path.stem + '"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
           + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>")
    path.write_text(xml, encoding="utf-8")


DIAGRAMS = {"01_usecase": use_case, "02_bpmn_phan_tich": bpmn_analysis, "03_bpmn_dang_nhap": bpmn_login, "04_bpmn_mo_hinh": bpmn_model,
            "05_dfd_muc0": dfd0, "06_dfd_muc1": dfd1, "07_erd": erd, "08_kien_truc": architecture}

if __name__ == "__main__":
    for name, fn in DIAGRAMS.items():
        text = fn()
        (OUT / f"{name}.dot").write_text(text, encoding="utf-8")
        subprocess.run(["dot", "-Tpng", "-Gdpi=170", "-o", str(OUT / f"{name}.png")], input=text, text=True, check=True)
        to_drawio(text, OUT / f"{name}.drawio")
        print("ok", name)
    import seq_matplotlib                                   # sơ đồ tuần tự vẽ bằng matplotlib
    seq_matplotlib.main(OUT / "09_tuan_tu_phan_tich.png")
    print("ok 09_tuan_tu_phan_tich")
