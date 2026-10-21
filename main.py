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

# ---------- 员工 ----------
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

# ---------- 工序 ----------
def load_models():
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT product_model FROM process ORDER BY product_model").fetchall()
    conn.close()
    return [r[0] for r in rows]

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

# ---------- 记录 ----------
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

# ---------- CSV 导入 ----------
def import_employees_from_csv(path):
    conn = get_conn()
    count = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            name, group = row[0].strip(), row[1].strip()
            if not name or not group:
                continue
            if name == "姓名" and group == "组别":
                continue
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
            if len(row) < 3:
                continue
            model, pname, price = row[0].strip(), row[1].strip(), row[2].strip()
            if not model or not pname:
                continue
            if model == "产品型号":
                continue
            try:
                price = float(price)
            except ValueError:
                price = 0.0
            conn.execute(
                "INSERT INTO process(product_model, process_name, price) VALUES(?,?,?)",
                (model, pname, price)
            )
            count += 1
    conn.commit()
    conn.close()
    return count

# ---------- 统计 ----------
def stat_by_employee(start_date=None, end_date=None):
    conn = get_conn()
    sql = """SELECT employee_name, group_name,
                    SUM(qty), SUM(amount), COUNT(*)
             FROM record WHERE 1=1"""
    params = []
    if start_date:
        sql += " AND date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND date <= ?"
        params.append(end_date)
    sql += " GROUP BY employee_name, group_name ORDER BY 4 DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def main(page: ft.Page):
    page.title = "计件登记"
    page.padding = 12

    status_text = ft.Text("", color=ft.colors.GREEN, size=12)
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    # ==================== 登记页组件 ====================
    emp_dropdown = ft.Dropdown(label="员工", width=300, hint_text="请选择员工")
    model_dropdown = ft.Dropdown(label="产品型号", width=300, hint_text="请选择型号")
    process_dropdown = ft.Dropdown(label="工序", width=300, hint_text="请先选型号")
    price_field = ft.TextField(label="单价（可临时修改）", value="0", width=300,
                               keyboard_type=ft.KeyboardType.NUMBER)
    qty_field = ft.TextField(label="合格数量", value="0", width=300,
                             keyboard_type=ft.KeyboardType.NUMBER)
    amount_text = ft.Text("金额：0.00", size=16, weight=ft.FontWeight.BOLD, color=ft.colors.RED)

    # ==================== 新增员工弹窗 ====================
    new_emp_name = ft.TextField(label="姓名", width=250)
    new_emp_group = ft.TextField(label="班组", width=250)

    def do_add_employee(e):
        name = (new_emp_name.value or "").strip()
        group = (new_emp_group.value or "").strip()
        if not name or not group:
            status_text.value = "姓名和班组不能为空"
            status_text.color = ft.colors.RED
            page.update()
            return
        add_employee(name, group)
        new_emp_name.value = ""
        new_emp_group.value = ""
        dlg_emp.open = False
        status_text.value = f"已新增员工：{name}（{group}）"
        status_text.color = ft.colors.GREEN
        refresh_employees()
        page.update()

    dlg_emp = ft.AlertDialog(
        title=ft.Text("新增员工"),
        content=ft.Column([new_emp_name, new_emp_group], tight=True),
        actions=[
            ft.TextButton("取消", on_click=lambda e: close_dialog(dlg_emp)),
            ft.TextButton("保存", on_click=do_add_employee),
        ],
    )

    # ==================== 新增工序弹窗 ====================
    new_p_model = ft.TextField(label="产品型号", width=250)
    new_p_name = ft.TextField(label="工序名称", width=250)
    new_p_price = ft.TextField(label="单价", value="0", width=250,
                               keyboard_type=ft.KeyboardType.NUMBER)

    def do_add_process(e):
        model = (new_p_model.value or "").strip()
        pname = (new_p_name.value or "").strip()
        if not model or not pname:
            status_text.value = "型号和工序名称不能为空"
            status_text.color = ft.colors.RED
            page.update()
            return
        try:
            price = float(new_p_price.value or 0)
        except ValueError:
            price = 0.0
        add_process(model, pname, price)
        new_p_model.value = ""
        new_p_name.value = ""
        new_p_price.value = "0"
        dlg_proc.open = False
        status_text.value = f"已新增工序：{model} / {pname} / {price:.2f}"
        status_text.color = ft.colors.GREEN
        refresh_models()
        page.update()

    dlg_proc = ft.AlertDialog(
        title=ft.Text("新增工序"),
        content=ft.Column([new_p_model, new_p_name, new_p_price], tight=True),
        actions=[
            ft.TextButton("取消", on_click=lambda e: close_dialog(dlg_proc)),
            ft.TextButton("保存", on_click=do_add_process),
        ],
    )

    def close_dialog(dlg):
        dlg.open = False
        page.update()

    # ==================== 刷新下拉 ====================
    def refresh_employees():
        rows = load_employees()
        emp_dropdown.options = [ft.dropdown.Option(f"{r[0]}|{r[1]}") for r in rows]
        page.update()

    def refresh_models():
        models = load_models()
        model_dropdown.options = [ft.dropdown.Option(m) for m in models]
        page.update()

    def refresh_dropdowns():
        refresh_employees()
        refresh_models()

    # ==================== 事件 ====================
    def on_model_change(e):
        model = model_dropdown.value
        process_dropdown.options.clear()
        process_dropdown.value = None
        price_field.value = "0"
        if model:
            procs = load_processes(model)
            process_dropdown.options = [ft.dropdown.Option(p[0]) for p in procs]
        calc_amount()

    model_dropdown.on_change = on_model_change

    def on_process_change(e):
        model = model_dropdown.value
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
        try:
            qty = float(qty_field.value or 0)
        except ValueError:
            qty = 0
        try:
            price = float(price_field.value or 0)
        except ValueError:
            price = 0
        amount_text.value = f"金额：{qty * price:.2f}"
        page.update()

    # ==================== 保存登记 ====================
    def save(e):
        if not emp_dropdown.value:
            status_text.value = "请选择员工"
            status_text.color = ft.colors.RED
            page.update()
            return
        if not model_dropdown.value or not process_dropdown.value:
            status_text.value = "请选择型号和工序"
            status_text.color = ft.colors.RED
            page.update()
            return
        name, group = emp_dropdown.value.split("|")
        try:
            qty = float(qty_field.value or 0)
        except ValueError:
            qty = 0
        try:
            price = float(price_field.value or 0)
        except ValueError:
            price = 0
        amount = qty * price

        save_record((
            datetime.now().strftime("%Y-%m-%d"),
            name, group,
            model_dropdown.value,
            process_dropdown.value,
            price, qty, amount
        ))
        status_text.value = f"已保存：{name} / {process_dropdown.value} / {qty}件 / {amount:.2f}元"
        status_text.color = ft.colors.GREEN
        qty_field.value = "0"
        amount_text.value = "金额：0.00"
        page.update()

    # ==================== 导入 CSV ====================
    def pick_and_import(import_func, label):
        def on_result(e: ft.FilePickerResultEvent):
            if not e.files:
                return
            try:
                n = import_func(e.files[0].path)
                status_text.value = f"{label}导入成功，共 {n} 条"
                status_text.color = ft.colors.GREEN
                refresh_dropdowns()
            except Exception as ex:
                status_text.value = f"导入失败：{ex}"
                status_text.color = ft.colors.RED
            page.update()
        file_picker.on_result = on_result
        file_picker.pick_files(allowed_extensions=["csv"])

    # ==================== 登记页布局 ====================
    tab_register = ft.Column([
        ft.Row([
            ft.ElevatedButton("导入员工 CSV", icon=ft.icons.UPLOAD_FILE,
                              on_click=lambda _: pick_and_import(import_employees_from_csv, "员工")),
            ft.ElevatedButton("导入工序 CSV", icon=ft.icons.UPLOAD_FILE,
                              on_click=lambda _: pick_and_import(import_processes_from_csv, "工序")),
        ], spacing=8),
        status_text,
        ft.Divider(),
        ft.Row([
            emp_dropdown,
            ft.IconButton(icon=ft.icons.PERSON_ADD, tooltip="手动新增员工",
                          on_click=lambda e: open_dialog(dlg_emp)),
        ]),
        ft.Row([
            model_dropdown,
            ft.IconButton(icon=ft.icons.ADD_BOX, tooltip="手动新增工序",
                          on_click=lambda e: open_dialog(dlg_proc)),
        ]),
        process_dropdown,
        price_field,
        qty_field,
        amount_text,
        ft.ElevatedButton("保存登记", icon=ft.icons.SAVE, on_click=save, height=48),
        ft.Text("提示：CSV 用 Excel 另存为“CSV UTF-8”", size=11, color=ft.colors.GREY),
    ], spacing=12, scroll=ft.ScrollMode.AUTO)

    def open_dialog(dlg):
        page.dialog = dlg
        dlg.open = True
        page.update()

    # ==================== 统计页 ====================
    stat_start = ft.TextField(label="开始日期", hint_text="yyyy-mm-dd", width=160)
    stat_end = ft.TextField(label="结束日期", hint_text="yyyy-mm-dd", width=160)
    stat_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("员工")),
            ft.DataColumn(ft.Text("班组")),
            ft.DataColumn(ft.Text("合格数量"), numeric=True),
            ft.DataColumn(ft.Text("金额"), numeric=True),
            ft.DataColumn(ft.Text("记录数"), numeric=True),
        ],
        rows=[],
    )
    stat_total = ft.Text("合计：0.00 元 / 0 件", weight=ft.FontWeight.BOLD, color=ft.colors.RED)

    def refresh_stat(e=None):
        start = (stat_start.value or "").strip() or None
        end = (stat_end.value or "").strip() or None
        rows = stat_by_employee(start, end)
        stat_table.rows.clear()
        total_amt = 0.0
        total_qty = 0.0
        for name, group, qty, amt, cnt in rows:
            qty = qty or 0
            amt = amt or 0
            total_amt += amt
            total_qty += qty
            stat_table.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(name or "")),
                ft.DataCell(ft.Text(group or "")),
                ft.DataCell(ft.Text(f"{qty:.0f}")),
                ft.DataCell(ft.Text(f"{amt:.2f}")),
                ft.DataCell(ft.Text(str(cnt))),
            ]))
        stat_total.value = f"合计：{total_amt:.2f} 元 / {total_qty:.0f} 件"
        page.update()

    tab_stat = ft.Column([
        ft.Row([stat_start, stat_end,
                ft.ElevatedButton("查询", on_click=refresh_stat)]),
        stat_total,
        ft.Divider(),
        ft.Row([stat_table], scroll=ft.ScrollMode.AUTO),
    ], spacing=12, scroll=ft.ScrollMode.AUTO)

    # ==================== 标签页 ====================
    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(text="登记", content=tab_register),
            ft.Tab(text="统计", content=tab_stat),
        ],
        expand=1,
    )
    page.add(tabs)

    init_db()
    refresh_dropdowns()
    refresh_stat()


ft.app(target=main)