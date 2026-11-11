<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect.png" alt="Omega-Connect" width="384">
</div>

# 🔗 OMEGA-CONNECT

**Liên kết các ứng dụng của bộ công cụ omega với nhau, trên một máy và trên toàn mạng**

> Được xây dựng bởi [kraynux](https://github.com/kraynux) cho [Omega-Server](https://kraynux.snake-mackarel.ts.net)   

Trang chính thức: [OMEGA-CONNECT](https://kraynux.snake-mackarel.ts.net/omega-connect/translation/vi/) &nbsp; Xem trước: [Ảnh chụp màn hình](https://kraynux.snake-mackarel.ts.net/omega-connect/screenshots/)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-TUI%20%2B%20Textual-cyan.svg)](https://github.com/Textualize/textual)

🌐 Giao diện có sẵn bằng **17 ngôn ngữ** — xem [Ngôn ngữ giao diện](#ngôn-ngữ-giao-diện).  
**Ngôn ngữ:**  
<img src="https://flagcdn.com/w20/fr.png" alt="Français" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**Omega-connect** là bộ kết nối của bộ công cụ `omega-`: nó tìm các ứng dụng omega đã cài đặt (omega-serv, omega-fire, omega-jail…) trên máy này và trên các máy trong mạng của bạn, cho thấy những gì đã liên kết với nhau hay chưa, và khôi phục những gì còn thiếu — luôn cho thấy trước những gì nó sẽ làm. Khi đã được liên kết, các ứng dụng tự tìm thấy nhau mà không cần omega-connect đang chạy.

<p align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/vi/omega-connect/A.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/vi/omega-connect/B.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/vi/omega-connect/C.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/vi/omega-connect/D.png" width="24%" />
</p>

## 1. Tầm nhìn và phạm vi

Các ứng dụng omega được tạo ra để làm việc cùng nhau: nhật ký của omega-serv được các jail của omega-jail đọc, các lệnh cấm của fail2ban được đưa vào danh sách đen của omega-serv, omega-fire hiển thị tất cả những điều đó. Nhưng điều đó chỉ xảy ra khi các tệp nằm đúng chỗ, có đúng quyền, và mỗi ứng dụng biết các ứng dụng khác ở đâu. Omega-connect đảm nhận việc này.

### Những gì Omega-connect làm

- Tìm các ứng dụng omega trên máy này (thư mục cá nhân, dịch vụ systemd, OpenRC hoặc runit, `/srv`, sổ đăng ký instance của omega-serv) và trên các máy khác, kết nối qua SSH bằng khóa của bạn.
- Duy trì một **sổ đăng ký** gồm mọi ứng dụng trên mọi máy, kèm phiên bản và trạng thái của chúng.
- Kiểm tra từng **liên kết** giữa các ứng dụng (nhật ký được các jail đọc, cầu nối tới danh sách đen, danh sách được bảo vệ, các tệp của omega-jail trong fail2ban, thẻ định danh, không gian chia sẻ) và cho biết điều gì không ổn.
- **Đồng bộ hóa**: tạo các thẻ định danh còn thiếu và chuẩn bị **không gian chia sẻ**, nơi các ứng dụng tìm thấy nhau.
- **Sửa chữa**: để chính ứng dụng sở hữu tệp khắc phục từng sai lệch; omega-connect không bao giờ làm thay.
- **Cập nhật hoặc cài đặt lại** một ứng dụng quá cũ hoặc cài đặt sai trên một máy trong mạng, từ bản Release GitHub của nó (mã băm được kiểm tra).
- Thao tác trên một máy trong mạng **từ máy của bạn**: không cần gõ gì ở máy đó, mật khẩu của nó được chính nó hỏi một lần.
- Tạo một **báo cáo** đầy đủ (văn bản, JSON hoặc trang HTML).

### Những gì Omega-connect không làm

- Nó không thay thế ứng dụng nào: fail2ban, omega-fire, omega-jail và omega-serv mỗi cái giữ vai trò riêng.
- Nó không bao giờ viết lại tệp của một ứng dụng khác.
- Nó không cài đặt gì lâu dài trên một máy trong mạng để quét máy đó, và không để lại dịch vụ nào chạy.
- Nó không bao giờ hỏi mật khẩu SSH, và không bao giờ nhìn thấy mật khẩu quản trị của bạn.

## 2. Cài đặt

### Điều kiện tiên quyết

- Linux, Python 3.10+.
- Với các máy trong mạng: truy cập SSH bằng khóa, và Python 3.10+ trên các máy đó.
- Kết nối Internet cho các phụ thuộc (và cho việc cập nhật từ GitHub).

### Cài đặt

Từ thư mục chứa bản lưu trữ:

```bash
tar -xzf omega-connect-0.1.0.tar.gz
cd omega-connect/
./install.sh
```

`install.sh`:

1. Tạo môi trường ảo `.venv` (một `.venv` không đầy đủ sẽ được để sang một bên và tạo lại).
2. Cài đặt omega-lib (thư viện của bộ công cụ, có sẵn trong bản lưu trữ) và omega-connect.
3. Cấp quyền thực thi cho `omega-connect.sh` và `install.sh`.
4. Thêm alias `connect` vào `~/.bashrc` và `~/.zshrc` (không trùng lặp).

Không bước nào yêu cầu quyền quản trị.

### Cập nhật

Từ thư mục CHỨA `omega-connect/` (không bao giờ từ bên trong: `tar` sẽ tạo ra một thư mục lồng nhau), giải nén bản lưu trữ mới đè lên, rồi chạy lại `install.sh`. Bản lưu trữ không chứa dữ liệu cục bộ nào (`var/`: sổ đăng ký máy, thiết lập, bản xuất): không có gì hiện có bị ghi đè.

```bash
tar -xzf omega-connect-<version>.tar.gz
cd omega-connect/
./install.sh
```

## 3. Sử dụng

### Chế độ tương tác (TUI)

```bash
./omega-connect.sh
```

hoặc, nếu alias đã được tạo, `connect`.

Menu chính có hai cột:

| Quản lý | Bảo trì |
|---|---|
| **Sổ đăng ký** — mọi ứng dụng trên mọi máy, phiên bản và trạng thái của chúng | **Sửa chữa** — danh sách mọi thứ đang có vấn đề, và bạn chọn |
| **Quét** — máy này, và thêm các máy trong mạng | **Báo cáo** — một tài liệu đầy đủ, để xuất |
| **Liên kết** — những gì đã liên kết hay chưa, kèm trạng thái | **Thiết lập** — ngôn ngữ, giao diện, thư mục, dọn dẹp |
| **Đồng bộ hóa** — liên kết các ứng dụng, trên mọi máy | **Trợ giúp** — từng menu, chức năng và chi tiết |
| **Bảng điều khiển** — cái nhìn tổng quan | **Thoát** |

Quy trình điển hình: **Quét** (máy này, rồi các máy khác của bạn, được đề xuất dựa trên hồ sơ Unison, `~/.ssh/config` và `known_hosts` của bạn) → **Sổ đăng ký** (cập nhật hoặc cài đặt lại một ứng dụng cũ) → **Đồng bộ hóa** (đánh dấu, rồi đồng bộ) → **Liên kết** và **Bảng điều khiển** để xem kết quả → **Sửa chữa** nếu vẫn còn sai lệch.

Mỗi hành động đều hiển thị kế hoạch trước; không có gì được chạy trước khi bạn đồng ý. Với một máy trong mạng, giao diện nhường chỗ cho terminal trong thời gian thực hiện: chính máy đó hỏi mật khẩu của nó, một lần.

#### Phím tắt

| Phím | Hành động |
|---|---|
| `↑` / `↓` | Chuyển từ mục này sang mục khác |
| `Tab` / `Shift+Tab` | Chuyển từ vùng này sang vùng khác của màn hình |
| `Enter` / `Space` | Kích hoạt; đánh dấu một dòng (Đồng bộ hóa) |
| `Esc` | Quay lại màn hình trước |
| `a` | Trợ giúp |
| `s` | Thiết lập |
| `t` | Giao diện tiếp theo |
| `r` | Vẽ lại màn hình |
| `q` | Thoát (có xác nhận) |
| `Ctrl+P` | Lệnh: giao diện, chụp màn hình, thoát |

### Trạng thái

| Ứng dụng | Liên kết |
|---|---|
| ● Đã liên kết — có trong không gian chia sẻ, đã cập nhật | OK |
| ◐ Đã đăng ký — có thẻ định danh, chưa có trong không gian chia sẻ | cần sửa |
| ○ Đã phát hiện — chưa có thẻ định danh | cần sửa (gây chặn) |
| ▲ Cần sửa — có một sai lệch | không có — không có gì để liên kết |
| ◌ Phiên bản cũ — cần cập nhật | không kiểm tra được |
| ◇ Cài đặt dở dang — cần cài đặt lại | |
| ✕ Không liên lạc được — máy không còn phản hồi | |

### Ngôn ngữ giao diện

Giao diện có sẵn bằng 17 ngôn ngữ: tiếng Pháp, tiếng Anh, tiếng Tây Ban Nha, tiếng Bồ Đào Nha (Brazil), tiếng Ý, tiếng Đức, tiếng Hà Lan, tiếng Ba Lan, tiếng Nga, tiếng Trung giản thể, tiếng Việt, tiếng Thái, tiếng Indonesia, tiếng Nhật, tiếng Hàn, tiếng Hindi và tiếng Ả Rập. Ngôn ngữ được chọn trong Thiết lập (« Langue / Language », nhãn này không bao giờ được dịch) và được áp dụng sau khi khởi động lại giao diện; biến `OMEGA_CONNECT_LANG` (ví dụ `OMEGA_CONNECT_LANG=en ./omega-connect.sh`) buộc dùng một ngôn ngữ trong một phiên. Trong console văn bản Linux (TTY), các ngôn ngữ có chữ viết không phải Latinh được hiển thị bằng tiếng Anh trong phiên đó. Dòng lệnh vẫn bằng tiếng Pháp.

### Liên hệ và hỗ trợ

Trợ giúp (phím `a`) có màn hình **Liên hệ và hỗ trợ**: *Mời một ly cà phê* (trang PayPal của nhà phát triển), *Liên hệ hỗ trợ* (địa chỉ thư và biểu mẫu liên hệ của trang web, hiển thị rõ ràng), *Khai báo là người dùng (ẩn danh)* và *Kiểm tra cập nhật*. Việc khai báo là tự nguyện, tắt theo mặc định và chỉ gửi một lần: chỉ dùng để đếm số người dùng và, nếu muốn, châu lục hoặc quốc gia của họ (danh sách đóng, không bao giờ có văn bản tự do). Nội dung gửi gồm một khóa ngẫu nhiên, tên phần mềm (`omega-connect`) và phiên bản của nó; không bao giờ gửi tên, tên máy, địa chỉ hay thiết lập. Địa chỉ IP không được ghi trong các khai báo, nhưng như mọi lượt truy cập, nó đi qua các kiểm tra bảo mật và nhật ký của máy chủ nhận. Có thể rút lại bất cứ lúc nào từ cùng màn hình đó. Việc kiểm tra cập nhật chỉ đọc danh sách các phiên bản đã phát hành, và không bao giờ diễn ra nếu bạn không nhấp.

### Chế độ viết script (CLI)

Bất kỳ lệnh nào cũng kích hoạt chế độ dòng lệnh:

```bash
# Ứng dụng của máy này, hoặc của một máy trong mạng (SSH bằng khóa của bạn)
./omega-connect.sh scanner
./omega-connect.sh scanner moi@192.168.1.109

# Liên kết các ứng dụng của máy này, hoặc của một máy trong mạng
./omega-connect.sh synchroniser
./omega-connect.sh synchroniser --machine moi@192.168.1.109

# Cập nhật các ứng dụng quá cũ của một máy trong mạng (Release GitHub)
./omega-connect.sh mettre-a-jour --machine moi@192.168.1.109

# Sửa chữa: máy này, hoặc một máy trong mạng
./omega-connect.sh reparer --machine moi@192.168.1.109

# Trạng thái của từng liên kết, và báo cáo đầy đủ
./omega-connect.sh verifier
./omega-connect.sh rapport --format html --enregistrer
```

`--simulation` hiển thị kế hoạch mà không chạy gì; `--oui` chạy mà không hỏi; `--toutes-machines` xử lý lần lượt mọi máy đã biết, từng máy một.

## 4. Máy trong mạng

- **Kết nối:** chỉ SSH bằng khóa của bạn; `~/.ssh/config` được tôn trọng (alias, cổng, người dùng). Một khóa được bảo vệ bằng cụm mật khẩu phải được nạp vào SSH agent.
- **Lần kết nối đầu tiên:** dấu vân tay khóa của máy được hiển thị trước mọi thứ; một khóa đã thay đổi sẽ bị từ chối.
- **Quét:** một chương trình được gửi vào bộ nhớ, ở chế độ chỉ đọc; không cài đặt hay ghi gì, không hỏi mật khẩu nào.
- **Hành động** (đồng bộ, sửa chữa, cập nhật): một thư mục riêng tạm thời nhận chương trình và, nếu cần, các bản lưu trữ; thư mục này bị xóa khi kết thúc. Mật khẩu quản trị do chính máy đó hỏi, một lần.
- **Định danh:** một máy được nhận diện qua dấu vân tay của mã định danh hệ thống, không phải qua địa chỉ: dù được kết nối qua hai mạng, nó vẫn là một máy duy nhất.
- **Cập nhật:** từ bản Release GitHub của từng ứng dụng; mã băm của bản lưu trữ được kiểm tra với `sha.txt` trước mọi lần gửi, rồi kiểm tra lại trên máy. Mỗi ứng dụng được cài đặt đúng như mục « Cập nhật » trong README của nó.

## 5. Thẻ định danh và không gian chia sẻ

- **Thẻ định danh:** khi được cài đặt, mỗi ứng dụng omega ghi một tệp nhỏ cho biết nó là ai (ứng dụng, phiên bản, mã định danh, máy). Mọi người đều đọc được, các tài khoản khác không bao giờ sửa được.
- **Không gian chia sẻ:** `/var/lib/omega-synchro`, dành riêng cho nhóm `omega-synchro`, nơi chỉ quản trị viên được ghi. Omega-connect sao chép vào đó thẻ định danh và mô tả của từng ứng dụng; các ứng dụng tìm thấy nhau ở đó, ngay cả khi omega-connect không chạy.
- **Sổ đăng ký của không gian chia sẻ:** mọi thứ omega-connect tạo ra đều được ghi vào đó; việc gỡ bỏ chỉ hoàn tác những gì đã được ghi trong đó, và một tệp không rõ nguồn gốc không bao giờ bị xóa.

## 6. Bảo mật

- Không nâng quyền khi khởi chạy: omega-connect chạy dưới tài khoản của bạn; sudo được yêu cầu theo từng hành động, lệnh được hiển thị trước.
- Các sửa chữa do ứng dụng sở hữu tệp thực hiện (omega-jail cho những gì nó đặt vào fail2ban, omega-serv cho quyền của `var/` của nó, mỗi ứng dụng cho thẻ định danh của mình).
- Không ứng dụng nào được khởi chạy nếu nó có thể hỏi mật khẩu khi không có terminal.
- Việc tìm kiếm không bao giờ đi theo liên kết tượng trưng, không chuyển sang hệ thống tệp khác và bỏ qua các điểm gắn kết mạng.
- Việc dọn dẹp thư mục xuất và thư mục ảnh chụp từ chối các thư mục hệ thống, thư mục cá nhân và thư mục của omega-connect.

## 7. Bản xuất

- **Báo cáo**: tổng kết mọi máy, danh sách chính xác những việc còn phải làm, sổ đăng ký, các máy trong mạng, liên kết của từng máy, không gian chia sẻ. Văn bản, JSON hoặc trang HTML (giao diện tùy chọn).
- **Trợ giúp**: có thể xuất thành trang HTML.
- **Ảnh chụp màn hình**: `Ctrl+P` → « Chụp màn hình » (SVG).
- Thư mục mặc định: `var/exports/` và `var/screenshots/` trong thư mục của omega-connect, có thể thay đổi trong Thiết lập.

## 8. Kiến trúc

Clean Architecture, giống phần còn lại của bộ công cụ: `domain/` (quy tắc thuần), `application/` (ca sử dụng), `ports/`, `infrastructure/` (SSH, tệp, GitHub, bộ nhớ tạm), `interfaces/` (dòng lệnh và giao diện Textual), `app/` (lắp ráp). Các phụ thuộc luôn hướng vào trong, được kiểm tra bằng `import-linter`. Các hợp đồng dùng chung giữa các ứng dụng (thẻ định danh, mô tả, không gian chia sẻ) nằm trong `omega-lib`.

## 9. Kiểm thử

```bash
source .venv/bin/activate
lint-imports        # kiểm tra quy tắc phụ thuộc
pytest -q
ruff check src tests
mypy src
```

Các bài kiểm thử không bao giờ chạm vào `var/` thật, cũng không chạm vào mạng hay sudo: SSH giả chạy cục bộ, GitHub giả, thư mục tạm.

## 10. Ngoài phạm vi

- Thay thế fail2ban, omega-fire hoặc omega-jail.
- Giám sát liên tục (không có dịch vụ thường trực).
- Cài đặt một ứng dụng omega lần đầu tiên trên một máy trong mạng.
- Bảng điều khiển web.

## Giấy phép

MIT — xem [LICENSE](../../../LICENSE).

---

> Omega-connect — Tìm, liên kết, sửa chữa.
> Các ứng dụng omega trò chuyện với nhau; omega-connect đảm bảo chúng có thể làm vậy.
