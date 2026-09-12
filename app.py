import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify
from zk import ZK

app = Flask(__name__)

# حافظه موقت برای ذخیره داده‌های دستگاه AI09F (Push)
AI09F_LOGS = {}
AI09F_USERS = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>پنل یکپارچه دستگاه‌ها (کاربران و ترددها)</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
    <style>
        body { background-color: #f4f6f9; font-family: Tahoma, Segoe UI, sans-serif; padding-top: 30px; }
        .card { border-radius: 12px; border: none; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        .table-responsive { max-height: 400px; overflow-y: auto; }
        .spinner-border { display: none; }
        .clickable-row { cursor: pointer; transition: background 0.2s; }
        .clickable-row:hover { background-color: #e9ecef !important; }
    </style>
</head>
<body>
<div class="container">
    <div class="row justify-content-center">
        <div class="col-md-11">
            <div class="card p-4 mb-4">
                <h4 class="mb-3 text-primary">استعلام اطلاعات اشخاص و ترددها</h4>
                <form id="checkForm" class="row g-3 align-items-end">
                    <div class="col-md-3">
                        <label class="form-label">نوع دستگاه:</label>
                        <select id="deviceType" class="form-select">
                            <option value="zk">ZKTeco / Faratechno</option>
                            <option value="ai09f">AI09F / TIMMY (Push)</option>
                        </select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">آدرس IP دستگاه:</label>
                        <input type="text" id="ip" class="form-control" placeholder="192.168.1.x" required>
                    </div>
                    <div class="col-md-2" id="portDiv">
                        <label class="form-label">پورت:</label>
                        <input type="number" id="port" class="form-control" value="4370">
                    </div>
                    <div class="col-md-4">
                        <button type="submit" class="btn btn-primary w-100" id="btnSubmit">
                            <span class="spinner-border spinner-border-sm ms-2" id="spinner"></span>
                            دریافت اطلاعات کلی
                        </button>
                    </div>
                </form>
            </div>

            <div id="resultArea" style="display: none;">
                <div class="card p-4 mb-4">
                    <div id="statusBadge" class="alert mb-3"></div>
                    
                    <div class="row">
                        <!-- جدول لیست کاربران -->
                        <div class="col-md-5">
                            <h5 class="mb-3 text-success">👥 لیست اشخاص (برای جزئیات کلیک کنید):</h5>
                            <div class="table-responsive border rounded mb-3">
                                <table class="table table-hover align-middle mb-0">
                                    <thead class="table-success">
                                        <tr>
                                            <th>شناسه</th>
                                            <th>نام و نام خانوادگی</th>
                                            <th>نقش / دسترسی</th>
                                        </tr>
                                    </thead>
                                    <tbody id="usersTableBody"></tbody>
                                </table>
                            </div>
                        </div>

                        <!-- جدول لیست ترددها عمومی -->
                        <div class="col-md-7">
                            <h5 class="mb-3 text-info">🕒 آخرین ترددهای کل سیستم:</h5>
                            <div class="table-responsive border rounded mb-3">
                                <table class="table table-striped align-middle mb-0">
                                    <thead class="table-info">
                                        <tr>
                                            <th>#</th>
                                            <th>شناسه</th>
                                            <th>نام شخص</th>
                                            <th>تاریخ و زمان</th>
                                        </tr>
                                    </thead>
                                    <tbody id="logsTableBody"></tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- پنجره پاپ‌آپ (Modal) برای نمایش ترددهای اختصاصی شخص -->
<div class="modal fade" id="userLogsModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-scrollable">
    <div class="modal-content">
      <div class="modal-header bg-primary text-white">
        <h5 class="modal-title" id="modalTitle">گزارش تردد ۳۰ روز اخیر</h5>
        <button type="button" class="btn-close btn-close-white m-0" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">
        <div id="modalLoading" class="text-center py-4">
            <div class="spinner-border text-primary" role="status"></div>
            <p class="mt-2">در حال استخراج اطلاعات شخص از دستگاه...</p>
        </div>
        <div id="modalContent" style="display: none;">
            <p id="modalUserCount" class="text-muted text-center"></p>
            <table class="table table-bordered table-striped text-center">
                <thead class="table-light">
                    <tr>
                        <th>ردیف</th>
                        <th>تاریخ و زمان تردد</th>
                    </tr>
                </thead>
                <tbody id="modalLogsBody"></tbody>
            </table>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- اضافه کردن اسکریپت Bootstrap برای Modal -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

<script>
// کنترل نمایش/مخفی کردن فیلد پورت
document.getElementById('deviceType').addEventListener('change', function() {
    document.getElementById('portDiv').style.display = (this.value === 'ai09f') ? 'none' : 'block';
});

// فرم اصلی برای دریافت کل اطلاعات
document.getElementById('checkForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const deviceType = document.getElementById('deviceType').value;
    const ip = document.getElementById('ip').value;
    const port = document.getElementById('port').value;
    
    const spinner = document.getElementById('spinner');
    const btn = document.getElementById('btnSubmit');
    const resultArea = document.getElementById('resultArea');
    const statusBadge = document.getElementById('statusBadge');
    
    spinner.style.display = 'inline-block';
    btn.disabled = true;

    try {
        const response = await fetch('/api/check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip, port, deviceType })
        });
        const data = await response.json();
        resultArea.style.display = 'block';
        
        if (data.success) {
            statusBadge.className = 'alert alert-success';
            statusBadge.innerHTML = `✅ <strong>موفق:</strong> ${data.total_users} کاربر و ${data.total_logs} رکورد تردد در سیستم ثبت شده است.`;

            // ساخت جدول کاربران با قابلیت کلیک (افزودن کلاس clickable-row و رویداد onclick)
            let usersHtml = '';
            data.users.forEach((u) => {
                usersHtml += `<tr class="clickable-row" onclick="fetchUserLogs('${u.user_id}', '${u.name}')" title="برای مشاهده تردد ۳۰ روزه کلیک کنید">
                    <td><strong>${u.user_id}</strong></td>
                    <td>${u.name}</td>
                    <td><span class="badge ${u.role.includes('مدیر') ? 'bg-danger' : 'bg-secondary'}">${u.role}</span></td>
                </tr>`;
            });
            document.getElementById('usersTableBody').innerHTML = usersHtml;

            // ساخت جدول آخرین ترددهای عمومی
            let logsHtml = '';
            data.logs.forEach((log, index) => {
                logsHtml += `<tr>
                    <td>${index + 1}</td>
                    <td><strong>${log.user_id}</strong></td>
                    <td>${log.name}</td>
                    <td dir="ltr">${log.timestamp}</td>
                </tr>`;
            });
            document.getElementById('logsTableBody').innerHTML = logsHtml;
        } else {
            statusBadge.className = 'alert alert-danger';
            statusBadge.innerHTML = `❌ <strong>خطا:</strong> ${data.error}`;
            document.getElementById('usersTableBody').innerHTML = '';
            document.getElementById('logsTableBody').innerHTML = '';
        }
    } catch (err) {
        statusBadge.className = 'alert alert-danger';
        statusBadge.innerHTML = `❌ <strong>خطای شبکه:</strong> عدم برقراری ارتباط با سرور.`;
    } finally {
        spinner.style.display = 'none';
        btn.disabled = false;
    }
});

// تابع جدید برای دریافت ترددهای اختصاصی شخص و نمایش در Modal
let userModal = new bootstrap.Modal(document.getElementById('userLogsModal'));

async function fetchUserLogs(userId, userName) {
    // باز کردن پنجره مودال در حالت لودینگ
    document.getElementById('modalTitle').innerText = `تردد ۳۰ روز اخیر: ${userName} (کد: ${userId})`;
    document.getElementById('modalLoading').style.display = 'block';
    document.getElementById('modalContent').style.display = 'none';
    userModal.show();

    const deviceType = document.getElementById('deviceType').value;
    const ip = document.getElementById('ip').value;
    const port = document.getElementById('port').value;

    try {
        const response = await fetch('/api/user_logs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip, port, deviceType, user_id: userId })
        });
        const data = await response.json();

        document.getElementById('modalLoading').style.display = 'none';
        document.getElementById('modalContent').style.display = 'block';

        if (data.success) {
            document.getElementById('modalUserCount').innerText = `تعداد کل ترددهای یافت شده در ماه اخیر: ${data.logs.length} رکورد`;
            
            let modalLogsHtml = '';
            if (data.logs.length === 0) {
                modalLogsHtml = `<tr><td colspan="2" class="text-danger">هیچ ترددی در 30 روز گذشته یافت نشد</td></tr>`;
            } else {
                data.logs.forEach((log, index) => {
                    modalLogsHtml += `<tr>
                        <td>${index + 1}</td>
                        <td dir="ltr" class="fw-bold">${log.timestamp}</td>
                    </tr>`;
                });
            }
            document.getElementById('modalLogsBody').innerHTML = modalLogsHtml;
        } else {
            document.getElementById('modalLogsBody').innerHTML = `<tr><td colspan="2" class="text-danger">${data.error}</td></tr>`;
        }
    } catch (err) {
        document.getElementById('modalLoading').style.display = 'none';
        document.getElementById('modalContent').style.display = 'block';
        document.getElementById('modalLogsBody').innerHTML = `<tr><td colspan="2" class="text-danger">خطا در دریافت اطلاعات</td></tr>`;
    }
}
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/push', methods=['GET', 'POST'])
def receive_push_data():
    """ دریافت اطلاعات از دستگاه AI09F (وب‌هوک) """
    client_ip = request.remote_addr
    payload = request.json or request.form.to_dict() or {}
    if request.method == 'GET' and request.args:
        payload = request.args.to_dict()

    user_id = payload.get('emp_id') or payload.get('user_id') or payload.get('userid') or "نامشخص"
    user_name = payload.get('name') or payload.get('user_name') or payload.get('emp_name') or "نام ثبت‌نشده"
    timestamp = payload.get('verify_time') or payload.get('time') or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if client_ip not in AI09F_USERS:
        AI09F_USERS[client_ip] = {}
    
    AI09F_USERS[client_ip][user_id] = {'user_id': user_id, 'name': user_name, 'role': 'نامشخص (Push)'}

    log_entry = {'user_id': user_id, 'name': user_name, 'timestamp': timestamp}

    if client_ip not in AI09F_LOGS:
        AI09F_LOGS[client_ip] = []
    
    AI09F_LOGS[client_ip].insert(0, log_entry)
    
    # برای اینکه گزارش یک‌ماهه کار کند، محدودیت مموری را به 5000 رکورد افزایش می‌دهیم
    AI09F_LOGS[client_ip] = AI09F_LOGS[client_ip][:5000] 

    return jsonify({"status": "OK"})

