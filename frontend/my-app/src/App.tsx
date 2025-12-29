import { useState } from 'react';
import './App.css';

interface RetrievedDocument {
  rank: number;
  content: string;
  score: number;
  metadata: {
    source_file?: string;
    article?: string;
    article_full?: string;
    chapter_full?: string;
  };
}

interface ChatResponse {
  question: string;
  answer: string;
  retrieved_documents: RetrievedDocument[];
  num_documents: number;
  model_name: string;
}

function App() {
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!question.trim()) {
      return;
    }

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const res = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: question,
          top_k: 3,
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }

      const data: ChatResponse = await res.json();
      setResponse(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <div className="container">
        <header className="header">
          <h1>🎓 Chatbot Quy Chế Đào Tạo</h1>
          <p>Đại học Bách khoa Hà Nội</p>
        </header>

        <div className="chat-container">
          <form onSubmit={handleSubmit} className="question-form">
            <div className="input-group">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Nhập câu hỏi của bạn..."
                className="question-input"
                disabled={loading}
              />
              <button type="submit" className="submit-button" disabled={loading}>
                {loading ? '⏳ Đang xử lý...' : '🚀 Gửi'}
              </button>
            </div>
          </form>

          {error && (
            <div className="error-box">
              <h3>❌ Lỗi</h3>
              <p>{error}</p>
            </div>
          )}

          {response && (
            <div className="response-container">
              <div className="answer-box">
                <h2>💡 Câu trả lời</h2>
                <p className="answer-text">{response.answer}</p>
                <div className="meta-info">
                  <span>🤖 Model: {response.model_name}</span>
                  <span>📚 Số nguồn tham khảo: {response.num_documents}</span>
                </div>
              </div>

              <div className="sources-box">
                <h2>📖 Nguồn tham khảo</h2>
                {response.retrieved_documents.map((doc) => (
                  <div key={doc.rank} className="source-item">
                    <div className="source-header">
                      <span className="source-rank">#{doc.rank}</span>
                      <span className="source-score">
                        Độ liên quan: {(doc.score * 100).toFixed(1)}%
                      </span>
                    </div>

                    <div className="source-metadata">
                      {doc.metadata.source_file && (
                        <div className="metadata-item">
                          📄 <strong>File:</strong> {doc.metadata.source_file}
                        </div>
                      )}
                      {doc.metadata.article_full && (
                        <div className="metadata-item">
                          📌 <strong>Điều khoản:</strong> {doc.metadata.article_full}
                        </div>
                      )}
                      {doc.metadata.chapter_full && (
                        <div className="metadata-item">
                          📂 <strong>Chương:</strong> {doc.metadata.chapter_full}
                        </div>
                      )}
                    </div>

                    <div className="source-content">
                      <strong>Nội dung:</strong>
                      <p>{doc.content}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
