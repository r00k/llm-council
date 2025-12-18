import { forwardRef } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage3.css';

export default forwardRef(function Stage3({ finalResponse }, ref) {
  if (!finalResponse) {
    return null;
  }

  return (
    <div className="stage stage3" ref={ref}>
      <h3 className="stage-title">Stage 3: Final Council Answer</h3>
      <div className="final-response">
        <div className="chairman-label">
          Chairman: {finalResponse.model.split('/')[1] || finalResponse.model}
        </div>
        <div className="final-text markdown-content">
          <ReactMarkdown>{finalResponse.response}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
});
