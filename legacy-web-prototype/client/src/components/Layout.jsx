import { NavLink, Outlet } from "react-router-dom";
import styled from "styled-components";

const shellLinks = [
  { to: "/", label: "Market Overview" },
  { to: "/portfolio", label: "Portfolio Tracker" },
  { to: "/chat", label: "Finance Chat" }
];

const Shell = styled.div`
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  min-height: 100vh;

  @media (max-width: 920px) {
    grid-template-columns: 1fr;
  }
`;

const Sidebar = styled.aside`
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-height: 100vh;
  padding: 28px;
  background: rgba(5, 13, 24, 0.82);
  border-right: 1px solid var(--border);
  backdrop-filter: blur(22px);

  @media (max-width: 920px) {
    position: static;
    min-height: auto;
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }
`;

const Brand = styled.div`
  display: grid;
  gap: 10px;
`;

const BrandTitle = styled.h1`
  margin: 0;
  font-family: "Space Grotesk", sans-serif;
  font-size: 1.6rem;
`;

const BrandTag = styled.span`
  width: fit-content;
  padding: 6px 10px;
  border-radius: 999px;
  color: #08111f;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  font-weight: 800;
  font-size: 0.78rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
`;

const Nav = styled.nav`
  display: grid;
  gap: 10px;
`;

const NavItem = styled(NavLink)`
  padding: 14px 16px;
  border: 1px solid transparent;
  border-radius: 18px;
  color: var(--muted);
  transition: 180ms ease;

  &:hover,
  &.active {
    color: var(--text);
    background: rgba(107, 188, 255, 0.08);
    border-color: rgba(107, 188, 255, 0.18);
    transform: translateX(4px);
  }
`;

const SidebarNote = styled.div`
  margin-top: auto;
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(16, 30, 51, 0.82), rgba(8, 19, 34, 0.92));
  color: var(--muted);
  line-height: 1.6;
`;

const Main = styled.main`
  padding: 30px;

  @media (max-width: 700px) {
    padding: 18px;
  }
`;

export default function Layout() {
  return (
    <Shell>
      <Sidebar>
        <Brand>
          <BrandTag>Fintech Sandbox</BrandTag>
          <BrandTitle>Quant Market</BrandTitle>
          <div>A full-stack stock workstation with server-side analytics and a polished dark interface.</div>
        </Brand>

        <Nav>
          {shellLinks.map((item) => (
            <NavItem key={item.to} to={item.to} end={item.to === "/"}>
              {item.label}
            </NavItem>
          ))}
        </Nav>

        <SidebarNote>
          Stock detail pages are generated dynamically from the market table, with server-side quant metrics and 30-day historical data.
        </SidebarNote>
      </Sidebar>

      <Main>
        <Outlet />
      </Main>
    </Shell>
  );
}
