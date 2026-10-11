from fastapi import FastAPI, Depends, Form, Request, Query, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from typing import Optional
import os
import uuid
import urllib.parse

# تعريف التطبيق في السطر الأول ليتعرف عليه Vercel فوراً
app = FastAPI(title="منصة أمانة للمفقودات")

# 1. إعداد قاعدة البيانات والملفات المرفوعة لتتوافق مع بيئة Vercel (المجلد /tmp)
IS_VERCEL = os.environ.get("VERCEL", False)
DB_FILE = "/tmp/amana.db" if IS_VERCEL else "amana.db"
UPLOAD_DIR = "/tmp/uploads" if IS_VERCEL else "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_FILE}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. جدول البلاغات
class ReportDB(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(20), nullable=False)         # مفقود أو معثور عليه
    category = Column(String(50), nullable=False)      # الفئة
    title = Column(String(150), nullable=False)        # اسم الشيء أو الوثيقة
    governorate = Column(String(50), nullable=False)   # المحافظة
    area = Column(String(100), nullable=False)         # المنطقة
    phone = Column(String(20), nullable=False)         # رقم الهاتف للتواصل
    description = Column(Text, nullable=True)          # تفاصيل إضافية
    image_url = Column(String(255), nullable=True)     # مسار الصورة
    date = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 3. قالب الواجهة العربية المتكاملة
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>منصة أَمانَة - المفقودات والمعثورات</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800 font-sans">

    <!-- شريط العنوان -->
    <header class="bg-emerald-700 text-white p-4 shadow-md text-center">
        <h1 class="text-2xl font-bold">منصة أَمانَة</h1>
        <p class="text-sm text-emerald-100 mt-1">أمانتك ترجعلك.. بلّغ عن مفقوداتك أو عثوراتك بسهولة</p>
    </header>

    <div class="max-w-xl mx-auto p-4 space-y-6">

        $match_alert_html$

        <!-- قسم البحث والفلترة -->
        <div class="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 space-y-3">
            <h2 class="text-sm font-bold text-slate-700 flex items-center gap-1">🔍 البحث والفلترة السريعة</h2>
            <form action="/" method="GET" class="space-y-2">
                <div class="flex gap-2">
                    <input type="text" name="q" value="$search_query$" placeholder="ابحث بالاسم أو التفاصيل (مثل: بطاقة موحدة...)" class="w-full border border-slate-300 p-2 rounded-xl text-sm bg-slate-50">
                    <button type="submit" class="bg-slate-800 text-white px-4 py-2 rounded-xl text-sm font-bold hover:bg-slate-900 transition">بحث</button>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <select name="type" onchange="this.form.submit()" class="border border-slate-300 p-2 rounded-xl text-xs bg-slate-50">
                        <option value="">كل الحالات (مفقود / معثور)</option>
                        <option value="🔴 مفقود" $selected_lost$>🔴 مفقود فقط</option>
                        <option value="🟢 معثور عليه" $selected_found$>🟢 معثور عليه فقط</option>
                    </select>
                    <input type="text" name="gov" value="$gov_query$" placeholder="تصفية حسب المحافظة..." onchange="this.form.submit()" class="border border-slate-300 p-2 rounded-xl text-xs bg-slate-50">
                </div>
                $clear_filter_btn$
            </form>
        </div>

        <!-- نموذج إضافة بلاغ -->
        <div class="bg-white p-5 rounded-2xl shadow-sm border border-slate-200">
            <h2 class="text-lg font-bold mb-4 text-emerald-800 border-b pb-2">➕ إضافة بلاغ جديد</h2>
            <form action="/add" method="POST" enctype="multipart/form-data" class="space-y-3">
                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-xs font-semibold mb-1 text-slate-600">نوع الحالة:</label>
                        <select name="type" class="w-full border border-slate-300 p-2 rounded-xl text-sm bg-slate-50">
                            <option value="🔴 مفقود">🔴 مفقود</option>
                            <option value="🟢 معثور عليه">🟢 معثور عليه</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold mb-1 text-slate-600">الفئة:</label>
                        <select name="category" class="w-full border border-slate-300 p-2 rounded-xl text-sm bg-slate-50">
                            <option value="🪪 وثائق وهويات">🪪 وثائق وهويات</option>
                            <option value="📱 أجهزة وموبايلات">📱 أجهزة وموبايلات</option>
                            <option value="🔑 مفاتيح ومقتنيات">🔑 مفاتيح ومقتنيات</option>
                            <option value="🐾 حيوانات أليفة">🐾 حيوانات أليفة</option>
                            <option value="📦 أشياء أخرى">📦 أشياء أخرى</option>
                        </select>
                    </div>
                </div>

                <div>
                    <label class="block text-xs font-semibold mb-1 text-slate-600">عنوان البلاغ (مثال: بطاقة موحدة باسم محمد...):</label>
                    <input type="text" name="title" required class="w-full border border-slate-300 p-2 rounded-xl text-sm">
                </div>

                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-xs font-semibold mb-1 text-slate-600">المحافظة:</label>
                        <input type="text" name="governorate" placeholder="مثل: ميسان" required class="w-full border border-slate-300 p-2 rounded-xl text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold mb-1 text-slate-600">المنطقة أو الحي:</label>
                        <input type="text" name="area" placeholder="مثل: العمارة - حي الحسين" required class="w-full border border-slate-300 p-2 rounded-xl text-sm">
                    </div>
                </div>

                <div>
                    <label class="block text-xs font-semibold mb-1 text-slate-600">رقم الهاتف للتواصل المباشر:</label>
                    <input type="tel" name="phone" placeholder="07xxxxxxxxx" required class="w-full border border-slate-300 p-2 rounded-xl text-sm">
                </div>

                <div>
                    <label class="block text-xs font-semibold mb-1 text-slate-600">صورة المفقود/المعثور عليه (اختياري):</label>
                    <input type="file" name="image" accept="image/*" class="w-full border border-slate-300 p-1.5 rounded-xl text-xs bg-slate-50">
                </div>

                <div>
                    <label class="block text-xs font-semibold mb-1 text-slate-600">تفاصيل إضافية (اختياري):</label>
                    <textarea name="description" placeholder="اكتب أي ملاحظات أو علامات مميزة..." class="w-full border border-slate-300 p-2 rounded-xl text-sm h-16"></textarea>
                </div>

                <button type="submit" class="w-full bg-emerald-700 text-white p-3 rounded-xl font-bold hover:bg-emerald-800 transition shadow-md">
                    نشر البلاغ والمطابقة الذكية 🚀
                </button>
            </form>
        </div>

        <!-- قائمة عرض البلاغات -->
        <div>
            <h2 class="text-lg font-bold mb-3 text-slate-800">📋 البلاغات المسجلة</h2>
            <div class="space-y-3">
                $reports_list_html$
            </div>
        </div>

    </div>

