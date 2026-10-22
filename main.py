import flet as ft
import sqlite3
import os
import csv
from datetime import datetime

# ========== 配置与数据库 ==========
DATA_DIR = os.getenv("FLET_APP_STORAGE_DATA", ".")
DB_PATH = os.path.join(DATA_DIR, "piece_mobile.db")
PRIMARY_COLOR = "#3B82F6"  # 截图中的蓝色主题
BG_COLOR = "#F5F6F8"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_conn()
    try:
        c = conn.cursor()
        # 员工表
        c.execute("""CREATE TABLE IF NOT EXISTS employee (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            group_name TEXT NOT NULL
        )""")
        # 产品表 (型号+工序 = 产品名称)
        c.execute("""CREATE TABLE IF NOT EXISTS product (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            price REAL DEFAULT 0
        )""")
        # 记账表
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

# ---------- 数据操作：产品 ----------
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

# ---------- 数据操作：记账流水 ----------
def save_record(date, emp, product, price, qty):
    amount = price * qty
    conn = get_conn()
    try:
        conn.execute("INSERT INTO record(date, employee_name, product_name, unit_price, qty, amount) VALUES(?,?,?,?,?,?)",
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

# ---------- 数据操作：统计与明细 ----------
def get_employee_summary(year_month):
    conn = get_conn()
    rows = conn.execute(
        "SELECT employee_name, SUM(qty), SUM(amount) FROM record WHERE date LIKE ? GROUP BY employee_name ORDER BY SUM(amount) DESC", 
        (f"{year_month}%",)
    ).fetchall()
    conn.close()
    return rows

def get_employee_details(year_month, emp_name):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, date, product_name, unit_price, qty, amount FROM record WHERE date LIKE ? AND employee_name=? ORDER BY date DESC, id DESC", 
        (f"{year_month}%", emp_name)
    ).fetchall()
    conn.close()
    return rows

def update_record(rec_id, qty):
    conn = get_conn()
    try:
        row = conn.execute("SELECT unit_price FROM record WHERE id=?", (rec_id,)).fetchone()
        price = row[0] if row else 0
        conn.execute("UPDATE record SET qty=?, amount=? WHERE id=?", (qty, qty*price, rec_id))
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

# ---------- 导入导出 ----------
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

