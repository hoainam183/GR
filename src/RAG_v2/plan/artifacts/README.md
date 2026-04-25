# 📁 Plan Artifacts

Thư mục này chứa tất cả kế hoạch và tài liệu kỹ thuật được tạo bởi Antigravity agent.

## Cấu trúc

```
plan/artifacts/
├── README.md                 ← File này
├── implementation_plan.md    ← Kế hoạch triển khai hiện tại (do agent tạo)
├── task.md                   ← TODO list đang thực hiện (do agent cập nhật)
├── walkthrough.md            ← Tóm tắt sau khi hoàn thành (do agent tạo)
└── archive/                  ← Plans cũ đã hoàn thành
```

## Quy tắc đặt tên

| Loại file | Pattern | Ví dụ |
|-----------|---------|-------|
| Implementation plan | `implementation_plan.md` hoặc `implementation_plan_<feature>.md` | `implementation_plan_agent_v2.md` |
| Task list | `task.md` | `task.md` |
| Walkthrough | `walkthrough.md` hoặc `walkthrough_<feature>.md` | `walkthrough_langgraph.md` |
| Bug fix plan | `bugfix_plan_<component>.md` | `bugfix_plan_synthesis.md` |
| Research notes | `research_<topic>.md` | `research_reranking.md` |

## Workflow

```
1. User request → Agent đọc codebase
2. Agent tạo implementation_plan.md → User review
3. User approve → Agent tạo task.md
4. Agent thực hiện → cập nhật task.md
5. Hoàn thành → Agent tạo walkthrough.md
6. Move old plans → archive/
```

## Notes

- Tất cả files trong folder này được tạo TỰ ĐỘNG bởi Antigravity
- Không edit thủ công khi agent đang làm việc
- Có thể đọc để hiểu trạng thái hiện tại của task
