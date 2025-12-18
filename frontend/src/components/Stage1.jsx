import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage1.css';

export default function Stage1({ responses }) {
  const [activeTab, setActiveTab] = useState(0);
  const [isExpanded, setIsExpanded] = useState(false);

  if (!responses || responses.length === 0) {
    return null;
  }

  return (
    <div className="stage stage1">
      <h3 className="stage-title collapsible" onClick={() => setIsExpanded(!isExpanded)}>
        <span className="collapse-icon">{isExpanded ? '▼' : '▶'}</span>
        Stage 1: Individual Responses
      </h3>

      {isExpanded && (
        <>
          <div className="tabs">
            {responses.map((resp, index) => (
              <button
                key={index}
                className={`tab ${activeTab === index ? 'active' : ''}`}
                onClick={() => setActiveTab(index)}
              >
                {resp.model.split('/')[1] || resp.model}
              </button>
            ))}
          </div>

          <div className="tab-content">
            <div className="model-name">{responses[activeTab].model}</div>
            <div className="response-text markdown-content">
              <ReactMarkdown>{responses[activeTab].response}</ReactMarkdown>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
