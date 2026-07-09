# Module: `routers`

Router xác thực (auth) đứng tách khỏi `api/routes`: xử lý OAuth 2.0 Microsoft, đăng ký/đăng nhập username-password, JWT + refresh token, và quản lý hồ sơ user. Được gắn vào app với prefix `/auth`.

## Files

### `__init__.py`
File rỗng (chỉ đánh dấu package).

### `auth.py`
Định nghĩa toàn bộ endpoint `/auth/*`: OAuth Microsoft, đăng ký/đăng nhập thủ công, rotate token, và CRUD hồ sơ user; chỉ chấp nhận email `@sis.hust.edu.vn` cho luồng OAuth.
- `login_oauth()` — trả về URL uỷ quyền Microsoft để frontend redirect.
- `callback()` — xử lý callback OAuth: đổi code lấy token, validate domain HUST, upsert user, phát refresh cookie rồi redirect.
- `register()` / `login()` — đăng ký và đăng nhập bằng username/password (bcrypt), phát JWT.
- `refresh()` — rotate refresh token (cookie web hoặc token mobile) và cấp access token mới.
- `get_me()` / `update_me()` — xem và cập nhật hồ sơ user hiện tại (yêu cầu Bearer JWT).
- `create_admin()` — tạo tài khoản admin, chỉ superadmin (theo `SUPERADMIN_USER_IDS`) được gọi.
