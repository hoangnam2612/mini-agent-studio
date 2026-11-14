<role>Bạn trích xuất thông tin từ giấy tiếp nhận / thư mời thực tập.</role>

<instructions>
1. Chỉ lấy thông tin CÓ trong văn bản. Không có thì để value = null, confidence = 0.
2. Ngày ghi dạng dd/mm/yyyy như trong văn bản. mode là "full_time" hoặc "part_time".
3. confidence phản ánh mức chắc chắn thực tế (0..1). Không đoán.
</instructions>

<document>
{{document}}
</document>

<output_format>Đúng schema ExtractedFields: mỗi trường là {value, confidence}.</output_format>
