# Báo cáo cá nhân — Day 6

> **Tình trạng audit thủ công:** Các kết quả retrieval bên dưới được đo bằng
> pipeline. Coherence và grounding có đề xuất điểm AI trong
> `starter/results/assessment_suggestions_test.jsonl`, nhưng học viên chưa xác
> nhận độc lập. Không trình bày các đề xuất này như nhãn chấm thủ công hoàn tất.

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:** Báo cáo World Bank
  *Demographic Change in South Asia: From Tailwinds to Headwinds for
  Development* (2026), DOI
  [10.1596/978-1-4648-0959-0](https://doi.org/10.1596/978-1-4648-0959-0),
  CC BY 3.0 IGO; cần attribution, và third-party material có thể có quyền
  riêng. PDF có 204 trang vật lý, 199 trang trích được text. Chọn 153 trang
  nội dung theo khoảng trang vật lý 17–26, 31–44, 47–92, 101–142, 151–191;
  loại front matter, trang xen giữa, notes/references và back matter. Cả 153
  trang đã chọn đều có text; tổng cộng 428,687 ký tự chuẩn hóa. Chi tiết ở
  [manifest](../../starter/data/manifest.csv),
  [benchmark README](../../starter/benchmark/README.md) và
  [page inventory](../../starter/results/my_document_page_inventory.csv).
- **Chuẩn hóa, lỗi và giới hạn:** pypdf trích xuất theo trang; chuẩn hóa Unicode
  NFC, bỏ NUL, chuẩn hóa khoảng trắng và giữ dòng/đoạn; ghi trạng thái và số ký
  tự từng trang. Trang 2, 28, 30, 150, 203 không có text trích xuất; chúng
  không nằm trong corpus chọn và không dùng OCR. Trích xuất PDF có thể làm hỏng
  ký tự và nội dung biểu đồ/bảng; pipeline dùng text, không diễn giải hình ảnh.
- **Embedding/store/metric/chạy/chi phí:** Sentence Transformers chạy local,
  model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384
  chiều; normalize vector và dùng cùng đường encode cho query/document.
  Requirements khai báo `sentence-transformers>=5.7,<6`. Store là PostgreSQL
  16.16 + pgvector 0.8.7, Docker Compose service `postgres`, local port 55433,
  DB `day6_lab`, bảng `ingestion_chunks`; tìm kiếm exact cosine distance.
  Lệnh từ `starter/`: `python -m src.run` (dev) và
  `python -m src.run --split test`. Không gọi embedding API trả phí, API spend
  là $0; không tính chi phí điện/phần cứng. Python runtime ghi nhận là 3.10.0,
  thấp hơn 3.11–3.14 khuyến nghị trong starter README; cần lưu ý khi tái lập.
- **Metadata:** Mỗi chunk có `document_id`, `source`, `page`, text và JSONB
  metadata. `section` lấy từ bảng nội dung và khoảng trang vật lý đã ghi trong
  benchmark README; dùng để lọc chương khi câu hỏi đưa filter trước truy vấn.
  Đây là metadata cấp trang, không phân biệt chủ đề nhỏ trong chương. Không
  dùng gold source hoặc đáp án làm query/filter.

## Cấu hình và benchmark

- **A:** fixed-size 500 ký tự, overlap 50, không filter.
- **B:** gom theo paragraph, giới hạn 500 ký tự, không filter.
- **C:** cùng chunks và vectors với B; chỉ áp dụng `section` filter khi câu hỏi
  có filter, còn lại không lọc. A–B thay chunking; B–C chỉ thay filter.
- **Benchmark:** 20 câu (15 dev / 5 test), 8 câu có section filter (5 dev,
  3 test). Evidence quote được kiểm tra với trang gold sau chuẩn hóa; câu hỏi,
  split và evidence ở
  [questions.jsonl](../../starter/benchmark/questions.jsonl).
- **Tiêu chí chọn trước khi xem test:** Tối đa Evidence Hit@3 trên dev; nếu hòa,
  ưu tiên tuân thủ filter khi câu hỏi yêu cầu. B và C hòa trên dev; dùng C cho
  câu có filter vì C giới hạn phạm vi chính xác. Quy tắc được ghi trong
  [selection_rule.txt](../../starter/results/selection_rule.txt) trước khi
  test chạy; không thay đổi cấu hình dựa trên test.
- **Nhật ký:** Các cấu hình, giả thuyết và kết quả ở
  [experiment_log.csv](../../artifacts/experiment_log.csv). Giả thuyết được
  ghi hồi cứu sau các lần chạy, không tuyên bố đã đăng ký trước.

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Embedding / upsert (s) | API cost |
|---|---|---:|---:|---:|---:|
| A | dev | 5/15 | 6/15 | 1,015 | 83.95 / 0.92 | $0 |
| B | dev | 4/15 | 8/15 | 987 | 91.74 / 3.88 | $0 |
| C | dev | 4/15 | 8/15 | 987 | 0 additional / 2.30 | $0 |
| A | test | 2/5 | 2/5 | 1,015 | 79.08 / 0.93 | $0 |
| B | test | 1/5 | 2/5 | 987 | 79.67 / 0.92 | $0 |
| C | test | 1/5 | 2/5 | 987 | 0 additional / 0.70 | $0 |

Đây là thời gian local wall-clock cho embedding và upsert, phụ thuộc máy và
điều kiện chạy; không đo riêng extraction/chunking. C tái sử dụng vectors của
B. Thời gian load model và encode query nằm trong các file summary. Kết quả và
top-3 trace: [dev summary](../../starter/results/summary_dev.json),
[test summary](../../starter/results/summary_test.json),
[dev traces](../../starter/results/traces_dev.jsonl),
[test traces](../../starter/results/traces_test.jsonl).

| Strategy | Coherence trung bình /2 (n) — AI đề xuất | Metadata consistency, kiểm tra tự động (n/N) | Filter compliant | Grounding score AI đề xuất (0/1/2; mean /2) |
|---|---:|---:|---:|---:|
| A | 1.3 (10) | 15/15 test top-3 records | N/A | 0/0/5; 2.0 |
| B | 1.6 (10) | 15/15 test top-3 records | N/A | 0/0/5; 2.0 |
| C | 1.6 (10) | 15/15 test top-3 records | 3/3 test filtered questions; 9/9 returned chunks | 0/0/5; 2.0 |

Các điểm ở bảng này là đề xuất AI, **không phải nhãn thủ công đã được học viên
xác nhận**. Công cụ: Copilot AI assistant trong VS Code. Cách tạo đề xuất: so
sánh chunk/evidence top-3 với rubric 0–2, xét chunk có tự đủ nghĩa hay không và
evidence có đủ hỗ trợ câu hỏi/truy được nguồn hay không; đã đối chiếu với trace
và evidence excerpt nhưng chưa được học viên xác nhận, không dùng như độ chính
xác của câu trả lời LLM. Xem từng lý do và xác nhận/chỉnh trong
[dev coherence template](../../starter/results/manual_assessment_dev.jsonl)
và [test grounding template](../../starter/results/manual_assessment_test.jsonl).
Chi tiết đề xuất tại
[assessment_suggestions_test.jsonl](../../starter/results/assessment_suggestions_test.jsonl).

Coherence dùng cùng 10 vị trí nguồn cho A/B/C trên trang vật lý 17, 38, 53,
61, 70, 86, 121, 127, 138, 188; các vị trí được chọn bằng cách lấy đều trên
các trang có đoạn text đủ dài, rồi tìm chunk chứa cùng excerpt. Mẫu được tạo
sau retrieval, không preregister. Test grounding dùng cả 5 câu test cho mỗi
strategy. Kiểm tra tự động `document_id`, `source`, `page`, `section` đối chiếu
bảng trang/section thấy 45/45 bản ghi test nhất quán và truy vết được; đây
không thay thế audit thủ công. C filter compliance là 5/5 câu dev và 3/3 câu
test; tất cả chunks trả về đều đúng filter (15/15 dev, 9/9 test). Metadata
giúp truy vết và thu hẹp chương, nhưng `section` cấp trang còn thô.

## Phân tích và kết luận

- **A–B:** Trên dev, B tăng Evidence Hit@3 từ 6/15 lên 8/15 nhưng Hit@1 giảm
  từ 5/15 xuống 4/15. Test có Evidence Hit@3 bằng nhau (2/5), A có Hit@1 2/5
  so với 1/5 của B. Điểm coherence AI đề xuất là 1.3/2 cho A và 1.6/2 cho B,
  cần học viên xác nhận. B có ít chunks hơn (987 so với 1,015), nhưng thời gian
  embed/upsert đo được không thấp hơn A.
- **B–C:** Cùng chunks và vectors; chỉ thêm filter. Metrics retrieval tổng thể
  bằng nhau trên dev và test. Khi câu hỏi cung cấp chương, C tuân thủ ở 5/5
  dev và 3/3 test; B không giới hạn kết quả theo chương. Chọn C khi cần phạm
  vi section; không có lý do cho rằng C cải thiện unfiltered query.
- **Ví dụ lỗi q05:** Câu hỏi hỏi tỉ lệ working-age peak trong Chapter 1; top-3
  có evidence tương đương “about 69 percent in 2034” ở trang vật lý 37, trong
  khi gold page là 33. Metric strict source/page/evidence tính là miss, dù
  câu trả lời có hỗ trợ từ trang khác. Đây là giới hạn gold một trang.
- **Ví dụ lỗi q16:** Gold page là 101, nhưng top-3 không có trang 101. C vẫn
  lọc đúng Chapter 3 và trả về trang 103 với số liệu 64% về disease burden,
  nhưng không khớp gold page/quote; metric strict tính là miss dù có thể là
  evidence tương đương.
- **Lựa chọn và đánh đổi:** Theo quy tắc đã ghi trước test, chọn C khi câu hỏi
  có filter. A có top-1 nhỉnh hơn trong 5 câu test; mẫu nhỏ không đủ kết luận
  A tốt hơn nói chung. Với truy vấn không filter, B/C dùng cùng chunk/vector.
- **Giới hạn và cải tiến:** Test chỉ có 5 câu; không suy rộng ra ngoài corpus.
  Strict metric không tự chấp nhận trang/evidence thay thế nếu chưa ghi trong
  gold. PDF có thể lỗi OCR/biểu đồ; thời gian phụ thuộc phần cứng; manual
  assessment còn cần học viên xác nhận. Nếu làm lại: preregister mẫu coherence,
  kiểm chứng gold thay thế trước test, tăng kích thước test chưa dùng để tune,
  và đo riêng extraction/chunking/storage. Lần test đầu timeout vì Compose DB
  đang dừng; khởi động lại service hiện có, `check_setup.py` đạt, sau đó test
  chạy thành công.

## Tái lập và attribution

Từ `starter/`, cài `requirements.txt`, cấu hình `.env` từ `.env.example`, chạy
`docker compose -p day6_student_starter up -d --wait`, rồi
`python -m src.run` và `python -m src.run --split test`. 12 unit tests đã pass.
Adapted from Pradhan et al. (2026), World Bank, CC BY 3.0 IGO; third-party
content may have separate rights.
