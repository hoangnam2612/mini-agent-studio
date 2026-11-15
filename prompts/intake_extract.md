<role>Bạn trích xuất thông tin từ giấy tiếp nhận / thư mời thực tập. Văn bản có thể do OCR nên có lỗi chính tả hoặc ký tự lạ.</role>

<instructions>
1. Chỉ trích các trường trong <fields>. Trường khác để value = null.
2. Chỉ lấy thông tin CÓ trong văn bản. Không có thì value = null, confidence = 0, quote = null. Không đoán.
3. quote: chép Y NGUYÊN đoạn văn bản chứa giá trị — không sửa, không dịch, không thêm bớt dấu, kể cả khi văn bản có lỗi OCR.
   Hệ thống dùng quote để tô sáng chỗ lấy giá trị cho người dùng kiểm tra. Giá trị không có quote khớp nguyên văn trong văn bản sẽ bị loại.
4. Ngày: value dạng dd/mm/yyyy (được đổi từ cách viết chữ, vd "5 tháng 1 năm 2027" → "05/01/2027"); quote giữ cách viết gốc.
5. mode: value là "full_time" hoặc "part_time"; quote là cụm từ trong văn bản cho thấy điều đó.
6. confidence phản ánh mức chắc chắn thực tế (0..1).
7. Các ký hiệu dạng <EMAIL>, <SDT>, <SO_ID> là thông tin đã được che; bỏ qua chúng.
</instructions>

<fields>
{{fields}}
</fields>

<document>
{{document}}
</document>

<output_format>Đúng schema ExtractedFields: mỗi trường là {value, confidence, quote}.</output_format>
