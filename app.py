from fastapi import FastAPI, Depends, Form, Request, Query, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from typing import Optional
import os
import uuid
import urllib.parse
import json

app = FastAPI(title="منصة أمانة - خدمة ملصقات أمانة الذكية")

# 1. إعداد قاعدة البيانات والملفات المرفوعة
IS_VERCEL = os.environ.get("VERCEL", False)
DB_FILE = "/tmp/amana.db" if IS_VERCEL else "amana.db"
UPLOAD_DIR = "/tmp/uploads" if IS_VERCEL else "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_FILE}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. جدول البلاغات العامة
class ReportDB(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(20), nullable=False)         
    category = Column(String(50), nullable=False)      
    title = Column(String(150), nullable=False)        
    governorate = Column(String(50), nullable=False)   
    area = Column(String(100), nullable=False)         
    phone = Column(String(20), nullable=False)         
    pin = Column(String(10), nullable=True, default="1234")
    description = Column(Text, nullable=True)          
    image_url = Column(String(255), nullable=True)     
    date = Column(DateTime, default=datetime.utcnow)

# 3. جدول ملصقات أمانة المطبوعة المفعّلة
class StickerDB(Base):
    __tablename__ = "stickers"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True) # الكود المطبوع على الملصق
    item_name = Column(String(150), nullable=True)     # اسم الغرض بعد التفعيل
    phone = Column(String(20), nullable=True)         # رقم صاحب الملصق بعد التفعيل
    pin = Column(String(10), nullable=True)           # كود التفعيل السرّي
    note = Column(Text, nullable=True)                 # ملاحظة أو مكافأة
    is_active = Column(Boolean, default=False)        # هل تم تفعيله بشراء الزبون؟
    date = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>منصة أَمانَة - المفقودات والملصقات الذكية</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800 font-sans">

    <header class="bg-emerald-700 text-white p-4 shadow-md text-center">
        <h1 class="text-2xl font-bold">منصة أَمانَة</h1>
        <p class="text-sm text-emerald-100 mt-1">أمانتك ترجعلك.. بلّغ عن مفقوداتك أو فعّل ملصقك الذكي</p>
    </header>

    <div class="max-w-xl mx-auto p-4 space-y-6">

        $match_alert_html$

        <!-- قسم التبويب -->
        <div class="grid grid-cols-2 gap-2 bg-emerald-100/60 p-1.5 rounded-2xl border border-emerald-200">
            <button onclick="switchTab('reports')" id="tab-reports" class="py-2.5 px-3 rounded-xl font-bold text-xs bg-emerald-700 text-white shadow-sm transition">
                📢 البلاغات العامة
            </button>
            <button onclick="switchTab('stickers')" id="tab-stickers" class="py-2.5 px-3 rounded-xl font-bold text-xs text-emerald-800 hover:bg-emerald-200/50 transition">
                🏷️ تفعيل ملصق أمانة الذكي
            </button>
        </div>

        <!-- قسم البلاغات -->
        <div id="section-reports" class="space-y-6">
            <div class="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 space-y-3">
                <h2 class="text-sm font-bold text-slate-700 flex items-center gap-1">🔍 البحث والفلترة السريعة</h2>
                <form action="/" method="GET" class="space-y-2">
                    <div class="flex gap-2">
                        <input type="text" name="q" value="$search_query$" placeholder="ابحث بالاسم أو التفاصيل..." class="w-full border border-slate-300 p-2 rounded-xl text-sm bg-slate-50">
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
                                <option value="وثائق وهويات">📄 وثائق وهويات</option>
                                <option value="أجهزة وموبايلات">📱 أجهزة وموبايلات</option>
                                <option value="مفاتيح ومقتنيات">🔑 مفاتيح ومقتنيات</option>
                                <option value="حيوانات أليفة">🐾 حيوانات أليفة</option>
                                <option value="أشياء أخرى">📦 أشياء أخرى</option>
                            </select>
                        </div>
                    </div>

                    <div>
                        <label class="block text-xs font-semibold mb-1 text-slate-600">عنوان البلاغ (مثال: بطاقة موحدة باسم...):</label>
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

                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="block text-xs font-semibold mb-1 text-slate-600">رقم الهاتف:</label>
                            <input type="tel" name="phone" placeholder="07xxxxxxxxx" required class="w-full border border-slate-300 p-2 rounded-xl text-sm">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold mb-1 text-slate-600">رمز سرّي للحذف:</label>
                            <input type="password" name="pin" placeholder="مثال: 1234" required class="w-full border border-slate-300 p-2 rounded-xl text-sm">
                        </div>
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
                <div class="flex justify-between items-center mb-3">
                    <h2 class="text-lg font-bold text-slate-800">📋 البلاغات المسجلة</h2>
                    <span class="text-xs bg-slate-200 text-slate-700 px-2.5 py-1 rounded-full font-bold">إجمالي: $total_count$</span>
                </div>
                <div class="space-y-3">
                    $reports_list_html$
                </div>
            </div>
        </div>

        <!-- قسم تفعيل الملصقات المشتراة -->
        <div id="section-stickers" class="hidden bg-white p-5 rounded-2xl shadow-sm border border-slate-200 space-y-4">
            <div class="text-center space-y-1">
                <span class="text-3xl">🔑</span>
                <h2 class="text-lg font-bold text-emerald-800">تفعيل ملصق أمانة المشترى</h2>
                <p class="text-xs text-slate-500">هل اشتريت ملصق أمانة الذكي؟ أدخل كود التفعيل المطبوع على غلاف البطاقة لربطه بهاتفك فوراً.</p>
            </div>

            <form action="/activate-sticker" method="POST" class="space-y-3 pt-2">
                <div>
                    <label class="block text-xs font-semibold mb-1 text-slate-600">رقم الملصق (Serial Code):</label>
                    <input type="text" name="code" placeholder="مثال: AMN-1001" required class="w-full border border-slate-300 p-2 rounded-xl text-sm uppercase">
                </div>

                <div>
                    <label class="block text-xs font-semibold mb-1 text-slate-600">كود التفعيل السرّي (PIN):</label>
                    <input type="password" name="pin" placeholder="مثال: 5821" required class="w-full border border-slate-300 p-2 rounded-xl text-sm">
                </div>

                <div>
                    <label class="block text-xs font-semibold mb-1 text-slate-600">اسم الغرض المُلصق عليه:</label>
                    <input type="text" name="item_name" placeholder="مثال: مفاتيح سيارة / موبايل أيفون" required class="w-full border border-slate-300 p-2 rounded-xl text-sm">
                </div>

                <div>
                    <label class="block text-xs font-semibold mb-1 text-slate-600">رقم هاتفك للتواصل عند العثور:</label>
                    <input type="tel" name="phone" placeholder="07xxxxxxxxx" required class="w-full border border-slate-300 p-2 rounded-xl text-sm">
                </div>

                <div>
                    <label class="block text-xs font-semibold mb-1 text-slate-600">ملاحظة لمن يجد الغرض (اختياري):</label>
                    <textarea name="note" placeholder="مثال: يرجى الاتصال بي فوراً وتوجد مكافأة مالية..." class="w-full border border-slate-300 p-2 rounded-xl text-sm h-16"></textarea>
                </div>

                <button type="submit" class="w-full bg-emerald-700 text-white p-3 rounded-xl font-bold hover:bg-emerald-800 transition shadow-md">
                    ✨ تفعيل الملصق وربطه بـ QR
                </button>
            </form>
        </div>

    </div>

    <!-- نافذة تفاصيل البلاغ المنبثقة (Modal) -->
    <div id="detailsModal" class="fixed inset-0 bg-slate-900/60 backdrop-blur-sm hidden flex items-center justify-center p-4 z-50">
        <div class="bg-white rounded-3xl max-w-lg w-full p-5 space-y-4 shadow-2xl overflow-y-auto max-h-[90vh] relative border border-slate-100">
            <button onclick="closeModal()" class="absolute top-4 left-4 bg-slate-100 text-slate-600 hover:bg-slate-200 w-8 h-8 rounded-full font-bold text-sm flex items-center justify-center transition">✕</button>            
            <div id="modalHeader"></div>
            <div id="modalBody" class="space-y-3"></div>
            <div id="modalFooter" class="pt-3 border-t flex justify-between items-center gap-2"></div>
        </div>
    </div>

    <script>
    function switchTab(tab) {
        const repSec = document.getElementById('section-reports');
        const stkSec = document.getElementById('section-stickers');
        const repBtn = document.getElementById('tab-reports');
        const stkBtn = document.getElementById('tab-stickers');

        if (tab === 'reports') {
            repSec.classList.remove('hidden');
            stkSec.classList.add('hidden');
            repBtn.className = "py-2.5 px-3 rounded-xl font-bold text-xs bg-emerald-700 text-white shadow-sm transition";
            stkBtn.className = "py-2.5 px-3 rounded-xl font-bold text-xs text-emerald-800 hover:bg-emerald-200/50 transition";
        } else {
            repSec.classList.add('hidden');
            stkSec.classList.remove('hidden');
            stkBtn.className = "py-2.5 px-3 rounded-xl font-bold text-xs bg-emerald-700 text-white shadow-sm transition";
            repBtn.className = "py-2.5 px-3 rounded-xl font-bold text-xs text-emerald-800 hover:bg-emerald-200/50 transition";
        }
    }

    function openModal(report) {
        const modal = document.getElementById('detailsModal');
        const modalHeader = document.getElementById('modalHeader');
        const modalBody = document.getElementById('modalBody');
        const modalFooter = document.getElementById('modalFooter');

        const badgeBg = report.type.includes("مفقود") ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700";

        modalHeader.innerHTML = `
            <div class="flex items-center gap-2 mb-1">
                <span class="text-xs px-2.5 py-1 rounded-full font-bold ${badgeBg}">${report.type}</span>
                <span class="text-xs text-slate-400">📅 ${report.date}</span>
            </div>
            <h2 class="text-xl font-bold text-slate-800">${report.title}</h2>
            <p class="text-xs text-slate-500">الفئة: ${report.category}</p>
        `;

        let imgHtml = report.image_url ? `<div class="rounded-2xl overflow-hidden border border-slate-200"><img src="${report.image_url}" class="w-full object-contain max-h-80 bg-slate-900/5"></div>` : '';

        modalBody.innerHTML = `
            ${imgHtml}
            <div class="bg-slate-50 p-3 rounded-xl border border-slate-200/60 space-y-1">
                <p class="text-xs font-bold text-slate-700">📍 الموقع والمكان:</p>
                <p class="text-sm text-slate-800">${report.governorate} - ${report.area}</p>
            </div>
            <div class="bg-slate-50 p-3 rounded-xl border border-slate-200/60 space-y-1">
                <p class="text-xs font-bold text-slate-700">📝 التفاصيل الإضافية:</p>
                <p class="text-sm text-slate-800 whitespace-pre-line">${report.description || 'لا توجد تفاصيل إضافية مكتوبة.'}</p>
            </div>
        `;

        const shareText = encodeURIComponent(`بلاغ عبر منصة أمانة (${report.type}): ${report.title}\nالمكان: ${report.governorate} - ${report.area}\nللتواصل: ${report.phone}`);
        const waLink = `https://api.whatsapp.com/send?text=${shareText}`;

        modalFooter.innerHTML = `
            <div class="flex gap-2">
                <a href="tel:${report.phone}" class="bg-emerald-600 text-white text-xs font-bold px-4 py-2.5 rounded-xl hover:bg-emerald-700 transition flex items-center gap-1 shadow-sm">
                    📞 اتصل: ${report.phone}
                </a>
                <a href="${waLink}" target="_blank" class="bg-green-600 text-white text-xs font-bold px-3 py-2.5 rounded-xl hover:bg-green-700 transition flex items-center gap-1 shadow-sm">
                    💬 مشاركة
                </a>
            </div>
            <button onclick="promptDelete(${report.id})" class="text-xs text-red-500 hover:text-red-700 underline font-semibold">
                🗑️ حذف
            </button>
        `;

        modal.classList.remove('hidden');
    }

    function closeModal() {
        document.getElementById('detailsModal').classList.add('hidden');
    }

    function promptDelete(reportId) {
        const pin = prompt("رجاءً أدخل الرمز السرّي الخاص بك لحذف البلاغ:");
        if (pin) {
            window.location.href = `/delete/${reportId}?pin=${encodeURIComponent(pin)}`;
        }
    }
    </script>
