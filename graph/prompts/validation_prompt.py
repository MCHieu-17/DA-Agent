from langchain_core.prompts import ChatPromptTemplate


validation_prompt = ChatPromptTemplate.from_messages([
    ("system", """Đánh giá câu trả lời phân tích bằng ngôn ngữ của người dùng. Chọn đúng một decision:
accept: đáp ứng mọi yêu cầu; số liệu và nhận định được evidence hỗ trợ; diễn đạt tự nhiên, rõ ràng; ảnh hoặc liên kết Markdown tham chiếu đúng artifact hợp lệ.
revise_answer: evidence và artifact đủ, nhưng câu trả lời thiếu ý, sai số liệu, máy móc, lộ log/đường dẫn trong lời kể, bố cục khó đọc, hoặc tham chiếu ảnh/tệp sai. Feedback phải chỉ rõ cách sửa bằng evidence sẵn có.
reanalyze: evidence hoặc artifact thực sự thiếu để đáp ứng yêu cầu; cần tính thêm số liệu hoặc tạo đúng biểu đồ/tệp. Một ảnh đơn không thay được yêu cầu nhiều biểu đồ trong cùng bố cục.
Nếu evidence biểu đồ chỉ có loại biểu đồ, số dòng và tên file mà thiếu các giá trị đã vẽ, không thể xác minh tỷ lệ, so sánh hoặc kết luận định lượng; chọn reanalyze ngay cả khi câu trả lời nghe hợp lý.
Kiểm tra yêu cầu hiện tại và các lời nhắn liên quan; lời nhắn cũ chỉ là ngữ cảnh, không là bằng chứng số liệu. Nếu thiếu dữ liệu, chấp nhận câu trả lời nêu rõ giới hạn khi đó là đáp án trung thực đầy đủ. Không yêu cầu phân tích lại chỉ vì lỗi diễn đạt. Feedback ngắn và có thể thực hiện."""),
    ("human", """Yêu cầu hiện tại: {user_question}
Lời nhắn người dùng trước: {related_user_messages}
Hỏi đáp đã chấp nhận: {conversation_history}
Catalog: {profile_summary}
Giả định: {assumptions}
Evidence đã xác minh: {evidence}
Artifact hợp lệ: {artifacts}

Câu trả lời cần đánh giá: {final_answer}"""),
])
