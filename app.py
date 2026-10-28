"""Personal Expense Manager with AI assistance (Python standard library only)."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import urllib.error
import urllib.request
from datetime import date, datetime
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("EXPENSE_DB", ROOT / "data" / "expense_ai.db"))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
COOKIE = "expense_session"


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180_000)
    return salt.hex() + "$" + digest.hex()


def password_matches(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 180_000).hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
          password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user'
        );
        CREATE TABLE IF NOT EXISTS sessions (
          token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          csrf TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS transactions (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          kind TEXT NOT NULL CHECK(kind IN ('income','expense')), amount REAL NOT NULL CHECK(amount > 0),
          category TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', txn_date TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS budgets (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          month TEXT NOT NULL, category TEXT NOT NULL, amount REAL NOT NULL CHECK(amount > 0),
          UNIQUE(user_id, month, category)
        );
        CREATE TABLE IF NOT EXISTS goals (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          title TEXT NOT NULL, target REAL NOT NULL CHECK(target > 0), saved REAL NOT NULL DEFAULT 0 CHECK(saved >= 0),
          due_date TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS categories (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          name TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('income','expense')),
          UNIQUE(user_id,name,kind)
        );
        """)
        if not db.execute("SELECT id FROM users WHERE username='binh'").fetchone():
            uid = db.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)", ("binh", password_hash("Demo@12345"), "admin")).lastrowid
            today = date.today()
            samples = [
                ("income", 12000000, "Lương", "Lương tháng", today.replace(day=2).isoformat()),
                ("expense", 85000, "Ăn uống", "Ăn trưa", today.replace(day=3).isoformat()),
                ("expense", 45000, "Di chuyển", "Đổ xăng", today.replace(day=5).isoformat()),
                ("expense", 210000, "Học tập", "Sách và tài liệu", today.replace(day=8).isoformat()),
                ("expense", 120000, "Ăn uống", "Ăn tối cùng bạn", today.replace(day=10).isoformat()),
            ]
            db.executemany("INSERT INTO transactions(user_id,kind,amount,category,note,txn_date) VALUES(?,?,?,?,?,?)", [(uid, *r) for r in samples])
            month = today.strftime("%Y-%m")
            db.executemany("INSERT INTO budgets(user_id,month,category,amount) VALUES(?,?,?,?)", [(uid, month, "Ăn uống", 2500000), (uid, month, "Di chuyển", 1000000), (uid, month, "Học tập", 800000)])
            db.execute("INSERT INTO goals(user_id,title,target,saved,due_date) VALUES(?,?,?,?,?)", (uid, "Quỹ dự phòng", 15000000, 4200000, ""))
        for user_row in db.execute("SELECT id FROM users").fetchall():
            uid=user_row["id"]
            db.executemany("INSERT OR IGNORE INTO categories(user_id,name,kind) VALUES(?,?,?)", [(uid,n,k) for k,names in (("expense",("Ăn uống","Di chuyển","Học tập","Nhà ở","Sức khỏe","Mua sắm","Giải trí","Khác")),("income",("Lương","Thưởng","Đầu tư","Làm thêm","Khác"))) for n in names])
            oldcats=db.execute("SELECT DISTINCT category,kind FROM transactions WHERE user_id=?",(uid,)).fetchall()
            db.executemany("INSERT OR IGNORE INTO categories(user_id,name,kind) VALUES(?,?,?)",[(uid,r["category"],r["kind"]) for r in oldcats])


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "ExpenseAI/1.0"

    def send_json(self, data, status=200, extra_headers=None):
        body = json_bytes(data)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:")
        if extra_headers:
            for k, v in extra_headers.items(): self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 100_000)
            return json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return None

    def session(self):
        jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        morsel = jar.get(COOKIE)
        if not morsel: return None
        token = morsel.value
        with connect() as db:
            row = db.execute("SELECT s.csrf,u.id,u.username,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        return dict(row) if row else None

    def require_user(self, mutating=False):
        user = self.session()
        if not user:
            self.send_json({"error": "Vui lòng đăng nhập."}, 401); return None
        if mutating and not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), user["csrf"]):
            self.send_json({"error": "Phiên bảo mật không hợp lệ. Hãy tải lại trang."}, 403); return None
        return user

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/me":
            u = self.session()
            return self.send_json({"user": {k: u[k] for k in ("id", "username", "role")} if u else None, "csrf": u["csrf"] if u else None})
        if path.startswith("/api/"):
            u = self.require_user()
            if not u: return
            if path == "/api/dashboard": return self.dashboard(u)
            if path == "/api/transactions": return self.transactions(u)
            if path == "/api/budgets": return self.budgets(u)
            if path == "/api/goals": return self.goals(u)
            if path == "/api/categories": return self.categories(u)
            if path == "/api/trends": return self.trends(u)
            return self.send_json({"error": "Không tìm thấy chức năng."}, 404)
        return self.static_file(path)

    def do_POST(self): self.route_write("POST")
    def do_PUT(self): self.route_write("PUT")
    def do_DELETE(self): self.route_write("DELETE")

    def route_write(self, method):
        path = urlparse(self.path).path
        data = self.body() if method != "DELETE" else {}
        if data is None:
            return self.send_json({"error": "Dữ liệu gửi lên không đúng định dạng JSON."}, 400)
        if path == "/api/login" and method == "POST": return self.login(data)
        if path == "/api/register" and method == "POST": return self.register(data)
        if path == "/api/logout" and method == "POST": return self.logout()
        u = self.require_user(mutating=True)
        if not u: return
        if path == "/api/transactions" and method == "POST": return self.save_transaction(u, data)
        if path.startswith("/api/transactions/"):
            try: tid = int(path.rsplit("/", 1)[1])
            except ValueError: return self.send_json({"error": "Mã giao dịch không hợp lệ."}, 400)
            if method == "PUT": return self.save_transaction(u, data, tid)
            if method == "DELETE": return self.delete_row("transactions", u, tid)
        if path == "/api/budgets" and method == "POST": return self.save_budget(u, data)
        if path.startswith("/api/budgets/") and method == "DELETE": return self.delete_row("budgets", u, self.safe_id(path))
        if path == "/api/goals" and method == "POST": return self.save_goal(u, data)
        if path.startswith("/api/goals/") and method == "PUT": return self.save_goal(u, data, self.safe_id(path))
        if path.startswith("/api/goals/") and method == "DELETE": return self.delete_row("goals", u, self.safe_id(path))
        if path == "/api/categories" and method == "POST": return self.save_category(u,data)
        if path.startswith("/api/categories/"):
            try: cid=int(path.rsplit("/",1)[1])
            except ValueError: return self.send_json({"error":"Mã danh mục không hợp lệ."},400)
            if method == "PUT": return self.save_category(u,data,cid)
            if method == "DELETE": return self.delete_category(u,cid)
        if path == "/api/ai/summary" and method == "POST": return self.ai_summary(u, data)
        if path == "/api/ai/chat" and method == "POST": return self.ai_chat(u, data)
        return self.send_json({"error": "Không tìm thấy chức năng."}, 404)

    @staticmethod
    def safe_id(path):
        try: return int(path.rsplit("/", 1)[1])
        except ValueError: return -1

    def login(self, d):
        username, password = str(d.get("username", "")).strip(), str(d.get("password", ""))
        with connect() as db:
            row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            if not row or not password_matches(password, row["password"]): return self.send_json({"error": "Tên đăng nhập hoặc mật khẩu chưa đúng."}, 401)
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
            db.execute("INSERT INTO sessions(token_hash,user_id,csrf,created_at) VALUES(?,?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), row["id"], csrf, datetime.utcnow().isoformat()))
        return self.send_json({"ok": True}, extra_headers={"Set-Cookie": f"{COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200"})

    def register(self, d):
        username, password = str(d.get("username", "")).strip(), str(d.get("password", ""))
        if len(username) < 3 or len(username) > 32 or not username.replace("_", "").isalnum(): return self.send_json({"error": "Tên đăng nhập cần 3–32 ký tự chữ, số hoặc dấu gạch dưới."}, 400)
        if len(password) < 8: return self.send_json({"error": "Mật khẩu cần ít nhất 8 ký tự."}, 400)
        with connect() as db:
            try: db.execute("INSERT INTO users(username,password,role) VALUES(?,?, 'user')", (username, password_hash(password)))
            except sqlite3.IntegrityError: return self.send_json({"error": "Tên đăng nhập đã tồn tại."}, 409)
        return self.login({"username": username, "password": password})

    def logout(self):
        jar = cookies.SimpleCookie(self.headers.get("Cookie", "")); morsel = jar.get(COOKIE)
        if morsel:
            with connect() as db: db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(morsel.value.encode()).hexdigest(),))
        return self.send_json({"ok": True}, extra_headers={"Set-Cookie": f"{COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"})

    def dashboard(self, u):
        month = date.today().strftime("%Y-%m")
        with connect() as db:
            rows = db.execute("SELECT kind,COALESCE(SUM(amount),0) amount FROM transactions WHERE user_id=? AND substr(txn_date,1,7)=? GROUP BY kind", (u["id"], month)).fetchall()
            bycat = db.execute("SELECT category,SUM(amount) amount FROM transactions WHERE user_id=? AND kind='expense' AND substr(txn_date,1,7)=? GROUP BY category ORDER BY amount DESC", (u["id"], month)).fetchall()
            recent = db.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY txn_date DESC,id DESC LIMIT 6", (u["id"],)).fetchall()
            budget = db.execute("SELECT b.category,b.amount limit_amount,COALESCE(SUM(t.amount),0) spent FROM budgets b LEFT JOIN transactions t ON t.user_id=b.user_id AND t.category=b.category AND t.kind='expense' AND substr(t.txn_date,1,7)=b.month WHERE b.user_id=? AND b.month=? GROUP BY b.id", (u["id"], month)).fetchall()
        sums = {r["kind"]: r["amount"] for r in rows}
        return self.send_json({"month": month, "income": sums.get("income", 0), "expense": sums.get("expense", 0), "balance": sums.get("income", 0)-sums.get("expense", 0), "by_category": [dict(r) for r in bycat], "recent": [dict(r) for r in recent], "budgets": [dict(r) for r in budget]})

    def trends(self,u):
        q=parse_qs(urlparse(self.path).query)
        try: year=int(q.get("year",[str(date.today().year)])[0]); assert 2000<=year<=2100
        except (ValueError,AssertionError): return self.send_json({"error":"Năm cần nằm trong khoảng 2000–2100."},400)
        with connect() as db: rows=db.execute("SELECT substr(txn_date,6,2) month,kind,SUM(amount) amount FROM transactions WHERE user_id=? AND substr(txn_date,1,4)=? GROUP BY month,kind",(u["id"],str(year))).fetchall()
        values={str(m).zfill(2):{"income":0,"expense":0} for m in range(1,13)}
        for r in rows: values[r["month"]][r["kind"]]=r["amount"] or 0
        return self.send_json({"year":year,"months":[{"month":f"{year}-{m}",**values[m]} for m in values]})

    def categories(self,u):
        with connect() as db: rows=db.execute("SELECT * FROM categories WHERE user_id=? ORDER BY kind,name",(u["id"],)).fetchall()
        return self.send_json({"items":[dict(r) for r in rows]})

    def save_category(self,u,d,cid=None):
        name=str(d.get("name","")).strip()[:50];kind=str(d.get("kind",""))
        if not name or kind not in ("income","expense"): return self.send_json({"error":"Nhập tên danh mục và chọn loại thu/chi."},400)
        with connect() as db:
            try:
                if cid:
                    old=db.execute("SELECT name,kind FROM categories WHERE id=? AND user_id=?",(cid,u["id"])).fetchone()
                    if not old: return self.send_json({"error":"Không tìm thấy danh mục."},404)
                    if old["kind"]!=kind: return self.send_json({"error":"Không đổi loại thu/chi của danh mục đã tạo."},400)
                    db.execute("UPDATE categories SET name=? WHERE id=? AND user_id=?",(name,cid,u["id"]))
                    db.execute("UPDATE transactions SET category=? WHERE user_id=? AND kind=? AND category=?",(name,u["id"],kind,old["name"]))
                    if kind=="expense": db.execute("UPDATE budgets SET category=? WHERE user_id=? AND category=?",(name,u["id"],old["name"]))
                else: db.execute("INSERT INTO categories(user_id,name,kind) VALUES(?,?,?)",(u["id"],name,kind))
            except sqlite3.IntegrityError: return self.send_json({"error":"Danh mục này đã tồn tại."},409)
        return self.send_json({"ok":True})

    def delete_category(self,u,cid):
        with connect() as db:
            row=db.execute("SELECT name,kind FROM categories WHERE id=? AND user_id=?",(cid,u["id"])).fetchone()
            if not row: return self.send_json({"error":"Không tìm thấy danh mục."},404)
            used=db.execute("SELECT 1 FROM transactions WHERE user_id=? AND kind=? AND category=? LIMIT 1",(u["id"],row["kind"],row["name"])).fetchone()
            used_budget=db.execute("SELECT 1 FROM budgets WHERE user_id=? AND category=? LIMIT 1",(u["id"],row["name"])).fetchone() if row["kind"]=="expense" else None
            if used or used_budget: return self.send_json({"error":"Danh mục đang được giao dịch hoặc ngân sách sử dụng. Hãy sửa hoặc xóa dữ liệu liên quan trước."},409)
            db.execute("DELETE FROM categories WHERE id=? AND user_id=?",(cid,u["id"]))
        return self.send_json({"ok":True})

    def transactions(self, u):
        q = parse_qs(urlparse(self.path).query); month = q.get("month", [""])[0]; kind = q.get("kind", [""])[0]; needle = q.get("q", [""])[0][:80]
        sql = "SELECT * FROM transactions WHERE user_id=?"; args = [u["id"]]
        if month: sql += " AND substr(txn_date,1,7)=?"; args.append(month)
        if kind in ("income", "expense"): sql += " AND kind=?"; args.append(kind)
        if needle: sql += " AND (category LIKE ? OR note LIKE ?)"; args.extend([f"%{needle}%", f"%{needle}%"])
        sql += " ORDER BY txn_date DESC,id DESC"
        with connect() as db: rows = db.execute(sql, args).fetchall()
        return self.send_json({"items": [dict(r) for r in rows]})

    def save_transaction(self, u, d, tid=None):
        try:
            kind = str(d.get("kind", "")); amount = round(float(d.get("amount", 0)), 2)
            category = str(d.get("category", "")).strip()[:50]; note = str(d.get("note", "")).strip()[:200]
            txn_date = date.fromisoformat(str(d.get("txn_date", ""))).isoformat()
            if kind not in ("income", "expense") or amount <= 0 or amount > 1_000_000_000_000 or not category: raise ValueError()
        except (ValueError, TypeError): return self.send_json({"error": "Vui lòng kiểm tra loại, số tiền, danh mục và ngày giao dịch."}, 400)
        with connect() as db:
            if tid:
                cur = db.execute("UPDATE transactions SET kind=?,amount=?,category=?,note=?,txn_date=? WHERE id=? AND user_id=?", (kind, amount, category, note, txn_date, tid, u["id"]))
                if not cur.rowcount: return self.send_json({"error": "Không tìm thấy giao dịch."}, 404)
                new_id = tid
            else:
                new_id = db.execute("INSERT INTO transactions(user_id,kind,amount,category,note,txn_date) VALUES(?,?,?,?,?,?)", (u["id"],kind,amount,category,note,txn_date)).lastrowid
            db.execute("INSERT OR IGNORE INTO categories(user_id,name,kind) VALUES(?,?,?)",(u["id"],category,kind))
        return self.send_json({"ok": True, "id": new_id})

    def budgets(self, u):
        month = parse_qs(urlparse(self.path).query).get("month", [date.today().strftime("%Y-%m")])[0]
        with connect() as db:
            rows = db.execute("SELECT b.*,COALESCE(SUM(t.amount),0) spent FROM budgets b LEFT JOIN transactions t ON t.user_id=b.user_id AND t.category=b.category AND t.kind='expense' AND substr(t.txn_date,1,7)=b.month WHERE b.user_id=? AND b.month=? GROUP BY b.id ORDER BY b.category", (u["id"], month)).fetchall()
        return self.send_json({"items": [dict(r) for r in rows], "month": month})

    def save_budget(self, u, d):
        try:
            month = str(d.get("month", "")); datetime.strptime(month, "%Y-%m"); category = str(d.get("category", "")).strip()[:50]; amount = float(d.get("amount", 0))
            if not category or amount <= 0: raise ValueError()
        except (ValueError, TypeError): return self.send_json({"error": "Nhập tháng, danh mục và hạn mức hợp lệ."}, 400)
        with connect() as db: db.execute("INSERT INTO budgets(user_id,month,category,amount) VALUES(?,?,?,?) ON CONFLICT(user_id,month,category) DO UPDATE SET amount=excluded.amount", (u["id"],month,category,amount))
        return self.send_json({"ok": True})

    def goals(self, u):
        with connect() as db: rows = db.execute("SELECT * FROM goals WHERE user_id=? ORDER BY id DESC", (u["id"],)).fetchall()
        return self.send_json({"items": [dict(r) for r in rows]})

    def save_goal(self, u, d, gid=None):
        try:
            title = str(d.get("title", "")).strip()[:80]; target = float(d.get("target", 0)); saved = float(d.get("saved", 0)); due = str(d.get("due_date", ""))
            if not title or target <= 0 or saved < 0 or saved > target: raise ValueError()
            if due: date.fromisoformat(due)
        except (ValueError, TypeError): return self.send_json({"error": "Kiểm tra tên mục tiêu, số tiền và hạn hoàn thành."}, 400)
        with connect() as db:
            if gid:
                cur = db.execute("UPDATE goals SET title=?,target=?,saved=?,due_date=? WHERE id=? AND user_id=?", (title,target,saved,due,gid,u["id"]))
                if not cur.rowcount: return self.send_json({"error": "Không tìm thấy mục tiêu."}, 404)
            else: db.execute("INSERT INTO goals(user_id,title,target,saved,due_date) VALUES(?,?,?,?,?)", (u["id"],title,target,saved,due))
        return self.send_json({"ok": True})

    def delete_row(self, table, u, row_id):
        if table not in ("transactions", "budgets", "goals"): return self.send_json({"error": "Yêu cầu không hợp lệ."}, 400)
        with connect() as db: cur = db.execute(f"DELETE FROM {table} WHERE id=? AND user_id=?", (row_id,u["id"]))
        if not cur.rowcount: return self.send_json({"error": "Không tìm thấy dữ liệu."}, 404)
        return self.send_json({"ok": True})

    def ai_summary(self, u, d):
        month = str(d.get("month", date.today().strftime("%Y-%m")))
        try: datetime.strptime(month, "%Y-%m")
        except ValueError: return self.send_json({"error": "Tháng không hợp lệ."}, 400)
        with connect() as db:
            totals = db.execute("SELECT kind,SUM(amount) total FROM transactions WHERE user_id=? AND substr(txn_date,1,7)=? GROUP BY kind", (u["id"],month)).fetchall()
            cats = db.execute("SELECT category,SUM(amount) amount FROM transactions WHERE user_id=? AND kind='expense' AND substr(txn_date,1,7)=? GROUP BY category ORDER BY amount DESC", (u["id"],month)).fetchall()
            budgets = db.execute("SELECT b.category,b.amount limit_amount,COALESCE(SUM(t.amount),0) spent FROM budgets b LEFT JOIN transactions t ON t.user_id=b.user_id AND t.category=b.category AND t.kind='expense' AND substr(t.txn_date,1,7)=b.month WHERE b.user_id=? AND b.month=? GROUP BY b.id", (u["id"],month)).fetchall()
        values={r["kind"]:r["total"] or 0 for r in totals}; income=values.get("income",0); expense=values.get("expense",0); top=dict(cats[0]) if cats else None
        insights=[]
        if not cats: insights.append("Chưa có khoản chi nào trong tháng này. Hãy thêm giao dịch để nhận phân tích sát hơn.")
        else:
            insights.append(f"Tổng thu {income:,.0f} đồng, tổng chi {expense:,.0f} đồng; số dư thu chi là {income-expense:,.0f} đồng.")
            insights.append(f"Danh mục chi nhiều nhất là {top['category']} ({top['amount']:,.0f} đồng)." if top else "")
            exceeded=[b for b in budgets if b["spent"]>b["limit_amount"]]
            if exceeded: insights.append("Đã vượt ngân sách: " + ", ".join(f"{b['category']} ({b['spent']:,.0f}/{b['limit_amount']:,.0f} đồng)" for b in exceeded) + ".")
            elif budgets: insights.append("Các danh mục có ngân sách hiện vẫn trong hạn mức.")
            if income and expense > income: insights.append("Chi tiêu đang cao hơn thu nhập trong tháng; hãy xem lại các khoản không thiết yếu.")
            elif income and expense/income > .75: insights.append("Chi tiêu đã vượt 75% thu nhập; cân nhắc giữ lại một khoản dự phòng.")
            else: insights.append("Gợi ý: duy trì ghi chép đều và đặt ngân sách cho nhóm chi lớn nhất.")
        prompt_data={"month":month,"income":income,"expense":expense,"by_category":[dict(r) for r in cats],"budgets":[dict(r) for r in budgets]}
        answer, provider = self.call_ai(prompt_data, "\n".join(insights))
        return self.send_json({"answer":answer,"provider":provider,"data":prompt_data,"disclaimer":"Phân tích tham khảo dựa trên dữ liệu của tài khoản đang đăng nhập. Không phải tư vấn tài chính chuyên nghiệp."})

    def ai_chat(self, u, d):
        question = str(d.get("question", "")).strip()[:500]
        month = str(d.get("month", date.today().strftime("%Y-%m")))
        if not question: return self.send_json({"error": "Hãy nhập câu hỏi cho trợ lý."}, 400)
        try: datetime.strptime(month, "%Y-%m")
        except ValueError: return self.send_json({"error": "Tháng không hợp lệ."}, 400)
        with connect() as db:
            totals = db.execute("SELECT kind,SUM(amount) total FROM transactions WHERE user_id=? AND substr(txn_date,1,7)=? GROUP BY kind", (u["id"],month)).fetchall()
            cats = db.execute("SELECT category,SUM(amount) amount FROM transactions WHERE user_id=? AND kind='expense' AND substr(txn_date,1,7)=? GROUP BY category ORDER BY amount DESC", (u["id"],month)).fetchall()
            budgets = db.execute("SELECT b.category,b.amount limit_amount,COALESCE(SUM(t.amount),0) spent FROM budgets b LEFT JOIN transactions t ON t.user_id=b.user_id AND t.category=b.category AND t.kind='expense' AND substr(t.txn_date,1,7)=b.month WHERE b.user_id=? AND b.month=? GROUP BY b.id", (u["id"],month)).fetchall()
        values={r["kind"]:r["total"] or 0 for r in totals}
        data={"month":month,"income":values.get("income",0),"expense":values.get("expense",0),"by_category":[dict(r) for r in cats],"budgets":[dict(r) for r in budgets]}
        fallback=self.answer_local(question,data)
        answer,provider=self.call_ai(data, fallback, question=question)
        return self.send_json({"answer":answer,"provider":provider,"data":data,"disclaimer":"Câu trả lời chỉ dựa trên số liệu tổng hợp của tài khoản đang đăng nhập; hãy kiểm tra lại trước khi quyết định."})

    @staticmethod
    def answer_local(question, data):
        q=question.casefold(); cats=data["by_category"]
        if any(k in q for k in ("nhiều nhất", "nhiều nhất", "cao nhất", "lớn nhất", "nhiều tiền nhất")):
            if cats: return f"Trong tháng {data['month']}, bạn chi nhiều nhất cho danh mục {cats[0]['category']}: {cats[0]['amount']:,.0f} đồng."
            return f"Tháng {data['month']} chưa có dữ liệu chi tiêu để so sánh danh mục."
        if any(k in q for k in ("ngân sách", "hạn mức", "vượt")):
            over=[b for b in data["budgets"] if b["spent"]>b["limit_amount"]]
            if over: return "Các danh mục đã vượt ngân sách: "+"; ".join(f"{b['category']} ({b['spent']:,.0f}/{b['limit_amount']:,.0f} đồng)" for b in over)+"."
            return "Theo dữ liệu hiện có, chưa có danh mục nào vượt ngân sách đã đặt." if data["budgets"] else "Bạn chưa đặt ngân sách cho tháng này."
        if any(k in q for k in ("thu nhập", "tổng thu", "được bao nhiêu")):
            return f"Tổng thu tháng {data['month']} là {data['income']:,.0f} đồng. Tổng chi là {data['expense']:,.0f} đồng; chênh lệch thu trừ chi là {data['income']-data['expense']:,.0f} đồng."
        if any(k in q for k in ("tổng chi", "đã chi", "chi bao nhiêu", "chi tiêu")):
            return f"Tổng chi tháng {data['month']} là {data['expense']:,.0f} đồng."
        if any(k in q for k in ("gợi ý", "tiết kiệm", "nên làm", "đề xuất")):
            if cats:
                top=cats[0]
                return f"Danh mục đang chi nhiều nhất là {top['category']} ({top['amount']:,.0f} đồng). Bạn có thể đặt hạn mức cho nhóm này, ghi lại các khoản chi nhỏ hằng ngày và ưu tiên khoản cần thiết. Đây là gợi ý tham khảo."
            return "Hãy thêm giao dịch thu chi để mình phân tích và gợi ý sát với tình hình của bạn hơn."
        return f"Trong tháng {data['month']}, tổng thu là {data['income']:,.0f} đồng và tổng chi là {data['expense']:,.0f} đồng. Bạn có thể hỏi danh mục chi nhiều nhất, tình hình ngân sách hoặc gợi ý tiết kiệm."

    @staticmethod
    def call_ai(data, fallback, question=None):
        key=os.environ.get("AI_API_KEY", ""); base=os.environ.get("AI_BASE_URL", "https://api.deepseek.com/chat/completions"); model=os.environ.get("AI_MODEL", "deepseek-flash")
        if not key: return "[Chế độ demo ngoại tuyến]\n"+fallback, "demo-local"
        user_content=("Câu hỏi của người dùng: "+question+"\n" if question else "Phân tích dữ liệu tháng sau, gợi ý ngân sách thực tế.\n")+json.dumps(data,ensure_ascii=False)
        payload={"model":model,"temperature":0.2,"messages":[{"role":"system","content":"Bạn là trợ lý quản lý chi tiêu cá nhân. Chỉ dùng dữ liệu JSON được cung cấp để trả lời. Không bịa số, không suy đoán khoản không có trong dữ liệu và không đưa lời khuyên đầu tư. Trả lời ngắn bằng tiếng Việt; nếu thiếu dữ liệu, nói rõ."},{"role":"user","content":user_content}]}
        req=urllib.request.Request(base, data=json_bytes(payload), headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req,timeout=20) as res: body=json.loads(res.read(500_000))
            text=body["choices"][0]["message"]["content"]
            return str(text)[:5000], model
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError) as exc:
            return "[Không kết nối được AI trực tuyến; dùng phân tích dự phòng]\n"+fallback+f"\n\nTrạng thái kết nối: {type(exc).__name__}.", "demo-fallback"

    def static_file(self, path):
        rel = "index.html" if path == "/" else path.lstrip("/")
        target = (ROOT / "static" / rel).resolve()
        if not target.is_relative_to((ROOT / "static").resolve()) or not target.is_file(): return self.send_json({"error":"Không tìm thấy trang."},404)
        content=target.read_bytes(); types={".html":"text/html; charset=utf-8",".css":"text/css; charset=utf-8",".js":"text/javascript; charset=utf-8",".svg":"image/svg+xml"}
        self.send_response(200); self.send_header("Content-Type",types.get(target.suffix,"application/octet-stream")); self.send_header("Content-Length",str(len(content))); self.send_header("X-Content-Type-Options","nosniff"); self.end_headers(); self.wfile.write(content)

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")


if __name__ == "__main__":
    init_db()
    print(f"Expense AI running at http://{HOST}:{PORT}")
    print("Demo login: binh / Demo@12345")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