@app.route('/api/check', methods=['POST'])
def check_device():
    """ استخراج اولیه کاربران و ۵۰ تردد آخر برای صفحه اصلی """
    data = request.get_json()
    device_type = data.get('deviceType', 'zk')
    ip = data.get('ip')
    
    if device_type == 'ai09f':
        if ip in AI09F_LOGS and len(AI09F_LOGS[ip]) > 0:
            user_list = list(AI09F_USERS.get(ip, {}).values())
            return jsonify({
                'success': True,
                'total_users': len(user_list),
                'total_logs': len(AI09F_LOGS[ip]),
                'users': user_list,
                'logs': AI09F_LOGS[ip][:50]
            })
        else:
            return jsonify({'success': False, 'error': f"اطلاعاتی از دستگاه AI09F با آی‌پی {ip} دریافت نشده است."})

    elif device_type == 'zk':
        port = int(data.get('port', 4370))
        zk = ZK(ip, port=port, timeout=5)
        conn = None
        try:
            conn = zk.connect()
            conn.disable_device()
            
            users = conn.get_users()
            user_dict = {}
            formatted_users = []
            
            for u in users:
                role = "مدیر سیستم" if u.privilege == 14 else "کاربر عادی"
                u_name = u.name if u.name else "بدون نام"
                user_dict[str(u.user_id)] = u_name
                formatted_users.append({'user_id': u.user_id, 'name': u_name, 'role': role})
            
            logs = conn.get_attendance()
            formatted_logs = []
            for log in reversed(logs[-50:]):
                formatted_logs.append({
                    'user_id': log.user_id,
                    'name': user_dict.get(str(log.user_id), 'ناشناس'),
                    'timestamp': str(log.timestamp)
                })

            conn.enable_device()
            conn.disconnect()

            return jsonify({
                'success': True,
                'total_users': len(users),
                'total_logs': len(logs),
                'users': formatted_users,
                'logs': formatted_logs
            })
        except Exception as e:
            if conn:
                try:
                    conn.enable_device()
                    conn.disconnect()
                except: pass
            return jsonify({'success': False, 'error': f"خطا در اتصال: {str(e)}"})

