import { useEffect, useState } from 'react';
import BatchChannelInput from '../components/BatchChannelInput';
import { useApp } from '../context/AppContext';
import { getLearningInsights } from '../lib/api';

const APPEAL_COLORS = { high: '#4caf50', medium: '#ff9800', low: '#9e9e9e' };

/** Check if any learned insights existed when this analysis ran. */
function hasLearnedContext(insightTexts) {
  return insightTexts.length > 0;
}

function AnalyzePage() {
  const {
    batchStrategy,
    loading,
    thumbnails,
    handleBatchAnalyze,
    handleCopy,
    handleAppendMemory,
  } = useApp();

  const [insightTexts, setInsightTexts] = useState([]);

  useEffect(() => {
    getLearningInsights()
      .then((data) => setInsightTexts(data.map((d) => d.insight_text)))
      .catch(() => {});
  }, []);

  return (
    <>
      <header className="hero">
        <p className="helper" style={{ textTransform: 'uppercase', letterSpacing: '0.18em' }}>
          Multi-channel trend analysis
        </p>
        <h1>YouTube Strategy Lab</h1>
        <p>
          Add your competitor or inspiration channels below. The agent will fetch the last 5 videos
          with subtitles from each, analyze cross-channel trends, and suggest your next video topics.
        </p>
      </header>

      <BatchChannelInput onAnalyze={handleBatchAnalyze} disabled={loading} />

      {/* Next Video Suggestions */}
      {batchStrategy?.next_video_suggestions?.length > 0 && (
        <section className="panel" style={{ marginTop: 24, marginBottom: 24, borderColor: 'rgba(0,194,255,0.25)' }}>
          <h2>Next Video Suggestions</h2>
          <p className="helper">Based on trends across all analyzed channels and their recent content.</p>
          <div className="suggestions-grid">
            {batchStrategy.next_video_suggestions.map((s, idx) => (
              <div key={idx} className="suggestion-card">
                <div className="suggestion-thumb">
                  {thumbnails[idx] ? (
                    <img
                      src={`data:${thumbnails[idx].mime_type};base64,${thumbnails[idx].image_base64}`}
                      alt={`Thumbnail for: ${s.topic}`}
                    />
                  ) : (
                    <div className="thumb-placeholder">
                      <span>{loading ? '' : 'Generating thumbnail\u2026'}</span>
                    </div>
                  )}
                </div>
                <div className="suggestion-body">
                  <div className="suggestion-header">
                    <span className="suggestion-num">{idx + 1}</span>
                    <h3>{s.topic}</h3>
                    {hasLearnedContext(insightTexts) ? (
                      <span className="learning-badge learned" title="Agent had learned performance patterns injected into its prompt">
                        Data-Informed
                      </span>
                    ) : (
                      <span className="learning-badge experimental" title="No performance data yet — run a learning cycle first">
                        Experimental
                      </span>
                    )}
                    {s.estimated_appeal && (
                      <span
                        className="appeal-badge"
                        style={{ background: APPEAL_COLORS[s.estimated_appeal] || '#9e9e9e' }}
                      >
                        {s.estimated_appeal}
                      </span>
                    )}
                  </div>
                  <p>{s.why}</p>
                  {s.reference_channels?.length > 0 && (
                    <p className="helper" style={{ margin: 0 }}>
                      Inspired by: {s.reference_channels.join(', ')}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Cross-channel strategy */}
      {batchStrategy && (
        <section className="panel strategy-card" style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
            <h2>Cross-Channel Strategy</h2>
            <div className="actions-row">
              <button className="btn secondary" onClick={handleCopy} disabled={!batchStrategy.summary}>
                Copy summary
              </button>
              <button className="btn primary" onClick={handleAppendMemory}>
                Append to memory
              </button>
            </div>
          </div>

          <div className="strategy-columns" style={{ marginTop: 20, display: 'grid', gap: 24, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
            {batchStrategy.trending_topics?.length > 0 && (
              <div>
                <h3>Trending Topics</h3>
                <ul>
                  {batchStrategy.trending_topics.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              </div>
            )}
            {batchStrategy.common_patterns?.length > 0 && (
              <div>
                <h3>Common Patterns</h3>
                <ul>
                  {batchStrategy.common_patterns.map((p) => (
                    <li key={p}>{p}</li>
                  ))}
                </ul>
              </div>
            )}
            {batchStrategy.content_gaps?.length > 0 && (
              <div>
                <h3>Content Gaps</h3>
                <ul>
                  {batchStrategy.content_gaps.map((g) => (
                    <li key={g}>{g}</li>
                  ))}
                </ul>
              </div>
            )}
            {batchStrategy.key_findings?.length > 0 && (
              <div>
                <h3>Key Findings</h3>
                <ul>
                  {batchStrategy.key_findings.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </div>
            )}
            <div>
              <h3>Confidence</h3>
              <p style={{ fontSize: '2.5rem', margin: '0 0 8px' }}>
                {Math.round((batchStrategy.confidence || 0) * 100)}%
              </p>
              <p className="helper">Grows with more channels and consistent signals.</p>
            </div>
          </div>
          {batchStrategy.summary && <div className="summary-copy">{batchStrategy.summary}</div>}
        </section>
      )}
    </>
  );
}

export default AnalyzePage;
