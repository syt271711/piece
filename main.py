import flet as ft
import sqlite3
import os
import csv
from datetime import datetime

# ========== 配置 ==========
DATA_DIR = os.getenv("FLET_APP_STORAGE_DATA", ".")
DB_PATH = os.path.join(DATA_DIR, "piece_mobile.db")
PRIMARY_COLOR = "#3B82F6"
BG_COLOR = "#F5F6F8"
APP_TITLE = "盛煜通计件系统V6"

# ========== 数据库 ==========
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS employee (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            group_name TEXT NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS product (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            price REAL DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            employee_name TEXT,
            product_name TEXT,
            unit_price REAL,
            qty REAL,
            amount REAL
        )""")
        conn.commit()
    finally:
        conn.close()

def get_employees():
    conn = get_conn()
    rows = conn.execute("SELECT id, name, group_name FROM employee ORDER BY id DESC").fetchall()
    conn.close()
    return rows

def add_employee(name, group):
    conn = get_conn()
    try:
        conn.execute("INSERT OR IGNORE INTO employee(name, group_name) VALUES(?,?)", (name, group))
        conn.commit()
    finally:
        conn.close()

def get_products(keyword=""):
    conn = get_conn()
    rows = conn.execute("SELECT id, name, price FROM product WHERE name LIKE ? ORDER BY id DESC", (f"%{keyword}%",)).fetchall()
    conn.close()
    return rows

def add_product(name, price):
    conn = get_conn()
    try:
        conn.execute("INSERT OR REPLACE INTO product(name, price) VALUES(?,?)", (name, price))
        conn.commit()
    finally:
        conn.close()

def update_product(p_id, name, price):
    conn = get_conn()
    try:
        conn.execute("UPDATE product SET name=?, price=? WHERE id=?", (name, price, p_id))
        conn.commit()
    finally:
        conn.close()

def save_record(date, emp, product, price, qty):
    amount = price * qty
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO record(date, employee_name, product_name, unit_price, qty, amount) VALUES(?,?,?,?,?,?)",
            (date, emp, product, price, qty, amount))
        conn.commit()
    finally:
        conn.close()
    return amount

def get_daily_summary():
    conn = get_conn()
    rows = conn.execute("SELECT date, SUM(amount) FROM record GROUP BY date ORDER BY date DESC").fetchall()
    conn.close()
    return rows

def get_employee_summary(year_month):
    conn = get_conn()
    rows = conn.execute(
        "SELECT employee_name, SUM(qty), SUM(amount) FROM record WHERE date LIKE ? GROUP BY employee_name ORDER BY SUM(amount) DESC",
        (f"{year_month}%",)).fetchall()
    conn.close()
    return rows

def get_employee_details(year_month, emp_name):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, date, product_name, unit_price, qty, amount FROM record WHERE date LIKE ? AND employee_name=? ORDER BY date DESC, id DESC",
        (f"{year_month}%", emp_name)).fetchall()
    conn.close()
    return rows

def update_record(rec_id, qty):
    conn = get_conn()
    try:
        row = conn.execute("SELECT unit_price FROM record WHERE id=?", (rec_id,)).fetchone()
        price = row[0] if row else 0
        conn.execute("UPDATE record SET qty=?, amount=? WHERE id=?", (qty, qty * price, rec_id))
        conn.commit()
    finally:
        conn.close()

def delete_record(rec_id):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM record WHERE id=?", (rec_id,))
        conn.commit()
    finally:
        conn.close()

def import_employees_csv(filepath):
    conn = get_conn()
    count = 0
    try:
        with open(filepath, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2:
                    continue
                name, group = row[0].strip(), row[1].strip()
                if not name or name == "姓名":
                    continue
                conn.execute("INSERT OR IGNORE INTO employee(name, group_name) VALUES(?,?)", (name, group))
                count += 1
        conn.commit()
        return True, f"成功导入 {count} 名员工"
    except Exception as e:
        return False, f"导入失败: {e}"
    finally:
        conn.close()

def import_products_csv(filepath):
    conn = get_conn()
    count = 0
    try:
        with open(filepath, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2:
                    continue
                name, price = row[0].strip(), row[1].strip()
                if not name or name == "产品名称":
                    continue
                try:
                    price = float(price)
                except:
                    price = 0.0
                conn.execute("INSERT OR IGNORE INTO product(name, price) VALUES(?,?)", (name, price))
                count += 1
        conn.commit()
        return True, f"成功导入 {count} 条产品"
    except Exception as e:
        return False, f"导入失败: {e}"
    finally:
        conn.close()

def export_csv_to_dir(filename_prefix, headers, data_generator):
    try:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{stamp}.csv"
        filepath = os.path.join(DATA_DIR, filename)
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(headers)
            count = 0
            for row in data_generator():
                w.writerow(row)
                count += 1
        return True, f"成功导出 {count} 条数据\n路径: {filepath}"
    except Exception as e:
        return False, f"导出失败: {e}"


# ==================== 主程序 ====================
def main(page: ft.Page):
    page.title = APP_TITLE
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = BG_COLOR
    page.padding = 0

    state = {
        "current_date": datetime.now().strftime("%Y-%m-%d"),
        "current_emp": "未登录",
        "current_month": datetime.now().strftime("%Y-%m")
    }

    file_picker_emp = ft.FilePicker()
    file_picker_prod = ft.FilePicker()
    page.overlay.append(file_picker_emp)
    page.overlay.append(file_picker_prod)

    def snack(msg):
        page.snack_bar = ft.SnackBar(ft.Text(msg), duration=3000)
        page.snack_bar.open = True
        page.update()

    # ==================== 登记页（含产品选择、数字键盘） ====================
    product_search = ft.TextField(
        hint_text="搜索或选择产品", prefix_icon=ft.icons.SEARCH,
        border_radius=8, bgcolor=ft.colors.WHITE, on_change=lambda e: load_products()
    )
    product_list = ft.ListView(height=160, spacing=2, visible=False)
    qty_text = ft.Text("0", size=60, color=PRIMARY_COLOR, weight=ft.FontWeight.BOLD)
    qty_value = {"val": "0"}
    selected_product = {"name": "", "price": 0.0}

    def load_products(e=None):
        product_list.controls.clear()
        kw = product_search.value.strip()
        for p_id, name, price in get_products(kw):
            def make_click(n, p):
                def click(ev):
                    selected_product["name"] = n
                    selected_product["price"] = p
                    product_search.value = n
                    product_list.visible = False
                    page.update()
                return click
            product_list.controls.append(
                ft.ListTile(title=ft.Text(name), subtitle=ft.Text(f"单价: {price}"),
                            on_click=make_click(name, price), dense=True)
            )
        product_list.visible = True
        page.update()

    def update_qty(val):
        if val == "clear":
            qty_value["val"] = "0"
        elif val == "back":
            qty_value["val"] = qty_value["val"][:-1] or "0"
        elif val == ".":
            if "." not in qty_value["val"]:
                qty_value["val"] += "."
        else:
            if qty_value["val"] == "0" and val != ".":
                qty_value["val"] = val
            else:
                qty_value["val"] += val
        qty_text.value = qty_value["val"]
        page.update()

    def do_save(ev):
        if state["current_emp"] == "未登录":
            snack("请先在【员工】页选择当前员工！")
            tabs.selected_index = 1
            page.update()
            return
        if not selected_product["name"]:
            snack("请先搜索并选择产品！")
            return
        try:
            qty = float(qty_value["val"])
        except:
            qty = 0
        if qty <= 0:
            snack("数量必须大于 0")
            return
        amt = save_record(state["current_date"], state["current_emp"],
                          selected_product["name"], selected_product["price"], qty)
        snack(f"已记录: {qty}件, 共{amt:.2f}元")
        qty_value["val"] = "0"
        qty_text.value = "0"
        page.update()

    def num_btn(txt, val, color=ft.colors.WHITE, bg=ft.colors.GREY_700):
        return ft.Container(
            content=ft.Text(txt, size=20, color=color), bgcolor=bg,
            alignment=ft.alignment.center, expand=True, height=60,
            on_click=lambda _: update_qty(val)
        )

    keyboard = ft.Column([
        ft.Row([num_btn("+", "+"), num_btn("1", "1"), num_btn("2", "2"),
                num_btn("3", "3"), num_btn("×", "back")], spacing=1),
        ft.Row([num_btn("-", "-"), num_btn("4", "4"), num_btn("5", "5"),
                num_btn("6", "6"), num_btn("清除", "clear")], spacing=1),
        ft.Row([num_btn("×", "*"), num_btn("7", "7"), num_btn("8", "8"),
                num_btn("9", "9")], spacing=1),
        ft.Row([
            num_btn("÷", "/"),
            ft.Container(content=ft.Text("0", size=20, color=ft.colors.WHITE),
                         alignment=ft.alignment.center, expand=True, height=60,
                         on_click=lambda _: update_qty("0")),
            num_btn(".", "."),
            ft.Container(content=ft.Text("保存", size=20, color=ft.colors.WHITE),
                         bgcolor=PRIMARY_COLOR, alignment=ft.alignment.center,
                         expand=True, height=120, on_click=do_save)
        ], spacing=1)
    ], spacing=1)

    tab_register = ft.Column([
        ft.Container(
            content=ft.Row([
                ft.Text(f"当前员工: {state['current_emp']}", size=14, color=PRIMARY_COLOR,
                        weight=ft.FontWeight.BOLD, expand=True),
                ft.TextButton("切换员工", on_click=lambda _: (setattr(tabs, "selected_index", 1), page.update())),
            ]),
            padding=10, bgcolor=ft.colors.WHITE
        ),
        ft.Container(
            content=ft.Column([product_search, product_list]),
            bgcolor=ft.colors.WHITE, padding=10
        ),
        ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text("输入数量", size=14, color=ft.colors.GREY),
                    qty_text
                ], expand=True),
                ft.Text("件", size=18, color=ft.colors.GREY)
            ]),
            padding=20, bgcolor=ft.colors.WHITE
        ),
        keyboard
    ], scroll=ft.ScrollMode.AUTO)

    # ==================== 员工页 ====================
    emp_list = ft.ListView(spacing=1, expand=True)

    def load_emp_list():
        emp_list.controls.clear()
        for e_id, name, group in get_employees():
            def make_select(n):
                def click(ev):
                    state["current_emp"] = n
                    snack(f"已切换为当前员工：{n}")
                    page.update()
                return click
            emp_list.controls.append(
                ft.Container(
                    content=ft.ListTile(
                        title=ft.Text(name, size=16, weight=ft.FontWeight.BOLD),
                        subtitle=ft.Text(f"班组: {group}", size=12),
                        trailing=ft.IconButton(ft.icons.CHECK_CIRCLE, icon_color=PRIMARY_COLOR,
                                               tooltip="设为当前员工",
                                               on_click=make_select(name))
                    ),
                    bgcolor=ft.colors.WHITE,
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.GREY_200))
                )
            )
        page.update()

    new_emp_name = ft.TextField(label="姓名", width=250)
    new_emp_group = ft.TextField(label="班组", width=250)

    def do_add_employee(e):
        name = new_emp_name.value.strip()
        group = new_emp_group.value.strip()
        if name and group:
            add_employee(name, group)
            new_emp_name.value = ""
            new_emp_group.value = ""
            dlg_add_emp.open = False
            load_emp_list()
            page.update()

    dlg_add_emp = ft.AlertDialog(
        title=ft.Text("新增员工"),
        content=ft.Column([new_emp_name, new_emp_group], tight=True),
        actions=[
            ft.TextButton("取消", on_click=lambda e: (setattr(dlg_add_emp, "open", False), page.update())),
            ft.TextButton("保存", on_click=do_add_employee)
        ]
    )

    def do_import_emp(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        success, msg = import_employees_csv(e.files[0].path)
        snack(msg)
        if success:
            load_emp_list()

    file_picker_emp.on_result = do_import_emp

    tab_employee = ft.Column([
        ft.Container(
            content=ft.Row([
                ft.TextButton("新增员工", icon=ft.icons.PERSON_ADD,
                              on_click=lambda e: (setattr(dlg_add_emp, "open", True), page.update())),
                ft.TextButton("导入 CSV", icon=ft.icons.UPLOAD_FILE,
                              on_click=lambda _: file_picker_emp.pick_files(allowed_extensions=["csv"]))
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
            bgcolor=ft.colors.WHITE, padding=10
        ),
        emp_list
    ], expand=True)

    # ==================== 产品管理页 ====================
    prod_manage_list = ft.ListView(spacing=1, expand=True)

    def load_manage_products(e=None):
        prod_manage_list.controls.clear()
        for p_id, name, price in get_products():
            prod_manage_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(name, size=16),
                            ft.Text(f"单价: {price}元", size=14, color=PRIMARY_COLOR)
                        ], spacing=5, expand=True),
                        ft.IconButton(ft.icons.EDIT_OUTLINED, icon_color=ft.colors.GREY_400,
                                      on_click=lambda e, i=p_id, n=name, p=price:
                                      open_product_dialog(i, n, p))
                    ]),
                    padding=15, bgcolor=ft.colors.WHITE,
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.GREY_200))
                )
            )
        page.update()

    prod_name_field = ft.TextField(label="产品名称", width=250)
    prod_price_field = ft.TextField(label="单价", width=250, keyboard_type=ft.KeyboardType.NUMBER)
    edit_product_id = {"id": None}

    def open_product_dialog(p_id=None, name="", price=""):
        edit_product_id["id"] = p_id
        prod_name_field.value = name
        prod_price_field.value = str(price) if price != "" else ""
        dlg_product.open = True
        page.update()

    def do_save_product(e):
        name = prod_name_field.value.strip()
        try:
            price = float(prod_price_field.value or 0)
        except:
            price = 0.0
        if not name:
            snack("请填写产品名称")
            return
        if edit_product_id["id"]:
            update_product(edit_product_id["id"], name, price)
        else:
            add_product(name, price)
        dlg_product.open = False
        load_manage_products()
        load_products()
        snack("保存成功")
        page.update()

    dlg_product = ft.AlertDialog(
        title=ft.Text("产品信息"),
        content=ft.Column([prod_name_field, prod_price_field], tight=True),
        actions=[
            ft.TextButton("取消", on_click=lambda e: (setattr(dlg_product, "open", False), page.update())),
            ft.TextButton("保存", on_click=do_save_product)
        ]
    )

    def do_import_prod(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        success, msg = import_products_csv(e.files[0].path)
        snack(msg)
        if success:
            load_manage_products()
            load_products()

    file_picker_prod.on_result = do_import_prod

    tab_product = ft.Column([
        ft.Container(
            content=ft.Row([
                ft.TextButton("新增产品", icon=ft.icons.ADD,
                              on_click=lambda e: open_product_dialog()),
                ft.TextButton("导入 CSV", icon=ft.icons.UPLOAD_FILE,
                              on_click=lambda _: file_picker_prod.pick_files(allowed_extensions=["csv"]))
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
            bgcolor=ft.colors.WHITE, padding=10
        ),
        prod_manage_list
    ], expand=True)

    # ==================== 统计页 ====================
    total_text = ft.Text("0", size=30, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR)
    qty_stat_text = ft.Text("0", size=30, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR)
    summary_list = ft.ListView(spacing=1, expand=True)

    def load_total():
        conn = get_conn()
        total = conn.execute("SELECT SUM(qty), SUM(amount) FROM record WHERE date LIKE ?",
                             (f"{state['current_month']}%",)).fetchone()
        conn.close()
        qty_stat_text.value = str(int(total[0] or 0))
        total_text.value = f"{total[1]:.2f}" if total[1] else "0.00"
        page.update()

    def load_summary():
        summary_list.controls.clear()
        rows = get_employee_summary(state["current_month"])
        if not rows:
            summary_list.controls.append(
                ft.Text("本月暂无记录", color=ft.colors.GREY, text_align=ft.TextAlign.CENTER))
        for emp, qty, amt in rows:
            summary_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(emp, size=16, weight=ft.FontWeight.BOLD),
                            ft.Text(f"计件数: {int(qty)}", size=13, color=ft.colors.GREY)
                        ], spacing=5, expand=True),
                        ft.Text(f"¥{amt:.2f}", size=18, color=PRIMARY_COLOR,
                                weight=ft.FontWeight.BOLD)
                    ]),
                    padding=15, bgcolor=ft.colors.WHITE,
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.GREY_200)),
                    on_click=lambda e, en=emp: open_detail_dialog(en)
                )
            )
        page.update()

    detail_list = ft.ListView(spacing=1, expand=True)

    def open_detail_dialog(emp_name):
        detail_list.controls.clear()
        records = get_employee_details(state["current_month"], emp_name)
        if not records:
            detail_list.controls.append(ft.Text("该员工本月无记录", color=ft.colors.GREY))
        for rec_id, date, p_name, price, qty, amt in records:
            detail_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(p_name, size=15, weight=ft.FontWeight.BOLD),
                            ft.Text(date, size=12, color=ft.colors.GREY)
                        ], spacing=3, expand=True),
                        ft.Text(f"{qty}件", size=14, weight=ft.FontWeight.BOLD),
                        ft.Text(f"¥{amt:.2f}", size=15, color=PRIMARY_COLOR,
                                weight=ft.FontWeight.BOLD, width=70, text_align=ft.TextAlign.RIGHT),
                        ft.IconButton(ft.icons.EDIT, icon_size=18, icon_color=PRIMARY_COLOR,
                                      on_click=lambda e, i=rec_id, q=qty, p=p_name:
                                      open_edit_dialog(i, q, p)),
                        ft.IconButton(ft.icons.DELETE, icon_size=18, icon_color=ft.colors.RED,
                                      on_click=lambda e, i=rec_id: open_delete_dialog(i))
                    ]),
                    padding=12, bgcolor=ft.colors.WHITE,
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.GREY_200))
                )
            )
        dlg_detail.title = ft.Text(f"{emp_name} 的明细")
        dlg_detail.open = True
        page.update()

    dlg_detail = ft.AlertDialog(
        title=ft.Text("明细"),
        content=ft.Container(content=detail_list, width=340, height=400),
        actions=[ft.TextButton("关闭", on_click=lambda e: (setattr(dlg_detail, "open", False), page.update()))]
    )

    edit_qty_field = ft.TextField(label="新数量", width=250, keyboard_type=ft.KeyboardType.NUMBER)
    edit_rec_id = {"id": None}

    def open_edit_dialog(rec_id, current_qty, p_name):
        edit_rec_id["id"] = rec_id
        edit_qty_field.value = str(current_qty)
        dlg_edit.title = ft.Text(f"修改: {p_name}")
        dlg_edit.open = True
        page.update()

    def do_save_edit(e):
        try:
            new_q = float(edit_qty_field.value)
            update_record(edit_rec_id["id"], new_q)
            dlg_edit.open = False
            dlg_detail.open = False
            load_total()
            load_summary()
            snack("修改成功")
            page.update()
        except:
            snack("请输入有效数字")

    dlg_edit = ft.AlertDialog(
        title=ft.Text("修改数量"),
        content=edit_qty_field,
        actions=[
            ft.TextButton("取消", on_click=lambda e: (setattr(dlg_edit, "open", False), page.update())),
            ft.TextButton("保存", on_click=do_save_edit)
        ]
    )

    def open_delete_dialog(rec_id):
        def do_delete(e):
            delete_record(rec_id)
            dlg_delete.open = False
            dlg_detail.open = False
            load_total()
            load_summary()
            snack("已删除")
            page.update()

        dlg_delete.actions = [
            ft.TextButton("取消", on_click=lambda e: (setattr(dlg_delete, "open", False), page.update())),
            ft.TextButton("删除", on_click=do_delete)
        ]
        dlg_delete.open = True
        page.update()

    dlg_delete = ft.AlertDialog(
        title=ft.Text("确认删除"),
        content=ft.Text("删除后不可恢复，确定吗？"),
        actions=[]
    )

    def do_export_records(e):
        def gen():
            conn = get_conn()
            rows = conn.execute(
                "SELECT date, employee_name, product_name, unit_price, qty, amount FROM record WHERE date LIKE ?",
                (f"{state['current_month']}%",)).fetchall()
            conn.close()
            yield from rows
        success, msg = export_csv_to_dir(f"明细_{state['current_month']}",
                                         ["日期", "员工", "产品", "单价", "数量", "金额"], gen)
        snack(msg)

    tab_statistics = ft.Column([
        ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Column([ft.Text("月总收入(元)", size=14, color=PRIMARY_COLOR), total_text],
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Column([ft.Text("计件数", size=14, color=PRIMARY_COLOR), qty_stat_text],
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                ft.Row([
                    ft.TextButton("导出本月明细", icon=ft.icons.FILE_DOWNLOAD, on_click=do_export_records),
                ], alignment=ft.MainAxisAlignment.CENTER)
            ], spacing=15),
            padding=20, bgcolor=ft.colors.WHITE
        ),
        summary_list
    ], expand=True)

    # ==================== 主框架 ====================
    page.appbar = ft.AppBar(
        title=ft.Text(APP_TITLE, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
        bgcolor=PRIMARY_COLOR, center_title=True
    )

    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(text="登记", icon=ft.icons.EDIT_NOTE, content=tab_register),
            ft.Tab(text="员工", icon=ft.icons.PERSON_OUTLINE, content=tab_employee),
            ft.Tab(text="产品", icon=ft.icons.INVENTORY, content=tab_product),
            ft.Tab(text="统计", icon=ft.icons.PIE_CHART, content=tab_statistics),
        ],
        expand=1,
    )

    page.overlay.extend([dlg_add_emp, dlg_product, dlg_detail, dlg_edit, dlg_delete])
    page.add(tabs)

    init_db()
    load_emp_list()
    load_products()
    load_manage_products()
    load_total()
    load_summary()


ft.app(target=main)
