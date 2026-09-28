import { BrowserRouter, Route, Routes } from "react-router-dom";
import PartyCreation from "./PartyCreation";
import PlayScreen from "./PlayScreen";
import SeedWizard from "./SeedWizard";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<SeedWizard />} />
        <Route path="/campaigns/:campaignId/party/:actorId" element={<PartyCreation />} />
        <Route path="/campaigns/:campaignId/play/:actorId" element={<PlayScreen />} />
      </Routes>
    </BrowserRouter>
  );
}
