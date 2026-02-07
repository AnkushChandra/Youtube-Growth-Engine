const TOOL_LABELS = {
  YOUTUBE_GET_CHANNEL_ID_BY_HANDLE: 'Resolving channel handle',
  YOUTUBE_GET_CHANNEL_STATISTICS: 'Fetching channel stats',
  YOUTUBE_LIST_CHANNEL_VIDEOS: 'Listing recent videos',
  YOUTUBE_VIDEO_DETAILS: 'Getting video details',
  YOUTUBE_LIST_CAPTION_TRACK: 'Listing caption tracks',
  YOUTUBE_LOAD_CAPTIONS: 'Downloading captions',
  YOUTUBE_SEARCH_YOU_TUBE: 'Searching YouTube',
};

const AgentTrace = ({ steps, loading }) => {
  if (!steps.length && !loading) {
    return (
      <div className="panel">
        <h2>Agent Trace</h2>
        <p className="helper">
          The AI agent will show its reasoning and tool calls here as it analyzes the channel.
        </p>
      </div>
    );
  }

  return (
    <div className="panel">
      <h2>Agent Trace</h2>
      <div className="timeline">
        {steps.map((step, idx) => {
          if (step.type === 'tool_call') {
            const label = TOOL_LABELS[step.tool] || step.tool;
            const argsPreview = step.arguments
              ? Object.entries(step.arguments)
                  .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
                  .join(', ')
              : '';
            return (
              <div key={idx} className="timeline-step completed">
                <span className="bullet" style={{ background: '#00c2ff' }} />
                <div>
                  <div style={{ fontWeight: 600 }}>{label}</div>
                  {argsPreview && (
                    <small className="helper" style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                      {argsPreview.length > 120 ? argsPreview.slice(0, 120) + '…' : argsPreview}
                    </small>
                  )}
                </div>
              </div>
            );
          }

          if (step.type === 'tool_result') {
            return (
              <div key={idx} className="timeline-step completed">
                <span className="bullet" style={{ background: '#4caf50' }} />
                <div>
                  <small className="helper" style={{ color: '#4caf50' }}>
                    ✓ {TOOL_LABELS[step.tool] || step.tool} — result received
                  </small>
                </div>
              </div>
            );
          }

          if (step.type === 'reasoning') {
            return (
              <div key={idx} className="timeline-step completed">
                <span className="bullet" style={{ background: '#ff9800' }} />
                <div>
                  <div style={{ fontWeight: 600 }}>Agent reasoning</div>
                  <small className="helper" style={{ whiteSpace: 'pre-wrap' }}>
                    {step.content && step.content.length > 300
                      ? step.content.slice(0, 300) + '…'
                      : step.content}
                  </small>
                </div>
              </div>
            );
          }

          return null;
        })}

        {loading && (
          <div className="timeline-step active">
            <span className="bullet" />
            <div>
              <div>Agent is thinking…</div>
              <small className="helper">Calling tools and analyzing data</small>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AgentTrace;
