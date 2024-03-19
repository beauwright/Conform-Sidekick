// Other imports remain the same
import {
  BrowserRouter as Router,
  Routes,
  Route,
  useNavigate,
} from "react-router-dom";
import EvenResPhotos from "./EvenResPhotos/EvenResPhotos";
import Toolbar from "./components/Toolbar";
import { useEffect, useState } from "react";
import { Separator } from "./components/ui/separator";
import { platform } from "@tauri-apps/api/os";
import ConnectingStatus from "./ResolveConnectionStatus";
import { useResolveContext } from "./ResolveContext";

// This component needs to be a child of a Router component to work
function NavigateOnViewChange({ view }: { view: string }) {
  const navigate = useNavigate();

  useEffect(() => {
    if (view === "photos") {
      navigate("/photos");
    } else if (view === "interlaced") {
      navigate("/interlaced");
    }
  }, [view, navigate]);
  
  // Render nothing, as this component is only for redirecting when the view is changed by the Toolbar
  return null;
}
const platformName = await platform();

export function App() {
  const [view, setView] = useState<string>("photos");
  const handleViewChange = (newView: string) => {
    setView(newView);
  };
  const context = useResolveContext();
  const { currentProject } = context || {};

  return (
    <div className="min-w-screen min-h-screen bg-white dark:bg-slate-950 select-none cursor-default">
      {/*render top bar with drag region on macOS, nothing for windows/linux*/}
      {platformName === "darwin" ? (
        <div id="macOS title bar">
          <div
            data-tauri-drag-region
            className="bg-slate-50 py-3 dark:bg-slate-900"
          ></div>
          <Separator className="bg-slate-100 dark:bg-slate-800" />
        </div>
      ) : (
        <div />
      )}
      {/*render loading screen or app depending on connection*/}
      {currentProject === "" ? (
        <div className="mx-auto my-auto justify-center p-40">
          <ConnectingStatus loadingText="Connecting to DaVinci Resolve"/>
        </div>
      ) : (
        <>
          <Toolbar defaultValue={view} onViewChange={handleViewChange} />
          <Router>
            <NavigateOnViewChange view={view} />
            <Routes>
              <Route path="/" element={<></>} />
              <Route path="/photos" element={<EvenResPhotos />} />
              <Route
                path="/interlaced"
                element={<h1 className="dark:text-white">Placeholder</h1>}
              />
            </Routes>
          </Router>
        </>
      )}
    </div>
  );
}

export default App;
