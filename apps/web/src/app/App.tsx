import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../features/layout/AppShell";
import { ActivityPage } from "../features/pages/ActivityPage";
import { MemoryPage } from "../features/pages/MemoryPage";
import { SettingsPage } from "../features/pages/SettingsPage";
import { SkillsPage } from "../features/pages/SkillsPage";
import { ChatPage } from "../features/chat/ChatPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/chat/:conversationId" element={<ChatPage />} />
        <Route path="/memory" element={<MemoryPage />} />
        <Route path="/skills" element={<SkillsPage />} />
        <Route path="/activity" element={<ActivityPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/chat/mock-1" replace />} />
      </Route>
    </Routes>
  );
}
