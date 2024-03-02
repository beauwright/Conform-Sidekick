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

export function App() {
  const [view, setView] = useState<string>("photos");
  const handleViewChange = (newView: string) => {
    setView(newView);
  };

  return (
    <div className="min-w-screen min-h-screen bg-white dark:bg-slate-950">
      <Toolbar defaultValue={view} onViewChange={handleViewChange} />
      <Router>
        <NavigateOnViewChange view={view} />
        <Routes>
          <Route path="/photos" element={<EvenResPhotos />} />
          <Route path="/interlaced" element={<h1>Placeholder</h1>} />
        </Routes>
      </Router>
    </div>
  );
}

export default App;