</body>
</html>
"""

# قالب صفحة التواصل المباشر عند مسح ملصق أمانة بالهاتف
STICKER_SCAN_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>معلومات التواصل - منصة أمانة</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800 font-sans flex items-center justify-center min-h-screen p-4">

    <div class="max-w-md w-full bg-white p-6 rounded-3xl shadow-xl border border-slate-200 space-y-5 text-center">
        <div class="w-16 h-16 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center mx-auto text-3xl shadow-inner">
            🤝
        </div>

        <div>
            <span class="bg-emerald-100 text-emerald-800 text-xs px-3 py-1 rounded-full font-bold">معثور عليه بواسطة ملصق أمانة الذكي</span>
            <h1 class="text-xl font-bold text-slate-800 mt-2">$item_name$</h1>
        </div>

        $note_html$

        <div class="p-4 bg-emerald-50 rounded-2xl border border-emerald-200 space-y-3">
            <p class="text-xs font-bold text-emerald-900">يرجى التواصل المباشر مع صاحب الغرض لتسليمه:</p>
            
            <a href="tel:$phone$" class="block bg-emerald-700 text-white font-bold py-3 rounded-xl hover:bg-emerald-800 transition shadow-md text-sm">
                📞 اتصل بالصاحب: $phone$
            </a>

            <a href="https://api.whatsapp.com/send?phone=964$phone_clean$&text=$wa_msg$" target="_blank" class="block bg-green-600 text-white font-bold py-3 rounded-xl hover:bg-green-700 transition shadow-md text-sm">
                💬 مراسلة عبر الواتساب
            </a>
        </div>

        <p class="text-[11px] text-slate-400">شكراً لأمانتك وحرصك على إرجاع المفقودات لأصحابها ❤️</p>
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
    error: Optional[str] = Query(None),
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
    total_count = db.query(ReportDB).count()

    match_alert_html = ""
    if error:
        match_alert_html = f'<div class="bg-red-50 border-r-4 border-red-500 p-3 rounded-xl text-red-800 text-xs font-bold mb-3">{error}</div>'
    elif match_id:
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
            img_html = f'<img src="{r.image_url}" class="w-full h-44 object-cover rounded-xl mt-2 border">' if r.image_url else ''

            share_text = urllib.parse.quote(f"بلاغ عبر منصة أمانة ({r.type}): {r.title}\nالمكان: {r.governorate} - {r.area}\nللتواصل: {r.phone}")
            wa_link = f"https://api.whatsapp.com/send?text={share_text}"

            report_json = {
                "id": r.id,
                "type": r.type,
                "category": r.category,
                "title": r.title,
                "governorate": r.governorate,
                "area": r.area,
                "phone": r.phone,
                "description": r.description or "",
                "image_url": r.image_url or "",
                "date": r.date.strftime("%Y-%m-%d %H:%M") if r.date else ""
            }
            json_str = json.dumps(report_json, ensure_ascii=False).replace('"', '&quot;')

            cards_html += f"""
            <div onclick="openModal({json_str})" class="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 border-r-4 {border_color} space-y-2 cursor-pointer hover:shadow-md transition">
                <div class="flex justify-between items-center">
                    <span class="text-xs px-2.5 py-1 rounded-full font-bold {badge_bg}">{r.type}</span>
                    <span class="text-xs text-slate-400">📍 {r.governorate} - {r.area}</span>
                </div>
                <h3 class="font-bold text-base text-slate-800">{r.title}</h3>
                <span class="text-xs text-slate-500 block">الفئة: {r.category}</span>
                {img_html}
                {f'<p class="text-xs text-slate-600 bg-slate-50 p-2 rounded-lg line-clamp-2">{r.description}</p>' if r.description else ''}
                
                <div class="pt-2 border-t flex flex-wrap justify-between items-center gap-2" onclick="event.stopPropagation()">
                    <div class="flex gap-2">
                        <a href="tel:{r.phone}" class="bg-emerald-50 text-emerald-700 text-xs font-bold px-3 py-2 rounded-xl border border-emerald-200 hover:bg-emerald-100 transition">
                            📞 اتصل: {r.phone}
                        </a>
                        <a href="{wa_link}" target="_blank" class="bg-green-600 text-white text-xs font-bold px-3 py-2 rounded-xl hover:bg-green-700 transition flex items-center gap-1">
                            💬 مشاركة
                        </a>
                    </div>
                    <button onclick="promptDelete({r.id})" class="text-xs text-red-500 hover:text-red-700 underline font-semibold cursor-pointer">
                        🗑️ حذف
                    </button>
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
                                .replace("$clear_filter_btn$", clear_btn)\
                                .replace("$total_count$", str(total_count))

    return HTMLResponse(content=page_content)