</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def home(
    q: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    gov: Optional[str] = Query(None),
    match_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(ReportDB)

    if type:
        query = query.filter(ReportDB.type == type)
    if gov:
        query = query.filter(ReportDB.governorate.contains(gov))
    if q:
        search_filter = or_(
            ReportDB.title.contains(q),
            ReportDB.description.contains(q),
            ReportDB.area.contains(q)
        )
        query = query.filter(search_filter)

    reports = query.order_by(ReportDB.id.desc()).all()

    match_alert_html = ""
    if match_id:
        new_report = db.query(ReportDB).filter(ReportDB.id == match_id).first()
        if new_report:
            opposite_type = "🔴 مفقود" if "معثور" in new_report.type else "🟢 معثور عليه"
            matches = db.query(ReportDB).filter(
                ReportDB.type == opposite_type,
                ReportDB.category == new_report.category,
                ReportDB.governorate == new_report.governorate,
                ReportDB.id != new_report.id
            ).limit(3).all()

            if matches:
                match_items = "".join([f'<li class="text-xs font-semibold">• ({m.type}) {m.title} - {m.area} (هاتف: {m.phone})</li>' for m in matches])
                match_alert_html = f"""
                <div class="bg-amber-50 border-r-4 border-amber-500 p-4 rounded-xl shadow-sm space-y-2">
                    <h3 class="font-bold text-amber-800 text-sm flex items-center gap-1">🤖 نظام المطابقة الذكية عثر على نتائج محتملة لبلاغك!</h3>
                    <ul class="space-y-1 text-amber-900">{match_items}</ul>
                </div>
                """

    cards_html = ""
    if not reports:
        cards_html = '<div class="bg-white p-6 rounded-2xl text-center text-slate-400 border">لا توجد بلاغات تطابق البحث حالياً.</div>'
    else:
        for r in reports:
            border_color = "border-r-red-500" if "مفقود" in r.type else "border-r-emerald-500"
            badge_bg = "bg-red-100 text-red-700" if "مفقود" in r.type else "bg-emerald-100 text-emerald-700"
            img_html = f'<img src="{r.image_url}" class="w-full h-48 object-cover rounded-xl mt-2 border">' if r.image_url else ''

            share_text = urllib.parse.quote(f"بلاغ عبر منصة أمانة ({r.type}): {r.title}\nالمكان: {r.governorate} - {r.area}\nللتواصل: {r.phone}")
            wa_link = f"https://api.whatsapp.com/send?text={share_text}"

            cards_html += f"""
            <div class="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 border-r-4 {border_color} space-y-2">
                <div class="flex justify-between items-center">
                    <span class="text-xs px-2.5 py-1 rounded-full font-bold {badge_bg}">{r.type}</span>
                    <span class="text-xs text-slate-400">📍 {r.governorate} - {r.area}</span>
                </div>
                <h3 class="font-bold text-base text-slate-800">{r.title}</h3>
                <span class="text-xs text-slate-500 block">الفئة: {r.category}</span>
                {img_html}
                {f'<p class="text-xs text-slate-600 bg-slate-50 p-2 rounded-lg">{r.description}</p>' if r.description else ''}
                <div class="pt-2 border-t flex justify-between items-center gap-2">
                    <a href="tel:{r.phone}" class="bg-emerald-50 text-emerald-700 text-xs font-bold px-3 py-2 rounded-xl border border-emerald-200 hover:bg-emerald-100 transition">
                        📞 اتصل: {r.phone}
                    </a>
                    <a href="{wa_link}" target="_blank" class="bg-green-600 text-white text-xs font-bold px-3 py-2 rounded-xl hover:bg-green-700 transition flex items-center gap-1">
                        💬 مشاركة واتساب
                    </a>
                </div>
            </div>
            """

    clear_btn = '<a href="/" class="text-xs text-red-600 underline block text-center mt-1">إلغاء الفلترة والبحث</a>' if (q or type or gov) else ''
    
    page_content = HTML_TEMPLATE.replace("$reports_list_html$", cards_html)\
                                .replace("$match_alert_html$", match_alert_html)\
                                .replace("$search_query$", q or '')\
                                .replace("$gov_query$", gov or '')\
                                .replace("$selected_lost$", 'selected' if type == '🔴 مفقود' else '')\
                                .replace("$selected_found$", 'selected' if type == '🟢 معثور عليه' else '')\
                                .replace("$clear_filter_btn$", clear_btn)

    return HTMLResponse(content=page_content)

@app.post("/add")
async def add_report(
    type: str = Form(...),
    category: str = Form(...),
    title: str = Form(...),
    governorate: str = Form(...),
    area: str = Form(...),
    phone: str = Form(...),
    description: str = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    image_url = None
    if image and image.filename:
        ext = image.filename.split(".")[-1]
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(await image.read())
        image_url = f"/uploads/{filename}"

    new_report = ReportDB(
        type=type,
        category=category,
        title=title,
        governorate=governorate,
        area=area,
        phone=phone,
        description=description,
        image_url=image_url
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    return RedirectResponse(url=f"/?match_id={new_report.id}", status_code=303)