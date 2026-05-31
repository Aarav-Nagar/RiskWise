import styled, { keyframes } from "styled-components";

const fadeUp = keyframes`
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
`;

export const Page = styled.div`
  display: grid;
  gap: 22px;
  animation: ${fadeUp} 320ms ease;
`;

export const Header = styled.section`
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 28px;
  border: 1px solid var(--border);
  border-radius: 28px;
  background:
    linear-gradient(135deg, rgba(18, 43, 71, 0.95), rgba(6, 18, 32, 0.96)),
    rgba(16, 30, 51, 0.9);
  box-shadow: var(--shadow);

  @media (max-width: 800px) {
    flex-direction: column;
  }
`;

export const HeaderText = styled.div`
  display: grid;
  gap: 10px;
`;

export const Eyebrow = styled.span`
  color: var(--accent);
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 800;
`;

export const Title = styled.h2`
  margin: 0;
  font-family: "Space Grotesk", sans-serif;
  font-size: clamp(2rem, 4vw, 3rem);
`;

export const Subtitle = styled.p`
  margin: 0;
  max-width: 680px;
  color: var(--muted);
  line-height: 1.7;
`;

export const Grid = styled.section`
  display: grid;
  grid-template-columns: repeat(${({ columns = 3 }) => columns}, minmax(0, 1fr));
  gap: 18px;

  @media (max-width: 1080px) {
    grid-template-columns: 1fr;
  }
`;

export const Card = styled.article`
  padding: 22px;
  border: 1px solid var(--border);
  border-radius: 24px;
  background: linear-gradient(180deg, var(--surface), rgba(7, 16, 29, 0.96));
  box-shadow: var(--shadow);
`;

export const CardTitle = styled.h3`
  margin: 0 0 16px;
  font-size: 1rem;
`;

export const MetricValue = styled.div`
  font-size: clamp(1.6rem, 4vw, 2.4rem);
  font-weight: 800;
`;

export const MetricLabel = styled.div`
  color: var(--muted);
  margin-top: 6px;
`;