@app.post("/add")
async def add_report(
    type: str = Form(...),
    category: str = Form(...),
    title: str = Form(...),
    governorate: str = Form(...),
    area: str = Form(...),
    phone: str = Form(...),
    pin: str = Form(...),
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
        pin=pin,
        description=description,
        image_url=image_url
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    return RedirectResponse(url=f"/?match_id={new_report.id}", status_code=303)

# 4. مسار تفعيل الملصق بعد الشراء
@app.post("/activate-sticker")
def activate_sticker(
    code: str = Form(...),
    pin: str = Form(...),
    item_name: str = Form(...),
    phone: str = Form(...),
    note: str = Form(None),
    db: Session = Depends(get_db)
):
    code_clean = code.strip().upper()
    sticker = db.query(StickerDB).filter(StickerDB.code == code_clean).first()

    if not sticker:
        return RedirectResponse(url="/?error=" + urllib.parse.quote("رمز الملصق غير موجود! يرجى التأكد من كود البطاقة المشتراة."), status_code=303)

    if sticker.is_active:
        return RedirectResponse(url="/?error=" + urllib.parse.quote("هذا الملصق مفعّل مسبقاً!"), status_code=303)

    if sticker.pin != pin.strip():
        return RedirectResponse(url="/?error=" + urllib.parse.quote("كود التفعيل السرّي (PIN) غير صحيح!"), status_code=303)

    # ربط وتفعيل الملصق
    sticker.item_name = item_name
    sticker.phone = phone
    sticker.note = note
    sticker.is_active = True
    db.commit()

    return RedirectResponse(url=f"/qr/{sticker.code}", status_code=303)

# 5. مسار مسح كود الـ QR للملصق
@app.get("/qr/{code}", response_class=HTMLResponse)
def scan_qr(code: str, db: Session = Depends(get_db)):
    code_clean = code.strip().upper()
    sticker = db.query(StickerDB).filter(StickerDB.code == code_clean).first()

    if not sticker:
        return HTMLResponse(content="<h2 style='text-align:center;margin-top:50px;'>عذراً، هذا الملصق غير متاح أو غير مسجل.</h2>")

    if not sticker.is_active:
        return HTMLResponse(content=f"""
        <div style='text-align:center;margin-top:50px;font-family:sans-serif;'>
            <h2>🏷️ هذا الملصق جاهز ولم يتم تفعيله بعد!</h2>
            <p>إذا كنت قد اشتريت هذا الملصق، يرجى تفعيله من الصفحة الرئيسية للمنصة بزيارة amana.vercel.app</p>
        </div>
        """)

    phone_clean = sticker.phone.lstrip('0')
    wa_msg = urllib.parse.quote(f"مرحباً، لقد عثرت على ({sticker.item_name}) المخصص له ملصق أمانة وتواصلت معك لإرجاعه.")
    note_html = f'<div class="bg-amber-50 p-3 rounded-2xl border border-amber-200 text-xs text-amber-900 font-semibold">{sticker.note}</div>' if sticker.note else ''

    page_content = STICKER_SCAN_TEMPLATE.replace("$item_name$", sticker.item_name)\
                                        .replace("$phone$", sticker.phone)\
                                        .replace("$phone_clean$", phone_clean)\
                                        .replace("$wa_msg$", wa_msg)\
                                        .replace("$note_html$", note_html)

    return HTMLResponse(content=page_content)

# 6. لوحة تحكم مصغرة لتوليد ملصقات جديدة للطباعة والتوزيع التجاري (توليد الدومين ديناميكياً)
@app.get("/admin/generate-codes", response_class=HTMLResponse)
def admin_generate(request: Request, count: int = 10, passkey: str = Query(""), db: Session = Depends(get_db)):
    if passkey != "salar2026":
        return HTMLResponse(content="<h3 style='text-align:center;margin-top:50px;color:red;'>غير مصرح بالدخول! أضف ?passkey=salar2026 للرابط</h3>")

    # جلب رابط الموقع الحقيقي ديناميكياً
    base_domain = str(request.base_url).rstrip('/')

    generated = []
    import random
    for i in range(count):
        serial_num = f"AMN-{random.randint(10000, 99999)}"
        pin_code = str(random.randint(1000, 9999))
        
        if not db.query(StickerDB).filter(StickerDB.code == serial_num).first():
            new_sticker = StickerDB(code=serial_num, pin=pin_code, is_active=False)
            db.add(new_sticker)
            generated.append(f"<tr><td style='padding:8px;border:1px solid #ddd;'><b>{serial_num}</b></td><td style='padding:8px;border:1px solid #ddd;'>{pin_code}</td><td style='padding:8px;border:1px solid #ddd;'>{base_domain}/qr/{serial_num}</td></tr>")

    db.commit()

    table_rows = "".join(generated)
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html dir='rtl'>
    <head><title>لوحة توليد الأكواد - أمانة</title></head>
    <body style='font-family:sans-serif;padding:20px;'>
        <h2>✨ تم توليد {len(generated)} ملصق جديد بنجاح!</h2>
        <p>استخدم أرقام Serial والـ PIN أدناه لطباعتها على كروت/ملصقات الشراء للزبائن:</p>
        <table style='border-collapse:collapse;width:100%;max-w:600px;'>
            <tr style='background:#f2f2f2;'>
                <th style='padding:8px;border:1px solid #ddd;'>رقم الملصق (Serial)</th>
                <th style='padding:8px;border:1px solid #ddd;'>كود التفعيل السرّي (PIN)</th>
                <th style='padding:8px;border:1px solid #ddd;'>رابط الـ QR المطبوع</th>
            </tr>
            {table_rows}
        </table>
    </body>
    </html>
    """)

@app.get("/delete/{report_id}")
def delete_report(report_id: int, pin: Optional[str] = Query(None), db: Session = Depends(get_db)):
    report = db.query(ReportDB).filter(ReportDB.id == report_id).first()
    if report:
        if report.pin and report.pin != pin:
            return RedirectResponse(url="/?error=" + urllib.parse.quote("الرمز السرّي غير صحيح! لم يتم حذف البلاغ."), status_code=303)
        db.delete(report)
        db.commit()
    return RedirectResponse(url="/", status_code=303)