import {
  BrowserRouter as Router,
  Routes,
  Route,
  useNavigate,
} from "react-router-dom";
import EvenResPhotos from "./components/EvenResPhotos/EvenResPhotos";
import NavigationTabs from "./components/NavigationTabs";
import { useEffect, useState } from "react";
import { Separator } from "./components/ui/separator";
import { platform } from "@tauri-apps/api/os";
import ConnectingStatus from "./LoadingStatus";
import { useResolveContext } from "./ResolveContext";
import InterlacedMedia from "./components/InterlacedMedia/InterlacedMedia";
import CompoundClips from "./components/CompoundClips/CompoundClips";
import Licenses from "./licenses";
import { listen } from "@tauri-apps/api/event";

// This component needs to be a child of a Router component to work
function NavigateOnViewChange({ view }: { view: string }) {
  const navigate = useNavigate();

  useEffect(() => {
    if (view === "photos") {
      navigate("/photos");
    } else if (view === "interlaced") {
      navigate("/interlaced");
    } else if (view === "compound") {
      navigate("/compound");
    } else if (view === "licenses") {
      navigate("/licenses");
    }
  }, [view, navigate]);

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

  useEffect(() => {
    const unlisten = listen<string>("navigate", (event) => {
      setView(event.payload);
    });

    return () => {
      unlisten.then((f) => f());
    };
  }, []);

  return (
    <div className="min-w-screen min-h-screen bg-white dark:bg-slate-950 cursor-default">
      {/*render top bar with drag region on macOS, nothing for windows/linux*/}
      {platformName === "darwin" ? (
        <div id="macOS title bar" className="mac-title-bar">
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
      <div className="main-content">
        {currentProject === "" ? (
          <div className="mx-auto my-auto justify-center p-40">
            <ConnectingStatus loadingText="Connecting to DaVinci Resolve" />
          </div>
        ) : (
          <>
            <NavigationTabs defaultValue={view} onViewChange={handleViewChange} />
            <Router>
              <NavigateOnViewChange view={view} />
              <Routes>
                <Route path="/" element={<></>} />
                <Route path="/photos" element={<EvenResPhotos />} />
                <Route path="/interlaced" element={<InterlacedMedia />} />
                <Route path="/compound" element={<CompoundClips />} />
                <Route path="/licenses" element={<Licenses />} />
              </Routes>
            </Router>
          </>
        )}
      </div>
    </div>
  );
}

export default App;
