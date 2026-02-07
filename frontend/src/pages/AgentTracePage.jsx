import AgentTrace from '../components/ProgressTimeline';
import { useApp } from '../context/AppContext';

function AgentTracePage() {
  const { agentSteps, loading } = useApp();

  return (
    <>
      <header className="hero">
        <h1>Agent Trace</h1>
        <p>Live view of the AI agent's reasoning steps, tool calls, and results from the latest analysis.</p>
      </header>

      <div className="agent-trace-full">
        <AgentTrace steps={agentSteps} loading={loading} />
      </div>

      {!agentSteps.length && !loading && (
        <div className="panel" style={{ textAlign: 'center', marginTop: 24 }}>
          <p className="helper">No agent trace yet. Run a batch analysis from the Analyze page to see the agent in action.</p>
        </div>
      )}
    </>
  );
}

export default AgentTracePage;
