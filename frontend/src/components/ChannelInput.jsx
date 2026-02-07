import { useState } from 'react';
import clsx from 'clsx';

const placeholders = [
  'https://www.youtube.com/@marquesbrownlee',
  'https://www.youtube.com/@veritasium',
  'https://www.youtube.com/@aliabdaal',
];

function ChannelInput({ onAnalyze, disabled }) {
  const [value, setValue] = useState('');
  const [placeholder] = useState(() => placeholders[Math.floor(Math.random() * placeholders.length)]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!value.trim()) return;
    onAnalyze(value.trim());
  };

  return (
    <form className="panel channel-input" onSubmit={handleSubmit}>
      <div>
        <label htmlFor="channel" className="label">
          Channel URL or handle
        </label>
        <p className="helper">Paste a channel link, @handle, or /channel/ID. The agent will learn on each run.</p>
      </div>
      <div className="input-row">
        <input
          id="channel"
          type="text"
          placeholder={placeholder}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="input"
          disabled={disabled}
        />
        <button type="submit" className={clsx('btn primary', { loading: disabled })} disabled={disabled}>
          {disabled ? 'Analyzing…' : 'Analyze'}
        </button>
      </div>
    </form>
  );
}

export default ChannelInput;
