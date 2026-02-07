import { useEffect, useState } from 'react';
import ChannelList from '../components/ChannelList';
import { useApp } from '../context/AppContext';
import { getLearningInsights, runLearningCycle } from '../lib/api';

const formatNumber = (value) =>
  value === undefined || value === null ? '—' : new Intl.NumberFormat('en-US').format(value);

function DataPage() {
  const {
    trackedChannels,
    batchChannels,
    selectedChannel,
    videos,
    memory,
    videosLoading,
    handleSelectChannel,
  } = useApp();

  const [insights, setInsights] = useState([]);
  const [learningRunning, setLearningRunning] = useState(false);
  const [learningResult, setLearningResult] = useState(null);

  const refreshLearning = () => {
    getLearningInsights().then(setInsights).catch(() => {});
  };

  useEffect(() => { refreshLearning(); }, []);

  const handleRunLearning = async () => {
    setLearningRunning(true);
    setLearningResult(null);
    try {
      const result = await runLearningCycle();
      setLearningResult(result);
      refreshLearning();
    } catch {
      setLearningResult({ error: true });
    } finally {
      setLearningRunning(false);
    }
  };

  const renderChannelVideos = (ch) => {
    const vids = ch.top_videos || [];
    if (!vids.length) return <p className="helper">No videos fetched for this channel.</p>;
    return (
      <div className="table-wrapper">
        <table className="videos-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Views</th>
              <th>Engagement</th>
              <th>Captions</th>
              <th>Link</th>
            </tr>
          </thead>
          <tbody>
            {vids.map((video) => (
              <tr key={video.videoId || video.video_id}>
                <td>{video.title || 'Untitled'}</td>
                <td>{formatNumber(video.views)}</td>
                <td>
                  {video.likes != null && video.comments != null
                    ? `${formatNumber(video.likes)} / ${formatNumber(video.comments)}`
                    : '—'}
                </td>
                <td>
                  {video.captions ? (
                    <span title={video.captions} style={{ cursor: 'help' }}>
                      {video.captions.length > 80 ? video.captions.slice(0, 80) + '…' : video.captions}
                    </span>
                  ) : (
                    <span className="helper">—</span>
                  )}
                </td>
                <td>
                  <a
                    href={`https://www.youtube.com/watch?v=${video.videoId || video.video_id}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Watch ↗
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const renderSelectedChannelVideos = () => {
    if (videosLoading) return <p className="helper">Loading videos…</p>;
    if (!videos.length) return <p className="helper">No videos stored yet.</p>;
    return (
      <div className="table-wrapper">
        <table className="videos-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Views</th>
              <th>Engagement</th>
              <th>Score</th>
              <th>Link</th>
            </tr>
          </thead>
          <tbody>
            {videos.map((video) => (
              <tr key={video.video_id || video.videoId}>
                <td>{video.title || 'Untitled'}</td>
                <td>{formatNumber(video.views)}</td>
                <td>
                  {video.likes != null && video.comments != null
                    ? `${formatNumber(video.likes)} / ${formatNumber(video.comments)}`
                    : '—'}
                </td>
                <td>{(video.performance_score || video.performanceScore) ? (video.performance_score || video.performanceScore).toFixed(2) : '—'}</td>
                <td>
                  <a href={`https://www.youtube.com/watch?v=${video.video_id || video.videoId}`} target="_blank" rel="noreferrer">
                    Watch ↗
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
        <h1>Data &amp; Memory</h1>
        <p>Browse tracked channels, channel breakdowns from the last batch analysis, and agent memory.</p>
      </header>

      {/* Learning Log */}
      <section className="panel learning-log" style={{ marginBottom: 24, borderColor: 'rgba(76,175,80,0.25)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <h2 style={{ margin: 0 }}>Learning Log</h2>
          <button className="btn secondary" onClick={handleRunLearning} disabled={learningRunning} style={{ fontSize: '0.85rem' }}>
            {learningRunning ? 'Running…' : 'Run Learning Cycle'}
          </button>
        </div>
        <p className="helper" style={{ marginTop: 8 }}>
          Analyzes performance patterns across all tracked videos — what framings, topics, and keywords drive views and engagement — then feeds those insights into future suggestions.
        </p>
        {learningResult && !learningResult.error && (
          <p className="helper" style={{ color: 'var(--accent)', marginTop: 4 }}>
            Cycle complete: {learningResult.videos_analyzed} video(s) analyzed, {learningResult.insights_generated} insight(s) generated.
          </p>
        )}
        {learningResult?.error && (
          <p className="helper" style={{ color: '#f44336', marginTop: 4 }}>Learning cycle failed.</p>
        )}

        {insights.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h3>Learned Insights</h3>
            <div className="insights-list">
              {insights.map((ins) => (
                <div key={ins.id} className="insight-item">
                  <span className="insight-icon">&#x1f4a1;</span>
                  <span>{ins.insight_text}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {!insights.length && (
          <p className="helper" style={{ marginTop: 12 }}>
            No insights yet. Click "Run Learning Cycle" or run a batch analysis — the system
            will analyze all stored video performance data and generate actionable patterns.
          </p>
        )}
      </section>

      {/* Channel Breakdowns from batch */}
      {batchChannels.length > 0 && (
        <section style={{ marginBottom: 24 }}>
          <h2 style={{ marginBottom: 16 }}>Channel Breakdowns</h2>
          {batchChannels.map((ch, idx) => (
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

      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px' }}>
        <ChannelList channels={trackedChannels} onSelect={handleSelectChannel} selectedId={selectedChannel?.id} />

        <div className="panel">
          <h2>Memory</h2>
          <p className="helper">Agent retains recent runs ({memory.length} lines).</p>
          {memory.length ? (
            <div className="memory-list">
              {memory.slice().reverse().map((line, idx) => (
                <div key={`${line}-${idx}`} className="memory-entry">
                  {line}
                </div>
              ))}
            </div>
          ) : (
            <p className="helper">No memory yet.</p>
          )}
        </div>
      </div>

      {/* Selected channel history from DB */}
      {selectedChannel && (
        <section className="panel" style={{ marginTop: 24 }}>
          <h2>Videos — {selectedChannel.title || selectedChannel.channel_url}</h2>
          {renderSelectedChannelVideos()}
        </section>
      )}
    </>
  );
}

export default DataPage;