def import_products_csv(filepath):
    conn = get_conn()
    count = 0
    try:
        with open(filepath, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2: continue
                name, price = row[0].strip(), row[1].strip()
                if not name or name == "产品名称": continue
                try: price = float(price)
                except: price = 0.0
                conn.execute("INSERT OR IGNORE INTO product(name, price) VALUES(?,?)", (name, price))
                count += 1
        conn.commit()
        return True, f"成功导入 {count} 条产品"
    except Exception as e:
        return False, f"导入失败: {e}"
    finally:
        conn.close()


# ==================== 主程序 ====================
def main(page: ft.Page):
    page.title = "计件记账"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = BG_COLOR
    page.padding = 0
    
    state = {
        "current_date": datetime.now().strftime("%Y-%m-%d"),
        "current_emp": "默认员工", 
        "current_month": datetime.now().strftime("%Y-%m")
    }

    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    def snack(msg):
        page.snack_bar = ft.SnackBar(ft.Text(msg), duration=3000)
        page.snack_bar.open = True
        page.update()

    def go_back(e=None):
        if len(page.views) > 1:
            page.views.pop()
            page.update()

    def switch_page(view):
        page.views.append(view)
        page.update()

    # ==================== 页面 1：首页 (图1) ====================
    def view_home():
        daily_list = ft.ListView(spacing=0, expand=True)
        summaries = get_daily_summary()
        
        if not summaries:
            daily_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.EDIT_DOCUMENT, size=80, color=ft.colors.BLUE_200),
                        ft.Text("还没有记录\n点击开始今天的计件吧", text_align=ft.TextAlign.CENTER, color=ft.colors.GREY)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=50, alignment=ft.alignment.center
                )
            )
        else:
            for date_str, total_amt in summaries:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                day = dt.strftime("%d")
                weekday = ["周一","周二","周三","周四","周五","周六","周日"][dt.weekday()]
                
                def make_date_click(d):
                    def click(ev):
                        state["current_date"] = d
                        switch_page(view_select_product())
                    return click

                daily_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Text(day, size=22, weight=ft.FontWeight.BOLD),
                            ft.Text(f"日 {weekday}", size=14, color=ft.colors.GREY),
                            ft.Container(expand=True),
                            ft.Text(f"¥ {total_amt:.2f}" if total_amt else "", size=16, color=ft.colors.BLUE),
                            ft.Icon(ft.icons.CHEVRON_RIGHT, color=ft.colors.GREY_400)
                        ]),
                        padding=15, bgcolor=ft.colors.WHITE, border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.GREY_200)),
                        on_click=make_date_click(date_str)
                    )
                )

        bottom_nav = ft.Container(
            content=ft.Row([
                ft.Column([ft.Icon(ft.icons.INSERT_CHART_OUTLINED, color=ft.colors.GREY), ft.Text("统计", size=12, color=ft.colors.GREY)],
                          alignment=ft.MainAxisAlignment.CENTER, on_click=lambda _: switch_page(view_statistics())),
                ft.Container(
                    content=ft.Icon(ft.icons.ADD, color=ft.colors.WHITE, size=36),
                    bgcolor=PRIMARY_COLOR, width=60, height=60, border_radius=30,
                    alignment=ft.alignment.center, margin=ft.margin.only(top=-20),
                    on_click=lambda _: switch_page(view_select_product())
                ),
                ft.Column([ft.Icon(ft.icons.PERSON_OUTLINE, color=ft.colors.GREY), ft.Text("未登录", size=12, color=ft.colors.GREY)],
                          alignment=ft.MainAxisAlignment.CENTER)
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
            padding=10, bgcolor=ft.colors.WHITE, height=70,
            shadow=ft.BoxShadow(blur_radius=10, color=ft.colors.BLACK12)
        )

        return ft.View(
            route="/",
            controls=[
                ft.AppBar(title=ft.Text("计件工资系统", color=ft.colors.BLACK), bgcolor=ft.colors.WHITE,
                          center_title=False, actions=[ft.Icon(ft.icons.CLOUD_UPLOAD_OUTLINED, color=PRIMARY_COLOR)]),
                daily_list,
                bottom_nav
            ],
            padding=0
        )

    # ==================== 页面 2：选择产品 (图2) ====================
    def view_select_product():
        search_input = ft.TextField(hint_text="搜索", border_radius=20, bgcolor="#F0F0F0", border_width=0, height=45, prefix_icon=ft.icons.SEARCH)
        product_list = ft.ListView(spacing=5, padding=10, expand=True)

        def load_products(e=None):
            product_list.controls.clear()
            rows = get_products(search_input.value)
            for p_id, name, price in rows:
                def make_click(n, p):
                    def click(ev):
                        switch_page(view_input_qty(n, p))
                    return click
                product_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Text(name, size=16, expand=True),
                            ft.Text(f"¥{price}", size=16, color=PRIMARY_COLOR)
                        ]),
                        padding=15, bgcolor=ft.colors.WHITE, border_radius=8,
                        on_click=make_click(name, price)
                    )
                )
            page.update()

        search_input.on_change = load_products
        load_products()

        bottom_bar = ft.Container(
            content=ft.Row([
                ft.TextButton("管理", icon=ft.icons.EDIT, on_click=lambda _: switch_page(view_product_settings())),
                ft.VerticalDivider(width=1),
                ft.TextButton("添加新产品", icon=ft.icons.ADD, on_click=lambda _: switch_page(view_add_product()))
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
            bgcolor=ft.colors.WHITE, height=60
        )

        return ft.View(
            route="/select",
            controls=[
                ft.AppBar(
                    leading=ft.IconButton(ft.icons.CLOSE, on_click=go_back),
                    title=ft.Text("选择产品", color=ft.colors.WHITE),
                    bgcolor=PRIMARY_COLOR, center_title=True,
                    actions=[ft.TextButton("取消", on_click=go_back, style=ft.ButtonStyle(color=ft.colors.WHITE))]
                ),
                ft.Container(content=search_input, padding=10, bgcolor=ft.colors.WHITE),
                ft.Container(content=product_list, expand=True),
                bottom_bar
            ],
            padding=0
        )

    # ==================== 页面 3：产品设置 (图3) ====================
    def view_product_settings():
        product_list = ft.ListView(spacing=1, expand=True)
        search_field = ft.TextField(hint_text="搜索", prefix_icon=ft.icons.SEARCH, border_radius=20, bgcolor="#F0F0F0", border_width=0, height=40)

        def load_list(e=None):
            product_list.controls.clear()
            rows = get_products(search_field.value)
            for p_id, name, price in rows:
                product_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Column([
                                ft.Text(name, size=16),
                                ft.Text(f"单价: {price}元", size=14, color=PRIMARY_COLOR)
                            ], spacing=5, expand=True),
                            ft.IconButton(ft.icons.EDIT_OUTLINED, icon_color=ft.colors.GREY_400, 
                                          on_click=lambda e, i=p_id, n=name, p=price: switch_page(view_add_product(i, n, p)))
                        ]),
                        padding=15, bgcolor=ft.colors.WHITE,
                        border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.GREY_200))
                    )
                )
            page.update()

        search_field.on_change = load_list
        load_list()

        return ft.View(
            route="/settings",
            controls=[
                ft.AppBar(
                    leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=go_back, icon_color=ft.colors.BLACK),
                    title=ft.Text("产品设置", color=ft.colors.BLACK), bgcolor=ft.colors.WHITE, center_title=True,
                    actions=[ft.TextButton("排序")]
                ),
                ft.Container(content=search_field, padding=10, bgcolor=ft.colors.WHITE),
                product_list,
                ft.Container(
                    content=ft.TextButton("添加产品", icon=ft.icons.ADD, on_click=lambda _: switch_page(view_add_product())),
                    bgcolor=ft.colors.WHITE, height=60, alignment=ft.alignment.center
                )
            ],
            padding=0
        )

    # ==================== 页面 4：添加产品 (图4) ====================
    def view_add_product(p_id=None, old_name="", old_price=""):
        name_field = ft.TextField(label="产品名称", value=old_name, hint_text="请输入产品或工序名", border_width=0)
        price_field = ft.TextField(label="单价(元)", value=str(old_price) if old_price else "", hint_text="请输入金额", border_width=0, keyboard_type=ft.KeyboardType.NUMBER)

        def save(ev):
            if not name_field.value or not price_field.value:
                snack("请填写完整信息")
                return
            try:
                price = float(price_field.value)
            except:
                price = 0.0
            
            if p_id:
                update_product(p_id, name_field.value.strip(), price)
            else:
                add_product(name_field.value.strip(), price)
            
            snack("保存成功")
            go_back()

        def do_import(e: ft.FilePickerResultEvent):
            if not e.files: return
            success, msg = import_products_csv(e.files[0].path)
            snack(msg)
            if success:
                go_back()

        file_picker.on_result = do_import

        return ft.View(
            route="/add_product",
            controls=[
                ft.AppBar(
                    leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=go_back, icon_color=ft.colors.BLACK),
                    title=ft.Text("添加产品" if not p_id else "编辑产品", color=ft.colors.BLACK), 
                    bgcolor=ft.colors.WHITE, center_title=True
                ),
                ft.Container(
                    content=ft.Column([
                        name_field,
                        ft.Divider(height=1),
                        price_field,
                    ]),
                    bgcolor=ft.colors.WHITE, padding=15
                ),
                ft.Container(
                    content=ft.Text("上传产品图片 (暂不支持)", color=PRIMARY_COLOR),
                    alignment=ft.alignment.center, padding=20
                ),
                ft.Container(
                    content=ft.ElevatedButton("完成", bgcolor=PRIMARY_COLOR, color=ft.colors.WHITE, width=300, height=50, on_click=save),
                    alignment=ft.alignment.center, margin=20
                ),
                ft.Container(
                    content=ft.TextButton("批量导入产品 (CSV格式: 产品名称,单价)", icon=ft.icons.UPLOAD_FILE, on_click=lambda _: file_picker.pick_files(allowed_extensions=["csv"])),
                    alignment=ft.alignment.center
                )
            ],
            padding=0
        )

    # ==================== 页面 5：输入数量 (图5) ====================
    def view_input_qty(product_name, price):
        qty_text = ft.Text("0", size=60, color=PRIMARY_COLOR, weight=ft.FontWeight.BOLD)
        qty_value = {"val": "0"}

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
            try: qty = float(qty_value["val"])
            except: qty = 0
            if qty <= 0: return
            amt = save_record(state["current_date"], state["current_emp"], product_name, price, qty)
            snack(f"已记录: {qty}件, 共{amt:.2f}元")
            go_back() 

        def num_btn(txt, val, color=ft.colors.WHITE, bg=ft.colors.GREY_700):
            return ft.Container(
                content=ft.Text(txt, size=20, color=color), bgcolor=bg,
                alignment=ft.alignment.center, expand=True, height=60,
                on_click=lambda _: update_qty(val)
            )

        keyboard = ft.Column([
            ft.Row([num_btn("+","+"), num_btn("1","1"), num_btn("2","2"), num_btn("3","3"), num_btn("×","back")], spacing=1),
            ft.Row([num_btn("-","-"), num_btn("4","4"), num_btn("5","5"), num_btn("6","6"), num_btn("清除","clear")], spacing=1),
            ft.Row([num_btn("×","*"), num_btn("7","7"), num_btn("8","8"), num_btn("9","9")], spacing=1),
            ft.Row([
                num_btn("÷","/"), 
                ft.Container(content=ft.Text("0", size=20, color=ft.colors.WHITE), alignment=ft.alignment.center, expand=True, height=60, on_click=lambda _: update_qty("0")),
                num_btn(".","."),
                ft.Container(content=ft.Text("保存", size=20, color=ft.colors.WHITE), bgcolor=PRIMARY_COLOR, alignment=ft.alignment.center, expand=True, height=120, on_click=do_save)
            ], spacing=1)
        ], spacing=1)

        return ft.View(
            route="/input_qty",
            controls=[
                ft.AppBar(
                    leading=ft.IconButton(ft.icons.CLOSE, on_click=go_back, icon_color=ft.colors.WHITE),
                    title=ft.Text(f"{state['current_date']}", color=ft.colors.WHITE), bgcolor=PRIMARY_COLOR, center_title=True,
                    actions=[ft.TextButton("保存", on_click=do_save, style=ft.ButtonStyle(color=ft.colors.WHITE))]
                ),
                ft.Container(
                    content=ft.Row([
                        ft.Text(product_name, size=18, expand=True),
                        qty_text,
                        ft.Text("数量", color=ft.colors.GREY)
                    ]),
                    padding=20, bgcolor=ft.colors.WHITE
                ),
                ft.Container(expand=True),
                ft.Container(
                    content=ft.Row([
                        ft.TextButton("备注", icon=ft.icons.NOTE_ALT_OUTLINED),
                        ft.TextButton("标签", icon=ft.icons.LOCAL_OFFER_OUTLINED),
                        ft.TextButton("照片", icon=ft.icons.IMAGE_OUTLINED),
                    ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                    bgcolor=ft.colors.WHITE, height=50
                ),
                keyboard
            ],
            padding=0
        )

    # ==================== 页面 6：统计与明细 ====================
    def view_statistics():
        total_text = ft.Text("0", size=30, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR)
        qty_text = ft.Text("0", size=30, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR)
        
        summary_list = ft.ListView(spacing=1, expand=True)
        detail_list = ft.ListView(spacing=1, expand=True, visible=False)

        tab_state = {"current": "summary"}
        
        # 顶部搜索框 (方案一)
        emp_search = ft.TextField(
            hint_text="输入员工姓名查找明细...", 
            prefix_icon=ft.icons.SEARCH, 
            border_radius=20, 
            bgcolor="#F0F0F0", 
            border_width=0, 
            height=40,
            on_change=lambda e: load_details()
        )
        search_container = ft.Container(
            content=emp_search, 
            padding=ft.padding.only(left=15, right=15, top=10, bottom=10), 
            bgcolor=ft.colors.WHITE, 
            visible=False
        )

        def load_total():
            conn = get_conn()
            total = conn.execute("SELECT SUM(qty), SUM(amount) FROM record WHERE date LIKE ?", (f"{state['current_month']}%",)).fetchone()
            conn.close()
            qty_text.value = str(int(total[0] or 0))
            total_text.value = f"{total[1]:.2f}" if total[1] else "0.00"
            page.update()

        # 加载汇总页 (方案二：点击跳转)
        def load_summary():
            summary_list.controls.clear()
            rows = get_employee_summary(state["current_month"])
            
            if not rows:
                summary_list.controls.append(ft.Text("本月暂无记录", color=ft.colors.GREY, text_align=ft.TextAlign.CENTER))
            
            for emp, qty, amt in rows:
                summary_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Column([
                                ft.Text(emp, size=16, weight=ft.FontWeight.BOLD),
                                ft.Text(f"计件数: {int(qty)}", size=13, color=ft.colors.GREY)
                            ], spacing=5, expand=True),
                            ft.Column([
                                ft.Text(f"¥{amt:.2f}", size=18, color=PRIMARY_COLOR, weight=ft.FontWeight.BOLD),
                                ft.Icon(ft.icons.CHEVRON_RIGHT, size=16, color=ft.colors.GREY_300)
                            ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=0)
                        ]),
                        padding=15, bgcolor=ft.colors.WHITE, 
                        border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.GREY_200)),
                        on_click=lambda e, en=emp: select_emp_for_detail(en)
                    )
                )
            page.update()

        def select_emp_for_detail(emp_name):
            switch_tab("detail")
            emp_search.value = emp_name
            load_details()

        # 加载明细页 (带搜索和左滑)
        def load_details():
            detail_list.controls.clear()
            kw = emp_search.value.strip()
            
            if not kw:
                detail_list.controls.append(ft.Text("请输入员工姓名搜索", color=ft.colors.GREY, text_align=ft.TextAlign.CENTER))
                page.update()
                return

            conn = get_conn()
            emps = conn.execute("SELECT DISTINCT employee_name FROM record WHERE date LIKE ? AND employee_name LIKE ?", (f"{state['current_month']}%", f"%{kw}%")).fetchall()
            conn.close()
            emp_names = [r[0] for r in emps]

            if not emp_names:
                detail_list.controls.append(ft.Text("未找到匹配员工", color=ft.colors.GREY, text_align=ft.TextAlign.CENTER))
                page.update()
                return

            # 模糊匹配到多人
            if len(emp_names) > 1 or emp_names[0] != kw:
                detail_list.controls.append(ft.Text("请选择员工：", size=14, color=ft.colors.GREY, margin=ft.margin.only(left=15, bottom=5)))
                for name in emp_names:
                    detail_list.controls.append(
                        ft.Container(
                            content=ft.ListTile(
                                title=ft.Text(name),
                                trailing=ft.Icon(ft.icons.CHEVRON_RIGHT, size=16),
                                on_click=lambda e, n=name: (setattr(emp_search, "value", n), load_details())
                            ),
                            bgcolor=ft.colors.WHITE, border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.GREY_200))
                        )
                    )
                page.update()
                return

            # 精确匹配单人
            selected_emp = emp_names[0]
            records = get_employee_details(state["current_month"], selected_emp)
            
            if not records:
                detail_list.controls.append(ft.Text("该员工本月无记录", color=ft.colors.GREY, text_align=ft.TextAlign.CENTER))
            
            for rec_id, date, p_name, price, qty, amt in records:
                actions = ft.Row([
                    ft.Container(content=ft.Text("修改", color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
                        bgcolor=ft.colors.BLUE, width=80, alignment=ft.alignment.center,
                        on_click=lambda e, i=rec_id, q=qty, p=p_name, pr=price: open_edit_dialog(i, q, p, pr)),
                    ft.Container(content=ft.Text("删除", color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
                        bgcolor=ft.colors.RED, width=80, alignment=ft.alignment.center,
                        on_click=lambda e, i=rec_id: open_delete_dialog(i))
                ], spacing=0, width=160)

                content_card = ft.Container(
                    content=ft.Row([
                        ft.Column([ft.Text(p_name, size=16, weight=ft.FontWeight.BOLD), ft.Text(f"{date}", size=12, color=ft.colors.GREY)], spacing=5, expand=True),
                        ft.Column([ft.Text(f"{qty} 件", size=15, weight=ft.FontWeight.BOLD), ft.Text(f"单价: ¥{price}", size=12, color=ft.colors.GREY)], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2),
                        ft.Container(width=10),
                        ft.Text(f"¥{amt:.2f}", size=16, color=PRIMARY_COLOR, weight=ft.FontWeight.BOLD, width=60, text_align=ft.TextAlign.RIGHT)
                    ]),
                    padding=15, bgcolor=ft.colors.WHITE,
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.GREY_300)),
                    animate=ft.animation.Animation(300, ft.AnimationCurve.EASE_OUT),
                )

                def make_swipe(card):
                    def on_pan_update(e: ft.DragUpdateEvent):
                        if e.delta_x < 0:
                            card.left = max(-160, min(0, card.left + e.delta_x))
                            card.update()
                    def on_pan_end(e: ft.DragEndEvent):
                        card.left = -160 if card.left < -80 else 0
                        card.update()
                    return on_pan_update, on_pan_end

                on_update, on_end = make_swipe(content_card)

                detail_list.controls.append(
                    ft.Stack([
                        ft.Container(content=actions, alignment=ft.alignment.center_right, height=70),
                        ft.GestureDetector(content=content_card, on_pan_update=on_update, on_pan_end=on_end, drag_interval=10)
                    ])
                )
            page.update()

        def open_edit_dialog(rec_id, current_qty, p_name, price):
            qty_field = ft.TextField(label="新数量", value=str(current_qty), keyboard_type=ft.KeyboardType.NUMBER)
            def do_save(e):
                try:
                    new_q = float(qty_field.value)
                    update_record(rec_id, new_q)
                    dlg.open = False
                    load_details()
                    load_summary()
                    load_total()
                    snack("修改成功")
                except:
                    snack("请输入有效数字")
            
            dlg = ft.AlertDialog(
                title=ft.Text(f"修改: {p_name}"), content=qty_field,
                actions=[ft.TextButton("取消", on_click=lambda _: setattr(dlg, "open", False) or page.update()), ft.TextButton("保存", on_click=do_save)]
            )
            page.dialog = dlg
            dlg.open = True
            page.update()

        def open_delete_dialog(rec_id):
            def do_delete(e):
                delete_record(rec_id)
                dlg.open = False
                load_details()
                load_summary()
                load_total()
                snack("已删除")
            dlg = ft.AlertDialog(
                title=ft.Text("确认删除"), content=ft.Text("删除后不可恢复，确定吗？"),
                actions=[ft.TextButton("取消", on_click=lambda _: setattr(dlg, "open", False) or page.update()), ft.TextButton("删除", on_click=do_delete)]
            )
            page.dialog = dlg
            dlg.open = True
            page.update()

        def switch_tab(tab):
            tab_state["current"] = tab
            if tab == "summary":
                btn_summary.bgcolor = PRIMARY_COLOR
                btn_summary.content.color = ft.colors.WHITE
                btn_detail.bgcolor = ft.colors.WHITE
                btn_detail.content.color = ft.colors.GREY
                summary_list.visible = True
                detail_list.visible = False
                search_container.visible = False
            else:
                btn_summary.bgcolor = ft.colors.WHITE
                btn_summary.content.color = ft.colors.GREY
                btn_detail.bgcolor = PRIMARY_COLOR
                btn_detail.content.color = ft.colors.WHITE
                summary_list.visible = False
                detail_list.visible = True
                search_container.visible = True
                load_details()
            page.update()

        btn_summary = ft.Container(content=ft.Text("按员工汇总"), padding=ft.padding.symmetric(horizontal=15, vertical=8), bgcolor=PRIMARY_COLOR, border_radius=15, on_click=lambda _: switch_tab("summary"))
        btn_summary.content.color = ft.colors.WHITE
        btn_detail = ft.Container(content=ft.Text("单人明细"), padding=ft.padding.symmetric(horizontal=15, vertical=8), bgcolor=ft.colors.WHITE, border_radius=15, on_click=lambda _: switch_tab("detail"))
        btn_detail.content.color = ft.colors.GREY

        def do_export_records(e):
            def gen():
                conn = get_conn()
                rows = conn.execute("SELECT date, employee_name, product_name, unit_price, qty, amount FROM record WHERE date LIKE ?", (f"{state['current_month']}%",)).fetchall()
                conn.close()
                yield from rows
            success, msg = export_csv_to_dir(f"明细_{state['current_month']}", ["日期","员工","产品","单价","数量","金额"], gen)
            snack(msg)

        def do_export_products(e):
            def gen():
                conn = get_conn()
                rows = conn.execute("SELECT name, price FROM product").fetchall()
                conn.close()
                yield from rows
            success, msg = export_csv_to_dir("产品库", ["产品名称", "单价"], gen)
            snack(msg)

        bottom_nav = ft.Container(
            content=ft.Row([
                ft.Column([ft.Icon(ft.icons.INSERT_CHART, color=PRIMARY_COLOR), ft.Text("统计", size=12, color=PRIMARY_COLOR)], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(content=ft.Icon(ft.icons.ADD, color=ft.colors.WHITE, size=36), bgcolor=PRIMARY_COLOR, width=60, height=60, border_radius=30, alignment=ft.alignment.center, margin=ft.margin.only(top=-20), on_click=lambda _: switch_page(view_select_product())),
                ft.Column([ft.Icon(ft.icons.PERSON_OUTLINE, color=ft.colors.GREY), ft.Text("未登录", size=12, color=ft.colors.GREY)], alignment=ft.MainAxisAlignment.CENTER, on_click=go_back)
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
            padding=10, bgcolor=ft.colors.WHITE, height=70, shadow=ft.BoxShadow(blur_radius=10, color=ft.colors.BLACK12)
        )

        load_total()
        load_summary()

        return ft.View(
            route="/stats",
            controls=[
                ft.AppBar(
                    leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=go_back, icon_color=ft.colors.BLACK),
                    title=ft.Text(f"{state['current_month']} 统计", color=ft.colors.BLACK), bgcolor=ft.colors.WHITE, center_title=True,
                    actions=[
                        ft.IconButton(ft.icons.FILE_DOWNLOAD, tooltip="导出本月明细", on_click=do_export_records),
                        ft.IconButton(ft.icons.INVENTORY, tooltip="导出产品库", on_click=do_export_products),
                    ]
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Column([ft.Text("月总收入(元)", size=14, color=PRIMARY_COLOR), total_text], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.Column([ft.Text("计件数", size=14, color=PRIMARY_COLOR), qty_text], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                    ], spacing=15),
                    padding=20, bgcolor=ft.colors.WHITE
                ),
                ft.Container(
                    content=ft.Row([btn_summary, btn_detail], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                    padding=10, bgcolor=ft.colors.WHITE, border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.GREY_200))
                ),
                search_container,
                ft.Container(content=summary_list, expand=True),
                ft.Container(content=detail_list, expand=True),
                bottom_nav
            ],
            padding=0
        )

    # ==================== 启动 ====================
    init_db()
    page.views.append(view_home())
    page.update()

ft.app(target=main)
