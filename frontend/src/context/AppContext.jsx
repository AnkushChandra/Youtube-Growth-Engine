import { createContext, useContext, useEffect, useState } from 'react';
import {
  analyzeBatch,
  appendMemory,
  fetchChannels,
  fetchMemory,
  fetchVideos,
  generateThumbnail,
} from '../lib/api';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [trackedChannels, setTrackedChannels] = useState([]);
  const [batchChannels, setBatchChannels] = useState([]);
  const [batchStrategy, setBatchStrategy] = useState(null);
  const [selectedChannel, setSelectedChannel] = useState(null);
  const [videos, setVideos] = useState([]);
  const [memory, setMemory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [videosLoading, setVideosLoading] = useState(false);
  const [agentSteps, setAgentSteps] = useState([]);
  const [thumbnails, setThumbnails] = useState({});
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

  const boot = async () => {
    try {
      const [channelList, memoryLines] = await Promise.all([fetchChannels(), fetchMemory()]);
      setTrackedChannels(channelList);
      setMemory(memoryLines);
    } catch (err) {
      console.error(err);
      setError('Failed to load initial data. Ensure backend is running.');
    }
  };

  useEffect(() => {
    boot();
  }, []);

  const refreshMemory = async () => {
    try {
      const lines = await fetchMemory();
      setMemory(lines);
    } catch (err) {
      console.error(err);
    }
  };

  const handleBatchAnalyze = async (channelUrls) => {
    setLoading(true);
    setError('');
    setBatchStrategy(null);
    setBatchChannels([]);
    setAgentSteps([]);
    setThumbnails({});
    setSelectedChannel(null);
    setVideos([]);
    try {
      const result = await analyzeBatch(channelUrls);
      setBatchStrategy(result.strategy);
      setBatchChannels(result.channels || []);
      setAgentSteps(result.agent_steps || []);
      const latestChannels = await fetchChannels();
      setTrackedChannels(latestChannels);
      await refreshMemory();

      const suggestions = result.strategy?.next_video_suggestions || [];
      suggestions.forEach((s, idx) => {
        generateThumbnail(s.topic, s.why)
          .then((data) => {
            setThumbnails((prev) => ({ ...prev, [idx]: data }));
          })
          .catch((err) => console.warn(`Thumbnail ${idx} failed:`, err));
      });
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || 'Batch analysis failed. Check backend logs.');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectChannel = async (channel) => {
    setSelectedChannel(channel);
    setVideos([]);
    setVideosLoading(true);
    setError('');
    try {
      const data = await fetchVideos(channel.id);
      setVideos(data);
    } catch (err) {
      console.error(err);
      setError('Failed to load video history for this channel.');
    } finally {
      setVideosLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!batchStrategy?.summary) return;
    try {
      await navigator.clipboard.writeText(batchStrategy.summary);
      setToast('Summary copied to clipboard');
      setTimeout(() => setToast(''), 2500);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAppendMemory = async () => {
    if (!batchStrategy) return;
    try {
      await appendMemory({
        channel_ref: 'batch',
        findings: batchStrategy.key_findings || [],
        action: (batchStrategy.next_video_suggestions?.[0]?.topic) || 'Review batch strategy',
      });
      setToast('Strategy appended to memory');
      await refreshMemory();
      setTimeout(() => setToast(''), 2500);
    } catch (err) {
      console.error(err);
      setError('Failed to write to memory.');
    }
  };

  return (
    <AppContext.Provider
      value={{
        trackedChannels,
        batchChannels,
        batchStrategy,
        selectedChannel,
        videos,
        memory,
        loading,
        videosLoading,
        agentSteps,
        thumbnails,
        error,
        toast,
        handleBatchAnalyze,
        handleSelectChannel,
        handleCopy,
        handleAppendMemory,
        setError,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
