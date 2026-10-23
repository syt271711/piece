import flet as ft
import sqlite3
import os
import csv
from datetime import datetime

# ========== 数据库路径 ==========
DATA_DIR = os.getenv("FLET_APP_STORAGE_DATA", ".")
DB_PATH = os.path.join(DATA_DIR, "piece_mobile.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS employee (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        group_name TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS process (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_model TEXT NOT NULL,
        process_name TEXT NOT NULL,
        price REAL DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        employee_name TEXT,
        group_name TEXT,
        product_model TEXT,
        process_name TEXT,
        unit_price REAL,
        qty REAL,
        amount REAL
    )""")
    conn.commit()
    conn.close()

# ---------- 基础数据操作 ----------
def load_employees():
    conn = get_conn()
    rows = conn.execute("SELECT name, group_name FROM employee ORDER BY group_name, name").fetchall()
    conn.close()
    return rows

def add_employee(name, group):
    conn = get_conn()
    conn.execute("INSERT INTO employee(name, group_name) VALUES(?,?)", (name, group))
    conn.commit()
    conn.close()

def load_all_models():
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT product_model FROM process "
        "UNION SELECT DISTINCT product_model FROM record WHERE product_model IS NOT NULL"
    ).fetchall()
    conn.close()
    return sorted([r[0] for r in rows if r[0]])

def load_processes(model):
    conn = get_conn()
    rows = conn.execute(
        "SELECT process_name, price FROM process WHERE product_model=? ORDER BY process_name",
        (model,)
    ).fetchall()
    conn.close()
    return rows

def add_process(model, pname, price):
    conn = get_conn()
    conn.execute(
        "INSERT INTO process(product_model, process_name, price) VALUES(?,?,?)",
        (model, pname, price)
    )
    conn.commit()
    conn.close()

def add_model(model):
    conn = get_conn()
    conn.execute(
        "INSERT INTO process(product_model, process_name, price) VALUES(?,?,?)",
        (model, "", 0.0)
    )
    conn.commit()
    conn.close()

def save_record(rec):
    conn = get_conn()
    conn.execute(
        """INSERT INTO record
        (date, employee_name, group_name, product_model, process_name, unit_price, qty, amount)
        VALUES (?,?,?,?,?,?,?,?)""",
        rec
    )
    conn.commit()
    conn.close()

def update_record(rec_id, date, model, pname, price, qty):
    conn = get_conn()
    conn.execute(
        """UPDATE record SET date=?, product_model=?, process_name=?, unit_price=?, qty=?, amount=?
           WHERE id=?""",
        (date, model, pname, price, qty, qty * price, rec_id)
    )
    conn.commit()
    conn.close()

def delete_record(rec_id):
    conn = get_conn()
    conn.execute("DELETE FROM record WHERE id=?", (rec_id,))
    conn.commit()
    conn.close()

def get_record(rec_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, date, product_model, process_name, unit_price, qty FROM record WHERE id=?",
        (rec_id,)
    ).fetchone()
    conn.close()
    return row

# ---------- CSV 导入 / 导出 ----------
def import_employees_from_csv(path):
    conn = get_conn()
    count = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2: continue
            name, group = row[0].strip(), row[1].strip()
            if not name or not group or (name == "姓名" and group == "组别"): continue
            conn.execute("INSERT INTO employee(name, group_name) VALUES(?,?)", (name, group))
            count += 1
    conn.commit()
    conn.close()
    return count

def import_processes_from_csv(path):
    conn = get_conn()
    count = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3: continue
            model, pname, price = row[0].strip(), row[1].strip(), row[2].strip()
            if not model or not pname or model == "产品型号": continue
            try: price = float(price)
            except ValueError: price = 0.0
            conn.execute("INSERT INTO process(product_model, process_name, price) VALUES(?,?,?)", (model, pname, price))
            count += 1
    conn.commit()
    conn.close()
    return count

def export_models_csv(path):
    models = load_all_models()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["产品型号"])
        for m in models:
            w.writerow([m])
    return len(models)

def export_processes_csv(path):
    conn = get_conn()
    rows = conn.execute(
        "SELECT product_model, process_name, price FROM process WHERE process_name<>'' ORDER BY product_model, process_name"
    ).fetchall()
    conn.close()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["产品型号", "工序名称", "单价"])
        for r in rows:
            w.writerow(r)
    return len(rows)

def export_all_details_csv(path, year, month):
    conn = get_conn()
    rows = conn.execute(
        """SELECT date, employee_name, group_name, product_model, process_name, unit_price, qty, amount
           FROM record WHERE strftime('%Y', date)=? AND strftime('%m', date)=?
           ORDER BY employee_name, date, id""",
        (year, f"{int(month):02d}")
    ).fetchall()
    conn.close()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["日期", "员工", "班组", "产品型号", "工序", "单价", "数量", "金额"])
        for r in rows:
            w.writerow(r)
    return len(rows)

# ---------- 统计与明细查询 ----------
def stat_by_month(year, month):
    conn = get_conn()
    sql = """SELECT employee_name, group_name, SUM(qty), SUM(amount), COUNT(*)
             FROM record WHERE strftime('%Y', date)=? AND strftime('%m', date)=?
             GROUP BY employee_name, group_name ORDER BY 4 DESC"""
    rows = conn.execute(sql, (year, f"{int(month):02d}")).fetchall()
    conn.close()
    return rows

def get_details(year, month, employee_name):
    conn = get_conn()
    sql = """SELECT id, date, product_model, qty, process_name, unit_price, amount
             FROM record 
             WHERE strftime('%Y', date)=? AND strftime('%m', date)=? AND employee_name=?
             ORDER BY date DESC, id DESC"""
    rows = conn.execute(sql, (year, f"{int(month):02d}", employee_name)).fetchall()
    conn.close()
    return rows


def main(page: ft.Page):
    # ==================== 页面基础设置 ====================
    page.title = "盛煜通计件工资系统"
    page.padding = 0
    page.bgcolor = "#F4F6F8"
    page.theme_mode = ft.ThemeMode.LIGHT

    PRIMARY_COLOR = "#2E7D32"
    page.theme = ft.Theme(
        color_scheme_seed=PRIMARY_COLOR,
        visual_density=ft.VisualDensity.COMFORTABLE
    )

    status_text = ft.Text("", color=ft.colors.GREEN, size=13, weight=ft.FontWeight.BOLD)
    file_picker = ft.FilePicker()
    save_picker = ft.FilePicker()
    page.overlay.append(file_picker)
    page.overlay.append(save_picker)

    # ==================== 向导状态 ====================
    wizard = {
        "step": 0,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "emp_name": "",
        "group": "",
        "model": "",
        "pname": "",
        "price": 0.0,
        "qty": 0.0,
    }

    # ---------- 日期选择器 ----------
    date_picker = ft.DatePicker(
        first_date=datetime(2020, 1, 1),
        last_date=datetime(2035, 12, 31),
        value=datetime.now(),
        on_change=lambda e: on_date_picked(e)
    )
    page.overlay.append(date_picker)

    date_text = ft.Text(wizard["date"], size=15, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR)

    def on_date_picked(e):
        if date_picker.value:
            wizard["date"] = date_picker.value.strftime("%Y-%m-%d")
            date_text.value = wizard["date"]
            page.update()

    def open_date_picker(e):
        date_picker.open = True
        page.update()

    date_row = ft.Row([
        ft.Text("记账日期：", size=14, color=ft.colors.GREY_700),
        ft.Container(
            content=ft.Row([date_text, ft.Icon(ft.icons.CALENDAR_MONTH, size=18, color=PRIMARY_COLOR)]),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            bgcolor=ft.colors.GREEN_50, border_radius=8,
            on_click=open_date_picker,
            ink=True,
        ),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    # ==================== 步骤指示器 ====================
    step_titles = ["① 选员工", "② 选产品", "③ 选工序/数量"]
    step_labels = []
    for i, t in enumerate(step_titles):
        step_labels.append(ft.Text(t, size=13, color=ft.colors.GREY))

    def refresh_step_indicator():
        for i, lbl in enumerate(step_labels):
            if i == wizard["step"]:
                lbl.color = PRIMARY_COLOR
                lbl.weight = ft.FontWeight.BOLD
            elif i < wizard["step"]:
                lbl.color = ft.colors.GREEN_300
                lbl.weight = ft.FontWeight.NORMAL
            else:
                lbl.color = ft.colors.GREY
                lbl.weight = ft.FontWeight.NORMAL
        page.update()

    step_indicator = ft.Container(
        content=ft.Row(step_labels, alignment=ft.MainAxisAlignment.SPACE_AROUND),
        padding=ft.padding.symmetric(vertical=10),
        bgcolor=ft.colors.WHITE, border_radius=8,
        margin=ft.padding.only(left=15, right=15, top=15),
    )

    # ==================== 第1步：选员工 ====================
    emp_field = ft.TextField(label="搜索员工姓名", width=None, border_radius=8, bgcolor=ft.colors.WHITE)
    emp_group_text = ft.Text("", size=13, color=ft.colors.BLUE, weight=ft.FontWeight.BOLD)
    emp_list = ft.ListView(height=220, spacing=5, visible=False)

    def on_emp_search(e):
        kw = emp_field.value.strip()
        emp_list.controls.clear()
        if not kw:
            emp_list.visible = False
            page.update()
            return
        rows = load_employees()
        matches = [r for r in rows if kw.lower() in r[0].lower()]
        if not matches:
            emp_list.controls.append(ft.Text("未找到该员工，可点击右侧「+」新增", color=ft.colors.RED))
        else:
            for name, group in matches:
                def make_click(n, g):
                    def click(ev):
                        wizard["emp_name"] = n
                        wizard["group"] = g
                        emp_field.value = n
                        emp_group_text.value = f"班组: {g}"
                        emp_list.visible = False
                        page.update()
                    return click
                emp_list.controls.append(
                    ft.ListTile(title=ft.Text(name), subtitle=ft.Text(group),
                                on_click=make_click(name, group), dense=True)
                )
        emp_list.visible = True
        page.update()

    emp_field.on_change = on_emp_search

    new_emp_name = ft.TextField(label="姓名", width=300, border_radius=8)
    new_emp_group = ft.TextField(label="班组", width=300, border_radius=8)

    def do_add_employee(e):
        name = new_emp_name.value.strip()
        group = new_emp_group.value.strip()
        if name and group:
            add_employee(name, group)
            new_emp_name.value = ""
            new_emp_group.value = ""
            wizard["emp_name"] = name
            wizard["group"] = group
            emp_field.value = name
            emp_group_text.value = f"班组: {group}"
            emp_list.visible = False
            status_text.value = f"员工 [{name}] 已新增"
            status_text.color = ft.colors.GREEN
            close_bottom_sheet(bs_emp)

    bs_emp = ft.BottomSheet(
        ft.Container(
            content=ft.Column([
                ft.Text("新增员工", size=18, weight=ft.FontWeight.BOLD),
                new_emp_name,
                new_emp_group,
                ft.Row([
                    ft.TextButton("取消", on_click=lambda e: close_bottom_sheet(bs_emp)),
                    ft.ElevatedButton("保存", on_click=do_add_employee),
                ], alignment=ft.MainAxisAlignment.END)
            ], tight=True, scroll=ft.ScrollMode.AUTO),
            padding=ft.padding.only(left=20, right=20, top=20, bottom=40),
        ),
        open=False,
    )

    step_emp_view = ft.Container(
        content=ft.Column([
            ft.Row([emp_field, ft.IconButton(icon=ft.icons.PERSON_ADD, icon_color=PRIMARY_COLOR,
                                             on_click=lambda e: open_bottom_sheet(bs_emp))]),
            emp_group_text,
            emp_list,
            ft.ElevatedButton("下一步 →", icon=ft.icons.ARROW_FORWARD, height=48, width=200,
                              on_click=lambda e: go_step(1)),
        ], spacing=15),
        padding=15,
    )

    # ==================== 第2步：选产品 ====================
    model_field = ft.TextField(label="搜索产品型号", width=None, border_radius=8, bgcolor=ft.colors.WHITE)
    model_list = ft.ListView(height=220, spacing=5, visible=False)

    def on_model_search(e):
        kw = model_field.value.strip()
        model_list.controls.clear()
        if not kw:
            model_list.visible = False
            page.update()
            return
        models = load_all_models()
        matches = [m for m in models if kw.lower() in m.lower()]
        if not matches:
            model_list.controls.append(ft.Text("未找到该型号，可点击右侧「+」新增", color=ft.colors.RED))
        else:
            for m in matches:
                def make_click(model_name):
                    def click(ev):
                        wizard["model"] = model_name
                        model_field.value = model_name
                        model_list.visible = False
                        page.update()
                    return click
                model_list.controls.append(
                    ft.ListTile(title=ft.Text(m), on_click=make_click(m), dense=True)
                )
        model_list.visible = True
        page.update()

    model_field.on_change = on_model_search

    new_m_model = ft.TextField(label="产品型号", width=300, border_radius=8)

    def do_add_model(e):
        model = new_m_model.value.strip()
        if model:
            models = load_all_models()
            if model in models:
                status_text.value = f"型号 [{model}] 已存在"
                status_text.color = ft.colors.ORANGE
            else:
                add_model(model)
                status_text.value = f"型号 [{model}] 已新增"
                status_text.color = ft.colors.GREEN
            new_m_model.value = ""
            wizard["model"] = model
            model_field.value = model
            model_list.visible = False
            close_bottom_sheet(bs_model)

    bs_model = ft.BottomSheet(
        ft.Container(
            content=ft.Column([
                ft.Text("新增产品型号", size=18, weight=ft.FontWeight.BOLD),
                new_m_model,
                ft.Row([
                    ft.TextButton("取消", on_click=lambda e: close_bottom_sheet(bs_model)),
                    ft.ElevatedButton("保存", on_click=do_add_model),
                ], alignment=ft.MainAxisAlignment.END)
            ], tight=True, scroll=ft.ScrollMode.AUTO),
            padding=ft.padding.only(left=20, right=20, top=20, bottom=40),
        ),
        open=False,
    )

    step_model_view = ft.Container(
        content=ft.Column([
            ft.Row([model_field, ft.IconButton(icon=ft.icons.ADD_BOX, icon_color=PRIMARY_COLOR,
                                               on_click=lambda e: open_bottom_sheet(bs_model))]),
            model_list,
            ft.Row([
                ft.OutlinedButton("← 上一步", height=48, on_click=lambda e: go_step(0)),
                ft.ElevatedButton("下一步 →", icon=ft.icons.ARROW_FORWARD, height=48,
                                  on_click=lambda e: go_step(2)),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ], spacing=15),
        padding=15,
        visible=False,
    )

    # ==================== 第3步：工序/数量 ====================
    process_dropdown = ft.Dropdown(label="工序", width=None, hint_text="选择工序", border_radius=8, bgcolor=ft.colors.WHITE)
    price_field = ft.TextField(label="单价 (可修改)", value="0", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8, bgcolor=ft.colors.WHITE)
    qty_field = ft.TextField(label="合格数量", value="0", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8, bgcolor=ft.colors.WHITE)
    amount_text = ft.Text("金额：0.00", size=18, weight=ft.FontWeight.BOLD, color=ft.colors.RED)

    def on_process_change(e):
        model = wizard["model"]
        pname = process_dropdown.value
        if model and pname:
            for name, price in load_processes(model):
                if name == pname:
                    price_field.value = f"{price:.2f}"
                    break
        calc_amount()

    process_dropdown.on_change = on_process_change
    price_field.on_change = lambda e: calc_amount()
    qty_field.on_change = lambda e: calc_amount()

    def calc_amount():
        try: qty = float(qty_field.value or 0)
        except ValueError: qty = 0
        try: price = float(price_field.value or 0)
        except ValueError: price = 0
        amount_text.value = f"金额：{qty * price:.2f}"
        page.update()

    new_p_model = ft.TextField(label="产品型号", width=300, border_radius=8)
    new_p_name = ft.TextField(label="工序名称", width=300, border_radius=8)
    new_p_price = ft.TextField(label="单价", value="0", width=300, keyboard_type=ft.KeyboardType.NUMBER, border_radius=8)

    def do_add_process(e):
        model = new_p_model.value.strip()
        pname = new_p_name.value.strip()
        try: price = float(new_p_price.value or 0)
        except ValueError: price = 0.0
        if model and pname:
            add_process(model, pname, price)
            new_p_model.value = ""
            new_p_name.value = ""
            new_p_price.value = "0"
            if wizard["model"] == model:
                load_process_options()
                process_dropdown.value = pname
                price_field.value = f"{price:.2f}"
                calc_amount()
            status_text.value = f"工序 [{model} / {pname}] 已新增"
            status_text.color = ft.colors.GREEN
            close_bottom_sheet(bs_proc)

    bs_proc = ft.BottomSheet(
        ft.Container(
            content=ft.Column([
                ft.Text("新增工序", size=18, weight=ft.FontWeight.BOLD),
                new_p_model,
                new_p_name,
                new_p_price,
                ft.Row([
                    ft.TextButton("取消", on_click=lambda e: close_bottom_sheet(bs_proc)),
                    ft.ElevatedButton("保存", on_click=do_add_process),
                ], alignment=ft.MainAxisAlignment.END)
            ], tight=True, scroll=ft.ScrollMode.AUTO),
            padding=ft.padding.only(left=20, right=20, top=20, bottom=40),
        ),
        open=False,
    )

    def load_process_options():
        procs = load_processes(wizard["model"])
        process_dropdown.options.clear()
        valid = [(n, p) for n, p in procs if n]
        if not valid:
            status_text.value = f"提示：型号 [{wizard['model']}] 下暂无工序，请点击右侧「+」新增！"
            status_text.color = ft.colors.RED
        else:
            status_text.value = ""
            process_dropdown.options = [ft.dropdown.Option(n) for n, _ in valid]
        process_dropdown.value = None
        price_field.value = "0"
        page.update()

    def open_add_process(e):
        new_p_model.value = wizard["model"] or ""
        open_bottom_sheet(bs_proc)

    step_proc_view = ft.Container(
        content=ft.Column([
            ft.Row([process_dropdown, ft.IconButton(icon=ft.icons.PLAYLIST_ADD, icon_color=PRIMARY_COLOR,
                                                    on_click=open_add_process)]),
            price_field,
            qty_field,
            ft.Row([amount_text], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([
                ft.OutlinedButton("← 上一步", height=48, on_click=lambda e: go_step(1)),
                ft.ElevatedButton("保存登记", icon=ft.icons.CHECK_CIRCLE, height=48,
                                  on_click=lambda e: do_save()),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ], spacing=15),
        padding=15,
        visible=False,
    )

    # ==================== 步骤切换逻辑 ====================
    step_views = [step_emp_view, step_model_view, step_proc_view]

    def go_step(target):
        if target > wizard["step"]:
            if wizard["step"] == 0:
                if not wizard["emp_name"] or not wizard["group"]:
                    status_text.value = "请从搜索列表中选择有效的员工！"
                    status_text.color = ft.colors.RED
                    page.update()
                    return
            if wizard["step"] == 1:
                if not wizard["model"]:
                    status_text.value = "请从搜索列表中选择有效的产品型号！"
                    status_text.color = ft.colors.RED
                    page.update()
                    return
        wizard["step"] = target
        for i, v in enumerate(step_views):
            v.visible = (i == target)
        if target == 2:
            load_process_options()
        refresh_step_indicator()
        status_text.value = ""
        page.update()

    def do_save():
        pname = process_dropdown.value
        if not pname:
            status_text.value = "请选择工序！"
            status_text.color = ft.colors.RED
            page.update()
            return
        try: qty = float(qty_field.value or 0)
        except ValueError: qty = 0
        try: price = float(price_field.value or 0)
        except ValueError: price = 0
        if qty <= 0:
            status_text.value = "数量必须大于 0！"
            status_text.color = ft.colors.RED
            page.update()
            return
        amount = qty * price
        save_record((
            wizard["date"],
            wizard["emp_name"], wizard["group"], wizard["model"], pname, price, qty, amount
        ))
        status_text.value = f"已保存：{wizard['date']} / {wizard['emp_name']} / {pname} / {qty}件 / {amount:.2f}元"
        status_text.color = ft.colors.GREEN
        qty_field.value = "0"
        amount_text.value = "金额：0.00"
        process_dropdown.value = None
        price_field.value = "0"
        page.update()

    # ==================== BottomSheet 通用控制 ====================
    def open_bottom_sheet(sheet):
        emp_list.visible = False
        model_list.visible = False
        try:
            emp_field.focus = False
            model_field.focus = False
            price_field.focus = False
            qty_field.focus = False
        except Exception:
            pass
        page.update()
        page.bottom_sheet = sheet
        page.bottom_sheet.open = True
        page.update()

    def close_bottom_sheet(sheet):
        sheet.open = False
        page.update()

    page.overlay.append(bs_emp)
    page.overlay.append(bs_model)
    page.overlay.append(bs_proc)

    # ==================== 导入 / 导出 ====================
    def pick_and_import(import_func, label):
        def on_result(e: ft.FilePickerResultEvent):
            if not e.files: return
            try:
                n = import_func(e.files[0].path)
                status_text.value = f"{label}导入成功，共 {n} 条"
                status_text.color = ft.colors.GREEN
                page.update()
            except Exception as ex:
                status_text.value = f"导入失败：{ex}"
                status_text.color = ft.colors.RED
                page.update()
        file_picker.on_result = on_result
        file_picker.pick_files(allowed_extensions=["csv"])

    def do_export(export_func, default_name, label):
        def on_result(e: ft.FilePickerResultEvent):
            if not e.path:
                return
            try:
                full_path = os.path.join(e.path, default_name)
                if os.path.exists(full_path):
                    base, ext = os.path.splitext(default_name)
                    full_path = os.path.join(
                        e.path, f"{base}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
                    )
                n = export_func(full_path)
                status_text.value = f"{label}导出成功，共 {n} 条"
                status_text.color = ft.colors.GREEN
                page.update()
                page.snack_bar = ft.SnackBar(ft.Text(f"{label}已导出到: {full_path}"))
                page.snack_bar.open = True
                page.update()
            except Exception as ex:
                status_text.value = f"导出失败：{ex}"
                status_text.color = ft.colors.RED
                page.update()
        save_picker.on_result = on_result
        try:
            save_picker.get_directory_path(dialog_title=f"选择保存目录 - {label}")
        except Exception as ex:
            status_text.value = f"打开保存对话框失败：{ex}"
            status_text.color = ft.colors.RED
            page.update()

    def export_models(e):
        do_export(lambda p: export_models_csv(p), "产品型号.csv", "产品型号")

    def export_processes(e):
        do_export(lambda p: export_processes_csv(p), "工序清单.csv", "工序")

    # ==================== 登记页布局 ====================
    register_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.ElevatedButton("导入员工", icon=ft.icons.UPLOAD,
                                  on_click=lambda _: pick_and_import(import_employees_from_csv, "员工"), height=40),
                ft.ElevatedButton("导入工序", icon=ft.icons.UPLOAD,
                                  on_click=lambda _: pick_and_import(import_processes_from_csv, "工序"), height=40),
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
            ft.Row([
                ft.ElevatedButton("导出型号", icon=ft.icons.DOWNLOAD, on_click=export_models, height=40),
                ft.ElevatedButton("导出工序", icon=ft.icons.DOWNLOAD, on_click=export_processes, height=40),
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
            status_text,
        ], spacing=10),
        bgcolor=ft.colors.WHITE, padding=15, border_radius=12,
        margin=ft.padding.only(left=15, right=15, top=15),
        shadow=ft.BoxShadow(blur_radius=10, color=ft.colors.BLACK12)
    )

    wizard_card = ft.Container(
        content=ft.Column([
            date_row,
            ft.Divider(height=1),
            step_emp_view,
            step_model_view,
            step_proc_view,
        ], spacing=5),
        bgcolor=ft.colors.WHITE, padding=10, border_radius=12,
        margin=ft.padding.only(left=15, right=15, top=15, bottom=15),
        shadow=ft.BoxShadow(blur_radius=10, color=ft.colors.BLACK12)
    )

    tab_register = ft.Column([
        register_card,
        step_indicator,
        wizard_card,
    ], scroll=ft.ScrollMode.AUTO)

    # ==================== 统计页（汇总卡片） ====================
    current_year = str(datetime.now().year)
    current_month = str(datetime.now().month)

    year_dd = ft.Dropdown(label="年份", width=120, value=current_year,
                          options=[ft.dropdown.Option(str(y)) for y in range(2020, 2031)],
                          border_radius=8, bgcolor=ft.colors.WHITE)
    month_dd = ft.Dropdown(label="月份", width=100, value=current_month,
                           options=[ft.dropdown.Option(str(m)) for m in range(1, 13)],
                           border_radius=8, bgcolor=ft.colors.WHITE)

    stat_list = ft.ListView(spacing=10, padding=10, expand=True)
    stat_total = ft.Text("合计：0.00 元 / 0 件", size=16, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR)

    # 明细页控件（提前定义，供汇总卡片跳转使用）
    detail_emp_dd = ft.Dropdown(label="选择员工查看明细", width=300, border_radius=8, bgcolor=ft.colors.WHITE)
    detail_list = ft.ListView(spacing=8, padding=10, expand=True)

    def open_employee_detail(emp_name):
        # 设置明细页员工并切换
        detail_emp_dd.value = emp_name
        load_detail()
        tabs.selected_index = 2
        page.update()

    def refresh_stat(e=None):
        rows = stat_by_month(year_dd.value, month_dd.value)
        stat_list.controls.clear()
        emp_names = [r[0] for r in rows]
        detail_emp_dd.options = [ft.dropdown.Option(n) for n in emp_names]
        detail_emp_dd.value = None
        detail_list.controls.clear()

        total_amt, total_qty = 0.0, 0.0
        if not rows:
            stat_list.controls.append(
                ft.Container(
                    content=ft.Text("本月暂无记录", color=ft.colors.GREY, size=14),
                    alignment=ft.alignment.center, padding=40,
                )
            )
        for name, group, qty, amt, cnt in rows:
            qty, amt = qty or 0, amt or 0
            total_amt += amt
            total_qty += qty
            card = ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(name or "", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(f"{group or ''}  ·  {cnt} 条记录", size=12, color=ft.colors.GREY),
                    ], spacing=4, expand=True),
                    ft.Column([
                        ft.Text(f"¥ {amt:.2f}", size=18, weight=ft.FontWeight.BOLD, color=ft.colors.RED,
                                text_align=ft.TextAlign.RIGHT),
                        ft.Text(f"{qty:.0f} 件", size=12, color=ft.colors.GREY,
                                text_align=ft.TextAlign.RIGHT),
                    ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.END),
                    ft.Icon(ft.icons.CHEVRON_RIGHT, color=ft.colors.GREY_400),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=15, bgcolor=ft.colors.WHITE, border_radius=10,
                shadow=ft.BoxShadow(blur_radius=4, color=ft.colors.BLACK12),
                on_click=lambda e, n=name: open_employee_detail(n),
                ink=True,
            )
            stat_list.controls.append(card)
        stat_total.value = f"合计：{total_amt:.2f} 元 / {total_qty:.0f} 件"
        page.update()

    year_dd.on_change = refresh_stat
    month_dd.on_change = refresh_stat

    def go_to_detail(e):
        refresh_stat()
        tabs.selected_index = 2
        page.update()

    def export_all_details(e):
        do_export(
            lambda p: export_all_details_csv(p, year_dd.value, month_dd.value),
            f"明细_{year_dd.value}_{month_dd.value}.csv",
            "全部明细"
        )

    stat_header = ft.Container(
        content=ft.Column([
            ft.Row([year_dd, month_dd, ft.ElevatedButton("查询", on_click=refresh_stat, height=45)],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            stat_total,
            ft.Row([
                ft.ElevatedButton("导出全部员工明细", icon=ft.icons.DOWNLOAD, height=42,
                                  on_click=export_all_details),
            ], alignment=ft.MainAxisAlignment.CENTER),
        ], spacing=10),
        bgcolor=ft.colors.WHITE, padding=15, border_radius=12, margin=15,
        shadow=ft.BoxShadow(blur_radius=10, color=ft.colors.BLACK12)
    )

    tab_stat = ft.Column([
        stat_header,
        stat_list,
    ], expand=True)

    # ==================== 明细页（左滑编辑/删除） ====================
    # 编辑弹窗
    edit_id_state = {"id": None}
    edit_date = ft.TextField(label="日期 (YYYY-MM-DD)", width=250)
    edit_model = ft.TextField(label="产品型号", width=250)
    edit_pname = ft.TextField(label="工序", width=250)
    edit_price = ft.TextField(label="单价", width=250, keyboard_type=ft.KeyboardType.NUMBER)
    edit_qty = ft.TextField(label="数量", width=250, keyboard_type=ft.KeyboardType.NUMBER)

    def close_dialog(dlg):
        dlg.open = False
        page.update()

    def open_dialog(dlg):
        page.dialog = dlg
        dlg.open = True
        page.update()

    def do_save_edit(e):
        rec_id = edit_id_state["id"]
        try: price = float(edit_price.value or 0)
        except ValueError: price = 0
        try: qty = float(edit_qty.value or 0)
        except ValueError: qty = 0
        date = edit_date.value.strip()
        model = edit_model.value.strip()
        pname = edit_pname.value.strip()
        if not date or not model or not pname:
            page.snack_bar = ft.SnackBar(ft.Text("日期/型号/工序不能为空"))
            page.snack_bar.open = True
            page.update()
            return
        update_record(rec_id, date, model, pname, price, qty)
        dlg_edit.open = False
        load_detail()
        refresh_stat()
        page.snack_bar = ft.SnackBar(ft.Text("修改已保存"))
        page.snack_bar.open = True
        page.update()

    dlg_edit = ft.AlertDialog(
        title=ft.Text("修改明细"),
        content=ft.Column([edit_date, edit_model, edit_pname, edit_price, edit_qty],
                          tight=True, scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("取消", on_click=lambda e: close_dialog(dlg_edit)),
            ft.TextButton("保存", on_click=do_save_edit),
        ]
    )

    def open_edit(rec_id):
        row = get_record(rec_id)
        if not row: return
        rec_id, date, model, pname, price, qty = row
        edit_id_state["id"] = rec_id
        edit_date.value = date or ""
        edit_model.value = model or ""
        edit_pname.value = pname or ""
        edit_price.value = f"{price or 0}"
        edit_qty.value = f"{qty or 0}"
        open_dialog(dlg_edit)

    # 删除确认
    delete_id_state = {"id": None}

    def confirm_delete(rec_id):
        delete_id_state["id"] = rec_id

        def do_delete(e):
            rid = delete_id_state["id"]
            if rid:
                delete_record(rid)
            dlg_del.open = False
            load_detail()
            refresh_stat()
            page.snack_bar = ft.SnackBar(ft.Text("记录已删除"))
            page.snack_bar.open = True
            page.update()

        dlg_del = ft.AlertDialog(
            title=ft.Text("确认删除"),
            content=ft.Text("确定要删除这条记录吗？删除后不可恢复。"),
            actions=[
                ft.TextButton("取消", on_click=lambda e: close_dialog(dlg_del)),
                ft.TextButton("删除", on_click=do_delete,
                              style=ft.ButtonStyle(color=ft.colors.RED)),
            ]
        )
        open_dialog(dlg_del)

    # ---------- 左滑卡片构建 ----------
    ACTION_WIDTH = 140  # 两个按钮总宽

    def make_swipe_row(rec_id, date, model, qty, pname, price, amt):
        # 内容层
        content = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(date, weight=ft.FontWeight.BOLD, size=13, color=ft.colors.GREY_700),
                    ft.Text(f"{model}", size=15, weight=ft.FontWeight.BOLD, expand=True,
                            text_align=ft.TextAlign.RIGHT),
                ]),
                ft.Divider(height=1, thickness=1, color=ft.colors.GREY_200),
                ft.Row([
                    ft.Text(pname, size=13, color=ft.colors.GREY_700),
                    ft.Text(f"×{qty:.0f}  @{price}", size=12, color=ft.colors.GREY,
                            expand=True, text_align=ft.TextAlign.RIGHT),
                ]),
                ft.Row([
                    ft.Text(f"金额 ¥{amt:.2f}", size=16, color=ft.colors.RED,
                            weight=ft.FontWeight.BOLD, expand=True,
                            text_align=ft.TextAlign.RIGHT),
                ]),
            ], spacing=6),
            padding=12, bgcolor=ft.colors.WHITE, border_radius=10,
            shadow=ft.BoxShadow(blur_radius=4, color=ft.colors.BLACK12),
        )

        # 右侧操作按钮层（固定在卡片下方，内容左移后露出）
        actions = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.EDIT, color=ft.colors.WHITE, size=20),
                        ft.Text("编辑", color=ft.colors.WHITE, size=11),
                    ], alignment=ft.MainAxisAlignment.CENTER,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                    width=70, height=70, bgcolor=ft.colors.BLUE,
                    border_radius=10, alignment=ft.alignment.center,
                    on_click=lambda e: open_edit(rec_id),
                    ink=True,
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.DELETE, color=ft.colors.WHITE, size=20),
                        ft.Text("删除", color=ft.colors.WHITE, size=11),
                    ], alignment=ft.MainAxisAlignment.CENTER,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                    width=70, height=70, bgcolor=ft.colors.RED,
                    border_radius=10, alignment=ft.alignment.center,
                    on_click=lambda e: confirm_delete(rec_id),
                    ink=True,
                ),
            ], spacing=0, alignment=ft.MainAxisAlignment.END),
            width=ACTION_WIDTH, height=70,
            alignment=ft.alignment.center_right,
        )

        # 用 Stack 叠放：底层是 actions，上层是 content
        # 通过 content 的 left 偏移实现滑出
        # Flet 没有直接 left 动画，用 container 的 offset 实现
        content_holder = ft.Container(content=content, offset=ft.transform.Offset(0, 0))

        # 拖动状态
        drag_state = {"start_x": 0, "current": 0.0, "opened": False}

        def on_pan_start(e):
            drag_state["start_x"] = drag_state["current"]

        def on_pan_update(e):
            dx = e.local_delta.x if hasattr(e, "local_delta") and e.local_delta else 0
            new_x = drag_state["start_x"] + dx
            # 限制范围 [-ACTION_WIDTH, 0]
            if new_x > 0:
                new_x = 0
            if new_x < -ACTION_WIDTH:
                new_x = -ACTION_WIDTH
            drag_state["current"] = new_x
            content_holder.offset = ft.transform.Offset(new_x / 100.0, 0)
            page.update()

        def on_pan_end(e):
            # 松手后吸附：超过一半就打开，否则回弹
            if drag_state["current"] < -ACTION_WIDTH / 2:
                drag_state["current"] = -ACTION_WIDTH
                drag_state["opened"] = True
            else:
                drag_state["current"] = 0
                drag_state["opened"] = False
            content_holder.offset = ft.transform.Offset(drag_state["current"] / 100.0, 0)
            page.update()

        gesture = ft.GestureDetector(
            content=content_holder,
            on_pan_start=on_pan_start,
            on_pan_update=on_pan_update,
            on_pan_end=on_pan_end,
        )

        row = ft.Stack([
            ft.Container(
                content=actions,
                alignment=ft.alignment.center_right,
                height=70,
            ),
            gesture,
        ])
        return row

    def load_detail(e=None):
        emp = detail_emp_dd.value
        detail_list.controls.clear()
        if not emp:
            detail_list.controls.append(
                ft.Container(
                    content=ft.Text("请先选择员工", color=ft.colors.GREY),
                    alignment=ft.alignment.center, padding=40,
                )
            )
            page.update()
            return
        rows = get_details(year_dd.value, month_dd.value, emp)
        if not rows:
            detail_list.controls.append(
                ft.Container(
                    content=ft.Text("该月无记录", color=ft.colors.GREY),
                    alignment=ft.alignment.center, padding=40,
                )
            )
        else:
            for rec_id, date, model, qty, pname, price, amt in rows:
                detail_list.controls.append(
                    ft.Container(
                        content=make_swipe_row(rec_id, date, model, qty, pname, price, amt),
                        margin=ft.padding.symmetric(horizontal=5, vertical=4),
                    )
                )
        page.update()

    detail_emp_dd.on_change = load_detail

    def go_back(e):
        tabs.selected_index = 1
        page.update()

    detail_header = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.IconButton(icon=ft.icons.ARROW_BACK, icon_color=PRIMARY_COLOR, on_click=go_back),
                ft.Text("明细查询", size=18, weight=ft.FontWeight.BOLD),
            ]),
            ft.Row([detail_emp_dd]),
            ft.Text("提示：左右滑动记录可显示「编辑 / 删除」按钮", size=11, color=ft.colors.GREY),
        ], spacing=8),
        bgcolor=ft.colors.WHITE, padding=12, border_radius=12,
        margin=ft.padding.only(left=15, right=15, top=15)
    )

    tab_detail = ft.Column([
        detail_header,
        detail_list,
    ], expand=True)

    # ==================== 主框架 ====================
    page.appbar = ft.AppBar(
        title=ft.Text("盛煜通计件工资系统", color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
        bgcolor=PRIMARY_COLOR,
        center_title=True,
        elevation=4
    )

    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(text="登记", icon=ft.icons.EDIT_NOTE, content=tab_register),
            ft.Tab(text="汇总", icon=ft.icons.PIE_CHART, content=tab_stat),
            ft.Tab(text="明细", icon=ft.icons.FORMAT_LIST_BULLETED, content=tab_detail),
        ],
        expand=1,
    )
    page.add(tabs)

    init_db()
    refresh_step_indicator()
    refresh_stat()


ft.app(target=main)
