import { NavLink } from 'react-router-dom';

function NavMenu() {
  return (
    <nav className="nav-menu">
      <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
        Analyze
      </NavLink>
      <NavLink to="/history" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
        History
      </NavLink>
      <NavLink to="/data" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
        Data
      </NavLink>
      <NavLink to="/agent" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
        Agent Trace
      </NavLink>
    </nav>
  );
}

export default NavMenu;
