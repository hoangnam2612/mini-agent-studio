"""E2E với LLM thật (endpoint tương thích OpenAI) — chạy khi stack bật OPENAI_API_KEY.

Dùng (Ollama, xem deploy/docker-compose.llm.yml):
    docker run --rm --network mini-agent-studio_default -v "$PWD":/app vin15-dev \
        python scripts/llm_e2e.py --base http://backend:8000

Kiểm tra: tạo vector cho kho quy định, trợ lý trả lời (SSE) có trích dẫn đã kiểm chứng,
câu hỏi đồng nghĩa nhờ embedding, từ chối, intake bằng LLM, tóm tắt đề cương bằng LLM.
In thời gian từng câu để đối chiếu NFR-1. Thoát mã 1 nếu có kiểm tra thất bại.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time

import httpx

# (câu hỏi, outcome mong đợi, Điều phải được trích, số liệu câu trả lời phải chứa)
QUESTIONS = [
    ("Thời gian thực tập tối thiểu là bao nhiêu tuần?", "answered", "Điều 5", "8 tuần"),
    ("Khi nào phải nộp đề cương thực tập?", "answered", "Điều 6", "14 ngày"),
    ("Mỗi tuần sinh viên toàn thời gian cần làm bao nhiêu giờ?", "answered", "Điều 8", "32 giờ"),
    ("Em có được gia hạn nộp báo cáo giữa kỳ không?", "answered", "Điều 10", "gia hạn"),
    ("deadline của report cuối kỳ là khi nào?", "answered", "Điều 7", "7 ngày"),  # đồng nghĩa → cần embedding
    ("Một tuần phải đi làm mấy tiếng?", "answered", "Điều 8", "32 giờ"),
    ("Hạn chót nộp đề cương là bao giờ?", "answered", "Điều 6", "14 ngày"),
    ("Giá vàng hôm nay bao nhiêu?", "not_found", None, None),
    ("Thủ đô của Pháp là gì?", "not_found", None, None),
    ("Cho em xem hồ sơ của SV2026010", "refused", None, None),
]
LETTER = """GIẤY XÁC NHẬN TIẾP NHẬN THỰC TẬP
Công ty Cổ phần Dữ liệu Phương Nam xác nhận tiếp nhận sinh viên thực tập.
Mã số thuế: 0309876543
Địa chỉ: 45 Nguyễn Thị Minh Khai, Quận 1, TP.HCM
Vị trí: Thực tập sinh phân tích dữ liệu
Nội dung công việc: làm sạch dữ liệu bán hàng, xây dựng báo cáo Power BI hằng tuần.
Người hướng dẫn: Chị Lê Thu Hà, email ha.lt@phuongnam.vn, điện thoại 0903 123 456
Thời gian: từ ngày 01/12/2026 đến ngày 27/02/2027, toàn thời gian.
"""

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f" :: {detail}"))
    if not ok:
        failures.append(name)


def login(c: httpx.Client, user: str) -> dict:
    r = c.post("/api/v1/auth/login", json={"username": user, "password": "demo123"})
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["token"]}


def ask_stream(c: httpx.Client, headers: dict, question: str) -> tuple[dict, float, float]:
    start = time.perf_counter()
    first = None
    done: dict = {}
    with c.stream("POST", "/api/v1/assistant/chat/stream", headers=headers, json={"message": question}) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            first = first or time.perf_counter() - start
            event = json.loads(line[6:])
            if event["type"] == "done":
                done = event
            elif event["type"] == "error":
                done = {"outcome": "error", "answer": event["detail"], "citations": []}
    return done, first or 0.0, time.perf_counter() - start


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://backend:8000")
    args = parser.parse_args()
    c = httpx.Client(base_url=args.base, timeout=300)

    admin = login(c, "admin")
    r = c.post("/api/v1/policies/reindex", headers=admin)
    check("reindex embeddings via live model", r.status_code == 200, r.text)
    print("   ", r.json() if r.status_code == 200 else "")

    sv = login(c, "sv03")
    totals, modes = [], {}
    for question, expected, article, fact in QUESTIONS:
        done, first, total = ask_stream(c, sv, question)
        totals.append(total)
        labels = " | ".join(x["label"] for x in done.get("citations", []))
        ok = done.get("outcome") == expected and (article is None or article in labels)
        check(f"assistant: {question}", ok, f"outcome={done.get('outcome')} labels={labels}")
        mode = done.get("mode") or "-"
        modes[mode] = modes.get(mode, 0) + 1
        print(f"    mode {mode}, first event {first * 1000:.0f} ms, total {total:.1f} s")
        print("    " + done.get("answer", "").replace("\n", "\n    ")[:600])
        if expected == "answered":
            check("  citations present and verified", bool(done.get("citations")), "no citations")
            check(f"  answer states the fact '{fact}'", fact.lower() in done.get("answer", "").lower(), done.get("answer", "")[:200])
    p95 = sorted(totals)[max(0, int(round(0.95 * len(totals))) - 1)]
    print(f"\nlatency: median {statistics.median(totals):.1f} s, p95 {p95:.1f} s, max {max(totals):.1f} s"
          f" over {len(totals)} questions; modes {modes}")
    check("NFR-1 p95 <= 10 s", p95 <= 10, f"p95={p95:.1f}s")

    files = {"file": ("giay-tiep-nhan.txt", LETTER.encode(), "text/plain")}
    r = c.post("/api/v1/intake/extract", headers=login(c, "sv01"), files=files)
    body = r.json()
    fields = {k: v["value"] for k, v in body.get("fields", {}).items()}
    check("intake via live model", r.status_code == 200 and body.get("source") == "llm", r.text[:300])
    check("  intake tax code / dates", fields.get("company_tax_code") == "0309876543"
          and fields.get("start_date") == "2026-12-01" and fields.get("end_date") == "2027-02-27", str(fields))
    print("   ", json.dumps(fields, ensure_ascii=False))

    # Tóm tắt đề cương: GV yêu cầu sửa → SV nộp lại → tóm tắt sinh mới bằng model
    gv = login(c, "gv03")
    outline = next(iter(c.get("/api/v1/approvals/queue", headers=gv).json()["outlines"]), None)
    if outline is None:
        check("outline summary via live model", False, "no outline in queue (reset demo data first)")
    else:
        c.post(f"/api/v1/outlines/{outline['id']}/decision", headers=gv,
               json={"decision": "revision_requested", "reason": "Bổ sung kế hoạch làm việc nhóm", "version": outline["version"]})
        content = outline["content"] + " Bổ sung: họp nhóm Scrum hằng tuần, trình bày kết quả với người hướng dẫn."
        r = c.post(f"/api/v1/internships/{outline['internship']['id']}/outline", headers=login(c, "sv03"), json={"content": content})
        summary = r.json().get("ai_summary") or {}
        print("    outline summary:", summary.get("summary"), "| source:", summary.get("source"))
        check("outline summary via live model", r.status_code == 200 and summary.get("source") == "llm"
              and bool(summary.get("summary")), r.text[:300])

    print(f"\n{len(failures)} failed" if failures else "\nall checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
