import { useEffect, useState } from 'react';
import { fetchHistory, fetchHistoryDetail } from '../lib/api';

const formatNumber = (value) =>
  value === undefined || value === null ? '—' : new Intl.NumberFormat('en-US').format(value);

const APPEAL_COLORS = { high: '#4caf50', medium: '#ff9800', low: '#9e9e9e' };

function HistoryPage() {
  const [entries, setEntries] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchHistory()
      .then(setEntries)
      .catch(() => setError('Failed to load history.'))
      .finally(() => setLoading(false));
  }, []);

  const handleSelect = async (id) => {
    if (selected?.id === id) {
      setSelected(null);
      return;
    }
    setDetailLoading(true);
    setError('');
    try {
      const detail = await fetchHistoryDetail(id);
      setSelected(detail);
    } catch {
      setError('Failed to load analysis detail.');
    } finally {
      setDetailLoading(false);
    }
  };

  const formatDate = (iso) => {
    try {
      const d = new Date(iso + 'Z');
      return d.toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    } catch {
      return iso;
    }
  };

  const renderChannelVideos = (ch) => {
    const vids = ch.top_videos || [];
    if (!vids.length) return <p className="helper">No videos fetched.</p>;
    return (
      <div className="table-wrapper">
        <table className="videos-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Views</th>
              <th>Engagement</th>
              <th>Link</th>
            </tr>
          </thead>
          <tbody>
            {vids.map((v) => (
              <tr key={v.videoId || v.video_id}>
                <td>{v.title || 'Untitled'}</td>
                <td>{formatNumber(v.views)}</td>
                <td>
                  {v.likes != null && v.comments != null
                    ? `${formatNumber(v.likes)} / ${formatNumber(v.comments)}`
                    : '—'}
                </td>
                <td>
                  <a href={`https://www.youtube.com/watch?v=${v.videoId || v.video_id}`} target="_blank" rel="noreferrer">
                    Watch
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <>
      <header className="hero">
        <h1>Analysis History</h1>
        <p>Browse past batch analyses. Click an entry to view the full results.</p>
      </header>

      {error && (
        <div className="panel" style={{ borderColor: '#ff6b35', marginBottom: 16 }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {loading ? (
        <p className="helper">Loading history…</p>
      ) : entries.length === 0 ? (
        <div className="panel" style={{ textAlign: 'center' }}>
          <p className="helper">No analyses yet. Run a batch analysis from the Analyze page to get started.</p>
        </div>
      ) : (
        <div className="history-list">
          {entries.map((entry) => (
            <div
              key={entry.id}
              className={`history-item ${selected?.id === entry.id ? 'active' : ''}`}
              onClick={() => handleSelect(entry.id)}
            >
              <div className="history-item-header">
                <span className="history-date">{formatDate(entry.created_at)}</span>
                <span className="history-count">{entry.channel_urls.length} channel{entry.channel_urls.length !== 1 ? 's' : ''}</span>
              </div>
              <div className="history-channels">
                {entry.channel_urls.map((url, i) => (
                  <span key={i} className="history-channel-tag">{url.replace('https://www.youtube.com/', '')}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {detailLoading && <p className="helper" style={{ marginTop: 16 }}>Loading analysis…</p>}

      {selected && !detailLoading && (
        <div className="history-detail">
          {/* Suggestions */}
          {selected.strategy?.next_video_suggestions?.length > 0 && (
            <section className="panel" style={{ marginTop: 24, borderColor: 'rgba(0,194,255,0.25)' }}>
              <h2>Next Video Suggestions</h2>
              <div className="suggestions-grid">
                {selected.strategy.next_video_suggestions.map((s, idx) => (
                  <div key={idx} className="suggestion-card">
                    <div className="suggestion-body">
                      <div className="suggestion-header">
                        <span className="suggestion-num">{idx + 1}</span>
                        <h3>{s.topic}</h3>
                        {s.estimated_appeal && (
                          <span className="appeal-badge" style={{ background: APPEAL_COLORS[s.estimated_appeal] || '#9e9e9e' }}>
                            {s.estimated_appeal}
                          </span>
                        )}
                      </div>
                      <p>{s.why}</p>
                      {s.reference_channels?.length > 0 && (
                        <p className="helper" style={{ margin: 0 }}>Inspired by: {s.reference_channels.join(', ')}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Strategy */}
          <section className="panel strategy-card" style={{ marginTop: 16 }}>
            <h2>Cross-Channel Strategy</h2>
            <div className="strategy-columns" style={{ marginTop: 16, display: 'grid', gap: 24, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
              {selected.strategy.trending_topics?.length > 0 && (
                <div>
                  <h3>Trending Topics</h3>
                  <ul>{selected.strategy.trending_topics.map((t) => <li key={t}>{t}</li>)}</ul>
                </div>
              )}
              {selected.strategy.common_patterns?.length > 0 && (
                <div>
                  <h3>Common Patterns</h3>
                  <ul>{selected.strategy.common_patterns.map((p) => <li key={p}>{p}</li>)}</ul>
                </div>
              )}
              {selected.strategy.content_gaps?.length > 0 && (
                <div>
                  <h3>Content Gaps</h3>
                  <ul>{selected.strategy.content_gaps.map((g) => <li key={g}>{g}</li>)}</ul>
                </div>
              )}
              {selected.strategy.key_findings?.length > 0 && (
                <div>
                  <h3>Key Findings</h3>
                  <ul>{selected.strategy.key_findings.map((f) => <li key={f}>{f}</li>)}</ul>
                </div>
              )}
              <div>
                <h3>Confidence</h3>
                <p style={{ fontSize: '2.5rem', margin: '0 0 8px' }}>
                  {Math.round((selected.strategy.confidence || 0) * 100)}%
                </p>
              </div>
            </div>
            {selected.strategy.summary && <div className="summary-copy">{selected.strategy.summary}</div>}
          </section>

          {/* Channel breakdowns */}
          {selected.channels?.length > 0 && (
            <section style={{ marginTop: 16 }}>
              <h2 style={{ marginBottom: 12 }}>Channel Breakdowns</h2>
              {selected.channels.map((ch, idx) => (
                <details key={idx} className="panel channel-breakdown" style={{ marginBottom: 12 }}>
                  <summary style={{ cursor: 'pointer', fontWeight: 600, fontSize: '1.05rem' }}>
                    {ch.title || ch.channel_url}
                    <span className="helper" style={{ marginLeft: 12 }}>
                      {(ch.top_videos || []).length} videos
                    </span>
                  </summary>
                  <div style={{ marginTop: 12 }}>{renderChannelVideos(ch)}</div>
                </details>
              ))}
            </section>
          )}
        </div>
      )}
    </>
  );
}

export default HistoryPage;
