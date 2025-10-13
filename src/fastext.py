import pandas as pd
import fasttext
import fasttext.util
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# 1. Tải model fastText đã huấn luyện sẵn (có thể dùng model nhỏ)
fasttext.util.download_model('vi', if_exists='ignore')  # tiếng Việt
ft = fasttext.load_model('cc.vi.300.bin')

# 2. Đọc dataset
df = pd.read_csv("../clean_dataset.csv")  # có cột 'question' và 'answer'

# 3. Tạo embedding cho tất cả câu hỏi trong dataset
def get_vector(text):
    return ft.get_sentence_vector(text)

question_embeddings = np.vstack([get_vector(q) for q in df["questions"]])

# 4. Hàm tìm câu trả lời
def semantic_qa(question, threshold=0.7):
    q_vec = get_vector(question).reshape(1, -1)
    sims = cosine_similarity(q_vec, question_embeddings)[0]
    best_idx = np.argmax(sims)
    best_score = sims[best_idx]
    
    if best_score >= threshold:
        return df.iloc[best_idx]["answers"]
    else:
        return "không biết"

# 5. Test
print(semantic_qa("thưa thầy, em tên Phan Thanh Tùng , mssv 20164554 , Thầy cho em hỏi môn An Toàn Hệ Thống, mã học phần IT4910, có học phần tương đương là môn nào ạ?Em cám ơn.?"))         # nên khớp với "Thủ đô của Việt Nam là gì?"
print(semantic_qa("Tổng thống Mỹ hiện nay?"))  # nếu dataset chưa có thì ra "không biết"
