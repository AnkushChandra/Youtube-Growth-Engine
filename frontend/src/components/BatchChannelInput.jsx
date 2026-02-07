import { useState } from 'react';
import clsx from 'clsx';

const placeholders = [
  'https://www.youtube.com/@mkbhd',
  'https://www.youtube.com/@veritasium',
  'https://www.youtube.com/@aliabdaal',
];

function BatchChannelInput({ onAnalyze, disabled }) {
  const [channels, setChannels] = useState(['']);

  const handleAdd = () => {
    if (channels.length >= 10) return;
    setChannels([...channels, '']);
  };

  const handleRemove = (idx) => {
    if (channels.length <= 1) return;
    setChannels(channels.filter((_, i) => i !== idx));
  };

  const handleChange = (idx, value) => {
    const updated = [...channels];
    updated[idx] = value;
    setChannels(updated);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const urls = channels.map((c) => c.trim()).filter(Boolean);
    if (!urls.length) return;
    onAnalyze(urls);
  };

  const validCount = channels.filter((c) => c.trim()).length;

  return (
    <form className="panel batch-input" onSubmit={handleSubmit}>
      <div style={{ marginBottom: 16 }}>
        <label className="label">Channels to analyze</label>
        <p className="helper">
          Add up to 10 channels. The agent will fetch the last 5 videos + subtitles from each, then
          give you a cross-channel strategy with next video suggestions.
        </p>
      </div>

      <div className="batch-list">
        {channels.map((url, idx) => (
          <div key={idx} className="batch-row">
            <span className="batch-num">{idx + 1}</span>
            <input
              type="text"
              className="input"
              placeholder={placeholders[idx % placeholders.length]}
              value={url}
              onChange={(e) => handleChange(idx, e.target.value)}
              disabled={disabled}
            />
            {channels.length > 1 && (
              <button
                type="button"
                className="btn-icon"
                onClick={() => handleRemove(idx)}
                disabled={disabled}
                title="Remove channel"
              >
                ✕
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="batch-actions">
        <button
          type="button"
          className="btn secondary"
          onClick={handleAdd}
          disabled={disabled || channels.length >= 10}
        >
          + Add channel
        </button>
        <button
          type="submit"
          className={clsx('btn primary', { loading: disabled })}
          disabled={disabled || !validCount}
        >
          {disabled ? 'Analyzing…' : `Analyze ${validCount} channel${validCount !== 1 ? 's' : ''}`}
        </button>
      </div>
    </form>
  );
}

export default BatchChannelInput;
