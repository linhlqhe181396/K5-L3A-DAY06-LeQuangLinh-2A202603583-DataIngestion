# Starter · PostgreSQL + pgvector

Bộ khởi động **tùy chọn** cho lab cá nhân. Docker Compose tạo PostgreSQL + pgvector local. Phần đọc/chuẩn hóa PDF, chia chunk và tạo embedding local đã được triển khai; lưu vector, truy xuất, đánh giá và điều phối pipeline vẫn còn TODO. Vẫn có thể chọn Qdrant, Chroma hoặc vector store tương đương theo [GUIDE.md](../GUIDE.md).

## Cấu trúc

```text
starter/
├── docker-compose.yml     # PostgreSQL 16 + pgvector, chỉ mở cổng local
├── init.sql               # bật extension khi tạo database mới
├── requirements.txt       # psycopg, PDF parsing, python-dotenv, Sentence Transformers
├── .env.example           # cấu hình mẫu; copy thành .env
├── scripts/check_setup.py # kiểm tra kết nối và extension (đã chạy được)
├── src/
│   ├── models.py          # cấu trúc dữ liệu mẫu
│   ├── ingestion.py       # trích xuất PDF theo trang / chuẩn hóa văn bản
│   ├── chunking.py        # fixed-size và paragraph chunking
│   ├── embeddings.py      # embedding local bằng Sentence Transformers
│   ├── store.py           # PostgreSQL/pgvector + lọc metadata
│   ├── evaluation.py      # evidence matching và tổng hợp metrics
│   └── run.py             # điều phối ingestion, retrieval và báo cáo
├── data/                  # bạn tự chuẩn bị corpus được phép sử dụng
├── tests/                 # kiểm thử đơn vị
└── results/               # lưu kết quả của bạn
```

## 1. Cài và kiểm tra database

Cần Docker Desktop hoặc Docker Engine + Compose, Python **3.11–3.14**, và mạng để tải image/dependencies lần đầu. Các lệnh sau chạy từ thư mục `starter/`:

```bash
cd starter
python3 -m venv .venv
```

Kích hoạt `.venv`: macOS/Linux dùng `source .venv/bin/activate`; Windows PowerShell dùng `.venv\Scripts\Activate.ps1`. Sau đó:

```bash
python -m pip install -r requirements.txt
# macOS/Linux: cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
```

Kỳ vọng: hiện tên database, phiên bản PostgreSQL và pgvector, sau đó `Setup OK`. Đây **chỉ là kiểm tra hạ tầng**, không phải kết quả benchmark. Docker dùng cổng `127.0.0.1:55433` và mật khẩu cố định **chỉ dùng local cho lab**; nếu cổng bận, sửa đồng thời port trong `docker-compose.yml` và `DATABASE_URL` trong `.env`. `init.sql` chỉ chạy khi volume mới được tạo; nếu database sẵn có chưa bật extension, xem log Docker và kiểm tra cấu hình thay vì xóa volume chứa dữ liệu.

Dừng container nhưng giữ dữ liệu:

```bash
docker compose -p day6_student_starter stop
```

## 2. Chọn embedding model

Model mặc định là `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, chạy local và không cần API key. Lần chạy đầu sẽ tải model, cần mạng và dung lượng đĩa. Nếu chọn provider API thay thế, điền key trong `.env` (không commit file này), tự cài SDK và ghi lại version/lệnh cài trong báo cáo. Ghi tên model và số chiều; dùng cùng model cho toàn bộ chiến lược và vector query tương thích vector document.

## 3. Hoàn thiện pipeline

1. Đặt corpus vào `data/` hoặc cung cấp manifest/hướng dẫn truy cập. Đọc [GUIDE.md](../GUIDE.md) về **30 trang nội dung**, quyền dữ liệu và metadata.
2. Hoàn thiện từng hàm TODO trong `src/`. Lưu ID tài liệu, nguồn, trang/vị trí và ít nhất một trường filter có ích.
3. Xây ít nhất ba cấu hình; ví dụ A fixed-size, B theo đoạn, C như B nhưng có filter. Cần cùng corpus, model và benchmark; nạp lại không nhân đôi và xử lý chunk cũ khi dữ liệu đổi.
4. Bộ benchmark hiện có 20 câu đã tách 15 dev / 5 test và kiểm chứng evidence; xem [benchmark/README.md](benchmark/README.md).
5. Từ thư mục `starter/`, chạy `python -m src.run` để chạy **dev trước**. Pipeline nạp 153 trang đã chọn, tạo chiến lược A (500 ký tự, overlap 50), B (paragraph, tối đa 500 ký tự) và C (cùng chunk/vector B, áp dụng section filter theo câu hỏi), rồi lưu/retrieve bằng pgvector exact cosine search.
6. Chọn cấu hình dựa trên dev và ghi nhận quyết định trước khi chạy `python -m src.run --split test`. Không điều chỉnh chiến lược dựa trên test; nếu chạy `--split all`, hãy coi test đã được xem.
7. Kết quả được lưu trong `results/`: `traces_<split>.jsonl`, `summary_<split>.json` và `manual_assessment_<split>.jsonl`. Summary báo Hit@1, Evidence Hit@3, truy vết metadata, tuân thủ filter, số chunk và thời gian. Template dev có cùng 10 vị trí nguồn cho cả ba chiến lược để chấm coherence; template test có 5 câu test mỗi chiến lược để chấm grounding (thang 0–2). Chấm mỗi vị trí coherence một lần; chạy `--split all` tạo cả hai loại đánh giá trong cùng template. Hai tiêu chí thủ công không được suy ra từ string matching.

Model Sentence Transformers chạy local và không cần API key. Lần đầu có thể cần thời gian để tải model. Lưu code, cấu hình, kết quả và lệnh chạy để người chấm tái lập; không commit key, dữ liệu mật hoặc dữ liệu không có quyền chia sẻ. Kết quả có nội dung trích từ PDF; giữ thông tin attribution CC BY 3.0 IGO của nguồn.