# ------------------------------------------------------------------
# مسیر جدید: استخراج ترددهای اختصاصی شخص در یک ماه گذشته
# ------------------------------------------------------------------
@app.route('/api/user_logs', methods=['POST'])
def get_user_logs():
    data = request.get_json()
    device_type = data.get('deviceType', 'zk')
    ip = data.get('ip')
    target_user_id = str(data.get('user_id'))
    
    # محاسبه زمان دقیق برای 30 روز گذشته
    one_month_ago = datetime.now() - timedelta(days=30)
    filtered_logs = []

    if device_type == 'ai09f':
        # جستجو در حافظه (RAM) برای دستگاه‌های Push
        if ip in AI09F_LOGS:
            for log in AI09F_LOGS[ip]:
                if str(log['user_id']) == target_user_id:
                    try:
                        log_time = datetime.strptime(log['timestamp'], "%Y-%m-%d %H:%M:%S")
                        if log_time >= one_month_ago:
                            filtered_logs.append({'timestamp': log['timestamp']})
                    except:
                        # اگر فرمت تاریخ نامتعارف بود، فیلتر زمانی انجام نمی‌شود
                        filtered_logs.append({'timestamp': log['timestamp']})
        
        return jsonify({'success': True, 'logs': filtered_logs})

    elif device_type == 'zk':
        port = int(data.get('port', 4370))
        zk = ZK(ip, port=port, timeout=5)
        conn = None
        try:
            conn = zk.connect()
            conn.disable_device()
            all_logs = conn.get_attendance() # فراخوانی کل ترددها
            conn.enable_device()
            conn.disconnect()
            
            for log in all_logs:
                # بررسی آیدی شخص و تاریخ تردد
                if str(log.user_id) == target_user_id and log.timestamp >= one_month_ago:
                    filtered_logs.append({'timestamp': str(log.timestamp)})
            
            # مرتب‌سازی نزولی (جدیدترین به قدیمی‌ترین)
            filtered_logs.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return jsonify({'success': True, 'logs': filtered_logs})
            
        except Exception as e:
            if conn:
                try:
                    conn.enable_device()
                    conn.disconnect()
                except: pass
            return jsonify({'success': False, 'error': f"خطا در اتصال به دستگاه: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)