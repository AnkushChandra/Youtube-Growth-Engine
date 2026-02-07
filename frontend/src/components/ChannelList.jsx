function ChannelList({ channels = [], onSelect, selectedId }) {
  return (
    <div className="panel channels-list">
      <h2>Tracked Channels</h2>
      {channels.length === 0 ? (
        <p className="helper">No channels tracked yet. Run an analysis to store one.</p>
      ) : (
        <ul>
          {channels.map((channel) => (
            <li key={channel.id} className="channel-item">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                <div>
                  <strong>{channel.title || channel.channel_url}</strong>
                  <div className="helper" style={{ marginTop: 4 }}>{channel.channel_url}</div>
                </div>
                <button
                  className="btn secondary"
                  onClick={() => onSelect(channel)}
                  aria-pressed={selectedId === channel.id}
                >
                  View data
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default ChannelList;
