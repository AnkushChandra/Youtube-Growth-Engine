import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
});

export const fetchChannels = () => api.get('/channels').then((res) => res.data);
export const addChannel = (channel_url) => api.post('/add-channel', { channel_url }).then((res) => res.data);
export const analyzeChannel = (channelUrl) =>
  api.post('/analyze-channel', { channelUrl }).then((res) => res.data);
export const analyzeBatch = (channelUrls) =>
  api.post('/analyze-batch', { channelUrls }).then((res) => res.data);
export const generateThumbnail = (title, description = '') =>
  api.post('/generate-thumbnail', { title, description }).then((res) => res.data);
export const fetchHistory = () => api.get('/history').then((res) => res.data);
export const fetchHistoryDetail = (id) => api.get(`/history/${id}`).then((res) => res.data);
export const getLearningInsights = () => api.get('/learning/insights').then((res) => res.data);
export const getLearningMatches = () => api.get('/learning/matches').then((res) => res.data);
export const runLearningCycle = () => api.post('/learning/run').then((res) => res.data);
export const fetchVideos = (channelId) => api.get(`/videos/${channelId}`).then((res) => res.data);
export const fetchMemory = () => api.get('/memory').then((res) => res.data.memory);
export const appendMemory = (payload) => api.post('/memory', payload).then((res) => res.data);

export default api;
