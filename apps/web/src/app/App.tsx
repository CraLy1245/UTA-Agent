import { BrandMark } from "../components/BrandMark";
import { SystemStatus } from "../features/system/SystemStatus";

export function App() {
  return (
    <div className="app-shell">
      <aside className="brand-rail" aria-label="Survival Agent">
        <div className="brand-lockup">
          <BrandMark />
          <span>Survival Agent</span>
        </div>
      </aside>
      <SystemStatus />
    </div>
  );
}
